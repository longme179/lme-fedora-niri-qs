#!/usr/bin/env bash
# Static architecture checks; safe without a desktop session or Git metadata.
set -euo pipefail
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/check_architecture.py"
