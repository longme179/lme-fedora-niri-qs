#!/usr/bin/env python3
"""One-shot validated preferences writer for the native StorageState (Q6 leg 1).

quickshell 0.3.2 has no file-write API, so the shell's single-writer apply stages its
values here and this helper persists them through the SAME Preferences path the
backend uses — reused, not re-implemented: the settings.lock flock, the reload under
the lock, the per-key merge, the schema validation and the 0o600 temp + fsync +
atomic replace. Leg 2 re-homes these semantics out of desktop_backend.py together
with this helper; leg 3 retires the backend itself.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
# REL: qml/services/StorageState.qml (the apply surface); scripts/desktop_backend.py::Preferences.
import argparse
import json
import sys
from pathlib import Path

from desktop_backend import CommandError, Preferences


def reply(ok, **payload):
    print(json.dumps(dict(ok=ok, **payload), ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=None, help="The settings document (default: the user's)")
    parser.add_argument("--set", dest="values", required=True, help="A JSON object of preference values")
    args = parser.parse_args()
    try:
        values = json.loads(args.values)
    except ValueError:
        return reply(False, message="Invalid settings payload.")
    if not isinstance(values, dict) or not values:
        return reply(False, message="Invalid settings payload.")
    try:
        Preferences(args.path).update(values)
    except (CommandError, ValueError) as error:
        return reply(False, message=str(error)[:180])
    except OSError:
        return reply(False, message="Settings could not be written. Check the session and local storage.")
    return reply(True, message="Settings updated")


if __name__ == "__main__":
    raise SystemExit(main())
