#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
qsb_binary="${QSB_BINARY:-qsb}"
for shader in "$repo_dir"/qml/components/shaders/*.frag; do
    "$qsb_binary" --glsl "100 es,120,150" --hlsl 50 --msl 12 -o "$shader.qsb" "$shader"
done
