#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Know when the owner is away, and notice the moment they come back.

  idlegate.py watch  [--dir DIR]                      start the two idle watchers (idempotent)
  idlegate.py wait   --seconds 180 --max-wait 3600     block until the owner has been idle that long
  idlegate.py events [--dir DIR] [--since T]          print what the watchers recorded

Two swayidle clients watch the seat through ext-idle-notify (niri implements it; the shell's
own idle locker is a separate thing and is not involved):

  long   timeout 180 s   IDLE means: no input from anyone for the whole timeout before it.
                        This is the gate before a stand-in may touch the session.
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
LONG_SECONDS = 180
SHORT_SECONDS = 1
RESUME_BEFORE = 0.25   # s: an injection this recently before a RESUME explains it
RESUME_AFTER = 0.05    # s: ... or this soon after it (command spawn latency)
QUIET_MARGIN = 0.6     # s: extra time for the IDLE after a pause

STAMPER = "import sys,time\nfor line in sys.stdin: print(f'{time.time():.3f} {line.strip()}', flush=True)\n"


def watch_command(seconds: int, log: Path) -> str:
    return (f"exec /usr/bin/swayidle -w timeout {seconds} 'echo I' resume 'echo R' "
            f"| python3 -c {json.dumps(STAMPER)} >> {json.dumps(str(log))} 2>&1")


def watch(args) -> int:
    base = args.dir
    base.mkdir(parents=True, exist_ok=True)
    for name, seconds in (("long", LONG_SECONDS), ("short", SHORT_SECONDS)):
        unit = f"lme-perf-idle-{name}"
        active = subprocess.run(["systemctl", "--user", "is-active", unit], stdout=subprocess.PIPE, text=True)
        if active.stdout.strip() == "active":
            print(f"{name} watcher already running")
            continue
        log = base / f"{name}.log"
        if log.exists():
            log.rename(base / f"{name}.{int(log.stat().st_mtime)}.log")
        result = subprocess.run(["systemd-run", "--user", f"--unit={unit}", "--collect", "--quiet",
                                 "/bin/bash", "-c", watch_command(seconds, log)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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


def idle_since(long_log: Path, seconds: int, now: float):
    """Epoch time since which nobody touched the seat, or None. The last recorded event must be
    IDLE (no RESUME after it), which by itself guarantees `seconds` of silence before it."""
    history = events(long_log)
    if not history or history[-1][1] != "I":
        return None
    return history[-1][0] - seconds


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
        gone = idle_since(long_log, args.seconds, now)
        if gone is not None and now - gone >= args.seconds:
            print(json.dumps({"idle": True, "since": round(gone, 3), "waited": round(now - started, 1)}))
            return 0
        if not long_log.exists():
            print("IDLEGATE: the long watcher is not running (idlegate.py watch)", file=sys.stderr)
            return 2
        if now - started >= args.max_wait:
            print(json.dumps({"idle": False, "waited": round(now - started, 1),
                              "last": events(long_log)[-1] if events(long_log) else None}))
            return 3
        time.sleep(min(5, max(0.5, args.max_wait - (now - started))))


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
        if name == "wait":
            command.add_argument("--seconds", type=int, default=LONG_SECONDS, help="idle time required")
            command.add_argument("--max-wait", type=int, default=3600, help="give up after this many seconds")
        if name == "events":
            command.add_argument("--since", type=float, default=0.0)
    args = ap.parse_args()
    return {"watch": watch, "wait": wait, "events": show}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
