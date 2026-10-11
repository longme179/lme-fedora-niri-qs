#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"

usage() {
    cat <<'EOF'
Usage: scripts/start.sh [--demo] [--preview] [--config NAME] [--wallpaper FILE] [--no-wallpaper]

Start the installed LME Quickshell configuration. If a wallpaper was saved in
the shell settings, start awww-daemon when necessary and restore that wallpaper.
Also restore confirmed settings for supported, currently attached niri displays.

  --demo          Use sample data; skip wallpaper and all desktop mutations.
  --preview       Show an ordinary preview window with sample data; implies demo.
  --config NAME   Quickshell configuration name (default: lme-shell).
  --wallpaper     Restore this raster image instead of the saved wallpaper.
  --no-wallpaper  Preserve the current wallpaper without starting a daemon.
  --help          Show this help.
EOF
}

demo=false
preview=false
if [[ "${LME_SHELL_DEMO:-0}" == 1 ]]; then demo=true; fi
if [[ "${LME_SHELL_PREVIEW:-0}" == 1 ]]; then preview=true; demo=true; fi
restore_wallpaper=true
config_name=lme-shell
wallpaper=""
while (($#)); do
    case "$1" in
        --demo) demo=true ;;
        --preview) preview=true; demo=true ;;
        --no-wallpaper) restore_wallpaper=false ;;
        --config|--wallpaper)
            if (($# < 2)) || [[ -z "$2" ]]; then
                printf 'Error: %s requires a value.\n' "$1" >&2
                exit 2
            fi
            if [[ "$1" == --config ]]; then config_name="$2"; else wallpaper="$2"; fi
            shift
            ;;
        --help|-h) usage; exit 0 ;;
        *) printf 'Error: unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done
qs_binary="$(command -v quickshell || command -v qs || true)"
if [[ -z "$qs_binary" ]]; then
    printf 'Error: Quickshell is missing. See docs/INSTALL.md.\n' >&2
    exit 1
fi
if "$demo"; then
    export LME_SHELL_DEMO=1
    if "$preview"; then export LME_SHELL_PREVIEW=1; fi
elif "$restore_wallpaper"; then
    if [[ -z "$wallpaper" ]] && command -v python3 >/dev/null; then
        wallpaper="$(python3 - <<'PY'
import json
import os
from pathlib import Path
path = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "lme-shell/settings.json"
try:
    value = json.loads(path.read_text()).get("wallpaper", "")
    if isinstance(value, str) and "\n" not in value and "\0" not in value:
        print(value, end="")
except (OSError, ValueError, AttributeError):
    pass
PY
        )"
    fi
    if [[ -n "$wallpaper" ]]; then
        if [[ ! -f "$wallpaper" ]]; then
            printf 'Warning: saved wallpaper is unavailable: %s\n' "$wallpaper" >&2
        elif ! command -v python3 >/dev/null; then
            printf 'Warning: Python is unavailable; wallpaper restoration was skipped.\n' >&2
        else
            if ! python3 "$repo_dir/scripts/desktop_backend.py" --restore-wallpaper "$wallpaper"; then
                printf 'Warning: wallpaper restoration failed; starting the shell anyway.\n' >&2
            fi
        fi
    fi
fi
if ! "$demo" && command -v python3 >/dev/null; then
    if ! python3 "$repo_dir/scripts/desktop_backend.py" --restore-displays; then
        printf 'Warning: confirmed display restoration failed; starting the shell anyway.\n' >&2
    fi
fi
exec "$qs_binary" -c "$config_name"
