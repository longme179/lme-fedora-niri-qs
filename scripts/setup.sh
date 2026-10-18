#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"

usage() {
    cat <<'EOF'
Usage: scripts/setup.sh [--install] [--copr] [--replace] [--charge-helper]

Install LME Shell on Fedora as your normal desktop user. Without --install,
preview the package commands, config link and Settings launcher without writes.

  --install        Install core/recommended packages, link the shell, add Settings.
                   DNF keeps its transaction confirmation and sudo password prompt.
  --dry-run        Preview only (the default).
  --copr           Allow the documented Quickshell COPR only if needed.
  --replace        Back up existing config/launcher targets before replacing them.
  --charge-helper  Also install the privileged Lenovo charge helper through sudo.
  --help           Show this help.

Keep this checkout in a permanent directory. Existing shell preferences are
preserved. Review the printed niri includes and merge them manually; the script
does not rewrite your window-manager config or start another shell instance.
EOF
}

install=false
replace=false
copr=false
charge=false
while (($#)); do
    case "$1" in
        --install) install=true ;;
        --dry-run) install=false ;;
        --replace) replace=true ;;
        --copr) copr=true ;;
        --charge-helper) charge=true ;;
        --help|-h) usage; exit 0 ;;
        *) printf 'Error: unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done
if "$install" && ((EUID == 0)); then
    printf 'Error: run setup as your normal desktop user, without sudo. Only package/helper installation uses sudo.\n' >&2
    exit 1
fi
if ! command -v python3 >/dev/null; then
    printf 'Error: Python 3 is needed for the Settings installer. Install python3 first.\n' >&2
    exit 1
fi

package_args=(--optional)
file_args=()
if "$install"; then package_args+=(--install); else file_args+=(--dry-run); fi
if "$copr"; then package_args+=(--copr); fi
if "$replace"; then file_args+=(--replace); fi

if "$install"; then
    # Catch destination conflicts before asking DNF to change the system.
    "$repo_dir/scripts/install.sh" --dry-run "${file_args[@]}"
    "$repo_dir/scripts/install-settings.sh" --dry-run "${file_args[@]}"
fi
"$repo_dir/scripts/install-fedora.sh" "${package_args[@]}"
"$repo_dir/scripts/install.sh" "${file_args[@]}"
"$repo_dir/scripts/install-settings.sh" "${file_args[@]}"
if "$charge"; then
    if "$install"; then sudo "$repo_dir/scripts/install-charge-helper.sh" --install;
    else "$repo_dir/scripts/install-charge-helper.sh" --dry-run; fi
fi

if "$install"; then printf '\nShell files installed. Keep this checkout: %s\n' "$repo_dir";
else printf '\nPreview complete. Run again with --install to apply these steps.\n'; fi
printf '\nNext: finish niri integration (see docs/INSTALL.md).\n'
printf 'In %s/niri/config.kdl, review/merge these top-level includes:\n' "${XDG_CONFIG_HOME:-$HOME/.config}"
cat <<'EOF'

    include "../quickshell/lme-shell/config/niri/lme-shell.kdl"
    include "../quickshell/lme-shell/config/niri/popup-blur.kdl"

The blur include needs niri >=26.04 and goes after generic background-effect rules.
Merge an existing blur block instead of defining it twice. Resolve duplicate
keybindings before saving; keep one shell startup and notification/Polkit agent.

Then, inside your niri session:
    niri validate
    ./scripts/doctor.sh
    ./scripts/start.sh

Start only if this shell is not already running. After testing, stop it with
Ctrl+C and log out/in to verify the single niri startup entry. Wallpaper needs
both awww and awww-daemon; see docs/INSTALL.md if unavailable in your repositories.
EOF
