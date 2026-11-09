"""Shared private JSON persistence and advisory file locks.

Callers: desktop_backend.py, settings/feature code, workers, deploy/helpers (see edges.txt).
INVARIANT: writes are atomic (temp+fsync+os.replace+dir fsync); locks are advisory/exclusive with bounded wait.
Preserve lock/reload/merge/fsync/atomic-write semantics (AGENTS.md owner constraint).
REL: scripts/desktop_backend.py::Preferences/save paths; scripts/clipboard.py, battery_saver.py – locked/write_json.
"""
import contextlib
import fcntl
import json
import math
import os
import tempfile
import time

LOCK_TIMEOUT = 2.0
LOCK_RETRY_INTERVAL = 0.4


def acquire_exclusive(stream, path, timeout=LOCK_TIMEOUT):
    """Take an exclusive lock with a bounded wait instead of hanging forever."""
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    except BlockingIOError:
        deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"{path} is locked by another process") from None
            time.sleep(LOCK_RETRY_INTERVAL)


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = stream.name
            os.chmod(temporary, 0o600)
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)


def read_json(path, default, limit=8 * 1024 * 1024):
    try:
        if path.stat().st_size > limit: return default
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError): return default


@contextlib.contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(path, "a", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        acquire_exclusive(stream, path)
        yield


def finite_number(value):
    """Accept only numbers a float conversion and range check can handle."""
    if type(value) not in (int, float): return False
    if type(value) is int and abs(value) > 2 ** 53: return False
    try: return math.isfinite(value)
    except (OverflowError, TypeError): return False
