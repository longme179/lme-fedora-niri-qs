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
        --help|-h) printf 'Usage: scripts/settings.sh [--demo] [--daemonize] [--page utilities|appearance|elements|desktop|topbar|controlLayout|display|nightLight|wallpaper|weather|notifications|clipboard|idle|keybinds|behavior|about]\n'; exit 0 ;;
        *) printf 'Error: unknown argument: %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done
case "$page" in
    appearance|elements|desktop|topbar|controlLayout|display|notifications|behavior|about) ;;
    *)
        catalog_index=""
        if [[ -f "$repo_dir/config/features.json" ]]; then
            IFS= read -r -d '' -t 3 catalog_index < "$repo_dir/config/features.json" || true
        fi
        catalog_hit=false
        # --check enforces one compact record per line and a literal, first page key.
        # Admission is only a hint: QML still waits for the backend's validation.
        if [[ "$page" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]]; then
            while IFS= read -r catalog_record; do
                if [[ "$catalog_record" == '{"id":'* && "$catalog_record" == *'"enabled":true'* &&
                      "$catalog_record" == *'"settingsPage":{"key":"'"$page"'"'* ]]; then
                    catalog_hit=true; break
                fi
            done <<< "$catalog_index"
        fi
        if [[ "$catalog_hit" != true ]]; then
            if [[ "${catalog_index//[[:space:]]/}" == '{"version":1,"features":[]}' || "${catalog_index//[[:space:]]/}" == '{"features":[],"version":1}' ]]; then
                printf 'Error: unknown settings page: %s\n' "$page" >&2; exit 2
            fi
            python_binary="$(command -v python3 || printf /usr/bin/python3)"
            "$python_binary" "$repo_dir/scripts/feature_catalog.py" --page "$page"
        fi
        ;;
esac
qs_binary="${LME_QS_BINARY:-}"
if [[ -z "$qs_binary" ]]; then
    parent_binary="$(readlink -f "/proc/$PPID/exe" 2>/dev/null || true)"
    case "${parent_binary##*/}" in quickshell|qs) qs_binary="$parent_binary" ;; esac
fi
if [[ -z "$qs_binary" ]]; then qs_binary="$(command -v quickshell || command -v qs || true)"; fi
if [[ -z "$qs_binary" ]] || ! command -v "$qs_binary" >/dev/null 2>&1; then printf 'Error: install Quickshell 0.3.2 or newer (quickshell or qs).\n' >&2; exit 1; fi
export LME_QS_BINARY="$qs_binary"
if [[ "${LME_SHELL_PREVIEW:-}" == 1 ]]; then export LME_SHELL_DEMO=1; fi
unset LME_SHELL_PREVIEW
export LME_SETTINGS_PAGE="$page"
entry="$repo_dir/settings.qml"
if [[ "${LME_SHELL_DEMO:-}" == 1 ]]; then entry="$repo_dir/settings-demo.qml"; fi
# Quickshell 0.3.2 can return status 0 for an IPC error; require the window's reply.
if opened="$("$qs_binary" -p "$entry" ipc call settings openPage "$page" 2>/dev/null)"; then
    if [[ "$opened" != true ]]; then
        # Reuse a cold instance that has queued the page and is still loading its appearance.
        if [[ "$("$qs_binary" -p "$entry" ipc call settings startupPending 2>/dev/null || true)" == true ]]; then exit 0; fi
        printf 'Settings did not confirm a visible window; restarting this Settings instance.\n' >&2
        "$qs_binary" -p "$entry" kill >&2
        # IPC acknowledges shutdown before the instance necessarily exits.
        python3 - "$qs_binary" "$entry" <<'PY'
import json, subprocess, sys, time
deadline = time.monotonic() + 5
while True:
    reply = subprocess.check_output([sys.argv[1], '-p', sys.argv[2], 'list', '--json'], text=True, timeout=2).strip()
    # 0.3.2 prints a plain-text message for an empty list, even with --json.
    if not reply or reply.startswith('No running instances') or not json.loads(reply):
        break
    if time.monotonic() >= deadline:
        raise SystemExit('Settings is still stopping; retry after it exits.')
    time.sleep(.05)
PY
    else
        if [[ "${LME_SHELL_DEMO:-}" != 1 ]] && command -v niri >/dev/null 2>&1; then
            python3 - <<'PY'
import json, subprocess
try:
    result = subprocess.run(['niri', 'msg', '--json', 'windows'], capture_output=True, text=True, timeout=3)
    for window in json.loads(result.stdout):
        if window.get('app_id') == 'lme-shell-settings' or window.get('title') == 'LME Shell Settings':
            subprocess.run(['niri', 'msg', 'action', 'focus-window', '--id', str(window['id'])], check=False, timeout=3)
            break
except (OSError, ValueError, subprocess.TimeoutExpired):
    pass
PY
        fi
        exit 0
    fi
fi
exec "$qs_binary" --no-duplicate -p "$entry" "${qs_args[@]}"
