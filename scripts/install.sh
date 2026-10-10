#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/install.sh [--dry-run] [--replace] [--target PATH]

Link this checkout into the current user's Quickshell configuration directory.
The default target is $XDG_CONFIG_HOME/quickshell/lme-shell, or
$HOME/.config/quickshell/lme-shell. Keep this checkout after installation.

  --dry-run       Print the intended action without changing files.
  --replace       Back up an existing target before replacing it.
  --target PATH   Use a custom configuration target (useful for local testing).
  --help          Show this help.

This script does not install packages or edit the user's niri configuration.
EOF
}

dry_run=false
replace=false
target="${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/lme-shell"
while (($#)); do
    case "$1" in
        --dry-run) dry_run=true ;;
        --replace) replace=true ;;
        --target)
            if (($# < 2)) || [[ -z "$2" ]]; then
                printf 'Error: --target requires a path.\n' >&2
                exit 2
            fi
            target="$2"
            shift
            ;;
        --help|-h) usage; exit 0 ;;
        *) printf 'Error: unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ ! -f "$repo_dir/shell.qml" ]]; then
    printf 'Error: shell.qml is missing from %s.\n' "$repo_dir" >&2
    exit 1
fi
target="$(realpath -ms -- "$target")"
# Canonicalize the parent only. Dereferencing the final existing symlink would
# turn a repeat install into a request to replace the source checkout.
target_parent="$(realpath -m -- "$(dirname -- "$target")")"
target_location="${target_parent%/}/$(basename -- "$target")"
if [[ "$target" == / || "$target_location" == "$repo_dir" ||
      "$target_location" == "$repo_dir/"* || "$repo_dir" == "$target_location/"* ]]; then
    printf 'Error: choose a target outside the checkout and its ancestor directories.\n' >&2
    exit 1
fi
if [[ -L "$target" ]] && [[ "$(readlink -f -- "$target" || true)" == "$repo_dir" ]]; then
    printf 'Already installed: %s -> %s\n' "$target" "$repo_dir"
    exit 0
fi
if [[ -e "$target" || -L "$target" ]]; then
    if ! "$replace"; then
        printf 'Error: %s already exists. Use --replace to preserve it in a backup.\n' "$target" >&2
        exit 1
    fi
fi

backup=""
if [[ -e "$target" || -L "$target" ]]; then
    backup="$target.backup-$(date +%Y%m%d-%H%M%S)-$$"
    printf 'Preserve existing configuration: %s -> %s\n' "$target" "$backup"
fi
printf 'Install link: %s -> %s\n' "$target" "$repo_dir"
if "$dry_run"; then
    exit 0
fi
mkdir -p -- "$(dirname -- "$target")"
if [[ -n "$backup" ]]; then
    mv -- "$target" "$backup"
fi
if ! ln -sT -- "$repo_dir" "$target"; then
    if [[ -n "$backup" ]]; then
        mv -- "$backup" "$target"
    fi
    printf 'Error: installation failed; the previous target was restored.\n' >&2
    exit 1
fi
printf 'Installed. Start inside niri with: quickshell -c lme-shell\n'
printf 'Niri integration instructions: %s/docs/INSTALL.md\n' "$repo_dir"
