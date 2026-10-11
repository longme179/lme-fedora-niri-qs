#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -uo pipefail

required_failures=0
optional_missing=0
required() {
    if command -v "$1" >/dev/null 2>&1; then
        printf 'OK       %-22s %s\n' "$1" "$(command -v "$1")"
    else
        printf 'MISSING  %-22s install %s\n' "$1" "$2"
        required_failures=$((required_failures + 1))
    fi
}
optional() {
    if command -v "$1" >/dev/null 2>&1; then
        printf 'OK       %-22s %s\n' "$1" "$(command -v "$1")"
    else
        printf 'OPTIONAL %-22s %s\n' "$1" "$2"
        optional_missing=$((optional_missing + 1))
    fi
}

printf 'LME Shell: read-only runtime checks\n\n'
qs_binary="$(command -v quickshell || command -v qs || true)"
if [[ -n "$qs_binary" ]]; then
    printf 'OK       %-22s %s\n' Quickshell "$qs_binary"
else
    required quickshell quickshell
fi
required python3 python3
required niri niri
required nmcli NetworkManager
required wpctl wireplumber
required brightnessctl brightnessctl
required bluetoothctl bluez
required busctl systemd
required pkexec polkit
optional rfkill 'Bluetooth software-block recovery: util-linux'
if [[ -n "$qs_binary" ]] && command -v python3 >/dev/null 2>&1; then
    if "$qs_binary" --version | python3 -c 'import re, sys; match = re.search(r"(\d+)\.(\d+)\.(\d+)", sys.stdin.read()); sys.exit(0 if match and tuple(map(int, match.groups())) >= (0, 3, 2) else 1)'; then
        printf 'OK       Quickshell version is at least 0.3.2\n'
    else
        printf 'MISSING  Quickshell 0.3.2 or newer with PipeWire, Polkit and Wayland support\n'
        required_failures=$((required_failures + 1))
    fi
fi
optional powerprofilesctl 'power-profile CLI; busctl also supports Fedora tuned-ppd'
optional swaylock 'lock screen'
optional swayidle 'laptop idle profiles; enable in Settings > Idle and sleep'
optional wlsunset 'Night Light gamma control; Settings > Night Light'
optional tesseract 'Screenshot studio OCR; install tesseract-langpack-eng (and optionally -vie)'
optional awww 'wallpaper selection and restoration'
optional awww-daemon 'wallpaper daemon'
optional nm-connection-editor 'advanced Wi-Fi setup: network-manager-applet'
optional blueman-manager 'Bluetooth pairing: blueman'
optional pavucontrol 'advanced audio setup: pavucontrol'
optional notify-send 'notification smoke test: libnotify'
optional kitty 'default terminal; configurable'
required wl-copy wl-clipboard
required wl-paste wl-clipboard

if command -v fc-match >/dev/null 2>&1; then
    if [[ "$(fc-match -f '%{family}' Roboto)" == *Roboto* ]]; then
        printf 'OK       Roboto typography available\n'
    else
        printf 'OPTIONAL Roboto font missing; install google-roboto-fonts\n'
        optional_missing=$((optional_missing + 1))
    fi
fi

printf '\nSession checks\n'
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    printf 'OK       WAYLAND_DISPLAY is present\n'
else
    printf 'MISSING  WAYLAND_DISPLAY; run the shell inside a niri Wayland session\n'
    required_failures=$((required_failures + 1))
fi
if [[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
    printf 'OK       session D-Bus address is present\n'
else
    printf 'MISSING  session D-Bus address; notifications and MPRIS need session D-Bus\n'
    required_failures=$((required_failures + 1))
fi
if command -v niri >/dev/null 2>&1; then
    if niri msg --json outputs >/dev/null 2>&1; then
        printf 'OK       niri IPC responds\n'
    else
        printf 'MISSING  niri IPC; run this check inside the target niri session\n'
        required_failures=$((required_failures + 1))
    fi
fi
if [[ -n "$qs_binary" ]]; then
    "$qs_binary" --version 2>&1 || true
    printf 'INFO     Built-in authentication: run quickshell -c lme-shell ipc call shell authenticationStatus\n'
    printf 'INFO     Custom Quickshell builds need SERVICE_POLKIT=ON; see docs/AUTHENTICATION.md\n'
fi
if command -v busctl >/dev/null 2>&1; then
    if busctl --system get-property org.freedesktop.UPower.PowerProfiles \
            /org/freedesktop/UPower/PowerProfiles org.freedesktop.UPower.PowerProfiles \
            ActiveProfile >/dev/null 2>&1 ||
        busctl --system get-property net.hadess.PowerProfiles /net/hadess/PowerProfiles \
            net.hadess.PowerProfiles ActiveProfile >/dev/null 2>&1; then
        printf 'OK       a compatible power-profile provider responds\n'
    else
        printf 'OPTIONAL no power-profile provider responds; keep one working tuned-ppd or PPD service\n'
        optional_missing=$((optional_missing + 1))
    fi
fi

config_base="${XDG_CONFIG_HOME:-$HOME/.config}"
if [[ -f "$config_base/quickshell/lme-shell/shell.qml" ]]; then
    printf 'OK       installed Quickshell entry point\n'
else
    printf 'MISSING  installed config; run scripts/install.sh\n'
    required_failures=$((required_failures + 1))
fi
printf '\n%d required checks missing; %d optional tools unavailable.\n' "$required_failures" "$optional_missing"
printf 'No settings, services, radios, or power state were changed.\n'
if ((required_failures > 0)); then exit 1; fi
