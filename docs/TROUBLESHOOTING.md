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

Check `quickshell --version` and use Quickshell 0.3.2 or newer. Install Fedora's
`qt6-qtdeclarative`, `qt6-qtwayland`, and `qt6-qtsvg` packages with a Quickshell
binary built for the same distribution Qt version. A QML import failure after a
Qt update can indicate an incompatible custom or development Quickshell build;
update or rebuild that package rather than disabling checks or substituting
random libraries.

The wrappers and backend support both `quickshell` and `qs`. Settings launched
from the shell uses the running shell's executable, including custom builds.

The expanded shell also needs Quickshell's PipeWire, Polkit and Wayland idle
inhibitor modules. Distribution builds normally include them; enable
`SERVICE_PIPEWIRE`, `SERVICE_POLKIT` and Wayland support for a custom build.

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
tools. The Devices tab also connects/disconnects already paired devices and
selects a Bluetooth adapter; it does not manage secrets or perform first-time
pairing itself.

### BlueZ fails to power on

The shell enumerates BlueZ adapters, writes the selected adapter's `Powered`
property and verifies the resulting state. It no longer treats a zero
`bluetoothctl` exit code as success if BlueZ reports an error. If Bluetooth is
software-blocked, it retries after unblocking only Bluetooth rfkill entries;
hardware blocks require the laptop's radio switch or airplane-mode controls.
It never runs sudo or changes service configuration.

Read these diagnostics inside the niri desktop session:

```bash
bluetoothctl show
rfkill list bluetooth
systemctl status bluetooth --no-pager
journalctl -b -u bluetooth --no-pager
journalctl -b -k --no-pager | grep -Ei 'bluetooth|btusb|mt7921|firmware'
```

Choose the correct adapter in Control center → Devices if more than one is
listed. Install `util-linux` if `rfkill` is absent. A soft block can also be
cleared deliberately with `rfkill unblock bluetooth`; permission failures need
Fedora's existing device/session policy. The shell includes a Polkit agent;
see [authentication setup](AUTHENTICATION.md) if it is not registered.
If BlueZ still reports `org.bluez.Error.Failed`, the service or MediaTek firmware
may be responsible; keep the command output when reporting the issue. A shell
update cannot establish the cause without the laptop's logs.

### Audio devices or app sliders are missing

The Audio tab uses Quickshell's native PipeWire service. `wpctl status` should
show the same hardware and streams; check that PipeWire and WirePlumber are
running in this user's session. An application appears when it has an audio
stream, even if its window is open before playback starts. Selecting a default
device requests WirePlumber's configured default; final routing follows the
audio session's policy. In public demo/preview mode the native mixer is disabled.

### Overview or window movement is unavailable

Use niri 25.11+ and launch the shell inside that session so `NIRI_SOCKET` is
inherited. Left-click the overview button for actual window previews rendered
by niri. Right-click for the QML board, which uses app icons and titles. A failed
native overview request opens that board and shows the error. Drag a window
card onto a workspace or use its selector; menus include output names when
workspaces on separate monitors have the same number. A closed window or
removed workspace is rejected rather than moving another window.

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

Verify that both `awww` and `awww-daemon` are installed and that `awww query` responds
in the current Wayland session. Select an existing raster image. The bundled
SVG is artwork source, not an input format for `awww`; use the PNG.
Settings starts the daemon when needed and waits for readiness. An apply error
appears in the UI and does not replace your saved path.
The start wrapper restores an existing saved image and continues starting the
shell if the optional wallpaper tool is unavailable.

## Screenshot behavior

Prefer niri's built-in screenshot actions and bindings; they follow the
compositor's screenshot path configuration. Third-party tools can depend on
Wayland capture protocols that your installed niri version does not expose.
The shell uses native niri capture, then opens Screenshot studio for annotations
and OCR. Studio captures use private session files, and **Save PNG** exports to
the chosen folder. See [requirements, shortcuts and clipboard/redaction behavior](CAPTURE_NIGHT_MOTION.md).

If Night Light stays neutral, open **Settings → Night Light** for gamma errors.
Install `wlsunset`, restart the shell, and stop other gamma controllers. Nested
or headless outputs may not support gamma even if the protocol is present.

## Lock or suspend fails

Install `swaylock` for the shell's lock action and test it directly from a
terminal. Suspend and system power operations use `systemctl` under the current
desktop user's normal policy. Hardware wake-up behavior, NVIDIA suspend hooks,
and firmware sleep states need testing on the actual Lenovo laptop; the project
does not modify driver or power policy.

## Niri rejects the integration fragment

The expanded shell requires niri 25.11 or newer. Check for duplicate keys,
especially `Mod+Tab`, `Mod+Comma` and `Mod+Shift+E`, then run `niri validate`
again. Optional effects
from newer niri documentation may be unsupported by older installed versions.

## The glass appearance is subtle

The baseline effect is translucent layered surfaces with highlights. It can
look different with different wallpapers and panel opacity settings. True
background blur is compositor-dependent. Increase panel opacity for legibility
and disable animations in Settings if you prefer reduced motion or lower GPU
work. Avoid selecting the RTX GPU just to intensify visual effects.

## Settings app or typography

Run `./scripts/settings.sh` from the permanent checkout in your Wayland session.
It uses `settings.qml`, independently of the shell. The bar and Super+Comma open
the same application; `--page topbar` navigates an existing instance rather than
starting another. Register the launcher with `./scripts/install-settings.sh`.
If you moved the checkout, rerun it with `--replace` to back up the old entry.

For a config installed as `gpt`, run
`bash ~/.config/quickshell/gpt/scripts/settings.sh --page appearance` in a
terminal to see that application's own startup log. The main shell also logs
errors from its Settings launcher. Check the terminal environment matches your
niri session and uses Quickshell 0.3.2 or newer. Closing the native Settings
window now ends its instance, allowing a fresh open instead of reusing a hidden
native window. The independent app also supports `--page elements`.

Warnings about an existing `org.freedesktop.Notifications` service or Polkit
agent describe another process owning that service. They do not by themselves
identify a Settings load failure. Keep one notification server and one Polkit
agent in your session; use their own diagnostics when those services fail.

Install `google-roboto-fonts` and check `fc-match Roboto` if text uses a fallback.
After installing fonts, restart the existing Quickshell applications so Qt can
resolve the new family. Bar text size can be changed in Settings → Top bar.
Per-class color and font overrides are in Elements and fonts; Reset restores
their inherited values. See [Personalization](PERSONALIZATION.md).

A preference error appears inside Settings. Layouts accept only the documented
module IDs and unique modules across the three zones. External JSON edits reload
within the normal two-second poll; malformed JSON retains the previous running
state. If the app is tiled, review the floating-window rule in the niri fragment.
Stock niri is not assumed to blur the background: translucent flat fills remain
visible without a blur protocol.


## Weather does not load or shows the wrong city

Automatic location uses your public IP, so a VPN or network gateway may place
it in a nearby or different city. Use Settings → Weather → Detect now, or search
and select a city to switch to a fixed location. The refresh button updates both
location and forecast in automatic mode. No GPS permission or API key is needed.
Allow HTTPS to `ipwho.is`, `api.open-meteo.com` and
`geocoding-api.open-meteo.com`. Offline/service errors are shown in the widget;
the last good forecast is retained and retries occur after two minutes.
Settings does not automatically poll location/forecast services while open.

## Charge controls are disabled or do not show 85%

Run `python3 scripts/charge_control.py status` to inspect capability without
changing anything. No interface means the current kernel/BIOS does not expose
supported control. An available interface with a setup message needs the
root-owned helper and `pkexec`; follow [CHARGING.md](CHARGING.md).
Check the shell's [built-in Polkit agent](AUTHENTICATION.md) if its password popup
does not appear. Cancelling or rejecting the prompt leaves the read-back mode visible
and reports an error.

If the UI says “Conservation” without “85%”, the kernel exposes the firmware's
fixed conservation setting. This interface cannot choose a numerical threshold;
installing the helper does not change that hardware limitation. A limit below
the current battery charge also does not discharge the battery automatically.

## Clipboard capture and Activity

Install `wl-clipboard` and restart the shell if capture/copy is unavailable.
Run inside niri with Wayland data-control support. Check Settings → Clipboard
and the panel Pause state; stop duplicate shell instances if capture is owned
elsewhere. Do not launch a separate cliphist watcher for LME history.
Activity needs an enabled Activity or Window title module, or its IPC binding;
media controls require an MPRIS-compatible player on the same session bus.
Recording status supports only the recorder processes documented in
[CLIPBOARD_ACTIVITY.md](CLIPBOARD_ACTIVITY.md).
