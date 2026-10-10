# Troubleshooting

Start with `./scripts/doctor.sh` inside the target niri session, then run
`quickshell -c lme-shell` from a terminal to read startup errors.

## Quickshell cannot find the configuration

Confirm that `~/.config/quickshell/lme-shell/shell.qml` exists and that the
symlink points to the current checkout. Moving or deleting the checkout breaks
the installed link. Rerun `./scripts/install.sh`; use `--replace` only if you
intend to back up and replace a different target. If `XDG_CONFIG_HOME` is set,
Quickshell and the installer must use the same config home.

## A QML type or module is unavailable

Check `quickshell --version` and use Quickshell 0.2 or newer. Install Fedora's
`qt6-qtdeclarative`, `qt6-qtwayland`, and `qt6-qtsvg` packages with a Quickshell
binary built for the same distribution Qt version. A QML import failure after a
Qt update can indicate an incompatible custom or development Quickshell build;
update or rebuild that package rather than disabling checks or substituting
random libraries.

The supported command is `quickshell`; some packages also supply the `qs` alias.
If your custom build only provides `qs`, adapt your local command or install a
package with the standard binary name.

## The shell starts but has no desktop state

The shell must run in the current niri user's Wayland and D-Bus session. A cloud
terminal, root shell, SSH session, or an unrelated GNOME session cannot provide
the target niri socket. Check:

```bash
niri msg --json outputs
niri msg --json workspaces
python3 scripts/desktop_backend.py --once
```

The backend's JSON includes tool availability and a result message. Missing
tools produce unavailable controls. Demo mode intentionally shows sample data
and does not execute desktop actions.

## Duplicate bars or panels reserve too much screen space

Keep one startup entry for LME Shell and remove the previous bar's startup
entry when you switch. Do not run one instance by named configuration and
another by a different source path at the same time. Check `niri msg layers`
to inspect layer-shell surfaces and their namespaces.

## Notifications do not appear

Only one notification server can own `org.freedesktop.Notifications` on the
session bus. Check whether an existing daemon such as Dunst, Mako, or another
shell is active and remove its autostart entry if LME Shell is taking over.
Then restart the shell and send a test:

```bash
notify-send "LME Shell" "Desktop notifications are working."
```

Install `libnotify` if `notify-send` is missing. Turn Do Not Disturb off when
testing popups. A missing popup while DND is enabled is expected; check the
notification center instead.

## Audio, Wi-Fi, Bluetooth, or power profiles are unavailable

Test the same read-only commands the shell uses:

```bash
wpctl get-volume @DEFAULT_AUDIO_SINK@
nmcli radio wifi
bluetoothctl show
busctl --system get-property org.freedesktop.UPower.PowerProfiles \
  /org/freedesktop/UPower/PowerProfiles org.freedesktop.UPower.PowerProfiles ActiveProfile
brightnessctl --class=backlight get
```

For audio, inspect the user's `pipewire` and `wireplumber` service state. For
radios, inspect NetworkManager and Bluetooth service state. An unavailable
Bluetooth adapter, hard rfkill block, unsupported firmware power profile, or
missing backlight device cannot be solved by a QML refresh.

Use `nm-connection-editor` for Wi-Fi connection authentication and
`blueman-manager` for pairing. The sidebar toggles radios and opens those
tools; it does not manage secrets or perform first-time pairing itself.

Recent Fedora installations use TuneD/`tuned-ppd`; `power-profiles-daemon` is
an alternative. Both expose compatible power-profile D-Bus APIs. Do not run
competing providers or replace a working TuneD setup just to install this shell.
An older provider may expose only the legacy `net.hadess.PowerProfiles` name and
`/net/hadess/PowerProfiles` path; the backend also checks that API. Optional
`powerprofilesctl` can inspect a compatible provider if already installed.

If `brightnessctl` cannot write the laptop backlight, inspect Fedora's existing
device permissions and login/session membership. Do not run the whole shell
with sudo or make `/sys` writable globally.

## Wallpaper changes fail

Verify that `swww` and `swww-daemon` are installed and that `swww query` responds
in the current Wayland session. Select an existing raster image. The bundled
SVG is artwork source, not an input format for `swww`; use the PNG.
The start wrapper restores an existing saved image and continues starting the
shell if the optional wallpaper tool is unavailable.

## Screenshot behavior

Prefer niri's built-in screenshot actions and bindings; they follow the
compositor's screenshot path configuration. Third-party tools can depend on
Wayland capture protocols that your installed niri version does not expose.
The shell uses native niri capture for its screenshot shortcut.

## Lock or suspend fails

Install `swaylock` for the shell's lock action and test it directly from a
terminal. Suspend and system power operations use `systemctl` under the current
desktop user's normal policy. Hardware wake-up behavior, NVIDIA suspend hooks,
and firmware sleep states need testing on the actual Lenovo laptop; the project
does not modify driver or power policy.

## Niri rejects the integration fragment

`include` needs niri 25.11 or newer. On older versions, merge the startup line
and bindings into your existing file instead. Check for duplicate keys, especially
`Mod+Comma` and `Mod+Shift+E`, then run `niri validate` again. Optional effects
from newer niri documentation may be unsupported by older installed versions.

## The glass appearance is subtle

The baseline effect is translucent layered surfaces with highlights. It can
look different with different wallpapers and panel opacity settings. True
background blur is compositor-dependent. Increase panel opacity for legibility
and disable animations in Settings if you prefer reduced motion or lower GPU
work. Avoid selecting the RTX GPU just to intensify visual effects.
