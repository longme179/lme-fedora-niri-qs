<h1 align="center">LME Shell</h1>

<p align="center"><strong>Material 3 Expressive meets smoked glass.<br>A personal desktop shell for Fedora and niri.</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/Fedora-44-51a2da?style=flat-square" alt="Fedora 44">
  <img src="https://img.shields.io/badge/niri-26.04%2B-80ffea?style=flat-square" alt="niri 26.04 or newer for all integrations">
  <img src="https://img.shields.io/badge/Quickshell-0.3.2%2B-ff80bf?style=flat-square" alt="Quickshell 0.3.2 or newer">
</p>

<p align="center">
  <a href="#preview">Preview</a> · <a href="#installation">Install</a> · <a href="#features">Features</a> · <a href="#make-it-yours">Personalize</a> · <a href="#documentation">Documentation</a> · <a href="CHANGELOG.md">Changelog</a>
</p>

LME is a desktop shell built with **Quickshell and QML/Qt Quick**. It includes a
modular bar, an expandable Activity island and a standalone Settings app, with
translucent panels, spring animations, Dracula-inspired colors and Roboto fonts.
The interface and documentation are in English.

First run uses one connected top bar, a centered Activity island and a Control
Center on the right. Choose your own modules, colors, fonts, spacing and motion
without editing QML.

## Preview

![Control Center in edit mode, with draggable tiles and sliders over a blurred desktop](https://github.com/user-attachments/assets/429d8285-dc0d-4803-bb44-198c4b884b35)

https://github.com/user-attachments/assets/3efede13-30c6-45e3-b623-f73e7e535920

<details>
<summary><strong>More screenshots</strong></summary>

**Activity island**

![Compact Activity island showing media playback](https://github.com/user-attachments/assets/5b235203-1ff5-4a7f-9dd3-46c53d1b21ca)

<table>
  <tr>
    <th width="55%">Control Center</th>
    <th width="45%">Wi-Fi</th>
  </tr>
  <tr>
    <td valign="top"><img src="https://github.com/user-attachments/assets/0266766e-0ec2-44f1-a6ab-4e21be98d63f" alt="Control Center with weather, charging, media, system statistics and recording controls" width="480"></td>
    <td valign="top"><img src="https://github.com/user-attachments/assets/49043d58-ed26-49ce-b79a-d4ae3bd276fe" alt="Wi-Fi panel showing the connected network and saved networks" width="380"></td>
  </tr>
</table>

</details>

## Features

| Feature | Details |
| --- | --- |
| **Modular bar** | Enable, reorder and move modules; choose a connected bar or separate islands, top/bottom placement and distance from the screen edge. Assign left/right/middle click and scroll actions per module. Includes workspace switching and a tray dropdown. |
| **Activity island** | Seek, play/pause, shuffle/repeat where supported, focus/break timer, stopwatch and recording controls. Audio visualization uses Cava; media cards share the same controls. |
| **Control Center** | Drag toggles, actions and sliders on a scrolling canvas. Power/Settings use 1×1 cells; power profiles cycle in 2×1; volume, microphone and brightness each use 4×1. Hide buttons independently and arrange detailed cards. |
| **Launcher** | Fuzzy app search, calculator, emoji, open windows and file/folder search. |
| **Lyrics** | Follow synchronized lyrics in media panels. Read embedded/local LRC and cached results, with optional online lookup through LRCLIB. |
| **Desktop canvas** | Place clock, notes and media widgets per display. Drag and resize in Edit mode, then keep them below apps or make them click-through. |
| **Everyday tools** | Clipboard text/images with search, pins and image annotation; grouped, persistent notifications with [appearance controls](docs/NOTIFICATIONS.md) and a rotating Material emblem; timed DND; calendar, tasks and autosaved notes. |
| **Laptop controls** | Weather with automatic or manual location, supported Lenovo charging modes, AC/battery idle profiles, system monitoring and display settings with automatic revert. |
| **Screen capture and Night Light** | Record a screen or selected region; annotate/redact screenshots with built-in tools or Satty/Swappy; extract text with local OCR; schedule Night Light. |
| **Top bar styling** | Style the connected bar or each island separately. Adjust corners, borders, colors and transparency, with live updates from Settings. Popups can expand from the clicked module with a soft connecting surface. |
| **Themes and fonts** | Per-element colors and fonts, searchable font menus, HSV/alpha color picker, appearance profiles, 35 Gowall palette presets plus LME Dracula, and Material wallpaper palettes with scheme, light/dark and contrast controls. |

## Installation

### Requirements

The supported target is **Fedora 44 with an existing niri Wayland session**.
Use **niri 26.04+** for recording and native popup blur; basic shell integration
supports niri 25.11+. LME supplies the desktop interface; niri manages windows.

| Requirement | Purpose |
| --- | --- |
| Quickshell **0.3.2+** | Runs the shell; its build needs PipeWire, Polkit and Wayland/BackgroundEffect support |
| Matching Qt 6 runtime | Qt Quick, Wayland, SVG and image support |
| Python 3 | Desktop integration using the standard library |
| Roboto and Noto fonts | UI typography, fallback characters and emoji |
| Fedora desktop services | NetworkManager, BlueZ, PipeWire/WirePlumber and an existing power-profile provider |

[requirements-fedora.txt](requirements-fedora.txt) groups packages by purpose.
It is a **DNF package list** for the installation helper. Install niri before
running the helper; GPU drivers are managed separately.

### 1. Keep a permanent checkout

Install Git with `sudo dnf install git` if needed, then run:

```bash
mkdir -p ~/src
git clone https://github.com/longme179/lme-fedora-niri-qs.git ~/src/lme-fedora-niri-qs
cd ~/src/lme-fedora-niri-qs
```

This checkout tracks `main`. You can also use GitHub’s **Code → Download ZIP**
and extract it into a permanent directory. Run the following commands from
that source directory, and keep it after installation: the installed shell
links to it.

### 2. Review and install packages

Run these as your normal desktop user, inside Fedora:

```bash
# Preview the proposed DNF command; no packages are installed.
./scripts/install-fedora.sh --optional

# Install required and recommended packages; DNF asks before its transaction.
./scripts/install-fedora.sh --install --optional
```

`--optional` includes tools for locking, idle profiles, OCR, Night Light,
recording, audio spectrum and external annotation, plus recommended applications.
Keep your working TuneD/tuned-ppd or power-profiles-daemon provider.

<details>
<summary><strong>Quickshell is missing from my enabled repositories</strong></summary>

Review the [errornointernet/quickshell COPR](https://copr.fedorainfracloud.org/coprs/errornointernet/quickshell/)
and its Fedora 44 build. This flag allows the installer to enable that source
only when Quickshell is unavailable:

```bash
./scripts/install-fedora.sh --install --optional --copr
```

See the [repository availability guide](docs/INSTALL.md#quickshell-repository-availability)
for more details.

</details>

### 3. Link the shell, add Settings and try it

```bash
./scripts/install.sh
./scripts/install-settings.sh
./scripts/doctor.sh
./scripts/start.sh
```

| Command | What it does |
| --- | --- |
| `install.sh` | Links `~/.config/quickshell/lme-shell` to this source directory |
| `install-settings.sh` | Adds **LME Shell Settings** to the application launcher |
| `doctor.sh` | Reports missing tools and session integration without changing system state |
| `start.sh` | Restores saved wallpaper/confirmed display settings and starts Quickshell |

The two install scripts support `--dry-run`. If an existing target needs
replacement, `--replace` preserves it in a backup. Your niri configuration and
saved preferences stay separate. Keep the terminal open while testing; Ctrl+C
stops this shell instance.

To explore a windowed demo with sample data and no saved changes or desktop
actions, use `./scripts/start.sh --preview`.

### 4. Integrate with niri

Review [the integration fragment](config/niri/lme-shell.kdl), then add this to
`~/.config/niri/config.kdl` for the default installation:

```kdl
include "~/.config/quickshell/lme-shell/config/niri/lme-shell.kdl"
```

It starts LME at login, supplies its shortcuts and opens Settings/Screenshot
studio as floating windows. Remove or rebind conflicting keys before including
it, especially `Mod+Comma` and `Mod+Shift+E` from niri's sample config. Keep one
shell startup entry and one notification server/Polkit agent in your session.
LME includes its own notification server and password popup.

For **live blur behind the bar and popups** on niri 26.04+, also add:

```kdl
include "~/.config/quickshell/lme-shell/config/niri/popup-blur.kdl"
```

**Settings → Appearance** has separate **Blur behind the bar** and
**Blur behind popups** switches, both enabled by default. Then validate:

```bash
niri validate
```

Merge any existing `blur` block instead of defining it twice. The supplied rule
uses `xray false`, keeping live applications beneath the blur. The dim layer
animates; native blur intensity is region-based and does not interpolate.
[More about capture, blur and motion](docs/CAPTURE_NIGHT_MOTION.md).

## Make it yours

Open Settings from either gear button, the application launcher, **Super+Comma**,
or `./scripts/settings.sh`. It runs in its own window and shares saved preferences
with the shell, even when the shell is stopped.

Choose **Appearance → Shell name** to give your desktop a name of your own.

![LME Settings showing popup blur, spring motion, shape morphing and animation presets](https://github.com/user-attachments/assets/5a87fa0e-b7d2-47a4-968b-f78510552d0a)

| Page | Customize |
| --- | --- |
| **Appearance** | Shell display name, accent, smoked glass opacity, density, profiles, spring/morph motion, Smooth/Expressive/Jelly presets, connected popup surfaces and bar/popup blur |
| **Elements and fonts** | Individual color roles, hex input, HSV/alpha picker, installed fonts and text size |
| **Top bar / Control center** | Module/card order, visibility, sizes, bar position/margins and panel width |
| **Displays / Idle and sleep** | Resolution, refresh, scale and output placement; AC/battery timeouts, locking and suspend |
| **Wallpaper / Weather** | Image library, palette preview, automatic/manual location and units |
| **Desktop widgets** | Add clock/notes/media, choose an output, enable click-through and arrange widgets in Edit mode |
| **Behavior** | Lyrics and online lookup, Bluetooth pairing, privacy, OSD layout, notes, file search, recording, external editor and settings transfer |
| **Keyboard shortcuts / Clipboard** | Search niri bindings; configure history and image capture |

Jump to a page with `./scripts/settings.sh --page topbar`. Use
`./scripts/settings.sh --demo` for a Settings preview without saving changes.

Preferences live in `~/.config/lme-shell/settings.json`, separate from the
Quickshell source. Updates preserve them; saved choices override factory defaults.
If you set `XDG_CONFIG_HOME`, use that directory instead of `~/.config`.
Automatic idle management and Night Light start disabled.

**Share a preset:** use **Behavior → Settings export and restore → Export preset**.
Use the exported JSON to share your setup; it excludes personal paths, location,
device IDs and tasks. Import validates fields and backs up
current settings. Private backups include personal settings and should stay
private. Clipboard/notification history and notes are separate from settings
backups. [Configuration guide](docs/CONFIGURATION.md).

### Desktop widgets

The canvas starts disabled. To set it up:

1. Open **Settings → Desktop widgets**, enable it, then choose **Add clock**, **Add notes** or **Add media**.
2. Choose a display for each widget. Turn **Interactive** off to let clicks pass through; **Visible** hides a widget without removing its saved layout.
3. Click **Edit on desktop**. Drag the header grip to move a widget, resize its lower-right corner, then press **Done**. Focus the grip and use arrow keys to move it; Shift makes one-pixel adjustments.

Outside Edit, widgets sit below application windows, so an app can cover them.
You can add a **Desktop widgets** module in **Settings → Top bar** to toggle Edit.
The canvas supports up to 12 widgets. Notes widgets share the existing Quick notes
buffer; removing a widget leaves the note intact.

**Primary display** follows the first connected output. A widget assigned to a
named output stays saved while that output is absent. If a widget is missing,
check its Visible switch and display selection, or choose Primary display.
Moving a widget on a smaller output preserves its saved size. Layouts are
included in settings export/import; note contents are stored separately.

### Media and lyrics

Activity Island, Control Center and desktop media widgets use MPRIS. Click or
drag the timeline to seek. Shuffle/repeat stay disabled when the player does not
support them; this is common in browsers.

Click **Lyrics** in a media card. Embedded lyrics, a local `.lrc` sidecar and the
cache work without online lookup. To search LRCLIB, enable online lookup under
**Settings → Behavior → Lyrics**. This is off by default and sends track metadata
only while lyrics are open. Matches depend on the supplied title/artist; a
YouTube channel or video title may not identify a song. [Lyrics and media guide](docs/CONFIGURATION.md#synchronized-lyrics).

## Optional integrations

| Feature | What to install or configure |
| --- | --- |
| **Wallpaper** | Install `awww` **and** `awww-daemon` from a trusted available source; the package helper does not install them. [Setup](docs/INSTALL.md#wallpaper-and-charging) · [Upstream](https://codeberg.org/LGFae/awww) |
| **Material palette / Audio spectrum** | `matugen` / `cava`. Cava runs for visible, playing media cards, with 60 fps and reduced smoothing. |
| **External display mirroring** | `wl-mirror` (Fedora: `sudo dnf install wl-mirror`). Connect and enable both outputs, then use Settings → Displays or Control Center → Devices. Choose Source/Destination and Start mirror; Stop closes only LME’s mirror window. [Setup and hardware checks](docs/MIRRORING.md). |
| **Recording** | `wf-recorder`, compatible FFmpeg/`ffprobe`; `pulseaudio-utils` for audio and `slurp` for regions. Auto tries NVIDIA NVENC → integrated VAAPI → CPU, probing only when capture starts. Chosen codecs depend on your driver/build. |
| **External annotation / OCR** | Fedora `swappy`, or separately installed Satty; `tesseract` and language packs for local OCR. Click clipboard images or screenshot notifications to open a saved copy in your chosen editor. Screenshot studio exports flattened PNGs including redactions. |
| **Night Light / Idle** | `wlsunset` with working gamma control; `swayidle` and `swaylock` for idle profiles. Enable these in Settings. |
| **Lyrics** | No extra package. Optional LRCLIB lookup needs internet access; player metadata/local LRC and cached lyrics work offline. |
| **Weather** | Internet access for Open-Meteo and approximate IP location; no API key needed. Manual location is available. |
| **Lenovo charging** | Install the helper with `sudo ./scripts/install-charge-helper.sh --install`. Adjustable thresholds depend on firmware; some machines expose only a fixed conservation mode. [Charging guide](docs/CHARGING.md) |

The optional package set includes most tools above. `ffmpeg-free` may omit NVENC
or other chosen codecs; a working GPU driver and compatible encoder build are
required. LME does not install or replace GPU drivers. Recording format, codec,
FPS, bitrate and fallback details are in [the feature guide](docs/FEATURE_PORTS.md).

## Shortcuts

Active after including the niri fragment. `Mod` normally means **Super/Windows**.

| Shortcut | Action |
| --- | --- |
| `Mod+Space` | Application launcher |
| `Mod+A` | Control Center |
| `Mod+Comma` | Settings |
| `Mod+Tab` / `Mod+Shift+Tab` | niri live overview / themed workspace board |
| `Mod+N` / `Mod+V` | Notification history / clipboard history |
| `Mod+Shift+A` | Activity island |
| `Mod+Shift+E` | Power menu |
| `Escape` | Close an open shell panel |

The bar's Overview button opens niri's live overview; right-click opens the
workspace board. The Settings keybind viewer reads your niri config and includes.

## Updates

For a Git checkout tracking `main`, run from the permanent source directory:

```bash
git pull --ff-only
quickshell -c lme-shell kill
./scripts/start.sh
```

Restart Settings as well. If an update adds dependencies, rerun the package
helper to review and install them. For a release ZIP installation,
extract the new version to a permanent directory and rerun both install scripts
with `--replace` to update their targets while keeping backups.

<details>
<summary><strong>I use a configuration named gpt</strong></summary>

Keep the checkout outside `~/.config/quickshell/gpt`, then link it and start with
that configuration name:

```bash
./scripts/install.sh --replace --target "${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/gpt"
./scripts/install-settings.sh --replace
./scripts/start.sh --config gpt
```

Replace `lme-shell` with `gpt` in niri includes, startup and IPC bindings. The
supplied fragment targets `lme-shell` by default, so adapt it before inclusion.
To restart this instance, use `quickshell -c gpt kill` and
`./scripts/start.sh --config gpt`. Preferences still use `lme-shell/settings.json`.

</details>

## Documentation

| Guide | Covers |
| --- | --- |
| [Installation](docs/INSTALL.md) | Fedora packages, sources, niri setup, custom paths and services |
| [Configuration](docs/CONFIGURATION.md) / [Personalization](docs/PERSONALIZATION.md) | Preferences, profiles, colors, typography, geometry and expressive feedback |
| [Selected feature ports](docs/FEATURE_PORTS.md) | Detailed controls, dependencies, tests and hardware limits |
| [Capture, Night Light and motion](docs/CAPTURE_NIGHT_MOTION.md) | Screenshot drawing/redaction/OCR, external annotation, schedules and animations |
| [Laptop features](docs/LAPTOP_FEATURES.md) | System monitor, idle profiles, keybindings and native blur |
| [Clipboard and Activity](docs/CLIPBOARD_ACTIVITY.md) | History, pins, timers, media and recording status |
| [Charging](docs/CHARGING.md) / [Authentication](docs/AUTHENTICATION.md) | Firmware support, helper setup and password prompts |
| [Troubleshooting](docs/TROUBLESHOOTING.md) / [Validation](docs/VALIDATION.md) | Diagnosis, development checks and what has been tested |

## Help and development

Run `./scripts/doctor.sh` first. For Settings startup errors, run
`./scripts/settings.sh --page appearance` in a terminal and confirm you updated
the installed configuration. For wallpaper-only blur, check the blur include and
`xray false`. For pointer movement, remove an enabled `warp-mouse-to-focus` rule
if unwanted; niri owns that policy.

[Report a problem](https://github.com/longme179/lme-fedora-niri-qs/issues) with
reproduction steps, logs, doctor output, `niri --version` and `qs --version`.
Pair new Bluetooth devices from Control Center → Devices, including PIN and passkey confirmation. Install `python3-gobject-base` for the pairing agent. Blueman and the network editor remain available for external device settings and enterprise Wi-Fi.

Run `./scripts/check.sh` for backend regressions, script syntax and demo state.
Native UI checks require a private Wayland session. See [validation details](docs/VALIDATION.md)
for test coverage and hardware-specific limitations.

## Credits and license

Inspired by [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland),
[iNiR](https://github.com/snowarch/iNiR),
[DankMaterialShell](https://github.com/AvengeMedia/DankMaterialShell),
[Caelestia](https://github.com/caelestia-dots/shell) and
[Noctalia](https://github.com/noctalia-dev/noctalia).

**Based on iNiR by snowarch (https://github.com/snowarch/inir)**. Upstream morph
geometry and recording workflow adaptations are modified for LME; copyright,
licenses and the iNiR notice are retained.

LME's original code is **GPL-3.0-or-later**, with retained GPL-3.0-only terms in
adapted upstream components. See [LICENSE](LICENSE), [THIRD_PARTY.md](THIRD_PARTY.md)
and `third_party/` for attribution and licensing. Purchased Dracula Pro assets
and fonts are not bundled. Demo wallpaper and artwork belong to their respective
creators.
