#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/install-fedora.sh [--install] [--optional] [--copr]

Without --install this script only prints the package commands.

  --install    Run DNF interactively on Fedora. DNF asks before transactions.
  --optional   Include recommended applications and helper tools.
  --copr       Allow the upstream-documented errornointernet/quickshell COPR
               if quickshell is absent from currently enabled repositories.
  --help       Show this help.

No COPR is enabled unless --install and --copr are both supplied and needed.
Package signatures and TLS verification are kept enabled. This script does not
change NVIDIA drivers, services, the niri config, or any disk partitions.
EOF
}

install=false
optional=false
copr=false
while (($#)); do
    case "$1" in
        --install) install=true ;;
        --optional) optional=true ;;
        --copr) copr=true ;;
        --help|-h) usage; exit 0 ;;
        *) printf 'Error: unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

packages=(quickshell python3 qt6-qtbase qt6-qtdeclarative qt6-qtwayland
    qt6-qtsvg qt6-qtimageformats google-roboto-fonts google-noto-sans-fonts google-noto-color-emoji-fonts
    adwaita-icon-theme NetworkManager pipewire pipewire-pulseaudio
    wireplumber brightnessctl bluez systemd util-linux polkit wl-clipboard)
if "$optional"; then
    packages+=(kitty nautilus firefox pavucontrol network-manager-applet
        blueman swaylock swayidle wlsunset tesseract tesseract-langpack-eng tesseract-langpack-vie libnotify playerctl
        xdg-utils xdg-desktop-portal xdg-desktop-portal-gnome xdg-desktop-portal-gtk
        gnome-keyring)
fi

printf 'Required Quickshell version: 0.3.2 or newer, with PipeWire, Polkit and Wayland support.\n'
printf 'Idle profiles need swayidle/swaylock (--optional); full-screen blur needs niri >=26.04.\n'
printf 'Keep the existing power-profile provider (Fedora tuned-ppd or power-profiles-daemon).\n'
printf 'Proposed command:'
printf ' %q' sudo dnf install "${packages[@]}"
printf '\n'
if "$copr"; then
    printf 'Conditional fallback: sudo dnf copr enable errornointernet/quickshell\n'
fi
if ! "$install"; then
    printf 'Preview only. Use --install to run these commands on Fedora.\n'
    exit 0
fi

if [[ ! -r /etc/os-release ]]; then
    printf 'Error: cannot identify the operating system.\n' >&2
    exit 1
fi
source /etc/os-release
if [[ "${ID:-}" != fedora ]]; then
    printf 'Error: --install is supported only on Fedora (detected %s).\n' "${ID:-unknown}" >&2
    exit 1
fi
if ! command -v dnf >/dev/null; then
    printf 'Error: DNF was not found.\n' >&2
    exit 1
fi

quickshell_available=false
if rpm -q quickshell >/dev/null 2>&1; then
    quickshell_available=true
else
    if ! package_query="$(dnf --quiet repoquery --available --qf '%{name}' quickshell)"; then
        printf 'Error: repository lookup failed. Resolve the DNF error before changing package sources.\n' >&2
        exit 1
    fi
    while IFS= read -r package_name; do
        if [[ "$package_name" == quickshell ]]; then quickshell_available=true; fi
    done <<< "$package_query"
fi
if "$quickshell_available"; then
    printf 'Quickshell is installed or available from enabled repositories.\n'
else
    if ! "$copr"; then
        printf 'Error: quickshell is unavailable from enabled repositories.\n' >&2
        printf 'Review https://quickshell.org/docs/v0.2.0/guide/install-setup/ and the COPR before using --copr.\n' >&2
        exit 1
    fi
    printf 'Enabling the upstream-documented third-party Quickshell COPR.\n'
    sudo dnf copr enable errornointernet/quickshell
fi
sudo dnf install "${packages[@]}"
printf 'Packages installed. Run scripts/doctor.sh inside your niri session.\n'
