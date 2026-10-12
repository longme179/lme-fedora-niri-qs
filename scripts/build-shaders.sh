#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
qsb_binary="${QSB_BINARY:-qsb}"
"$qsb_binary" --glsl "100 es,120,150" --hlsl 50 --msl 12 -o "$repo_dir/qml/components/shaders/ripple.frag.qsb" "$repo_dir/qml/components/shaders/ripple.frag"
