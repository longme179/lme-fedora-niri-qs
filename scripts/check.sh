#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Role: fast repo checks (architecture/catalog, unittest discovery, bash syntax, demo JSON). REL: tests/, migration gates.
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$repo_dir"
# Child interpreters (and focused runs) need the backend modules on the path.
export PYTHONPATH="$repo_dir/scripts${PYTHONPATH:+:$PYTHONPATH}"
./scripts/check-architecture.sh
python3 scripts/feature_catalog.py --check
# tests/ is a local-only working set (untracked since the 2026-11-13 policy): run it where
# it exists, skip with a note on fresh clones.
if [ -d tests ]; then
    python3 -m unittest discover -s tests -v
else
    printf 'Tests directory absent (local-only policy) — skipping discovery.\n'
fi
for script in ./*.sh scripts/*.sh; do
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
