# Night Light, Screenshot studio and motion

The interface and all processing remain local. These features use the existing
shell backend, Qt Quick and native niri capture; there is no separate screen
recording daemon.

## Fedora requirements

```sh
sudo dnf install wlsunset tesseract tesseract-langpack-eng tesseract-langpack-vie
```

Vietnamese recognition is optional; the interface stays in English. Restart
LME Shell after installing commands so its cached capabilities refresh.
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

## Screenshot studio

Use **Control Center → Capture & actions** for screen, selected area or focused
window capture. The shell closes its panels before niri captures. Area selection
uses niri's native screenshot UI. Finish its selection to open the independent
**LME Screenshot** window; press Escape to cancel the native selector. If a
capture remains pending, **Cancel capture** in Control Center clears it so you
can start again. Unfinished captures expire after two minutes.

For editor shortcuts, merge/include [`capture-keys.kdl`](../config/niri/capture-keys.kdl)
instead of existing Print/Ctrl+Print/Alt+Print bindings. Replace `lme-shell` with
your installed Quickshell configuration name, such as `gpt`, and remove duplicate
bindings before running `niri validate`. Existing native screenshot bindings
continue to take plain screenshots; the new studio is available through the
Control Center or its IPC:

```sh
quickshell -c lme-shell ipc call shell capture area
quickshell -c lme-shell ipc call shell capture screen
quickshell -c lme-shell ipc call shell capture window
```

The editor supports Pen, Highlight, Rectangle, Arrow, solid-black Redact,
color/stroke choices, Undo/Redo and zoom with Pan. Ctrl+Z undoes, Ctrl+Shift+Z
redoes, Ctrl+S saves and Ctrl+C copies the edited image. Text fields keep their
normal copy/undo shortcuts while focused. PNGs keep their original pixel
dimensions. A session allows 200 strokes with up to 4000 points each; images are bounded to 32 megapixels,
16384 pixels per side and 64 MiB.

**Save PNG** creates a private file in the chosen folder, defaulting to your
XDG Pictures/Screenshots directory. Filenames are unique and existing files are
never overwritten. A failed save removes its partial new file. **Copy image**
copies the rendered PNG using `wl-clipboard`. The exported image is flattened:
redacted pixels are solid black, with no hidden annotation layer or original
image embedded in the PNG.

**Niri also puts the original capture in the clipboard.** Redacting in the
editor does not erase that earlier clipboard item or other clipboard managers'
history. Copy the edited image before sharing; delete the original history item
if it contains sensitive content. Session originals/working PNGs live in a
private runtime directory and are removed when the session closes normally;
saved PNGs remain in the chosen folder.

**Extract text** runs local Tesseract on the rendered image, including its
redactions. Choose an installed language or `eng+vie` when both are installed;
then select/copy the recognized text or use **Copy text**. No image is uploaded.
OCR is bounded to 45 seconds and 256 KiB of text. Closing a session discards
late results so they cannot appear in a newer screenshot. Tiny text, complex
layouts and handwriting can require a tighter capture or different language.

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

On niri 26.04, include [`popup-blur.kdl`](../config/niri/popup-blur.kdl) and enable
**Settings → Appearance → Blur behind popups**. The `xray false` layer rule is
essential: xray blur only samples the wallpaper, hiding application/bar detail
under a full-screen blur region. The owner confirmed that including this rule
keeps applications and the bar visible in the blurred background, with the
popup sharp. Merge the global blur block if one already exists. Native non-xray
blur remains an experimental compositor feature.
