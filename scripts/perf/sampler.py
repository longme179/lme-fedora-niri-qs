#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Watch the shell from outside while a scenario runs: the view the shell cannot have of itself.

  sampler.py --pid PID --out DIR [--settings <tree>/settings.qml] [--interval 50] [--ping-ms 100]
              [--stall-ms 150] [--no-niri] [--no-gpu]

Appends to DIR/sampler.jsonl one JSON object per line, `t` in epoch milliseconds:
  threads  every thread of each watched process: scheduler state, CPU time so far and the
           kernel function it sleeps in (wchan). With --settings the Settings process of that
           tree is picked up as it appears.
  ping     one `ipc call probe ping` per --ping-ms: the round trip the shell's GUI thread has
           to answer, so the longest round trip is the longest time the thread was unavailable
  niri     round trip of `niri msg`: how long the compositor took to answer
  gpu      nvidia-smi utilisation and the amdgpu busy counters
  stack    a ping that the GUI thread did not answer within --stall-ms: every thread's C++
           stack was written to DIR/stack-N.txt right then (eu-stack, ptrace), i.e. while the
           thread was known to be blocked

A frozen GUI thread cannot report itself, which is what this is for. The heartbeat inside the
shell (qml/services/Heartbeat.qml) says how long each stall was and which marks ran in it;
the sampler says what the thread was doing, and whether niri and the GPU stalled with it.
Sampling is observation only: nothing is sent to the shell but the ping.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

TICK_MS = 1000.0 / os.sysconf("SC_CLK_TCK")
QS = Path.home() / ".local/share/lme-shell/deployment/bin/quickshell"


def now_ms() -> float:
    return time.time() * 1000.0


def alive(pid: int) -> bool:
    return Path(f"/proc/{pid}").exists()


def read_threads(pid: int) -> dict:
    found = {}
    try:
        tasks = list(os.scandir(f"/proc/{pid}/task"))
    except OSError:
        return found
    for entry in tasks:
        try:
            with open(f"{entry.path}/stat") as handle:
                stat = handle.read()
            close = stat.rindex(")") + 2
            fields = stat[close:].split()
            with open(f"{entry.path}/wchan") as handle:
                wchan = handle.read().strip()
        except (OSError, ValueError):
            continue
        found[entry.name] = [stat[stat.index("(") + 1:close - 2], fields[0],
                             round(int(fields[11]) * TICK_MS), round(int(fields[12]) * TICK_MS), wchan]
    return found


def rss_kb(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return 0


def instance_pid(config_path: str) -> int:
    """Pid of the Quickshell instance started with `-p <config_path>` (never an ipc client)."""
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = [part.decode(errors="replace") for part in (entry / "cmdline").read_bytes().split(b"\0") if part]
        except OSError:
            continue
        if len(argv) >= 3 and argv[0].endswith("quickshell") and "ipc" not in argv and argv[1:3] == ["-p", config_path]:
            return int(entry.name)
    return 0


class Writer:
    def __init__(self, path: Path):
        self.lock = threading.Lock()
        self.handle = open(path, "a", buffering=1)

    def __call__(self, **record):
        line = json.dumps(record, separators=(",", ":"))
        with self.lock:
            self.handle.write(line + "\n")


class Sampler:
    def __init__(self, args):
        self.args = args
        self.running = threading.Event()
        self.running.set()
        self.write = Writer(args.out / "sampler.jsonl")
        self.stacks = 0
        self.pids = {"shell": args.pid}

    def stop(self):
        self.running.clear()

    # ---- one stack of every thread of the shell, while its GUI thread is known to be blocked
    def take_stack(self) -> str:
        pid = self.pids.get("shell")
        if not pid or not alive(pid):
            return ""
        self.stacks += 1
        name = f"stack-{self.stacks}.txt"
        try:
            done = subprocess.run(["eu-stack", "-n", "80", "-p", str(pid)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, timeout=40)
            self.args.out.joinpath(name).write_text(done.stdout)
        except (OSError, subprocess.TimeoutExpired) as error:
            self.args.out.joinpath(name).write_text(f"eu-stack failed: {error}\n")
        return name

    # ---- the ping thread: availability of the GUI thread, stacks on a miss ----------------------
    def ping_loop(self):
        period, stall = self.args.ping_ms / 1000.0, self.args.stall_ms / 1000.0
        while self.running.is_set():
            started = time.perf_counter()
            started_wall = now_ms()
            try:
                proc = subprocess.Popen([str(QS), "-c", "lme-shell", "ipc", "call", "probe", "ping"], env=self.env,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            except OSError as error:
                self.write(t=round(now_ms(), 3), kind="ping", error=str(error))
                break
            missed = False
            try:
                proc.communicate(timeout=stall)
            except subprocess.TimeoutExpired:
                # Not answered within the stall budget: the GUI thread is busy right now.
                missed = True
                stack = self.take_stack()
            out, _ = proc.communicate(timeout=60)
            rtt = (time.perf_counter() - started) * 1000.0
            record = {"t": round(started_wall, 3), "kind": "ping", "rtt_ms": round(rtt, 2), "rc": proc.returncode}
            if missed:
                record["stack"] = stack
                record["stall_ms"] = self.args.stall_ms
            self.write(**record)
            if proc.returncode != 0 and not alive(self.args.pid):
                self.write(t=round(now_ms(), 3), kind="gone", pid=self.args.pid)
                break
            rest = period - (time.perf_counter() - started)
            if rest > 0:
                self.running.wait(rest)

    # ---- GPU ---------------------------------------------------------------------------------------
    def gpu_loop(self):
        query = ["nvidia-smi", "--query-gpu=utilization.gpu,utilization.memory,memory.used,power.draw,clocks.current.graphics,temperature.gpu",
                 "--format=csv,noheader,nounits"]
        while self.running.is_set():
            try:
                done = subprocess.run(query, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5)
                nvidia = [float(value) for value in done.stdout.strip().split(",")] if done.returncode == 0 and done.stdout.strip() else None
            except (OSError, ValueError, subprocess.TimeoutExpired):
                nvidia = None
            amdgpu = []
            for card in sorted(Path("/sys/class/drm").glob("card[0-9]")):
                busy, mem = card / "device/gpu_busy_percent", card / "device/mem_busy_percent"
                try:
                    if busy.exists():
                        amdgpu.append([card.name, int(busy.read_text()), int(mem.read_text()) if mem.exists() else None])
                except (OSError, ValueError):
                    pass
            self.write(t=round(now_ms(), 3), kind="gpu", nvidia=nvidia, amdgpu=amdgpu or None)
            self.running.wait(0.5)

    # ---- main loop ---------------------------------------------------------------------------------
    def loop(self):
        args = self.args
        self.env = dict(os.environ)
        tick, index = args.interval / 1000.0, 0
        self.write(t=round(now_ms(), 3), kind="start", pid=args.pid, interval=args.interval, ping_ms=args.ping_ms,
                   stall_ms=args.stall_ms, tick_ms=round(TICK_MS, 3))
        threads = [threading.Thread(target=self.ping_loop, daemon=True)]
        if not args.no_gpu:
            threads.append(threading.Thread(target=self.gpu_loop, daemon=True))
        for thread in threads:
            thread.start()
        gone_since = None
        while self.running.is_set():
            started = time.perf_counter()
            if not args.no_niri and index % args.niri_every == 0:
                began = time.perf_counter()
                try:
                    done = subprocess.run(["niri", "msg", "--json", "focused-window"], env=self.env, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL, timeout=5)
                    self.write(t=round(now_ms() - (time.perf_counter() - began) * 1000.0, 3), kind="niri",
                               rtt_ms=round((time.perf_counter() - began) * 1000.0, 2), rc=done.returncode)
                except (OSError, subprocess.TimeoutExpired) as error:
                    self.write(t=round(now_ms(), 3), kind="niri", rtt_ms=None, error=str(error)[:120])
            procs = {}
            if args.settings and not self.pids.get("settings") and index % 10 == 0:
                found = instance_pid(args.settings)
                if found:
                    self.pids["settings"] = found
                    self.write(t=round(now_ms(), 3), kind="settings", pid=found)
            for name, pid in list(self.pids.items()):
                if not alive(pid):
                    if name == "settings":
                        del self.pids[name]
                        self.write(t=round(now_ms(), 3), kind="settings", pid=pid, gone=True)
                    continue
                procs[name] = {"pid": pid, "rss_kb": rss_kb(pid), "threads": read_threads(pid)}
            if procs:
                self.write(t=round(now_ms(), 3), kind="threads", procs=procs)
            if not alive(args.pid):
                gone_since = gone_since or now_ms()
                if now_ms() - gone_since > 5000:
                    self.write(t=round(now_ms(), 3), kind="gone", pid=args.pid)
                    break
            else:
                gone_since = None
            index += 1
            rest = tick - (time.perf_counter() - started)
            if rest > 0:
                self.running.wait(rest)
        self.write(t=round(now_ms(), 3), kind="stop")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pid", type=int, required=True, help="the stand-in shell")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--settings", help="settings.qml of the stand-in tree: its process is watched too")
    ap.add_argument("--interval", type=int, default=50, help="thread sample period, ms")
    ap.add_argument("--niri-every", type=int, default=4, help="niri round trip every N samples")
    ap.add_argument("--ping-ms", type=int, default=100, help="one probe ping every N ms")
    ap.add_argument("--stall-ms", type=int, default=150, help="a ping unanswered after this long takes a stack")
    ap.add_argument("--no-niri", action="store_true")
    ap.add_argument("--no-gpu", action="store_true")
    args = ap.parse_args()
    if not alive(args.pid):
        print(f"sampler: pid {args.pid} is not running", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    sampler = Sampler(args)

    def stop(*_):
        sampler.stop()

    import signal
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    sampler.env = dict(os.environ)
    sampler.loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
