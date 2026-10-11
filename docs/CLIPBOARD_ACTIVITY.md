# Clipboard history and Activity island

These are original LME integrations informed by iNiR and DankMaterialShell.
They use the existing Material tonal colors, translucent glass and Roboto.
There are no new gradients, shaders or background blur requirements.

## Clipboard

Install the new runtime dependency on Fedora:

```bash
sudo dnf install wl-clipboard
```

Open **Clipboard** from the modular bar or bind **Super+V**. Search matches the
full text, including text beyond its visible preview. All/Text/Images filters,
image previews, pin/unpin, individual deletion and confirmed clearing are
available. Use Up/Down to select and Enter to copy; the panel closes after a
successful copy. Paste into the destination application with its normal paste
shortcut. Copying from history does not synthesize typing into another window.

**Settings → Clipboard** controls capture, image capture and history size
(20–500 items; default 100). Pause/Resume in the history panel persists across
shell restarts. Existing history remains accessible when capture is disabled.
Resuming can capture the currently selected clipboard content.

History is stored locally in `$XDG_STATE_HOME/lme-shell/clipboard`, defaulting to
`~/.local/state/lme-shell/clipboard`. Text is limited to 1 MiB per item and images
to 8 MiB. PNG, JPEG, WebP, GIF and BMP are supported; Qt image-format plugins
may be needed for previewing some formats. Content is deduplicated by exact
bytes and MIME type. Up to 20 pins survive oldest-first automatic cleanup.
The payload budget is 64 MiB; image previews, text search indexes and SQLite
pages consume additional disk space. Directory/database permissions are private
but history is ordinary unencrypted local storage. Pause before copying content
you do not want retained. Sensitive-selection hints are skipped when supplied
by `wl-paste`; applications do not universally supply them.

The shell owns its `wl-paste` watchers and stops them when it exits or capture
is disabled. A lock prevents duplicate capture by multiple shell instances.
Do not add a separate `cliphist` watcher for this implementation. Missing tools
and unavailable Wayland data-control support are reported in the panel.
Settings alone, demo and preview do not start capture or write the clipboard.

## Activity island

Click the bar's **Activity island** to expand media, focus timer and stopwatch.
**Super+Shift+A** is provided in the niri fragment. The expanded surface morphs
from the compact pill using OutExpo easing; it collapses with Close, Escape or
an outside click. Turning off animations makes it immediate. The overlay keeps
the bar's 42 px exclusive zone unchanged and clamps itself to the selected output.

The compact caption prioritizes supported recording, then focus/break timer,
stopwatch and MPRIS media. With no activity it shows the focused window title.
Media controls honor player capabilities, and a player selector appears when
multiple MPRIS players are present. A timer or stopwatch started here is the
same timer shown in Control Center → Agenda. It continues while panels are
closed; shell restart resets timers. Completion uses the existing notification
service and respects Do Not Disturb.

Recording status detects the current user's `wf-recorder` and
`gpu-screen-recorder` processes. It shows process uptime, which includes any
paused recording time. Stop recording in its application. This feature does
not start a recorder or detect every browser/portal recording session.

**Settings → Top bar → Activity island** enables the integration. Add/move/remove
its module like any other bar module. Existing layouts using **Window title**
gain the expandable activity behavior while the setting is enabled; disable it
to restore the plain title. New/default layouts include Activity in Center and
Clipboard in Right. Existing custom layouts are retained. Add Clipboard in
Settings or use its shortcut; Restore default layout is optional.

For a config installed as `gpt`, substitute `gpt` for `lme-shell` in commands:

```bash
quickshell -c lme-shell ipc call shell toggle clipboard
quickshell -c lme-shell ipc call shell toggle activity
```

## Verify on Fedora + niri

After pulling, install `wl-clipboard`, restart the shell and merge the two new
bindings into your own niri config after resolving duplicates. Verify text and
image copy/paste, pins after restart, pause, clear and the size preference.
Test media controls with your player, timer completion, disabled motion,
multiple outputs and a recorder you actually use. Cloud checks exercise real
Wayland/D-Bus APIs with private test fixtures; they do not certify the laptop's
specific applications or compositor session.
