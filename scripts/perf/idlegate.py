#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Know when the owner's hands are off the seat, and notice the moment they come back.

  idlegate.py watch  [--dir DIR] [--seconds 3]       start the two idle watchers (idempotent)
  idlegate.py wait   [--seconds 3] [--max-wait 120]  block until the owner has been quiet that long
  idlegate.py stop                                     stop both watchers
  idlegate.py events [--dir DIR] [--since T]          print what the watchers recorded

Two swayidle clients watch the seat through ext-idle-notify (niri implements it; the shell's
own idle locker is a separate thing and is not involved):

  long   timeout QUIET_SECONDS (3 s)   IDLE means: no input from anyone for the whole timeout
                        before it. This is the gate before a stand-in may touch the session.
                        The owner asked for no long idle wait: the harness announces itself
                        (standin.py --notice) and starts once the seat has been quiet for a
                        few seconds. The timeout in force is recorded in the log header, so a
                        reader never has to guess the number swayidle was started with.
  short  timeout 1 s     RESUME lines that the harness did not cause itself are the owner.
                        The harness injects through uinput, which counts as real input, so its
                        own bursts are recognisable: a RESUME follows an injection within
                        milliseconds, and a pause of ~1.5 s always produces IDLE again.

Rules used by the scenario runner (functions below):
  - a RESUME with no harness injection in the 250 ms before / 50 ms after it = foreign input
  - no IDLE within `quiet + margin` after the last injection, while the harness stays quiet
    = foreign input too (the owner is moving while the state is already "active")
Either one aborts the batch; standin.py then restores the deployed shell.

Lines in <dir>/long.log and <dir>/short.log: "<epoch seconds> I" or "<epoch seconds> R".
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_DIR = Path.home() / ".cache/lme-perf/rv2/idle"
QUIET_SECONDS = 3
SHORT_SECONDS = 1
RESUME_BEFORE = 0.25   # s: an injection this recently before a RESUME explains it
RESUME_AFTER = 0.05    # s: ... or this soon after it (command spawn latency)
QUIET_MARGIN = 0.6     # s: extra time for the IDLE after a pause
UNITS = ("lme-perf-idle-long", "lme-perf-idle-short")
# Watchers stop by themselves after a day, so a crashed run cannot leave them behind for good.
MAX_RUNTIME = "20h"

STAMPER = ("import sys,time\n"
           "for line in sys.stdin: print('%.3f %s' % (time.time(), line.strip()), flush=True)\n")


def watch_command(seconds: int, log: Path) -> str:
    # The stamper runs as `python3 -c <code>` inside a systemd ExecStart: the code is
    # shell-quoted once more (systemd keeps backslash escapes literal), and it uses no
    # f-string braces that the surrounding shell could touch.
    return (f'echo "# timeout={seconds} started=$(date +%s.%N)"; '
            f"exec /usr/bin/swayidle -w timeout {seconds} 'echo I' resume 'echo R' "
            f"| python3 -c {json.dumps(json.dumps(STAMPER))} >> {json.dumps(str(log))} 2>&1")


def running(name: str) -> bool:
    result = subprocess.run(["systemctl", "--user", "is-active", f"lme-perf-idle-{name}"],
                            stdout=subprocess.PIPE, text=True)
    return result.stdout.strip() == "active"


def watch(args) -> int:
    base = args.dir
    base.mkdir(parents=True, exist_ok=True)
    for name, seconds in (("long", args.seconds), ("short", SHORT_SECONDS)):
        unit = f"lme-perf-idle-{name}"
        if running(name):
            print(f"{name} watcher already running")
            continue
        log = base / f"{name}.log"
        if log.exists():
            log.rename(base / f"{name}.{int(log.stat().st_mtime)}.log")
        result = subprocess.run(["systemd-run", "--user", f"--unit={unit}", "--collect", "--quiet",
                                 f"--property=RuntimeMaxSec={MAX_RUNTIME}",
                                 "/bin/bash", "-c", watch_command(seconds, log)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"IDLEGATE FAILED: cannot start the {name} watcher: {result.stderr.strip()}", file=sys.stderr)
            return 1
        print(f"{name} watcher started ({unit}, timeout {seconds}s, log {log})")
    return 0


def events(path: Path, since: float = 0.0) -> list:
    """[(epoch, 'I'|'R'), ...] recorded after `since`; unreadable or partial lines are skipped."""
    found = []
    try:
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) != 2 or parts[1] not in ("I", "R"):
                continue
            try:
                stamp = float(parts[0])
            except ValueError:
                continue
            if stamp >= since:
                found.append((stamp, parts[1]))
    except OSError:
        pass
    return sorted(found)


def quiet_since(long_log: Path):
    """Epoch time since which nobody touched the seat, or None when input is more recent than
    the watcher's timeout (or nothing was recorded). An IDLE event proves that the whole
    timeout before it was silent; a RESUME after it ends that at once."""
    timeout, since = QUIET_SECONDS, None
    try:
        for line in long_log.read_text().splitlines():
            if line.startswith("# timeout="):
                try:
                    timeout = int(line.split()[1].split("=", 1)[1])
                except (IndexError, ValueError):
                    pass
                continue
            parts = line.split()
            if len(parts) != 2 or parts[1] not in ("I", "R"):
                continue
            try:
                stamp = float(parts[0])
            except ValueError:
                continue
            since = stamp - timeout if parts[1] == "I" else None
    except OSError:
        return None
    return since


def is_quiet(long_log: Path, seconds: int, now: float):
    """`quiet_since` when the silence has lasted at least `seconds`, else None."""
    since = quiet_since(long_log)
    if since is not None and now - since >= seconds:
        return since
    return None


def foreign_resume(short_log: Path, since: float, injections: list) -> float:
    """Time of the first RESUME after `since` that no injection in `injections` explains, else 0."""
    for stamp, kind in events(short_log, since):
        if kind != "R":
            continue
        if not any(stamp - RESUME_BEFORE <= shot <= stamp + RESUME_AFTER for shot in injections):
            return stamp
    return 0.0


def quiet_confirmed(short_log: Path, last_injection: float, now: float) -> bool:
    """True when the seat went IDLE after the last injection: the harness is alone.
    False means the owner is moving (or the watcher is dead) while the state stays active."""
    idle_after = [stamp for stamp, kind in events(short_log, last_injection) if kind == "I" and stamp >= last_injection]
    return bool(idle_after) or now - last_injection < SHORT_SECONDS + QUIET_MARGIN


def wait(args) -> int:
    long_log = args.dir / "long.log"
    started = time.time()
    while True:
        now = time.time()
        quiet = is_quiet(long_log, args.seconds, now)
        if quiet is not None:
            print(json.dumps({"quiet": True, "since": round(quiet, 3), "waited": round(now - started, 1)}))
            return 0
        if not long_log.exists():
            print("IDLEGATE: the long watcher is not running (idlegate.py watch)", file=sys.stderr)
            return 2
        if now - started >= args.max_wait:
            print(json.dumps({"quiet": False, "waited": round(now - started, 1),
                              "last": events(long_log)[-1] if events(long_log) else None}))
            return 3
        time.sleep(min(1, max(0.1, args.max_wait - (now - started))))


def stop(args) -> int:
    result = subprocess.run(["systemctl", "--user", "stop", *UNITS], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"IDLEGATE: stop: {result.stderr.strip()}", file=sys.stderr)
    return result.returncode


def show(args) -> int:
    since = args.since
    for name in ("long", "short"):
        history = events(args.dir / f"{name}.log", since)
        print(name, len(history), "events", history[-6:])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("watch", "wait", "events"):
        command = sub.add_parser(name)
        command.add_argument("--dir", type=Path, default=DEFAULT_DIR)
        if name == "watch":
            command.add_argument("--seconds", type=int, default=QUIET_SECONDS,
                                 help="quiet time the long watcher needs before it reports IDLE")
        if name == "wait":
            command.add_argument("--seconds", type=int, default=QUIET_SECONDS, help="quiet time required")
            command.add_argument("--max-wait", type=int, default=120, help="give up after this many seconds")
        if name == "events":
            command.add_argument("--since", type=float, default=0.0)
    sub.add_parser("stop")
    args = ap.parse_args()
    return {"watch": watch, "wait": wait, "events": show, "stop": stop}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
