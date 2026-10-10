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
| `quickshell` ≥ 0.3.2 | QML shell host, Wayland layers/idle inhibitor, notification server, MPRIS, PipeWire mixer |
| `python3` | Application discovery and desktop integration backend |
| `qt6-qtbase`, `qt6-qtdeclarative`, `qt6-qtwayland`, `qt6-qtsvg` | Qt Quick runtime and image support |
| `NetworkManager` | Wi-Fi state and radio controls via `nmcli` |
| `pipewire`, `pipewire-pulseaudio`, `wireplumber` | Audio session and `wpctl` |
| `brightnessctl` | Backlight state and brightness controls |
| `bluez`, `systemd`, `util-linux` | Adapter/device controls through BlueZ D-Bus, `busctl`, `rfkill`; `bluetoothctl` fallback |
| `systemd` + existing `tuned-ppd` or `power-profiles-daemon` | Power profile controls through the common system D-Bus API |
| Noto Sans, Noto Color Emoji, Adwaita icon theme | Text and installed application icons |

Use a Quickshell build with `Quickshell.Services.Pipewire` and Wayland idle
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
pairing, `libnotify` for notification tests, and `swww` for wallpaper changes.
Check `dnf repoquery --available swww` before installing the optional wallpaper
daemon. It is excluded from the automated package transaction because availability
may depend on your enabled repositories. `playerctl` is useful for media keys;
the shell's media panel uses Quickshell's native MPRIS support.

For a complete bare niri session, also keep a **polkit authentication agent**
running so that apps can request authorized operations. The optional package
list includes `lxqt-policykit`, whose agent is `lxqt-policykit-agent`; an existing
working agent is equally suitable. Check the installed executable before adding
one startup entry:

```bash
command -v lxqt-policykit-agent
```

```kdl
spawn-at-startup "lxqt-policykit-agent"
```

Use one authentication agent per session. LME Shell delegates authentication to
Fedora's existing policy; it does not implement a privileged authentication UI.
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
```

This creates a symlink from `~/.config/quickshell/lme-shell` to the checkout.
It respects `XDG_CONFIG_HOME` when set. If a different configuration already
exists at that target, the installer stops. To back it up and then replace it:

```bash
./scripts/install.sh --replace
```

The old target is moved to a timestamped sibling backup. Existing niri settings
and `~/.config/lme-shell` preferences are preserved.

## 3. Run and validate

Inside the running niri session:

```bash
./scripts/doctor.sh
./scripts/start.sh
```

The Quickshell configuration name is `lme-shell`. Running
`quickshell -c lme-shell` directly is also supported. The wrapper restores a
previously selected wallpaper through `swww`, if that tool is available.
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

The default fragment launches `quickshell` directly. If you want saved wallpaper
restoration on login, replace its one startup line with the wrapper:

```kdl
spawn-sh-at-startup "$HOME/.config/quickshell/lme-shell/scripts/start.sh"
```

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
add the two overview bindings and run `niri validate`. Existing preferences and
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
