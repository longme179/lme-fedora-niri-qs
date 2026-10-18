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
  "shellName": "LME Shell",
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

The panel normally starts at 600 px, clamped to the output's available space.
An eight-column canvas requests at least 900 px so its labels remain readable.
Press `Ctrl+Tab` or `Ctrl+Shift+Tab` to cycle tabs. Escape leaves Edit mode first,
then closes the popup. Scroll the Controls and Devices tabs for lower actions.

In Controls, **Edit layout** enables the quick-control canvas. Choose four or
eight columns, then drag controls onto a cell. The complete factory layout fits
4×8 or 8×4; eight rows and restored larger canvases are available with scrolling.
Power and Settings occupy 1×1; Wi-Fi, Overview, capture actions and Power profile
occupy 2×1. Volume, microphone level and brightness each occupy 4×1. Empty drops
move only the selected control; matching-size tiles swap. Other occupied drops
cancel without moving anything. Arrow keys find the next valid cell, and dragging
near a viewport edge scrolls. Dropping outside the canvas cancels.
Edit mode blocks actions, including the detailed cards and Lock button.

Each valid drop saves automatically in `controlGrid`, including preset export and
backup/restore. Changing columns repacks controls; increasing rows preserves their
positions. **Reset grid** resets only quick-control positions. Hidden controls
reserve their cells so enabling them restores their positions. Empty trailing rows
collapse outside Edit mode. **Widgets…** opens Settings for visibility and detailed
card ordering/sizing; weather, charging, media, resources and recording retain their
natural card height below the canvas. Buttons have no order/size controls in
Settings: only visibility affects them. Reordering cards or their preference list
does not change canvas coordinates or recreate loaded cards.

Slider icons mute/unmute speaker or microphone; the Volume gear still opens audio
settings. Values retain the previous 0–100% range (brightness starts at 1%),
bounded update rate and final release update. Power profile cycles through the
service's advertised profiles, skipping Performance if it is absent. The normal
command-error path remains available if a provider cannot advertise its list.
Power opens the existing confirmation menu. To add its optional topbar shortcut,
enable **Power** in Settings → Top bar; existing bar layouts remain unchanged.

Saved layouts migrate automatically. New controls are placed in free cells;
additional rows are appended when necessary, up to 32, without moving saved tiles.
The three sliders inherit the old slider group's visibility; capture actions,
Power and Settings inherit the old capture group's visibility. Detailed card
order, sizes, custom colors and fonts are preserved. Importing older presets
uses the same validation/migration path.

| Tab | Controls |
| --- | --- |
| Controls | Local weather, battery charge modes, Wi-Fi/Bluetooth power, microphone mute, DND, stay awake, Night Light, motion presets, speaker/microphone sliders, brightness, power profile, MPRIS, system stats, Screenshot studio (screen/area/window, annotations and OCR), lock, settings, power menu and workspace board |
| Audio | Default output/input selection, each device's volume/mute, application stream volume/mute and advanced audio settings |
| Devices | Bluetooth adapter selection, nearby-device scan, pairing/PIN/passkey confirmation, connect/disconnect, block/error information, Wi-Fi scanning/password entry and saved profiles |
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
Bluetooth devices or Wi-Fi networks. Bluetooth scans start explicitly from Devices and stop after 60 seconds or when the panel closes. Pairing supports PIN/passkey entry, numeric confirmation and displayed keyboard codes. Closing the panel cancels the shell's pairing and stops its own discovery session. Enterprise Wi-Fi and external Bluetooth tools remain available.

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

## Surface style

Settings → Appearance → Surface style selects `surfaceStyle`: `"smoked"`
(default) or `"liquid"`. The switch is saved in settings and portable presets
and backups. It is independent of Material appearance profiles.

Liquid uses a neutral glass palette for all color roles, including custom bar
island fills/borders and notifications. Dracula, Matugen, palette.json, accent,
element overrides, panel/notification opacity and outline thickness remain
saved but are temporarily bypassed; their editors are paused. Switching back
reads those same saved values again. There is no backup/restore cycle and no
bulk preference rewrite. Fonts, sizes, bar placement, module layouts, per-island
corner geometry, density, features and motion preferences continue to apply.

Liquid surfaces use translucent cool tints rather than opaque gray Material plates.
Active tiles keep a faint status tint and selected tabs retain a translucent
highlight. The optical layer has a clear center and a narrow refractive rim.
Display labels, headings, bar text, button captions and menu text turn white
without an outline in Liquid mode; Smoked restores their original colors.
A neutral dark outer tint keeps white text readable over bright applications;
inner cards remain translucent. This tint applies only in Liquid and does not
change the saved Smoked palette or opacity.
The independent `liquidGlass` preference stores tint (`#RRGGBB` or alpha-first
`#AARRGGBB`), tint opacity, brightness, lens blur, feather, smearing, rim strength
and width. Their defaults/ranges are in `config/liquid-glass.json`; presets and
backups include them. Field edits merge under the shared preferences lock.
Resetting glass preserves all Material preferences and does not change a saved
niri snippet. Brightness dims backgrounds in the existing shader pass; feather
controls rim softness, while smearing scales its refraction. No new texture,
render layer or animation loop is added for these controls.

True background blur belongs to niri. Its protocol exposes a region rather than
per-window blur strength. The separate passes/spread controls write
`$XDG_CONFIG_HOME/lme-shell/liquid-blur.kdl` only when **Save niri blur snippet**
is clicked. Include it after `popup-blur.kdl`, then run `niri validate`; subsequent
saves use niri's normal include reload. This changes compositor-wide blur in
both surface styles. Existing unmarked files and symlinks are not replaced.
Preferences restore the original passes/spread when reset, but the snippet
needs to be saved again to apply them. No niri configuration is edited silently.
Editable fields retain native Qt input rendering, selection and IME behavior,
with a dark translucent fill behind white input text.

The material adds rounded refraction, dispersion and pointer highlights to
shared panel, card and button backgrounds; text and input remain separate.
It composes with the existing popup spring/Jelly-v2 effect. On niri 26.04+,
Liquid automatically requests local blur beneath rounded panels and popups,
including authentication, notifications, OSD and Settings. Regions follow
ancestor transforms, resize and visibility changes without a polling timer;
closing or hiding a surface releases its region. The surrounding desktop stays
sharp. The saved `popupBlur` preference controls full-screen blur in Smoked mode
and remains unchanged in Liquid. Popup dimming and motion remain active; bar
blur keeps its separate switch.
During Jelly-v2 motion, the native blur region follows the shader's bent and
tapered silhouette using inset two-pixel bands. Identical adjoining bands are
merged and native regions are reused during flight. The mask returns to a single
rounded region at rest; no frame timer, desktop capture or extra shader is added.
The clear-interior shader path preserves lighting without unused lens calculations.
Mask geometry is published after Qt's animation step and before scene-graph
synchronization, so interrupted springs share the same frame with their blur.
Glass sampling uses final scene transforms at that point too, instead of
watching every ancestor property on every button. Neither path adds an idle
animation driver.

With native Liquid blur, the main popup surface reserves its destination and
travel envelope rather than the whole output. Its layout still uses output
coordinates, while a separate surface handles the full-screen dim layer and
outside clicks. This reduces niri's intermediate blur texture area without
lowering blur passes, shader resolution, deformation or motion quality. Smoked
keeps the full-screen surface and its saved global blur preference.

Include the updated `config/niri/popup-blur.kdl` **after generic background-effect
rules**: later matching niri rules take precedence. If you copied its rules manually,
merge the `notifications`/`osd` namespaces and Settings window rule as well.
Niri defaults to xray blur if no matching rule explicitly sets `xray false`;
the Wayland blur protocol cannot override that compositor policy.
The Settings rule also disables niri's solid focus-ring backing inside the
transparent window, leaving the frame itself available.
No package is added. Without compositor support, tint and edge highlights remain
available, but they do not blur applications. In-window menus use translucent
plates for separation; compositor blur samples surfaces behind the shell window,
not widgets drawn within that same window.
This is a hybrid effect: a bounded wallpaper image supplies the thin refractive
rim, **not live application refraction**. No desktop screenshots or capture
permissions are used. Wallpaper crossfades and moved floating Settings windows
are not tracked exactly: the rim uses the saved image and assumes floating
windows are centered. Layer-shell panels follow their output and margins.

Each visible GPU window shares one wallpaper texture, decoded at half logical
resolution, capped at 1280 × 720. There are no per-button capture/poll timers;
texture sampling is confined to the rim. Hiding/destroying the last consumer or
switching back releases it and unloads the shaders. Missing images retain the
transparent tint/highlights. Qt's software renderer uses a rounded outline
instead of refraction. No new runtime package is required; the compiled shader
is bundled and can be rebuilt with `bash scripts/build-shaders.sh`.

The renderer is adapted from Serpantinum under AGPL-3.0-or-later; see
[its notice](../third_party/Serpantinum-NOTICE) for the source revision, local
changes and license.

## Appearance, displays and desktop libraries

See [Desktop upgrades](DESKTOP_UPGRADES.md) for appearance profile fields, display
preview/recovery, modular control layout, notification persistence, Wi-Fi
credentials and launcher prefixes. The additional Settings page keys are
`controlLayout` and `display`. `qt6-qtimageformats` is required for image-format
support in the wallpaper library.

## Laptop features and popup blur

Control Center → System provides detailed on-demand monitoring. Settings → Idle and sleep controls AC/battery timeouts and locking; Settings → Keyboard shortcuts reads your niri binds/includes. Appearance → Blur behind popups requests native full-screen blur on niri 26.04+ after merging the provided config fragment. See [LAPTOP_FEATURES.md](LAPTOP_FEATURES.md) for requirements, defaults, parser bounds and setup.

## Module gestures and media

Settings → Top bar → Click and scroll actions stores per-module `barGestures` overrides. Default preserves each left click; audio right click toggles mute and vertical scroll changes volume by 5% per notch. Notifications right click toggles DND, and middle click opens Settings. Workspace scroll selects adjacent workspaces on that output. Choose Do nothing to disable a gesture or Restore default gestures to reset all mappings. Scroll input is accumulated for 60 ms and uses relative volume updates.

Settings → Appearance provides `mediaControls` (seek/shuffle/repeat), `mediaStability` (brief cosmetic metadata retention) and `mediaShapes` (ambient Material polygons). Seek supports click/drag and keyboard arrows/Home/End when the player supports MPRIS seeking. Shuffle/repeat require writable player support; unavailable controls are disabled. Repeat cycles Off → All → One → Off. Shapes stop while hidden, paused or animations are disabled; the same settings apply to Activity Island and Control Center.

Settings → Desktop widgets → Floating wallpaper shapes controls `desktopShapes`
(default `false`, included in portable presets). This reuses the media card's
ambient shapes at a larger size on each connected display, above the wallpaper
and below application windows, with an empty input region and no reserved space.
It is independent of `desktopEnabled`, `mediaShapes` and media playback: enabled
shapes always drift, including when no player is connected. Turning the option
off destroys the surfaces completely. Disabling global animations keeps the
shapes visible and still. The same page saves these portable visual settings:

| Preference | Default | Range / choices |
| --- | --- | --- |
| `desktopShapeCount` | `4` | 1–12 shapes |
| `desktopShapeScale` | `1` | 0.5–2× the size fitted to each output |
| `desktopShapeOpacity` | `0.14` | 0.02–0.6 (2–60%) |
| `desktopShapeSpeed` | `1` | 0.1–3× translation and rotation speed |
| `desktopShapeStyle` | `mixed` | `mixed`, `flower`, `circle`, `square` |
| `desktopShapeRotation` | `true` | Spin while drifting; off preserves the current angle |

Colors follow the current theme. Shape count and size are bounded; no extra
packages, audio capture or wallpaper changes are required. These are decorative
shapes, not audio-reactive Cava bars.

Settings → Behavior → Bluetooth pairing controls `bluetoothPairing`. Native pairing needs Fedora's `python3-gobject-base`. The Gio agent runs only while Devices is open, retains no entered PIN/passkey on disk, and leaves other applications' default agents alone. A successful Pair is followed by Connect; if connecting fails the device remains paired and the error is shown.

## Synchronized lyrics

Open Lyrics in Activity Island, Control Center or a desktop media card. Settings → Behavior → Lyrics saves these choices:

- **Display mode** (`lyricsMode`): `scroll` shows the full transcript; `line` shows the current synchronized line. The default is `scroll`. Plain lyrics still show the whole text, and players without timing retain the full transcript.
- **Follow lyrics by default** (`lyricsFollow`, default `true`): center the active line when opening a transcript or changing tracks. Manual scrolling pauses follow for that view; **Follow** resumes it. Single-line mode always uses playback timing.
- **Lyrics on Activity Island** (`activityLyrics`, default `true`): replace the compact media title with the current line while playing. Before the first cue, during empty instrumental cues, with plain/missing lyrics or without timing, use the track title. Recording and timers keep their existing priority; the popup heading remains Activity Island.

Player-provided lyrics and a `.lrc` sidecar beside a local media file are checked first. LRCLIB lookup is off by default. When enabled, track title, artist, album and duration are sent when a visible, expanded lyrics view or the playing Island needs lyrics. Positive results are cached for 14 days, missing results for six hours, with at most 128 entries under `$XDG_CACHE_HOME/lme-shell/lyrics` (normally `~/.cache/lme-shell/lyrics`). Lookup has a seven-second timeout and response/line limits. Browser metadata may describe a video/channel rather than a song, so matches are not guaranteed.

Click a transcript line to seek when supported. Views of the Island's player share its lookup and playback state. Cue-boundary timers advance lines and a four-second local-clock refresh corrects timing; there is no 250 ms lyric polling. Closing the last view stops its helper and timers unless the playing Island still needs them. Paused players with no open view are idle. Mode, follow and Island preferences are included in presets and backups.

## Desktop widget canvas

Settings → Desktop widgets enables the canvas and adds clock, notes or media widgets (up to 12). Choose a display and whether a widget is interactive. Primary display follows the first connected output; a named output retains its configuration while disconnected. Positions are normalized to the available output size; size and position are clamped after scaling/resolution changes. Notes use the existing Quick notes buffer rather than creating another file. Media reuses MPRIS, playback controls and optional lyrics.

Edit on desktop raises the widgets above applications and opens a small toolbar. Drag a widget's header grip or resize its lower-right corner. Focus the grip and use arrows (Shift for 1-pixel steps) for keyboard movement. Done returns widgets below application windows. Non-interactive widgets pass clicks through; Edit restores access. Add the Desktop widgets module in Settings → Top bar or run `quickshell -c gpt ipc call shell desktopEdit` to toggle Edit. The desktop does not reserve application space.

The `desktopEnabled` and `desktopWidgets` preferences are included in export/import. Widget patches merge individual fields under the settings file lock, so a drag cannot overwrite a concurrent visibility/output edit. Moving a widget does not rewrite its saved dimensions when the output clips it. Resizing keeps the top-left corner fixed where space permits; unrelated setting updates do not clear an active gesture. Removing a notes widget leaves its note intact. The niri blur include now also matches `lme-desktop`; update that include if your installation is a copy.

## Popup motion

Popups slide in from the screen edge and close through the same edge. Activity Island uses the bar edge. Spring motion preserves velocity when opening is interrupted by closing or reversed; changing the size of an open Island keeps its existing spring. Settings → Appearance offers Smooth, Expressive, Jelly and Jelly-v2 presets, speed and bounce. Reduced motion skips the travel.

The former connected-surface animation and its switch have been removed. Existing settings, appearance profiles and imported presets/backups ignore `connectedPopups` while retaining the other customizations; no reset is needed.

## Activity Island size

Settings → Appearance → Activity Island size controls `activityCompactMaxWidth` (120–1200 px, default 300), `activityPopupMaxWidth` (400–1600 px, default 460) and `activityPopupMaxHeight` (320–2160 px, or 0 for automatic screen fitting). The bar's available module space still caps the pill. Popup limits remain bounded by the viewport and edge margin during spring resizing; overflow stays scrollable. These limits are saved in appearance profiles and portable presets/backups.

## Jelly-v2 popup motion

Choose Settings → Appearance → Motion preset → **Jelly-v2**, with **Spring motion** enabled. The existing preset stays the default. Speed and Bounce apply to this preset too; disabling Animations removes both travel and deformation.

Jelly-v2 retains the popup's edge-slide spring and drives a separate damped shape spring from signed travel velocity, normalized by popup size and motion speed. A 16×16 Qt Quick vertex mesh stretches along travel, compresses across it, tapers the trailing side and bows its edges. Targets can change without resetting either spring's velocity. Strain is bounded to ±0.42, keeping the mapping positive and preventing folded geometry.

The Qt software renderer uses area-preserving scale feedback. OSD/toast surfaces normalize the effect into their existing native bounds so their edges stay visible. Off-screen closure does not wait for the shape spring's settling tail. The effect layer is enabled only while deforming, then removed; text returns to its normal render path at rest. The compiled vertex/fragment shaders ship in the repo; rebuilding them is optional with `bash scripts/build-shaders.sh` and Qt's `qsb` tool. No new runtime package is required.

Design/implementation references inspected: [Apple WWDC23 · Animate with springs](https://developer.apple.com/videos/play/wwdc2023/10158/) (continuous position/velocity under interruptions), [Qt ShaderEffect](https://doc.qt.io/qt-6/qml-qtquick-shadereffect.html), [Qt Item layers](https://doc.qt.io/qt-6/qml-qtquick-item.html#item-layers) (transient texture cost) and [GridMesh](https://doc.qt.io/qt-6/qml-qtquick-gridmesh.html). The shape model and shaders are original LME code.

## GitHub updates

Open **Settings → About → Shell updates**. **Check for updates** fetches
`origin/main`; **Update shell** fetches again and applies a fast-forward only.
The checkout must be on `main` with no tracked/untracked changes. Local commits,
divergence, a missing remote or a ZIP/source installation produce an actionable
message. Commit or stash edits yourself before retrying. No reset, automatic
stash/rebase, branch switch, merge hook or package transaction is run.

The updater uses the configured `origin` (including your own fork), without
modifying its URL. It runs as your user, with noninteractive Git authentication
and bounded command timeouts. Its detached worker and lock survive QML reloads;
closing Settings does not interrupt an update. Atomic status files under
`$XDG_STATE_HOME/lme-shell/update-*.json` are scoped to the canonical checkout.
Only an active operation polls local status; idle checks do not contact GitHub.
A stopped worker is detected and can be retried.

After updating, close Settings and restart the existing shell instance to load
all backend/shader changes. Use the commands in [Updates](../README.md#updates),
adjusting the config name if you use `gpt`. New package requirements still need
`setup.sh`; GUI updates never run sudo/DNF. Demo/preview mode disables updates.
