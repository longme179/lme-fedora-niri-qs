#!/usr/bin/env python3
"""Generic bounded JSON document writer for the native QML services (lyrics --store pattern).

The native services own their flows but quickshell 0.3.2 has no file-write API, so a
service stages its document on stdin and this helper persists it exactly like
storage.write_json: a 0o600 temp file, fsync, atomic os.replace.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: equalizer; Phase 3 graph).
"""
# SPDX-License-Identifier: GPL-3.0-or-later
# REL: qml/services/EqualizerState.qml (the eq_state document writes); scripts/storage.py::write_json.
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

LIMIT = 262144


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True, help="The document to replace atomically")
    args = parser.parse_args()
    raw = sys.stdin.buffer.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("Document is too large")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("A JSON object is required")
    target = Path(args.path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(target.parent), delete=False) as stream:
            temporary = stream.name
            os.chmod(temporary, 0o600)
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass
        raise
    print("stored", flush=True)


if __name__ == "__main__":
    main()
