#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Role: deploy.sh (unclassified) — orchestration/helper script; see phase1-graph.md.
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
exec "$repo_dir/deploy.sh" "$@"
