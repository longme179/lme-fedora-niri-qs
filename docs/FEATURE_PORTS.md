# Selected shell ports

Each feature has its own commit. Settings are optional and keep the existing Dracula/glass defaults. Sources and licenses are recorded in THIRD_PARTY.md.

## Spring motion

Enable **Appearance → Spring motion**. Open and close the Control Center rapidly, then expand the Island while its content changes. The spring keeps velocity when retargeted, instead of replaying easing. Turning **Animations** off snaps to the final state and releases closed panels.

Validated: native QML retarget/velocity/convergence/reduced-motion regression, qmllint, existing native popup retention and Settings launch checks. GPU/120 Hz performance on the owner's laptop remains unmeasured.

## Geometric morph

Enable **Appearance → Geometric shape morph**, then hover/press a gear or another icon button. Its silhouette interpolates rounded polygon cubic paths. Animations off keeps a static circle. Source math is Apache-2.0, adapted Canvas retains iNiR GPL/NOTICE credits. Paint work is limited to interaction, resize and color changes; laptop CPU/GPU cost remains unmeasured.

## Moving tab indicator

**Appearance → Moving tab indicator** controls stretching selection in Control Center tabs and the Settings sidebar. Try mouse selection, Ctrl+Tab in Control Center, and filtered Settings navigation; reduced motion snaps. It adapts DMS independent leading/trailing edges to LME grid and vertical layouts.

## Installed font picker

In **Elements → Type that feels like you**, open the arrow menu, search, then select a font. The existing preview remains. Enter accepts the first search result, Down moves into the list; Escape closes it. Manual input remains available, including when **Searchable font menus** is off. Missing fonts still use Qt fallback.

## Pointer-origin ripple

Enable **Appearance → Pointer-origin ripple**. Press near a rounded button corner, hold, then release; ink starts at that point and stays clipped. Keyboard presses use the center. Shader source and compiled QSB are bundled; rebuild with `QSB_BINARY=/usr/lib64/qt6/bin/qsb bash scripts/build-shaders.sh` (Fedora build-only package: `qt6-qtshadertools`). Software rendering uses the same rounded clip in Canvas. The press/hold/release lifecycle remains Caelestia-derived.

## HSV + alpha picker

Enable **Elements → Visual color picker**, click a role swatch, drag saturation/value, and set hue/opacity. Hex is `#RRGGBB` or `#AARRGGBB` (alpha first). Arrow keys edit saturation/value; Shift uses larger steps. Apply commits only that token, Cancel preserves it. Native tests cover popup editing/apply and alpha persistence; original role input/reset/profile behavior remains tested. No screen eyedropper dependency is introduced.

## Privacy and sharing DND

**Behavior → Capture indicators / Silence popups while sharing**. Add the Privacy module in Top bar settings for older saved bar layouts. Start a microphone/camera PipeWire stream or a niri portal screen share; active icons appear in the bar/Control Center. Share suppression composes with manual DND and retains notification history. Fixtures test muted/virtual streams and native cast/DND transitions. Direct camera access outside PipeWire and applications bypassing niri/PipeWire capture are not detected; real meeting apps need testing on Fedora. `pipewire-utils` supplies `pw-dump`.

## Export, import and backup

**Behavior → Settings export and restore** accepts a JSON path. Export preset produces a portable document suitable for sharing/factory-default review; private backup includes personal settings and must be treated as private. Import validates the entire file before applying, preserves unimported settings, and creates `settings-before-import-*.json` beside the live settings. Use the same Import action to restore that backup. Exports refuse overwrite. Clipboard/notification history, notes and external wallpaper files are deliberately outside settings backups. Tests cover private-field exclusion, invalid all-or-nothing import, backup permissions and restoration data.

## Battery health, power and ETA

Enable **Behavior → Battery health details** and inspect the Battery charging card. The backend reads standard power_supply energy/charge/current units; absent or invalid data stays unavailable. ETA is an instantaneous estimate and may vary with load; multiple-pack ETA is omitted. Fixtures cover energy/charge units, charge/discharge, zero power and unknown design capacity. Actual IdeaPad telemetry is not available in cloud.

## Configurable spring OSD

**Behavior → Volume and brightness OSD** sets nine positions, horizontal/vertical layout, edge distance and focused/all/named output. Output popups own their timers and retain the surface through spring exit. Hover pauses autohide. Change volume/brightness to test; disable Animations to test instant hiding. Disconnected outputs are removed; unplugging a selected named output does not silently redirect feedback. Physical multi-monitor behavior still requires testing on niri.

## Real audio spectrum

Enable **Behavior → Audio spectrum** and play media with a visible Control Center media card or expanded Island. Cava starts only while an enabled visible card needs frames; silence uses zero levels, not decorative animation. Install Fedora `cava` if missing. Parsing/clamping is tested and the missing-binary state is exercised; actual audio capture remains untested without Cava in cloud.

## Autosaved quick notes

Enable **Behavior → Quick notes**, then **Control Center → Agenda → Notes**. A plain-text buffer autosaves after 600 ms and survives tab/panel changes. Storage: `$XDG_STATE_HOME/lme-shell/notes.txt` (default `~/.local/state/lme-shell/notes.txt`), initialized privately. External edits while dirty stop autosave and offer Copy/Reload; failed writes keep the buffer. Notes are outside settings exports/backups. Limit: 100,000 characters; force-killing the shell can lose the last unsaved interval.
