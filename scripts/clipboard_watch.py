#!/usr/bin/env python3
"""Single-instance clipboard watcher supervisor (the CaptureService spawn port).

Flocks the per-kind capture lock, arms PR_SET_PDEATHSIG against the shell pid, then
execs wl-paste --watch so the native ClipboardState owns capture without orphan risk:
quickshell SIGKILLs its children on normal exit, and the kernel SIGTERMs this
one if the shell dies any other way (probed on quickshell 0.3.2, 2026-11-13 —
a plain child orphaned on shell crash; the PDEATHSIG wrapper died clean).
"""
# SPDX-License-Identifier: AGPL-3.0-or-later
# REL: qml/services/ClipboardState.qml (the native watchers); scripts/clipboard.py (the
# capture worker + the lock path); scripts/idle_control.py (the prctl pattern this mirrors).
import argparse
import ctypes
import fcntl
import os
import shutil
import signal
import sys
from pathlib import Path

PR_SET_PDEATHSIG = 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=int, required=True, help="The shell pid to die with")
    parser.add_argument("--kind", choices=["text", "image"], required=True)
    parser.add_argument("--directory", type=Path, default=None)
    args = parser.parse_args()
    from clipboard import history_directory
    directory = (args.directory or history_directory()).resolve()
    paste = shutil.which("wl-paste")
    if not paste or not shutil.which("wl-copy"):
        print("Install wl-clipboard to capture and copy clipboard items.", flush=True)
        return 1
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    # The lock fd MUST survive execvp (Python opens fds close-on-exec by default, and the
    # flock evaporates with the fd) — the exec'd wl-paste holds it for its whole lifetime.
    # The lock is PER KIND: ClipboardState starts the text and image watchers together,
    # and one shared lock made them race at shell start — the loser exited as a "duplicate"
    # and its kind never captured again (the 2026-11-13 live bug). A second watcher of the
    # SAME kind (another shell instance) is still what the lock rejects.
    lock_fd = os.open(directory / f"capture-{args.kind}.lock", os.O_WRONLY | os.O_CREAT, 0o600)
    os.set_inheritable(lock_fd, True)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another shell instance owns clipboard capture.", flush=True)
        return 1
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    if libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0):
        print("Cannot supervise clipboard capture.", flush=True)
        return 1
    if os.getppid() != args.parent:
        return 0  # The shell died before the supervisor armed; nothing to watch for.
    os.execvp(paste, [paste, "--no-newline", "--type", args.kind, "--watch",
                      sys.executable, str(Path(__file__).with_name("clipboard.py").resolve()),
                      "--capture", args.kind, "--directory", str(directory)])


if __name__ == "__main__":
    raise SystemExit(main())
