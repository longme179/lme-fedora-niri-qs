#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$repo_dir"
python3 scripts/feature_catalog.py --check
python3 -m unittest discover -s tests -v
for script in scripts/*.sh; do
    bash -n "$script"
done
python3 scripts/desktop_backend.py --demo --once | python3 -c '
import json, sys
state = json.load(sys.stdin)
assert state["apps"] and state["niri"]["workspaces"]
assert state["preferences"]["language"] == "en"
print("Demo backend snapshot: valid")
'
printf 'Backend tests and Bash syntax checks passed.\n'
printf 'For GUI checks, use scripts/start.sh --preview in a Wayland session.\n'
