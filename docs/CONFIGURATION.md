# User configuration

The source checkout is separate from user preferences. Settings are stored
under `${XDG_CONFIG_HOME:-~/.config}/lme-shell`. The shell creates its settings
file only when a preference is saved; missing configuration uses defaults.

## Settings

Use the standalone Settings app to change preferences. Open it with
`./scripts/settings.sh`, the application launcher or Super+Comma. A typical
`settings.json` is:

```json
{
  "language": "en",
  "animations": true,
  "opacity": 0.9,
  "accent": "#9580ff",
  "wallpaper": "",
  "terminal": "kitty",
  "bluetoothAdapter": "",
  "tasks": [],
  "barStyle": "connected",
  "barFontSize": 13,
  "barLayout": {
    "left": ["launcher", "overview", "workspaces"],
    "center": ["windowTitle"],
    "right": ["tray", "notifications", "audio", "network", "battery", "clock", "settings"]
  }
}
```

The UI and codebase are intentionally English. The `language` field is fixed to
`en`; it does not change the rest of your Fedora system's locale. Motion can be
disabled, and higher panel opacity improves readability over busy wallpapers.
The configured terminal must be an executable name available on `PATH` that
supports `-e`, such as `kitty`, `foot`, or `alacritty`. This preference applies
to `Terminal=true` desktop entries even when `gio` is installed. Other entries
use `gio` when available, with a tokenized executable fallback otherwise.
`bluetoothAdapter` is an optional BlueZ adapter path such as `/org/bluez/hci0`;
an empty or unavailable preference selects the first available adapter. Tasks
are private local entries with `id`, `text` and `done` fields. Up to 100 tasks
of 240 characters each are supported. The Agenda tab edits them without needing
a separate application or network account.

The Settings app and shell reload changes to `settings.json` on their next
backend poll (normally within two seconds). No restart is needed. Writes use an
advisory lock, merge the latest saved preferences, and atomically replace the
JSON file. Invalid JSON preserves the last valid running configuration.

`barStyle` accepts `connected` (default) or `islands`. `barFontSize` is an integer
from 12 through 16. `barLayout` requires exactly `left`, `center` and `right`
arrays. Each module may appear only once across all zones; unknown module IDs
are rejected. Empty zones are allowed. Supported IDs are `launcher`, `overview`,
`workspaces`, `windowTitle`, `media`, `resources`, `tray`, `notifications`,
`audio`, `network`, `battery`, `clock` and `settings`.

Use **Top bar** to add/remove modules, drag them within/across zones, use the
up/down buttons, or choose a position menu. Drop on a row to insert before it,
or on a zone's append target to place it last. Crowded zones scroll horizontally;
workspace lists also scroll. The center receives the space between the side
zones so groups do not overlap. Below 1200 px, the clock uses a shorter format.
Unavailable tray, media and battery modules automatically hide. Removing the
Settings module does not remove access through Super+Comma or the app launcher.

Select an existing PNG, JPEG, WebP, GIF, or BMP wallpaper from the shell's
Settings app. Changing a wallpaper requires a running `swww-daemon`:

```bash
swww-daemon
```

Run that daemon once per session, not once per wallpaper change. The startup
wrapper starts it if necessary when restoring a saved wallpaper. The original
SVG in `assets/wallpapers` is editable source artwork; use the PNG version or
another raster image with `swww`.

## Palette

The defaults follow a Dracula Pro-style dark palette. Licensed Pro theme files
are not bundled. If you own a specific Pro variant, add your preferred colors
to `~/.config/lme-shell/palette.json`:

```json
{
  "background": "#22212c",
  "panel": "#2d293d",
  "surface": "#393447",
  "text": "#f8f8f2",
  "muted": "#aaa6c0",
  "purple": "#9580ff",
  "pink": "#ff80bf",
  "cyan": "#80ffea",
  "green": "#8aff80",
  "yellow": "#ffff80",
  "red": "#ff9580",
  "border": "#605975"
}
```

You may override only the keys you need. Use hex colors in this schema. The
shell watches `palette.json` and reloads valid color changes while it is running;
no restart is needed for palette edits. Keep passwords, tokens, and other
credentials out of these files.

The primary accent is also saved in `settings.json`; changing the palette's
`purple` token does not replace an explicitly saved accent. Use the Settings
accent field to change it. Roboto is the primary family, with bold section
headings and a 14 px body size.
Install `google-roboto-fonts` for the intended appearance. JetBrains Mono is
used for existing telemetry/terminal fields when installed. The supplied Noto
packages provide fallback coverage; no fonts are bundled.

## Surface effects

The default appearance combines Material 3 Expressive inspired rounded controls,
flat tonal surface roles, translucent glass fills, subtle edge highlights and
brief shape animations. Bar and panel surfaces have no gradients. It does not
depend on background blur, expensive
full-screen effects, or NVIDIA offloading. This makes the default practical for
the laptop's integrated Radeon GPU.

The top bar is 42 px tall with an 8 px top margin. It reserves its own height
and margin, leaving the gap to application windows to niri's `layout.gaps`
setting. The shared geometry lives in `qml/theme/Theme.qml`. Side panels and
notification popups start 8 px below the bar.
The outer bar and its buttons use half-height corner radii for a pill shape.
All bar labels use shared Roboto Medium at 13 px by default (12–16 px in
Settings). Workspaces are sorted
by output and numeric index instead of relying on niri's JSON array order.

Panels slide in with `OutExpo` easing over 360 ms: sidebars arrive from the
right, centered panels from below, and the tray dropdown from above. They do
not fade in. Turn off Motion or disable animations in Settings for immediate
placement. Wallpaper transitions are controlled separately by `swww`.

The system tray button appears when applications register tray items. Click it
to open the dropdown; left-click an application to activate it, right-click for
its native menu, and scroll over its row to send the application's tray scroll
action. Applications that expose only a menu open that menu on left-click.
Click outside the dropdown or press Escape to close it. The notification button
uses a bell, with a diagonal stroke while Do Not Disturb is enabled.

Some newer niri builds expose compositor background effects for layer surfaces.
If your version documents that feature, you can experiment in your own niri
config using the namespaces shown by `niri msg layers`. Keep those optional
rules outside this project's baseline fragment and validate them with
`niri validate`; unsupported blur options can invalidate older niri configs.

## Overview

Left-click the two-panel overview icon or press `Mod+Tab` to open niri's native
overview. This provides real window previews and compositor drag/drop without
a Hyprland-only screencopy dependency. Right-click the icon or press
`Mod+Shift+Tab` to open the themed workspace board.

The board shows each workspace's output, window titles and app icons. Drag a
window card onto another workspace; its selector provides a keyboard
alternative and includes monitor names in the popup. Clicking a workspace or
window focuses it and closes the board. Window movement targets stable niri
workspace IDs, including across outputs. The board lists windows; it does not
capture bitmap thumbnails. Its Live preview button opens the native overview.

## Control center

The panel is 600 px wide at the target resolution, clamped to the output's
available space. Press `Ctrl+Tab` or `Ctrl+Shift+Tab` to cycle tabs, and Escape
to close. Scroll the Controls and Devices tabs for lower actions.

| Tab | Controls |
| --- | --- |
| Controls | Wi-Fi/Bluetooth power, microphone mute, DND, stay awake, motion, speaker/microphone sliders, brightness, power profile, MPRIS, system stats, full-screen/area screenshot, lock, settings, power menu and workspace board |
| Audio | Default output/input selection, each device's volume/mute, application stream volume/mute and advanced audio settings |
| Devices | Bluetooth adapter selection, paired-device connect/disconnect, block/error information, pairing settings, cached Wi-Fi networks and connection editor |
| Agenda | English calendar, local to-do list, 25-minute focus/5-minute short break/15-minute long break, and stopwatch |
| Notifications | Session history, DND and clearing notifications |

Stay awake inhibits idle while enabled in this shell session. It does not
disable manual locking or explicit suspend and resets when the shell restarts.
The focus timer and stopwatch continue when the panel is closed but reset on
shell restart. A completed focus/break session produces a local notification;
DND suppresses its popup while retaining it in history. Tasks survive restart
because they are saved in `settings.json`.

The native mixer tracks devices only while its tab is loaded. Radio and
hardware probes remain cached between backend refreshes; the Wi-Fi list uses
NetworkManager's existing scan cache. The shell does not continuously scan for
Bluetooth devices or Wi-Fi networks. Pairing and credential entry open Fedora's
existing tools.

## Preferences and permissions

The backend delegates operations to the running user's existing tools. Backlight,
Bluetooth, Wi-Fi, and power-profile access therefore follows Fedora's current
device permissions, service state, and polkit policy. The project does not add
passwordless sudo rules, run privileged background code, or install new polkit
rules. Errors are shown in the shell instead of being treated as success.

Notifications are kept for the running shell session; restarting the shell
clears that history. Do Not Disturb affects shell popups and is not a system-wide
notification policy.
