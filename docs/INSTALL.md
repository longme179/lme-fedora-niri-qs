# Fedora 44 installation

The supported target is an existing niri 25.11+ Wayland session on Fedora 44. Install
and run the shell as your normal desktop user. Use `sudo` only for package
installation; running Quickshell as root breaks access to the user's session.

## 1. Packages

The complete categorized list is [requirements-fedora.txt](../requirements-fedora.txt).
It is a DNF list, not a Python dependency file. The backend uses Python's standard
library and needs no `pip install`.

| Package | Purpose |
| --- | --- |
| `quickshell` ≥ 0.3.2 | QML shell host, Wayland layers/idle inhibitor, notification server, MPRIS, PipeWire mixer, Polkit agent |
| `python3` | Application discovery and desktop integration backend |
| `qt6-qtbase`, `qt6-qtdeclarative`, `qt6-qtwayland`, `qt6-qtsvg` | Qt Quick runtime and image support |
| `NetworkManager` | Wi-Fi scans, password entry and saved-profile controls via `nmcli` |
| `pipewire`, `pipewire-pulseaudio`, `wireplumber` | Audio session and `wpctl` |
| `brightnessctl` | Backlight state and brightness controls |
| `bluez`, `systemd`, `util-linux` | Adapter/device controls through BlueZ D-Bus, `busctl`, `rfkill`; `bluetoothctl` fallback |
| `systemd` + existing `tuned-ppd` or `power-profiles-daemon` | Power profile controls through the common system D-Bus API |
| `polkit` | System authorization service and `pkexec` for administrator actions |
| Noto Sans, Noto Color Emoji, Adwaita icon theme | Text and installed application icons |

Use a Quickshell build with `Quickshell.Services.Pipewire`,
`Quickshell.Services.Polkit` and Wayland idle
inhibitor support. Older 0.2.x builds cannot run the expanded control center.
The backend still uses only Python's standard library.

Preview the package transaction:

```bash
./scripts/install-fedora.sh --optional
```

Install from your currently enabled Fedora repositories:

```bash
./scripts/install-fedora.sh --install --optional
```

The installer leaves DNF's normal transaction confirmation enabled and preserves
signature and TLS verification. It does not enable or disable desktop services.
On a normal Fedora desktop most of the audio, networking, and Bluetooth services
are already present.

Fedora uses TuneD/`tuned-ppd` by default on recent releases. Keep your existing
working provider. The shell supports its standard power-profile D-Bus API and
does not need to replace it with `power-profiles-daemon`. The installer therefore
does not install either competing power manager automatically.

### Quickshell repository availability

Quickshell's [official installation guide](https://quickshell.org/docs/v0.2.0/guide/install-setup/)
documents the Fedora release package and the
[errornointernet/quickshell COPR](https://copr.fedorainfracloud.org/coprs/errornointernet/quickshell/).
The guide version inspected lists the official package in Rawhide; this is not
proof that your Fedora 44 enabled repositories contain it. Check locally:

```bash
dnf repoquery --available quickshell
```

If no package is available, review the COPR, verify that it offers a current
Fedora 44 build, and choose that additional package source explicitly:

```bash
./scripts/install-fedora.sh --install --optional --copr
```

The script enables that COPR only if Quickshell is absent and `--copr` was
provided. Prefer the release package `quickshell`. `quickshell-git` tracks
unreleased changes and may require matching QML/API updates. Do not mix an
unrelated Qt build with the distribution's Quickshell binary.

Optional helpers include `swaylock` for locking, `pavucontrol` for advanced
sound routing, `network-manager-applet` for connection editing, `blueman` for
pairing, `libnotify` for notification tests, and `awww` for wallpaper changes.
Check `dnf repoquery --available awww` before installing the optional wallpaper
daemon. It is excluded from the automated package transaction because availability
may depend on your enabled repositories. `playerctl` is useful for media keys;
the shell's media panel uses Quickshell's native MPRIS support.

LME Shell now starts its own **Polkit authentication agent** and glass password
popup automatically, including when launched by niri. No terminal or separate
agent startup command is needed. Keep one agent per session: remove an old
`lxqt-policykit-agent`/other agent autostart entry if switching to this popup,
then log out and back into niri. Quickshell's build must include
`Quickshell.Services.Polkit` (`SERVICE_POLKIT=ON` for source builds).
See [AUTHENTICATION.md](AUTHENTICATION.md) for status checks and troubleshooting.
For Flatpak file pickers and screen sharing, keep niri's session setup and portal
configuration intact. The optional list includes the GTK and GNOME portal
backends and `gnome-keyring`; see niri's
[important software guide](https://niri-wm.github.io/niri/Important-Software/).

## 2. Install the user configuration

Place the checkout in a permanent location, such as `~/src/lme-fedora-niri-qs`:

```bash
git clone https://github.com/longme179/lme-fedora-niri-qs.git ~/src/lme-fedora-niri-qs
cd ~/src/lme-fedora-niri-qs
./scripts/install.sh --dry-run
./scripts/install.sh
./scripts/install-settings.sh --dry-run
./scripts/install-settings.sh
```

This creates a symlink from `~/.config/quickshell/lme-shell` to the checkout.
It respects `XDG_CONFIG_HOME` when set. If a different configuration already
exists at that target, the installer stops. To back it up and then replace it:

```bash
./scripts/install.sh --replace
```

The Settings installer adds `lme-shell-settings.desktop` under
`${XDG_DATA_HOME:-~/.local/share}/applications`. It is repeatable, supports
`--dry-run` and `--target`, and refuses to overwrite a different entry unless
`--replace` is provided. Keep the checkout at its permanent path. The topbar
Settings button works even before installing the launcher entry.

The old configuration target is moved to a timestamped sibling backup.
Existing niri settings
and `~/.config/lme-shell` preferences are preserved.

## 3. Run and validate

Inside the running niri session:

```bash
./scripts/doctor.sh
./scripts/start.sh
```

The Quickshell configuration name is `lme-shell`. Running
`quickshell -c lme-shell` directly is also supported. The wrapper restores a
previously selected wallpaper through `awww`, if that tool is available.
It preserves the current wallpaper when no wallpaper preference exists.

If another notification daemon owns `org.freedesktop.Notifications`, stop that
daemon through its existing session configuration before using this shell's
notification server. Avoid starting the shell twice with different config paths.

Preview sample data without changing desktop state:

```bash
./scripts/start.sh --preview
```

Preview mode uses an ordinary window with sample data. `--demo` instead uses
the normal layer-shell layout with sample data. Both need a running Wayland
compositor; a cloud/headless machine can use a nested compositor as described in
[VALIDATION.md](VALIDATION.md).

## 4. Add niri startup and keybindings

Back up your current `~/.config/niri/config.kdl` before editing it. Review
[config/niri/lme-shell.kdl](../config/niri/lme-shell.kdl). Check the existing
`binds` section and remove or rebind any duplicates. In particular, niri's
sample configuration uses `Mod+Comma` for consuming a window into a column and
`Mod+Shift+E` for quitting niri; the shell fragment assigns those keys to shell
settings and the power menu.

For **niri 25.11 or newer**, add a top-level include to your existing config:

```kdl
include "../quickshell/lme-shell/config/niri/lme-shell.kdl"
```

That path assumes the default neighboring `niri` and `quickshell` directories
inside your config home. It avoids home-directory expansion, which only newer
niri versions support. Adjust it if you installed to a custom target.

Upgrade older niri installations before enabling this fragment. The overview
uses `toggle-overview`; cross-output window movement uses stable workspace IDs
through the niri socket. Both are supported by the 25.11 baseline.

Validate the resulting configuration:

```bash
niri validate
```

The default fragment uses `scripts/start.sh` to restore a saved wallpaper through
awww before starting Quickshell. When updating an older installed fragment,
replace its direct Quickshell startup line with:

```kdl
spawn-sh-at-startup "exec \"${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/lme-shell/scripts/start.sh\""
```

The fragment also opens **LME Shell Settings** as a floating window. Settings
can be started independently with `./scripts/settings.sh --page topbar`. It
does not start a bar or register a notification server.

Use only one shell startup command. If you previously ran a bar such as Waybar
or another Quickshell config, remove its startup entry when you switch to LME
Shell so that screen reservations and notification ownership are predictable.

### Optional laptop keys and idle locking

[config/niri/media-keys.kdl](../config/niri/media-keys.kdl) contains volume,
microphone mute, backlight, media, `Super+L` locking, and niri screenshot bindings.
Review and merge the desired entries after removing duplicates from your
current `binds` block. In a normal niri session, `Super+L` conflicts with an
existing `Mod+L`; choose another key if you want to preserve focus-right there.
The media-key bindings require optional `playerctl`; the shell panel itself does
not require it.

Idle locking is optional and is never enabled by the installer. If you want it,
install `swayidle` and `swaylock`, verify that locking works on your session,
then add an explicit startup command such as:

```kdl
spawn-at-startup "swayidle" "-w" \
    "timeout" "300" "swaylock -f -c 22212c" \
    "timeout" "600" "niri msg action power-off-monitors" \
    "resume" "niri msg action power-on-monitors" \
    "before-sleep" "swaylock -f -c 22212c"
```

This locks after five minutes, turns off monitors after ten minutes, and locks
before a separately requested sleep. It does not suspend automatically. The
lock itself is implemented by `swaylock`; LME Shell is not a screen locker.

The panels can also be opened from a terminal:

```bash
quickshell -c lme-shell ipc call shell toggle launcher
quickshell -c lme-shell ipc call shell toggle control
quickshell -c lme-shell ipc call shell toggle notifications
quickshell -c lme-shell ipc call shell toggle settings
quickshell -c lme-shell ipc call shell toggle power
quickshell -c lme-shell ipc call shell toggle overview
quickshell -c lme-shell ipc call shell close
quickshell -c lme-shell ipc call shell refresh
```

`Mod+Tab` opens niri's live overview. `Mod+Shift+Tab` opens the shell's workspace
board. The topbar overview button provides the same actions with left- and
right-click respectively. Check existing `Mod+Tab` bindings too.

## Updating an existing installation

From the checkout linked to your Quickshell configuration:

```bash
git pull --ff-only
quickshell --version
niri --version
./scripts/install-fedora.sh --install --optional
./scripts/doctor.sh
```

Then restart the existing shell instance. Review the updated niri fragment to
add the overview bindings and the Settings floating-window rule, then run
`niri validate`. Install the new `google-roboto-fonts` requirement and run
`./scripts/install-settings.sh` to register the independent app. Existing
preferences and
the installation symlink are retained; never start a second shell alongside
the first to update it.

## 5. Lenovo display and graphics

Read the actual output name and supported modes; do not assume the laptop panel
is named `eDP-1` or that its refresh rate is exactly `120.000`:

```bash
niri msg outputs
```

Add an output block using the connector and exact mode string from that output:

```kdl
// Example only: replace both strings with values reported by your machine.
output "eDP-1" {
    mode "1920x1080@120.030"
    scale 1.0
}
```

For Ryzen + NVIDIA hybrid graphics, keep the existing working Fedora/niri GPU
setup. Start the shell normally so that Mesa and the compositor select the
usual render device. If a session-wide offload setting sends everything to the
RTX GPU, test `DRI_PRIME=0 quickshell -c lme-shell` and inspect the renderer
before making it permanent. This is an optional local diagnosis, not a driver
installation step; it does not guarantee routing for every EGL/driver setup.

MT7921 Wi-Fi support comes from Fedora's kernel and firmware. Shell radio
controls call NetworkManager; they do not install firmware or configure network
passwords. Use the connection editor for network authentication.

## Uninstall or restore

Quit this Quickshell configuration, remove its startup line and bindings, then
remove the configuration **symlink** only after verifying it:

```bash
ls -ld ~/.config/quickshell/lme-shell
test -L ~/.config/quickshell/lme-shell && unlink ~/.config/quickshell/lme-shell
```

Move a previous timestamped backup back to that location if needed. User
preferences and installed packages are not removed automatically.

To remove the Settings launcher, verify and remove only the generated entry:

```bash
cat ~/.local/share/applications/lme-shell-settings.desktop
rm ~/.local/share/applications/lme-shell-settings.desktop
```

Restore an installer-created `.backup-*` entry if you previously replaced one.


## Wallpaper and charging

For wallpaper selection, install **both `awww` and `awww-daemon`** from
[LGFae/awww](https://codeberg.org/LGFae/awww.git). On Fedora, first check:

```bash
dnf repoquery --available awww
```

If your enabled repositories provide it, use `sudo dnf install awww` and verify
`command -v awww awww-daemon`. Otherwise follow upstream's source build
instructions. At release 0.12.1 (`f66e12a76dbc4c669b2f1375f78bce49f5b19d66`),
Cargo declares Rust **1.89.0 or newer**; the README's older 1.87 minimum is stale.
Build requirements include Rust/Cargo, `pkgconf-pkg-config`, `lz4-devel`,
`wayland-devel` and `wayland-protocols-devel`. `libxkbcommon-devel` may also be
needed by the Wayland development environment. `scdoc` is optional for man pages.
Build with `cargo build --locked --release`, then install both binaries on PATH.
The automated Fedora package installer excludes awww because repository
availability varies. No extra package repository is enabled automatically.

Settings starts the daemon when applying an image. The startup wrapper does the
same when restoring one on login. Do not run a second wallpaper daemon for the
same output. After migration, remove any old wallpaper-daemon startup entry
from your own niri configuration.

For Lenovo charge controls, install `polkit` if `pkexec` is missing. The shell's
built-in popup handles authentication. On the **target laptop**, run:

```bash
./scripts/install-charge-helper.sh --dry-run
sudo ./scripts/install-charge-helper.sh --install
```

Then open Control Center → Controls → Battery charging. The shell detects the
helper on its next hardware poll. Read [CHARGING.md](CHARGING.md) before assuming
your firmware supports an exact 85% limit.

Weather needs no new packages or API key. Allow outbound HTTPS to `ipwho.is`,
`api.open-meteo.com` and `geocoding-api.open-meteo.com`. The widget detects an
approximate location by default; Settings → Weather also supports a fixed city.

## Clipboard and Activity update

Install `wl-clipboard` for text/image history; it is now included in the core
Fedora package list. No `cliphist`, Python package or new service is required.
See [CLIPBOARD_ACTIVITY.md](CLIPBOARD_ACTIVITY.md) for bindings, settings and
the upgrade path for existing modular layouts.

The desktop upgrade package list includes `qt6-qtimageformats` as required.
Confirmed display layouts restore alongside the saved wallpaper through the
startup wrapper. See [Desktop upgrades](DESKTOP_UPGRADES.md) for controls and
physical-laptop validation limits.

## Laptop idle and native popup blur

Install `swayidle swaylock` and restart the shell before enabling Settings → Idle and sleep. They are included by `scripts/install-fedora.sh --optional`. CPU/process monitoring and the keybinding viewer need no extra packages. Full-screen application blur requires niri 26.04+ and the optional `config/niri/popup-blur.kdl` fragment; do not include this fragment on older niri. Follow [LAPTOP_FEATURES.md](LAPTOP_FEATURES.md) for merging and validation.
