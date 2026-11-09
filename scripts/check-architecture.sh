#!/usr/bin/env bash
# Static architecture checks; safe without a desktop session or Git metadata.
# REL: scripts/check_architecture.py, config/architecture.json – dependency/cycle/size policy.
set -euo pipefail
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/check_architecture.py"
