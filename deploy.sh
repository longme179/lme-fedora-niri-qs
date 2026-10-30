#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Single entry for packages, runtime verification, shell/niri setup and rollback.
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$repo_dir/scripts/deploy.py" "$@"
