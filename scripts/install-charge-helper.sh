#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
case "${1:---dry-run}" in
    --dry-run) printf 'Install a root-owned helper: %s -> /usr/local/libexec/lme-shell-charge\nRun: sudo %q --install\n' "$repo_dir/scripts/charge_control.py" "$repo_dir/scripts/install-charge-helper.sh"; exit 0 ;;
    --install) ;;
    --help|-h) printf 'Usage: scripts/install-charge-helper.sh [--dry-run|--install]\nDefault: preview. --install requires root. Existing helper is backed up.\n'; exit 0 ;;
    *) printf 'Error: unknown option.\n' >&2; exit 2 ;;
esac
if (($# != 1)); then printf 'Error: supply --install only.\n' >&2; exit 2; fi
if ((EUID != 0)); then printf 'Error: run this installer with sudo.\n' >&2; exit 1; fi
parent=/usr/local/libexec
target="$parent/lme-shell-charge"
if [[ -L "$parent" || -L "$target" ]]; then printf 'Error: helper paths must not be symlinks.\n' >&2; exit 1; fi
if [[ ! -d "$parent" ]]; then install -d -o root -g root -m 0755 "$parent"; fi
for ancestor in / /usr /usr/local "$parent"; do
    if [[ "$(stat -c %u "$ancestor")" != 0 ]] || [[ -n "$(find "$ancestor" -maxdepth 0 -perm /022 -print)" ]]; then
        printf 'Error: unsafe helper parent: %s\n' "$ancestor" >&2; exit 1
    fi
done
if [[ -e "$target" ]]; then
    cp --preserve=all -- "$target" "$target.backup-$(date +%Y%m%d-%H%M%S)-$$"
fi
install -o root -g root -m 0755 "$repo_dir/scripts/charge_control.py" "$target"
printf 'Installed. The shell will ask through Polkit when changing a charge mode.\n'
