#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stop an owned tool's process group even if Quickshell kills its backend."""
import argparse
import ctypes
import os
import signal
import subprocess
import sys
import time

from idle_control import PR_SET_PDEATHSIG


def supervise(parent, command):
    if os.getpgrp() != os.getpid(): raise RuntimeError('Managed command requires its own process group')
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    if libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0):
        raise OSError(ctypes.get_errno(), 'Cannot supervise owned command')
    if stopping or os.getppid() != parent: return 0
    child = subprocess.Popen(command)
    while not stopping and os.getppid() == parent:
        try:
            code = child.wait(timeout=.05)
            if not stopping and os.getppid() == parent: return code if code >= 0 else 128-code
        except subprocess.TimeoutExpired: pass
    # Keep this group leader alive until the final signal, reserving its group ID.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    os.killpg(os.getpid(), signal.SIGTERM)
    deadline = time.monotonic()+.08
    while time.monotonic() < deadline:
        try: child.wait(timeout=min(.02, max(0, deadline-time.monotonic())))
        except subprocess.TimeoutExpired: pass
        time.sleep(.005)
    # SIGKILL includes this supervisor; adopted descendants are reaped by the session's init.
    os.killpg(os.getpid(), signal.SIGKILL)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=int, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if args.parent <= 0 or not command: parser.error('Provide the backend PID and command')
    try: return supervise(args.parent, command)
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
