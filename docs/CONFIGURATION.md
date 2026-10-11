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
  "weatherAutoLocation": true,
  "weatherLocation": {},
  "weatherUnit": "celsius",
  "clipboardEnabled": true,
  "clipboardImages": true,
  "clipboardLimit": 100,
  "activityEnabled": true,
  "barStyle": "connected",
  "barFontSize": 13,
  "barEdge": "top",
  "barEdgeMargin": 8,
  "barSideMargin": 12,
  "barHeight": 42,
  "fontSize": 14,
  "fontOverrides": {},
  "themeOverrides": {},
  "barLayout": {
    "left": ["launcher", "overview", "workspaces"],
    "center": ["activity"],
    "right": ["clipboard", "tray", "notifications", "audio", "network", "battery", "clock", "settings"]
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
`audio`, `network`, `battery`, `clock`, `settings`, `clipboard` and `activity`.

Use **Top bar** to add/remove modules, drag them within/across zones, use the
up/down buttons, or choose a position menu. Drop on a row to insert before it,
or on a zone's append target to place it last. Crowded zones scroll horizontally;
workspace lists also scroll. The center receives the space between the side
zones so groups do not overlap. Below 1200 px, the clock uses a shorter format.
Unavailable tray, media and battery modules automatically hide. Removing the
Settings module does not remove access through Super+Comma or the app launcher.

Select an existing PNG, JPEG, WebP, GIF, or BMP wallpaper in Settings.
Both Settings and the startup wrapper probe `awww query`, start `awww-daemon`
if necessary, wait for readiness, then call `awww img`. The selected path is
saved only after a successful apply. Restoration preserves the saved path and
uses an instant transition. Settings uses a fade when Motion is enabled.
Use the bundled PNG or your own raster image; the SVG is editable artwork.
Install both binaries from [awww upstream](https://codeberg.org/LGFae/awww.git).

## Weather

The Control Center automatically detects an approximate city through
`https://ipwho.is/` and retrieves current conditions and three forecast days
from `https://api.open-meteo.com/`. Celsius is the default. IP geolocation can
follow your VPN or provider's gateway; it is not GPS. No location history is
stored. The public IP is visible to the geolocation service, and approximate
coordinates are sent to Open-Meteo over HTTPS.

In **Settings → Weather**, use Detect now, turn automatic location off, search
for a city and select a result, or switch units. Search uses
`https://geocoding-api.open-meteo.com/`. Selecting a city atomically saves its
name, country, latitude and longitude together with `weatherAutoLocation: false`.
Turn automatic location back on to follow your current connection.
`weatherUnit` accepts `celsius` or `fahrenheit`; `weatherLocation` is `{}` or
an object with `name`, `latitude`, `longitude` and optional `country`.

Requests run on a background worker with a seven-second timeout and bounded
response size. Forecasts refresh every 15 minutes and automatic location hourly.
Failures retry after two minutes, retain the last forecast and mark it stale.
Changing location or units hides old data until the replacement arrives. The
refresh button requests a new forecast and, in automatic mode, a new location.
The independent Settings app only contacts location services on explicit
Detect/Search actions; it does not start forecast polling.
Demo weather is sample data and makes no network requests.

## Battery charging

Controls reads the kernel's charge interface. If numeric thresholds exist, the
buttons select 85% and 100%; an incompatible start threshold is lowered before
setting the stop threshold. Otherwise newer IdeaPad `charge_types` or legacy
`conservation_mode` switches use the firmware's fixed limit. The conservation
button omits “85%” in that case. Unsupported systems show disabled controls.

See [CHARGING.md](CHARGING.md) for the one-time administrator helper setup and
firmware limits. The shell verifies actual kernel state after each write and
reports rejection instead of storing a cosmetic preference. Authentication runs
in a worker so other shell actions continue during the prompt.

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

The bar defaults to 42 px tall with an 8 px top margin. Settings can move it
to the bottom and change its edge/side margins and height. It reserves its own height
and margin, leaving the gap to application windows to niri's `layout.gaps`
setting. The shared geometry lives in `qml/theme/Theme.qml`. Side panels and
notification popups start 8 px below the bar.
The outer bar and its buttons use half-height corner radii for a pill shape.
All bar labels use shared Roboto Medium at 13 px by default (12–16 px in
Settings). Workspaces are sorted
by output and numeric index instead of relying on niri's JSON array order.

Panels slide in with the shared Smooth/Expressive/Jelly curves: sidebars arrive
from the right, centered panels from below, and the tray from the bar's edge.
They retain content while sliding out. Turn off Motion for immediate placement.
Wallpaper transitions are controlled separately by `awww`. See
[Personalization](PERSONALIZATION.md) for element colors, fonts and geometry.

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
| Controls | Local weather, battery charge modes, Wi-Fi/Bluetooth power, microphone mute, DND, stay awake, Night Light, motion presets, speaker/microphone sliders, brightness, power profile, MPRIS, system stats, Screenshot studio (screen/area/window, annotations and OCR), lock, settings, power menu and workspace board |
| Audio | Default output/input selection, each device's volume/mute, application stream volume/mute and advanced audio settings |
| Devices | Bluetooth adapter selection, paired-device connect/disconnect, block/error information, pairing settings, Wi-Fi scanning/password entry and saved profiles |
| Agenda | English calendar, local to-do list, 25-minute focus/5-minute short break/15-minute long break, and stopwatch |
| Notifications | Persistent grouped/searchable history, per-app popup rules, timed DND and clearing notifications |

Stay awake inhibits idle while enabled in this shell session. It does not
disable manual locking or explicit suspend and resets when the shell restarts.
The focus timer and stopwatch continue when the panel is closed but reset on
shell restart. A completed focus/break session produces a local notification;
DND suppresses its popup while retaining it in history. Tasks survive restart
because they are saved in `settings.json`.

The native mixer tracks devices only while its tab is loaded. Radio and
hardware probes remain cached between backend refreshes; the Wi-Fi list uses
NetworkManager's existing scan cache. The shell does not continuously scan for
Bluetooth devices or Wi-Fi networks. Bluetooth pairing and enterprise setup open Fedora's
existing tools.

## Preferences and permissions

The backend delegates operations to the running user's existing tools. Backlight,
Bluetooth, Wi-Fi, and power-profile access therefore follows Fedora's current
device permissions, service state, and polkit policy. The project does not add
passwordless sudo rules, run privileged background code, or install new polkit
rules. Errors are shown in the shell instead of being treated as success.

Non-transient notification history survives shell restart in the private local
notification-history.json file. Restored entries have no live actions or popups.
Timed Do Not Disturb and per-app rules affect shell popups; they do not change
other applications' notification policies.

## Clipboard and Activity

`clipboardEnabled` and `clipboardImages` default to `true`; `clipboardLimit`
defaults to 100 and accepts 20–500. `activityEnabled` defaults to `true`.
The `clipboard` and `activity` bar modules can occupy any zone. Settings exposes
these options; [CLIPBOARD_ACTIVITY.md](CLIPBOARD_ACTIVITY.md) explains storage,
shortcuts and behavior when upgrading an existing layout.

## Appearance, displays and desktop libraries

See [Desktop upgrades](DESKTOP_UPGRADES.md) for appearance profile fields, display
preview/recovery, modular control layout, notification persistence, Wi-Fi
credentials and launcher prefixes. The additional Settings page keys are
`controlLayout` and `display`. `qt6-qtimageformats` is required for image-format
support in the wallpaper library.

## Laptop features and popup blur

Control Center → System provides detailed on-demand monitoring. Settings → Idle and sleep controls AC/battery timeouts and locking; Settings → Keyboard shortcuts reads your niri binds/includes. Appearance → Blur behind popups requests native full-screen blur on niri 26.04+ after merging the provided config fragment. See [LAPTOP_FEATURES.md](LAPTOP_FEATURES.md) for requirements, defaults, parser bounds and setup.
