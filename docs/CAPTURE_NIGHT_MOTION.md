# Night Light, Screenshots and motion

The interface and all processing remain local. These features use the existing
shell backend, Qt Quick and flameshot; there is no separate screen recording
daemon.

## Fedora requirements

```sh
sudo dnf install wlsunset flameshot
```

Missing commands are rediscovered on demand after installation.
`scripts/install-fedora.sh --optional --install` includes these packages.
`scripts/doctor.sh` reports missing commands. Use niri 26.04 for the complete
desktop configuration, including the native full-screen popup blur fragment.

## Night Light

Open **Settings → Night Light**. Choose a color temperature from 2500–6500 K
and enable the feature. The Control Center has a movable/hideable Night Light
tile; its layout survives upgrades.

- **Manual** keeps the selected warmth on until disabled.
- **Custom times** uses local HH:MM times, including schedules across midnight.
  The end boundary is exclusive; matching start/end times mean all day.
- **Sunset to sunrise** uses the existing Weather location, the local timezone
  and an approximate sunrise/sunset calculation. It makes no additional location
  request. If location is unavailable or the sun does not rise/set that day,
  the page shows the reason and you can select a time schedule.

The shell owns one `wlsunset` child only while warmth is needed. Temperature
changes restart that child; disabling the feature or exiting the backend
releases gamma control. The existing Linux parent-death helper also ends it if
Quickshell kills the backend. The Settings application reads the running shell's
state and never starts a second gamma controller. **Retry gamma control** asks
that shell to retry once.

The compositor must expose `wlr-gamma-control`, and each display's driver must
accept gamma ramps. Another gamma controller can prevent access. Errors are
shown in Settings and the tile; an alive process with a gamma failure is not
reported as an active filter. Headless/nested outputs commonly cannot apply
hardware gamma. This feature does not implement ICC calibration or HDR tone
mapping.

## Screenshots

Press **Print** to capture an area or **Ctrl+Print** to capture the whole
screen. The shell closes its panels first, then launches `flameshot gui` or
`flameshot full`; selection and editing happen entirely in flameshot. Saved
files land in `~/Pictures/Screenshots` and are created private (mode 0600).
There is no in-shell editor or OCR; use flameshot's annotation tools and your
own OCR workflow if needed. Escape cancels an area selection, and new capture
requests are ignored while a flameshot process is still running.

For keybindings, merge the Print bindings from [`lme-shell.kdl`](../config/niri/lme-shell.kdl)
instead of existing Print/Ctrl+Print/Alt+Print bindings. Replace `lme-shell` with
your installed Quickshell configuration name, such as `gpt`, and remove duplicate
bindings before running `niri validate`. Existing native screenshot bindings
continue to take plain screenshots. The **Control Center → Capture & actions**
tiles trigger the same two captures, and the IPC surface stays available for
scripts:

```sh
quickshell -c lme-shell ipc call shell capture area
quickshell -c lme-shell ipc call shell capture screen
```

While the session is locked, niri itself refuses screencopy; the shell answers
the keypress with the capture notice on the lock surface and never spawns
flameshot locked. A capture whose overlays cannot close within three seconds
expires with a status message instead of hanging.

## Motion presets

Open **Settings → Appearance → Glass and motion**:

- **Smooth** uses a monotonic eased slide, with no bounce/deformation.
- **Expressive** uses a restrained spatial overshoot and smooth shape changes.
- **Jelly** combines a bouncy spatial curve with subtle stretch/squash and
  elastic press feedback.

Speed ranges from 0.5–2×, and Bounce from 0–100%. **Replay preview** demonstrates
the same SlideLoader used by shell panels and authentication dialogs. Motion
settings are included in Appearance profiles. Old profiles keep their colors,
opacity and density and receive the new motion defaults.

Spatial animation is shared through `MotionAnimation` and Theme tokens. Color
transitions remain monotonic. Island expansion, buttons, switches and sliders
use the same settings; animation does not run continuously while idle. Disable
**Animations** for immediate changes without deformation. Start with the default
Expressive preset at 1× / 35% Bounce on the integrated Radeon.

Caelestia's shared spatial/effects motion approach informed this implementation;
the QML and configurable curves here are original. No Caelestia plugin or source
is required.

## Popup backdrop

On niri 26.04, include the blur section of [`lme-shell.kdl`](../config/niri/lme-shell.kdl) and enable
**Settings → Appearance → Blur behind popups**. The `xray false` layer rule is
essential: xray blur only samples the wallpaper, hiding application/bar detail
under a full-screen blur region. The owner confirmed that including this rule
keeps applications and the bar visible in the blurred background, with the
popup sharp. Merge the global blur block if one already exists. Native non-xray
blur remains an experimental compositor feature.

Liquid glass replaces this full-screen blur with local regions beneath rounded
panels and popups; the saved preference applies again when switching back to
Smoked. Local bar blur remains independent. Merge the updated blur fragment if
you previously copied its layer rules manually.


Recording audio choices now persist between popup openings and shell restarts.
System audio is the default; choose No audio explicitly for a silent recording
or Microphone for the default input. The existing PulseAudio-compatible capture
path remains, including Bluetooth sink monitors. When audio is requested,
`ffprobe` (included with the FFmpeg package) checks for a saved audio track. A
failed check retains the original video and reports an error instead of silently
saving a successful video-only recording.
