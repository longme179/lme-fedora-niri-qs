"""Shared private JSON persistence and advisory file locks."""
import contextlib
import fcntl
import json
import math
import os
import tempfile


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
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def finite_number(value):
    """Accept only numbers a float conversion and range check can handle."""
    if type(value) not in (int, float): return False
    if type(value) is int and abs(value) > 2 ** 53: return False
    try: return math.isfinite(value)
    except (OverflowError, TypeError): return False
