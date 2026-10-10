#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
page="appearance"
qs_args=()
while (($#)); do
    case "$1" in
        --demo) export LME_SHELL_DEMO=1 ;;
        --daemonize) qs_args+=(--daemonize) ;;
        --page)
            if (($# < 2)); then printf 'Error: --page requires a page name.\n' >&2; exit 2; fi
            page="$2"; shift ;;
        --help|-h) printf 'Usage: scripts/settings.sh [--demo] [--daemonize] [--page appearance|topbar|wallpaper|behavior|about]\n'; exit 0 ;;
        *) printf 'Error: unknown argument: %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done
case "$page" in appearance|topbar|wallpaper|behavior|about) ;; *) printf 'Error: unknown settings page: %s\n' "$page" >&2; exit 2 ;; esac
if ! command -v quickshell >/dev/null 2>&1; then printf 'Error: install Quickshell 0.3.2 or newer.\n' >&2; exit 1; fi
if [[ "${LME_SHELL_PREVIEW:-}" == 1 ]]; then export LME_SHELL_DEMO=1; fi
unset LME_SHELL_PREVIEW
export LME_SETTINGS_PAGE="$page"
entry="$repo_dir/settings.qml"
if [[ "${LME_SHELL_DEMO:-}" == 1 ]]; then entry="$repo_dir/settings-demo.qml"; fi
# Reuse the settings instance, then focus its native niri window when available.
if quickshell -p "$entry" ipc call settings openPage "$page" >/dev/null 2>&1; then
    if [[ "${LME_SHELL_DEMO:-}" != 1 ]] && command -v niri >/dev/null 2>&1; then
        python3 - <<'PY'
import json, subprocess
try:
    result = subprocess.run(['niri', 'msg', '--json', 'windows'], capture_output=True, text=True, timeout=3)
    for window in json.loads(result.stdout):
        if window.get('title') == 'LME Shell Settings':
            subprocess.run(['niri', 'msg', 'action', 'focus-window', '--id', str(window['id'])], check=False, timeout=3)
            break
except (OSError, ValueError, subprocess.TimeoutExpired):
    pass
PY
    fi
    exit 0
fi
exec quickshell --no-duplicate -p "$entry" "${qs_args[@]}"
