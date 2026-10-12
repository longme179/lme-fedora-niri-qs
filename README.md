# LME Shell

A desktop shell for **Fedora + niri**, built with **Quickshell and QML/Qt Quick**.
LME combines Material 3 Expressive controls, translucent glass, a Dracula-inspired
palette and Roboto typography. Its bar, panels, colors, fonts and motion are
customizable through a separate Settings app.

The default layout has one rounded top bar, an Activity island in the center and
a Control Center on the right. The interface and documentation are in English.

[Get started](#get-started) · [Personalize](#personalize) ·
[Shortcuts](#shortcuts) · [Update](#update) · [Help](#help)

## What you get

| Area | Features |
| --- | --- |
| Desktop | Modular bar, ordered workspaces, niri overview, workspace board with window drag/drop, tray dropdown |
| Launcher | Fuzzy app search, favorites, calculator, emoji and open-window search |
| Control Center | Rearrangeable cards, Wi-Fi connections, Bluetooth devices, audio mixer, brightness and power profiles |
| Everyday tools | Clipboard history with images and pins, grouped notifications, timed Do Not Disturb, calendar, tasks and media controls |
| Activity island | Expandable media controls, focus timer, stopwatch and supported recording status |
| Laptop | Weather, charge controls, AC/battery idle profiles, CPU/RAM/network monitoring and display previews with automatic revert |
| Capture and comfort | Screenshot annotations, redaction, local OCR, Night Light and optional blur behind popups |
| Appearance | Hex color editing, per-element colors and fonts, saved profiles, bar placement, Smooth/Expressive/Jelly motion presets |

For detailed behavior and feature requirements, use the [guides](#guides).

## Before you install

The supported target is **Fedora 44 with an existing niri Wayland session**.
The package helper assumes niri is already installed.

| Requirement | Why it is needed |
| --- | --- |
| niri **25.11+** | Workspaces, live overview, window movement and screen capture |
| niri **26.04+** for popup blur | Blurs the desktop and applications behind an open shell panel |
| Quickshell **0.3.2+** | Runs the QML interface; its build needs PipeWire, Polkit and Wayland/BackgroundEffect support |
| Matching Qt 6 runtime | Qt Quick, Wayland, SVG and image support |
| Python 3 | Desktop integration; only the standard library is used |
| Roboto and Noto fonts | UI text, fallback characters and emoji |

[requirements-fedora.txt](requirements-fedora.txt) lists the Fedora packages by
purpose. It is a **DNF package list**, not a pip requirements file.

Run the commands below as your normal desktop user. The package installer asks
for administrator access when needed.

## Get started

### 1. Download the repository

Keep the repository in a permanent directory: the installed shell will link to it.
Install Git with `sudo dnf install git` if the `git` command is unavailable.

```bash
mkdir -p ~/src
git clone https://github.com/longme179/lme-fedora-niri-qs.git ~/src/lme-fedora-niri-qs
cd ~/src/lme-fedora-niri-qs
```

Run the remaining `./scripts/…` commands from this repository directory.

### 2. Install the packages

First, print the proposed package command. This changes nothing:

```bash
./scripts/install-fedora.sh --optional
```

Then install the packages on Fedora:

```bash
./scripts/install-fedora.sh --install --optional
```

`--install` runs DNF and leaves its transaction confirmation enabled.
`--optional` adds recommended tools for locking, idle management, Night Light,
OCR and advanced desktop settings, plus applications such as Kitty and Firefox.
The installer preserves your current power-profile provider.

<details>
<summary>Quickshell is unavailable from my enabled repositories</summary>

Review the [errornointernet/quickshell COPR](https://copr.fedorainfracloud.org/coprs/errornointernet/quickshell/)
and check that it offers a Fedora 44 build. To allow this additional package source:

```bash
./scripts/install-fedora.sh --install --optional --copr
```

The script enables that COPR only when Quickshell is unavailable and you supply
`--copr`. See the [installation guide](docs/INSTALL.md#quickshell-repository-availability)
for the repository checks.

</details>

### 3. Install the shell and Settings launcher

```bash
./scripts/install.sh
./scripts/install-settings.sh
```

- `install.sh` links `~/.config/quickshell/lme-shell` to this checkout.
- `install-settings.sh` adds **LME Shell Settings** to your application launcher.

Both commands support `--dry-run` to show their planned changes. If a different
config or launcher entry already exists, they stop. Use the corresponding
command with `--replace` to preserve the old entry in a backup before replacing it.
Your niri config and saved shell preferences are kept intact.

### 4. Try it in your niri session

Check the available tools and session connections, then start the shell:

```bash
./scripts/doctor.sh
./scripts/start.sh
```

`doctor.sh` reports integration problems without changing system state.
`start.sh` restores a previously selected wallpaper and confirmed display settings,
then starts Quickshell. Keep this terminal open while testing; **Ctrl+C** stops
this shell instance.

To inspect the interface with sample data instead:

```bash
./scripts/start.sh --preview
```

Preview opens an ordinary window inside Wayland. It does not save preferences or
apply desktop actions.

### 5. Start automatically with niri

Review [config/niri/lme-shell.kdl](config/niri/lme-shell.kdl), then add this include
to `~/.config/niri/config.kdl` for the default installation:

```kdl
include "~/.config/quickshell/lme-shell/config/niri/lme-shell.kdl"
```

The fragment starts the shell at login, supplies the shortcuts below and opens
Settings and Screenshot studio as floating windows. Remove or rebind existing
shortcuts with the same keys before adding it, especially `Mod+Comma` and
`Mod+Shift+E` from niri's sample config.

Check the result before your next login:

```bash
niri validate
```

Keep one shell startup entry. If you are replacing another bar, notification
daemon or Polkit agent, remove its previous autostart entry to avoid conflicting
screen reservations or service ownership. The shell includes its own notification
server and password popup.

Custom config names and XDG paths are covered in the [installation guide](docs/INSTALL.md).

## Enable optional features

### Blur behind popups

On **niri 26.04+**, add this second include to your niri config:

```kdl
include "~/.config/quickshell/lme-shell/config/niri/popup-blur.kdl"
```

Enable **Settings → Appearance → Blur behind popups**, then run `niri validate`.
The fragment uses `xray false`, so both application windows and the desktop blur
while the popup stays sharp. If your config already has a `blur` block, merge the
settings instead of adding a second block. Older niri versions can still run the
shell with its translucent and dimmed backdrop.

### Wallpaper

Install both **`awww` and `awww-daemon`**, then open **Settings → Wallpaper** to
choose a folder and image. These tools are not installed by the package helper;
availability depends on your enabled repositories. See
[wallpaper installation](docs/INSTALL.md#wallpaper-and-charging) and
[awww upstream](https://codeberg.org/LGFae/awww).

### Laptop charging

For supported Lenovo charging controls, install the helper once from this checkout:

```bash
sudo ./scripts/install-charge-helper.sh --install
```

This installs the charge helper and its Polkit policy. Later changes from Control
Center use the shell's authentication popup when authorization is required.
Some firmware exposes only a fixed conservation mode; an exact **85%** limit is
available only when the hardware supports adjustable thresholds. See
[charging setup](docs/CHARGING.md).

### Other feature requirements

| Feature | Tools or service |
| --- | --- |
| Clipboard history and image copy | `wl-clipboard` — included in the required package set |
| Idle management and session lock | `swayidle`, `swaylock` — included with `--optional`; enable profiles in Settings |
| Night Light | `wlsunset` — included with `--optional`; requires compositor gamma-control support |
| Screenshot OCR | `tesseract` and language packs — English/Vietnamese included with `--optional` |
| Weather | Internet access for Open-Meteo and approximate IP location; no API key needed |

## Personalize

Click the gear on the bar or in Control Center, open **LME Shell Settings** from
the app launcher, or run:

```bash
./scripts/settings.sh
```

Settings runs in its own window, even when the shell is stopped. Changes save
automatically and synchronize with the running shell.

| Settings page | What you can change |
| --- | --- |
| Appearance | Accent, opacity, density, appearance profiles, motion and popup blur |
| Elements and fonts | Hex colors for individual UI roles, font families and body text size |
| Top bar | Modules, order, connected/island shape, text size, top/bottom placement, height and screen margins |
| Control center | Card visibility, order, full/half sizes and panel width |
| Displays | Resolution, refresh rate, scale and output positions, with a confirmation timer |
| Wallpaper and Weather | Wallpaper folder/favorites, automatic or manual weather location, °C/°F |
| Idle and sleep | Separate timeouts for AC and battery, locking and suspend |
| Keyboard shortcuts | Search the bindings from your niri config and its includes |

To jump directly to the bar settings, use `./scripts/settings.sh --page topbar`.
For a separate Settings demo that does not save changes, use
`./scripts/settings.sh --demo`.

### Defaults and saved settings

First run uses the repository's defaults: a connected top bar, Dracula-inspired
colors, Roboto text, expressive motion and automatic weather location. Automatic
idle management and Night Light are initially disabled.

Saved preferences live in `~/.config/lme-shell/settings.json`; optional base
palette overrides live in `~/.config/lme-shell/palette.json`. These are separate
from the Quickshell config directory and are preserved when you update the repo.
Existing saved values take precedence over the repository's defaults.
If you set `XDG_CONFIG_HOME`, replace `~/.config` with that directory.

To share a preferred factory preset with the maintainer, provide a copy of
`settings.json`, plus `palette.json` if you use it. Appearance and layout values
can become defaults for new users; personal tasks, locations, device IDs and
machine-specific paths should stay out of a distributed preset. See
[configuration details](docs/CONFIGURATION.md).

## Shortcuts

These bindings are active after including the niri fragment. `Mod` normally means
the **Super/Windows** key.

| Shortcut | Action |
| --- | --- |
| `Mod+Space` | Application launcher |
| `Mod+A` | Control Center |
| `Mod+Comma` | Settings |
| `Mod+Tab` | niri live overview |
| `Mod+Shift+Tab` | Shell workspace board |
| `Mod+N` | Notification history |
| `Mod+V` | Clipboard history |
| `Mod+Shift+A` | Activity island |
| `Mod+Shift+E` | Power menu |
| `Escape` | Close an open shell panel |

The bar's **Overview** button opens niri's live overview. Right-click it to open
the themed workspace board.

## Update

From your permanent repository directory:

```bash
git pull --ff-only
```

The installed symlink points to this checkout, so the source updates in place.
Saved settings stay in the separate `lme-shell` preferences directory. If an
update changes dependencies, rerun the package preview and install commands.

To restart the default shell instance after updating:

```bash
quickshell -c lme-shell kill
./scripts/start.sh
```

<details>
<summary>I already use a Quickshell config named gpt</summary>

Keep the permanent checkout outside `~/.config/quickshell/gpt`. After pulling
updates, link that name to the current source:

```bash
./scripts/install.sh --replace --target "${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/gpt"
./scripts/start.sh --config gpt
```

`--replace` backs up an old copied config before creating the symlink. An existing
symlink to this checkout is left intact. Use `gpt` in your niri startup and IPC
commands, including `--config gpt` when starting through `start.sh`. Change the
include paths to `quickshell/gpt/…` as well. The supplied integration fragment
targets `lme-shell` by default; adapt it before including it with a custom name.
Your preferences still live in the same `lme-shell/settings.json` file.

</details>

## Help

Start with `./scripts/doctor.sh` and the
[troubleshooting guide](docs/TROUBLESHOOTING.md).

- **Settings does not open:** run `./scripts/settings.sh --page appearance` in a
  terminal to see its startup log. Update the installed config, not just a
  separate copy of the repo. The launcher recovers stale Settings instances.
- **Only the wallpaper blurs:** check the popup blur include and its `xray false`
  setting, then run `niri validate`.
- **Wi-Fi, Bluetooth or audio needs advanced setup:** use the Control Center's
  links to Fedora's network editor, Blueman or pavucontrol. First-time Bluetooth
  pairing and enterprise Wi-Fi use those existing tools.

When reporting a problem, include what you clicked, what happened, the relevant
terminal log, `niri --version`, `qs --version` and the doctor output.

### Guides

| Guide | Read it for |
| --- | --- |
| [Installation](docs/INSTALL.md) | Package sources, niri integration, custom paths and services |
| [Configuration](docs/CONFIGURATION.md) | Preferences, palette overrides and feature behavior |
| [Personalization](docs/PERSONALIZATION.md) | Element colors, fonts, bar geometry and liquid feedback |
| [Laptop features](docs/LAPTOP_FEATURES.md) | Monitor, idle profiles, keybindings and native blur |
| [Night Light, capture and motion](docs/CAPTURE_NIGHT_MOTION.md) | Schedules, annotation, OCR and animation presets |
| [Clipboard and Activity](docs/CLIPBOARD_ACTIVITY.md) | History, pins, timers, media and recording status |
| [Charging](docs/CHARGING.md) / [Authentication](docs/AUTHENTICATION.md) | Lenovo firmware support, helper setup and password prompts |
| [Validation](docs/VALIDATION.md) | Development checks and the limits of cloud testing |

### Development

Run `./scripts/check.sh` for backend tests, script syntax checks and a demo state
check. Native UI tests need a private Wayland session; see the validation guide.
Cloud checks do not establish real GPU, backlight, radio or suspend behavior on
every laptop.

## Credits and license

Inspired by [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland),
[iNiR](https://github.com/snowarch/iNiR),
[DankMaterialShell](https://github.com/AvengeMedia/DankMaterialShell) and
[Caelestia](https://github.com/caelestia-dots/shell).

Licensed under **GPL-3.0-or-later**, with the motion adaptation's retained
GPL-3.0-only terms. See [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md)
for source, dependency and asset attribution. Purchased Dracula Pro assets and
fonts are not bundled.

Rounded-polygon morphing: **Based on iNiR by snowarch (https://github.com/snowarch/inir)**. Modified for LME; upstream notice and geometry license are preserved in `third_party/iNiR-NOTICE` and `qml/components/shapes/LICENSE`.
