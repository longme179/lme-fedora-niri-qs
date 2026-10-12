# Selected shell ports

Each feature has its own commit. Settings are optional and keep the existing Dracula/glass defaults. Sources and licenses are recorded in THIRD_PARTY.md.

## Spring motion

Enable **Appearance → Spring motion**. Open and close the Control Center rapidly, then expand the Island while its content changes. The spring keeps velocity when retargeted, instead of replaying easing. Turning **Animations** off snaps to the final state and releases closed panels.

Closing panels and the Island travel beyond the nearest screen edge, without waiting for the spring's sub-pixel settling tail. OSDs exit through their configured side. During exit, the main overlay releases input so another bar click can reverse the animation. The dim backdrop interpolates over 220 ms on entry / 150 ms on exit at motion speed 1. Compositor blur remains region-based (binary intensity), because the Quickshell/niri protocol has no blur-strength property; this does not substitute wallpaper or a captured image for live applications.

Hovering controls render above sibling plates. Bar and Settings scroll viewports reserve drawing gutters while retaining scrolling clips; workspace buttons in their tight nested viewport keep width/radius/ripple motion without scale growth. Morph Canvas fits the current cubic silhouette and reserves stroke/antialiasing space, including during overshoot.

Validated: native QML retarget/velocity/convergence/reduced-motion regression, qmllint, existing native popup retention and Settings launch checks. GPU/120 Hz performance on the owner's laptop remains unmeasured.

## Geometric morph

Enable **Appearance → Geometric shape morph**, then hover/press a gear or another icon button. Its silhouette interpolates rounded polygon cubic paths. Animations off keeps a static circle. Source math is Apache-2.0, adapted Canvas retains iNiR GPL/NOTICE credits. Paint work is limited to interaction, resize and color changes; laptop CPU/GPU cost remains unmeasured.

## Moving tab indicator

**Appearance → Moving tab indicator** controls stretching selection in Control Center tabs and the Settings sidebar. Try mouse selection, Ctrl+Tab in Control Center, and filtered Settings navigation; reduced motion snaps. It adapts DMS independent leading/trailing edges to LME grid and vertical layouts. Selection fill tracks ancestor layout offsets and shares the selected button’s hover/press scale and corner radius, so its plate and feedback outline remain aligned.

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

The reactive default reads 16 mono bars at 60 fps with automatic sensitivity and `noise_reduction=20`, instead of 25 fps and Cava's default 77% smoothing. Monstercat/wave smoothing stays off so separate frequency peaks remain visible. QML takes each height directly from the current frame, without an additional 50 ms animation repeatedly retargeting before it finishes. Attack and decay therefore follow Cava's signal smoothing. Closing the media surface or stopping playback still releases its subscription and owned process; there is no continuous idle visualizer. A private native QML regression checks immediate rising/falling frame heights, and a mocked Cava child checks generated configuration, peak/silence parsing and termination. Real musical response still needs listening/viewing on the laptop.

## Autosaved quick notes

Enable **Behavior → Quick notes**, then **Control Center → Agenda → Notes**. A plain-text buffer autosaves after 600 ms and survives tab/panel changes. Storage: `$XDG_STATE_HOME/lme-shell/notes.txt` (default `~/.local/state/lme-shell/notes.txt`), initialized privately. External edits while dirty stop autosave and offer Copy/Reload; failed writes keep the buffer. Notes are outside settings exports/backups. Limit: 100,000 characters; force-killing the shell can lose the last unsaved interval.

## Wallpaper Material palette

Install Fedora `matugen`, select an image in **Wallpaper**, then Preview palette → Apply palette. Generation uses an empty temporary config and dry-run, never your Matugen templates. Dark Material roles flow through existing theme tokens; manual element overrides win and glass stays unchanged. Use Dracula switches back; Accent settings can still customize the selected palette. Appearance profiles and portable exports include the generated colors, not the image path. Matugen 3/4 parsing and failure preservation use fixtures; generation on a real binary remains pending in cloud.

## Launcher file/folder search

Enable **Behavior → Launcher file search** and set local folders (semicolon-separated). Type `/ report` in the launcher, select a result, Enter opens it with its default application. Default roots are Documents/Desktop/Downloads/Pictures. Search skips hidden paths and symlinks, caps 100 results/10,000 paths/1.5 s, and cancels superseded jobs. Slow or network filesystem calls can exceed the traversal deadline; select local folders. No indexer or extra package is required. Tests cover cancellation, bounds, hidden/symlink exclusion and safe URI opening.

## Owned screen recording

Install `wf-recorder ffmpeg-free`; `pulseaudio-utils` adds audio, `slurp` adds region selection. **Behavior → Screen recording** sets folder, encoder, container (MKV/MP4/MOV/WebM), codec, 24/30/60/120 fps and bitrate (1,000–100,000 kbps). **Control Center → Controls → Capture** selects output, area and audio, then Record. Popup exit is awaited before capture/selector. Stop and save is also in the Island for shell-owned recordings.

**Auto** tries NVIDIA NVENC first, then AMD/Intel VAAPI, then CPU. GPU presence is read from sysfs; only starting capture runs synthetic encoder probes. No idle NVIDIA polling or global pkill is used. Explicit NVIDIA/Radeon/CPU choices restrict the encoder tier; use Auto for cross-tier fallback. The card reports actual encoder, GPU and startup fallback reasons. Old CPU defaults saved before format controls migrate once to Auto; selecting CPU now is preserved.

Encoder preflight uses one 1920×1080 frame at the selected FPS/bitrate. The former 128×128 probe falsely rejected the owner's RTX with `Frame Dimension less than the minimum supported value`; the owner confirmed the new H.264 NVENC probe at 30 fps / 12,000 kbps exits with code 0. This checks encoder initialization, not the complete wf-recorder capture/audio pipeline. Probe errors and recorder startup logs preserve their leading cause instead of only thread-cleanup messages. Actual small-region or output limits can still be reported by wf-recorder; Auto can retry compatible startup candidates.

Auto codec prefers H.264, then AV1/HEVC/VP9 where the container supports them. WebM allows AV1/VP9; MOV allows H.264/HEVC. MP4/MOV audio uses AAC, MKV/WebM uses Opus. Fedora `ffmpeg-free` may omit selected encoders; missing codec support causes a clear error or Auto fallback. NVIDIA requires a working NVIDIA driver and NVENC-capable FFmpeg/wf-recorder builds. AMD/Intel require working VAAPI codecs; this shell does not install or change GPU drivers. Check `ffmpeg -hide_banner -encoders` and the actual card result. High-fps CPU encoding, especially AV1, may not keep up.

Hybrid capture uses `--no-dmabuf` and an explicit upload for VAAPI to avoid cross-GPU buffer import failures. Frames are padded to even dimensions for 4:2:0 codecs. This prioritizes compatibility over zero-copy throughput. Capture always writes a private MKV first; Stop validates it, remuxes to the requested container without re-encoding, checks the result, and only then removes the original. Conversion failures keep the original MKV; existing files are never overwritten. Closing the shell finalizes only its owned recorder. Mid-recording GPU/driver failure is reported and retained; automatic recovery applies to startup, not a running recording.

`/usr/bin/wf-recorder` is rediscovered on demand even if installed after shell startup or niri supplies a minimal PATH. If an error persists, restart the updated shell and confirm its logged configuration path matches the copy you updated. niri 26.04 provides wlr-screencopy; real capture/audio/GPU behavior still needs testing on the laptop.

## Validation and remaining limits

The full opt-in private Wayland suite completed **187 tests, all passed, no skips** on Quickshell 0.3.2 / Qt 6.8.2. It covers the existing shell plus spring physics and bound-target retargeting, real frame overshoot/reduced motion, Settings launch/reopen, font search selection, HSV/alpha apply, notes autosave/conflicts, notification protocols, nearest-edge popup exits/reversals, immediate input release, backdrop interpolation, Canvas stroke pixels, and screenshot/OCR/external annotation flows. Backend fixtures cover transfer safety, battery units, capture classification, search bounds/cancellation, owned recorder signaling and nonblocking preparation/shutdown.

The latest regressions cover desktop-sized NVENC probes with selected FPS/bitrate, preservation of leading encoder/child errors, one stable-ID workspace request over a private Unix socket (no redundant monitor action), and reactive spectrum configuration/framing/owned shutdown plus immediate native QML attack/release. Niri 25.11/26.04 source confirms stable-ID workspace references; physical pointer behavior with the owner's niri input policy remains a laptop check. The owner separately confirmed H.264 NVENC initialization at 1920×1080/30 fps/12,000 kbps with exit code 0. This is not proof of full screen recording or actual Cava audio response.

Recording regressions additionally cover late executable discovery/minimal PATH, NVIDIA → integrated → software ordering, failed encoder probes and child startup, preservation of partial footage, validated formats/FPS/bitrate, legacy-default migration, and exclusive private remux publication. Actual FFmpeg-generated H.264/VP9 fixtures were remuxed into MP4/MOV/WebM and decoded, with 0600 permissions and no source deletion on failure. The source options were checked against wf-recorder v0.6.0, matching the owner's reported version. Native click/keyboard tests changed Settings containers/codecs and reset an incompatible choice; the 850×700 screenshot studio's external button rendered real Canvas redaction pixels before passing a saved path to a mocked editor. This verifies the integration contract, not an actual Swappy/Satty window or real GPU capture.

On Fedora, update the installed shell, restart `qs -c gpt` (use your actual configuration name), then choose **Behavior → Screen recording → Auto**, **MP4**, **H.264**, **30 fps**. Record the connected output without audio for 5 seconds; Stop and save, play the result, and check the card's actual encoder/fallback. Repeat with system audio, Region and a preferred FPS. Force Radeon or CPU to check those tiers; Auto enables cross-tier fallback. For annotation, install Swappy, capture an area, draw/redact, choose **Annotate externally**, save in the external app, and reopen the resulting image to verify edits. No system packages or GPU drivers were installed by this cloud task.

Integration review also corrected initial tab-indicator placement and fallback contrast, swatch presentation, full-profile matching, bound spring target changes, easing/spring toggles, overlay capture timing, and nonblocking recorder setup. The virtual keyboard remains connected during held-key tests so headless Sway models a real keyboard without resetting Qt focus.

Changed QML was checked with qmllint. The local Quickshell SDK emits known `QProcess::ExitStatus` metadata / generic `PanelWindow` resolution warnings; they are reported separately from actual configuration/load errors. Native configuration loading and the inspected Settings/Control Center/picker screenshots have no new QML runtime errors. Ripple QSB was built with qsb; software Canvas was exercised, while the GPU shader and animation smoothness on the 120 Hz laptop remain unmeasured.

Cloud lacks Cava, Matugen, wf-recorder, pactl, slurp, Swappy and Satty; no new packages were installed. Real audio capture, image generation, screen recording/region/audio and external editor windows remain unverified. Battery telemetry, camera/meeting apps, full NVIDIA NVENC/Radeon VAAPI recording and physical multi-output niri behavior also require the owner's machine. The implementation must not be interpreted as verification of those complete hardware paths. Direct V4L2 camera access outside PipeWire is not detected.
