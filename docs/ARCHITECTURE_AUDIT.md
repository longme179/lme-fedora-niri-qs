# LME Shell architecture audit — Phase 0

**Date:** 2026-10-20  
**Scope:** current runtime, feature integrations, settings, entry points and validation.  
**Baseline:** `1f54934`; recording/status-lock correction committed separately as `684f372`.

## Summary

LME is a Quickshell/Qt Quick shell, with separate main-shell and Settings processes,
Python controllers, and niri integration. Existing domain controllers and shared QML
controls provide useful boundaries. The main weakness is repeated knowledge about
feature registration, settings and lifecycle rules across those boundaries: a feature
can be implemented locally but still require several unrelated coordinator edits.
This report ranks seven change-cost problems and records the current contracts;
it does not propose replacing the shell or changing its appearance.

**Phase boundary:** the audit itself changes documentation only. Phase 1 architecture
design, Phase 2 refactors, and Phase 3 enforcement scripts await the owner's approval.
The separately requested recording bug fix is not part of a behavior-preserving
refactor. No feature folders, manifests, settings migrations or new dependencies
were introduced here.

## Scope and assumptions

- Read the actual composition, imports, calls, settings consumers and tests, rather
  than treating file size as evidence of a defect. Appendices inventory all 134 QML
  files under `qml/`, the other files there, 31 Python modules, 147 default settings,
  89 explicit live actions, IPC and shortcuts. There are 141 QML files including the
  seven root entry/demo files.
- Treat this as one owner-maintained application. The relevant
  [distance](https://coupling.dev/posts/dimensions-of-coupling/distance/) is between
  feature modules and, especially, the separate main/Settings/helper processes.
- Appearance, layout, media and customization have high product
  [volatility](https://coupling.dev/posts/dimensions-of-coupling/volatility/).
  Freedesktop/BlueZ/MPRIS contracts are relatively stable; provider support and
  implementation details can still change. Commit frequency alone was not used
  to classify a feature.
- Main `desktop_backend.py` uses Python stdlib. An existing exception is the separate
  `bluetooth_agent.py` process, which imports Gio/GLib through `gi`; the repository
  already declares `python3-gobject-base`. Preserve pairing rather than silently
  removing that dependency to claim every helper is stdlib-only.
- GPU, real backlight, hardware Bluetooth, suspend, and niri physical output changes
  need a real-session check. Private Wayland tests and fake hardware are explicitly
  distinguished below.

## Confirmed recording conflict and correction

`BatterySaver.snapshot()` used an exclusive, nonblocking lock just to inspect busy
state. Main shell and Settings have different backend instances but share the same
journal/lock. A Settings status probe could therefore briefly block the recorder's
guard after Battery saver had already restored the machine. A failed nonblocking
acquisition reported **“Battery saver is changing settings; wait for it to finish”**.
This exact result was reproduced before the correction in an enable → disable →
record test with a concurrent Settings status probe; it is a demonstrated failure
path, not a measurement of the user's machine.

Commit `684f372` uses shared locks for status probes and lets guarded writes retry
for up to 250 ms while a brief probe finishes. Long transitions still reject
conflicting actions, active saver still blocks display/profile mutations, and the
restoration journal and settings merge semantics remain intact. Two regression
tests cover simultaneous readers and the reported recording sequence. No encoder,
GPU preference or recording format was changed.

## Current entry points and ownership

| Entry / owner | Current responsibility and contract |
| --- | --- |
| `scripts/start.sh` → `shell.qml` | Live shell, optional wallpaper/display restore; `--demo` avoids mutations; `--preview` implies demo and uses an ordinary preview window. |
| `shell.qml` | `ShellRoot`, real `PanelWindow` variants, overlay routing/geometry, authentication, notifications, OSD, desktop canvas and `shell` IPC. |
| `scripts/settings.sh` → `settings.qml` → `SettingsApplication.qml` | Separate Settings instance and backend (`--settings`); queues pages during initial load, confirms a visible window through IPC, and retains the view over backend reconnects. |
| `settings-demo.qml` | Settings with isolated demo state. |
| `authentication-demo.qml`, `capture-demo.qml`, `native-features-demo.qml`, `upgrades-demo.qml` | Test/demo hosts for real components; their fixture IPC is not the production feature API. |
| `qml/services/ShellState.qml` | Process-local singleton owning backend JSON-lines transport, pending results, shared snapshots, routing and several feature policies. |
| `scripts/desktop_backend.py` | 2,221 lines; `DesktopBackend` constructor at 619, snapshot composition at 1107, completion dispatch at 1199, request handling at 1366, live dispatch at 1607, shutdown at 2201. `perform` is 377 lines; demo dispatch is another 196. |
| Backend CLI | `--once`, `--demo`, `--settings`, startup wallpaper/display restore, and JSON-lines service loop. Selectors watch stdin/niri; niri changes are coalesced, pending work wakes promptly, request size is bounded. |
| Worker ownership | Two general workers, one charging worker and a weather worker; owned recorder/mirror/idle/night-light lifecycles. Display rollback has a separate watchdog. QML owns Bluetooth pairing, clipboard, Cava, lyrics and updater helpers. Detached Launchpad/user applications deliberately outlive backend commands. |
| Persistence | `$XDG_CONFIG_HOME/lme-shell/settings.json`, protected by `settings.lock`; separate saver restore journal, feature data/cache and display-preview runtime state. |

The main shell and Settings do **not** share one Python object. They communicate
through persisted settings, selected shell IPC and session services. `Preferences`
is the write authority: lock → reload latest → validated merge/token patch → fsync
private temporary file → atomic replacement. Preserve this protocol when changing
schema ownership. Do not replace it with saving a stale whole-form snapshot.

Useful shared catalogs already exist: `config/control-grid.json`,
`config/liquid-glass.json`, `config/theme-tokens.json`, and `config/palettes.json`.
They are foundations to extend, rather than reasons to add a competing registry.

## Ranked integrations

Scores below express relative cost and expected frequency of legitimate product
changes, not an incident count. The
[balance rule](https://coupling.dev/posts/core-concepts/balance/) is used at the
module/process level; several stable shared helpers are appropriate reuse.

| Priority / integration | [Strength](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) | [Distance](https://coupling.dev/posts/dimensions-of-coupling/distance/) | [Volatility](https://coupling.dev/posts/dimensions-of-coupling/volatility/) | [Balanced?](https://coupling.dev/posts/core-concepts/balance/) / change cost |
| --- | --- | --- | --- | --- |
| A1 Feature identity → registries/renderers/validators/routes | [Functional](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) | QML, Python and CLI lists | High | Needs attention; high × frequent |
| A2 Settings meaning → storage/UI/export/helpers | [Functional](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) | Languages and processes | High | Needs attention; high × frequent |
| A3 Backend feature → coordinator contexts/results/teardown | [Model / functional](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) | Domain modules and coordinator | High | Needs attention; high × frequent |
| A4 Tab identity → routing/read-state/refresh behavior | [Functional](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) | Bar, shared state and panel | High | Needs attention; medium × frequent |
| A5 Feature result → global UI transport/presentation | [Functional](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) | Generic service and feature surfaces | High | Needs attention; medium/high × frequent |
| A6 Resource state → sampling/lifecycle/power consumers | [Functional](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) | Services, effects and two backends | Medium/high | Needs attention; high × intermittent |
| A7 Display watchdog → generic runner/persistence | [Contract / intrusive](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) | Domain helpers and composition root | Low/medium | Mixed; medium × intermittent |
| Shared notes, MPRIS model, visual geometry and catalogs | [Contract / model](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) | Cohesive service/component consumers | Low/medium | Mostly balanced; preserve |

## A1 — Feature registration requires coordinated edits

**Severity:** Significant. **Integration:** feature identity → host registries.

**Evidence:** `BarRegistry.qml:6` and `desktop_backend.py:93` repeat the factory bar
layout; backend `BAR_MODULES` separately validates IDs. `BarModule.qml:20` selects
renderers/availability independently of metadata. `ControlRegistry.qml:13` reads
the grid catalog, while `ControlDashboard.qml:30` and `:103` independently map cards
and tiles to components. Settings page registration spans `SettingsRegistry.qml:5`,
`SettingsView.qml:129`, `ShellState.qml:94`, `scripts/settings.sh:23` and `qmldir`.

**Shared knowledge and effect:** adding a page can make it searchable yet rejected
by the launch script; adding metadata alone cannot render a new bar module. The
current lists agree; these are demonstrated edit dependencies, not a claim that
an existing page is broken.

**Candidate improvement after approval:** extend existing registration metadata to
own identity, renderer, availability and routing. Retain saved IDs, strict validation
and load-error handling. One feature folder plus one registry entry is a useful
acceptance example. Trade-off: factories/catalogs add a startup contract, so missing
entries, preview and Settings startup need characterization before changing loaders.

## A2 — Settings have several sources of meaning

**Severity:** Significant. **Integration:** defaults/validation → UI/export/helpers.

**Evidence:** defaults at `desktop_backend.py:62`, validation at `:358`, portable
allowlist at `settings_transfer.py:8`, appearance membership in
`desktop_features.py:11`, and clipboard defaults/limits at `clipboard.py:178`.
Recording options/ranges also appear in `BehaviorPage.qml:123` and backend validation.
There are literal fallback reads for 81 distinct preferences across QML. Those
include defensive empty/default values and must not all be classified as redundant
factory-default definitions.

**Shared knowledge and effect:** a changed range must agree across processes and
controls; a new preference can save successfully but disappear from a portable
preset. Blindly exporting all defaults would also expose private fields.

**Candidate improvement after approval:** gradually extend the proven JSON schema
approach with default, validation metadata and explicit portable/profile membership.
Keep specialized validators and runtime-dependent paths in their appropriate code.
Preserve `Preferences` lock/reload/merge/atomic writes and migrations. Trade-off:
schema loading/versioning adds responsibility; do not generate an entire Settings
UI simply to remove a few fallback expressions.

## A3 — Backend domain wiring is scattered through the coordinator

**Severity:** Significant. **Integration:** domain controller → backend lifecycle.

**Evidence:** constructor `desktop_backend.py:619`, snapshot `:1107`, completion
dispatch `:1199`, Settings allowlist `:1371`, invalidation `:1380`, demo `:1402`, live
dispatch `:1607`, and shutdown `:2201`. Completion also installs feature-specific
capture/image-utility state. There are 89 explicit live action IDs, of which 41 are
allowed from standalone Settings.

**Shared knowledge and effect:** adding an async operation requires knowing where
its state is published, how it completes, which process may invoke it, and how it
closes. A feature can succeed in the shell and fail from Settings, or leave a pending
UI if its completion contract is missed. Moving the existing 31 Python modules into
a package without changing these connections would not resolve that cost.

**Candidate improvement after approval:** characterize and register one domain's
existing actions, allowed contexts, completion, snapshot and cleanup behavior. Keep
the public action/result shapes and shared runner/preferences. Trade-off: explicit
registration is additional structure; avoid migrating every controller in one step.

## A4 — Tab positions are a cross-feature API

**Severity:** Significant. **Integration:** bar gestures → Control Center side effects.

**Evidence:** `ControlCenter.qml:15` has the labels, `:18` another positional list,
`:19` refreshes tabs 0/2, `:20` marks tab 4 read, and `:116` selects components by
index. `BarGestures.qml:52` maps audio/devices/agenda/system to numeric positions;
`ShellState.qml:40` stores an integer. `Agenda.qml` repeats positional dispatch.

**Shared knowledge and effect:** inserting or reordering a tab can silently open a
different surface or trigger the wrong refresh/read behavior. This is a small but
frequently crossed integration boundary.

**Candidate improvement after approval:** use stable IDs and derive rendering indices
at the boundary from one registry. Retain numeric demo/environment compatibility
while migrating. Trade-off: a compatibility adapter is temporarily necessary; a
wholesale navigation rewrite is not.

## A5 — ShellState combines transport with feature policy

**Severity:** Significant. **Integration:** backend protocol → UI routing/presentation.

**Evidence:** `ShellState.qml:47` lists panel flags and visibility consumers, `:73`
routes panels/pages, `:119` coordinates close-before-capture/record, `:140` transports
commands, and `:154` combines snapshots with peripheral alerts, OSD, Wi-Fi results,
overview fallback and toast suppression. Process recovery/Settings launch follow
at `:187`. The host geometry in `shell.qml:82` also knows individual popup identities.

**Shared knowledge and effect:** a backend action can require presentation edits in a
generic transport singleton, including whether it should toast or refresh a specific
surface. Feature policy is implicit in string lists. Capture timing in particular
must not be lost while simplifying this service.

**Candidate improvement after approval:** keep a compatibility facade for transport
and expose cohesive routing/result-presentation contracts to feature coordinators.
Move policy before moving files. Trade-off: a few explicit hooks are preferable to
a universal event bus or one backend instance per widget.

## A6 — Sampling, power policy and lifecycle coordination need explicit ownership

**Severity:** Significant. **Integration:** controls/resource owners → shared snapshots.

**Evidence:** backend privacy/Bluetooth/power/system caches have different cadences;
`saver_snapshot():1062`, `finish_features():1226`, request handling `:1380` and Wi-Fi
watch handling `:1674` invalidate them separately. `Theme.qml`, ShellState blur flags,
`VisualizerState.qml`, desktop ambient and `Wallpapers.power_saving` each apply saver
policy. Bluetooth, Cava, clipboard, privacy and lyrics have distinct acquire/retry/
cancel protocols. The reproduced status-lock conflict illustrates why separate
processes and observations belong in that test matrix.

**Shared knowledge and effect:** an action can work but show stale state unless all
readback paths agree; a global power/lifecycle change has many consumers. Conversely,
clearing a broad cache can repeat unrelated expensive probes. These observations do
not establish a new polling leak or failure in each existing worker.

**Candidate improvement after approval:** preserve current cadences and consumer
leases; give each domain ownership of its cache/readback invalidation. Document
resource acquire/release, expected exits and transition-lock semantics, then extract
only identical lifecycle mechanisms. Trade-off: provider-specific cancellation and
restart behavior must remain local. A cached global snapshot is not a substitute
for hardware arbitration, and changing polling frequency is outside this refactor.

## A7 — Generic infrastructure is owned by a display feature

**Severity:** Significant for the reverse import; minor for stable helper placement.
**Integration:** display safety helper → composition root and unrelated persistence.

**Evidence:** `display_control.py:70` owns `write_json`, `read_json` and `locked` used
by saver, launcher history, lyrics and the backend. Its watchdog CLI at `:197`
imports `desktop_backend.CommandRunner`. Thus an independent recovery process
depends on the large composition root just to run commands.

**Shared knowledge and effect:** changing coordinator imports during extraction can
break rollback even when display logic was untouched. Stable persistence reuse is
appropriate; the ownership/import direction makes unrelated moves more expensive.

**Candidate improvement after approval:** extract the existing runner/error and
generic persistence helpers into shared infrastructure, preserving permissions,
fsync/atomicity, file locks, cancellation and independent rollback. Keep display
mode/apply/restore code together. Trade-off: one deliberate import migration;
do not create a generic framework for all feature-to-feature calls.

## Existing boundaries to preserve

- Reuse `SlideLoader`, `PopupElasticity`, `JellyGeometry`, `SurfaceBlurRegion`,
  `GlassMaterial`, `Theme` and house controls; avoid separate feature copies.
- Keep the common grid migration, media presentation/progress/actions, independent
  player selection per media surface, per-player lyric sessions and shared notes.
- Keep atomic settings/token merges, confidential portable-export allowlists,
  saver restoration data and display-preview rollback.
- Keep `--preview`/demo mutation isolation and the standalone Settings startup/
  reconnect contract. Test fixtures that copy or rewrite source need migration too.
- Keep user application/Launchpad processes detached while canceling owned workers.
- Installers must remain non-destructive: `install.sh` validates targets and backs
  up replacements; setup documents manual niri includes. Never overwrite the user's
  `~/.config/niri/config.kdl`. Update remains clean-main fast-forward or the explicit
  backed-up ZIP bootstrap, without resets/stashes or package installation.

## Verification and limits

- Before the fix, both new lock regressions failed; the backend regression reproduced
  the exact reported recorder error. Afterward, all 42 saver/controller/backend tests
  passed, including real lock contention with fake hardware.
- `bash scripts/check.sh`: 471 tests, 384 passed and 87 skipped because opt-in/runtime
  prerequisites were absent. Bash syntax and demo JSON checks passed. A green
  `check.sh` alone does not mean all native UI/hardware branches were tested.
- Private Sway/Wayland with Mesa OpenGL: four saver visual/UI checks and the native
  Settings startup/queued-page check passed. The full shell preview rendered and
  saved its screenshot without QML errors. These use fixtures/virtual hardware,
  not the user's niri/GPU session.
- `qmllint`: all 141 QML files, zero errors and 67 existing import/type-metadata
  warnings with the configured Quickshell/Qt import paths. No QML was changed by
  the recording correction.
- **Needs real-session check:** repeated saver Off → record on the user's laptop,
  real NVENC/audio, niri output restoration, backlight, Bluetooth and suspend. The
  audit does not claim a measured GPU/FPS improvement.

The appendices below are a source snapshot, not a new registry or generated runtime
schema. `docs` names refer to `docs/<NAME>.md`, and `test_*` names refer to modules
under `tests/`. File line references describe this audit baseline.

## Appendix A — Feature-to-integration map

Backend action names below are JSON actions dispatched via ShellState unless otherwise stated. `setting` is a generic validated merge action; Clipboard uses its own JSONL worker rather than desktop_backend.

| Feature | QML files / services | Commands / provider | Settings | IPC and consumers | Docs | Tests |
|---|---|---|---|---|---|---|
| Bar modules | `bar/{BarRegistry,BarModule,BarGroup,BarSurface,ActivityButton,BarGestures,ModuleGestures}`, `panels/Bar`, `services/ShellState` | `workspace`, `volume`, `mute`, nativeOverview, shared panel actions; MPRIS for media gestures | barLayout,barStyle,barGestures,barFontSize,barBorderWidth,barCorners,barIslandStyles,activityEnabled,privacyIndicators,launchpadEnabled + Theme element roles | `shell.toggle`; window title/niri, notifications unread/DND, media, privacy, desktop edit | `docs/CONFIGURATION.md`,`docs/PERSONALIZATION.md` | `tests/test_bar_gestures.py`, `tests/test_bar_styling.py`, `tests/test_personalization.py`, `tests/test_island_size.py` |
| Launcher / launchpad | `panels/{Launcher,LaunchpadPanel,LaunchpadEditor}`, `services/LauncherSearch.js` | launch,launchpadRun,fileSearch,fileOpen,calculate,copyText,focusWindow; app list/niri | launcherRanking,fileSearchEnabled,fileSearchRoots,launchpadEnabled,launchpadEntries | shell.toggle launcher/launchpad | `docs/CONFIGURATION.md`,`docs/DESKTOP_UPGRADES.md` | `tests/test_launcher_history.py`,`tests/test_launchpad.py`,`tests/test_utilities_ui.py`,`tests/test_ports.py` |
| Clipboard | `panels/ClipboardPanel`, `services/ClipboardState` | separate `clipboard.py` JSONL: search,copy,pin,delete,clear,pause; desktop action imageAnnotate | clipboardEnabled,clipboardImages,clipboardLimit | shell.toggle clipboard; screenshot/annotation | `docs/CLIPBOARD_ACTIVITY.md`,`docs/CONFIGURATION.md` | `tests/test_clipboard.py`,`tests/test_image_annotation_ui.py` |
| Activity / media | `panels/{ActivityIsland,ActivityCard}`, `bar/ActivityButton`, `services/{ActivityState,FocusTimer,VisualizerState}`, `components/{MediaPresentation,MediaProgress,MediaActions,MediaAmbient,LyricsSession,LyricsView,AudioVisualizer,WaveProgress}` | MPRIS direct play/previous/next/seek/shuffle/repeat; `recordStop`; lyrics.py / audio_visualizer.py workers | activityEnabled,activityCompactMaxWidth/activityPopupMaxWidth/activityPopupMaxHeight via Theme; activityLyrics,lyricsEnabled,lyricsOnline,lyricsMode,lyricsFollow,mediaStability,mediaControls,mediaShapes,mediaWave,audioVisualizer | shell.toggle activity, mediaStatus; reused in CC and desktop | `docs/CLIPBOARD_ACTIVITY.md`,`docs/CONFIGURATION.md`,`docs/FEATURE_PORTS.md` | `tests/test_activity.py`,`tests/test_media_controls.py`,`tests/test_media_presentation.py`,`tests/test_media_ambient.py`,`tests/test_lyrics.py`,`tests/test_lyrics_modes.py`,`tests/test_visualizer.py`,`tests/test_island_size.py` |
| CC host / quick controls | `panels/{ControlCenter,ControlDashboard}`, `services/ControlRegistry`, `components/{ControlGrid,ControlSlider}`, `ControlGridLogic.js` | controlsRefresh,appearanceApply,setting,batterySaver,powerProfile,bluetoothToggle,micMute,mute,volume,micVolume,brightness,lock,captureClose; panel routing | controlWidth,controlLayout,controlGrid; all visible features' enabled flags; animations/nightLight... | shell.toggle control; bar gestures select tab indexes | `docs/CONFIGURATION.md`,`docs/CODE_REVIEW.md` | `tests/test_control_grid.py`,`tests/test_controls.py`,`tests/test_polling_ui.py`,`tests/test_tab_indicator.py`,`tests/test_battery_saver_qml.py` |
| CC Audio | `panels/AudioMixer` | Quickshell.Pipewire direct device defaults, stream/node volume/mute; openSettings(audio) | none direct | CC tab1, bar gesture audio | `docs/CONFIGURATION.md`,`docs/TROUBLESHOOTING.md` | `tests/test_controls.py`,`tests/test_polling_ui.py` |
| CC Devices | `panels/{DeviceControls,PeripheralBatteryList,WifiWidget}`, `services/{BluetoothState,PeripheralBatteries}`, `components/{BluetoothPairing,MirrorControls}` | bluetoothToggle,bluetoothDevice,refresh,openSettings; BlueZ worker watch/scan/pair/reply/cancel/close; Wi-Fi + mirror actions | bluetoothPairing,bluetoothAdapter,peripheralBatteryAlerts,peripheralBatteryThreshold,mirroringEnabled | CC tab2; controlsRefresh and Wifi leases | `docs/CONFIGURATION.md`,`docs/MIRRORING.md` | `tests/test_bluetooth_pairing.py`,`tests/test_bluetooth_status_qml.py`,`tests/test_peripheral_battery.py`,`tests/test_peripheral_batteries_qml.py`,`tests/test_mirroring.py`,`tests/test_polling_ui.py` |
| CC Agenda | `panels/{Agenda,CalendarWidget,TasksWidget,TimerWidget,QuickNotes}`, `services/{FocusTimer,NotesState}` | setting(tasks),notesInit,copyText; NotesState FileView autosave | tasks,quickNotes | CC tab3; desktop shares notes; Island shares timer | `docs/CONFIGURATION.md`,`docs/FEATURE_PORTS.md` | `tests/test_notes_ui.py`,`tests/test_features.py`,`tests/test_controls.py` |
| Notifications | `services/Notifications`, `panels/{NotificationCenter,NotificationToasts}`, `components/{NotificationCard,NotificationEmblem,StatusWindow}` | Quickshell notification server + notificationSave, imageAnnotate, setting; Notifications.local for shell errors/warnings | dndUntil,dndWhileSharing,notificationMutedApps; notificationPosition,width,margin,etc Theme roles (see Appendix F) | shell.toggle notifications; CC tab4; privacy-based DND; screenshot click annotation; bar unread/DND | `docs/NOTIFICATIONS.md`,`docs/CONFIGURATION.md` | `tests/test_notification_appearance.py`,`tests/test_notification_ids.py`,`tests/test_image_annotation_ui.py`,`tests/test_polling_ui.py` |
| CC System | `panels/SystemMonitor`, `components/HistoryChart` | monitor on-demand | no direct prefs | CC tab5 | `docs/LAPTOP_FEATURES.md`,`docs/CONFIGURATION.md` | `tests/test_laptop_features.py`,`tests/test_polling_ui.py` |
| Weather | `panels/WeatherWidget` | weatherRefresh,openSettingsPage(weather) | weather location/units via Settings | CC card weather | `docs/CONFIGURATION.md` | `tests/test_features.py`,`tests/test_polling.py` |
| Charging | `panels/ChargingWidget` | chargeMode, needs optional privileged installed helper | batteryDetails; runtime capability checks | CC card charging; Polkit agent independently prompts | `docs/CHARGING.md`,`docs/AUTHENTICATION.md` | `tests/test_features.py`,`tests/test_peripheral_battery.py`,`tests/test_authentication.py` |
| Polkit | `auth/{AuthenticationAgent,AuthenticationWindow,AuthenticationDialog}` | Quickshell.Services.Polkit directly; flow submit/cancel | theme only | shell.authenticationStatus; closes panels on auth request, suppresses normal overlays | `docs/AUTHENTICATION.md` | `tests/test_authentication.py`,`tests/test_glass_controls.py` |
| Screenshot / recording | `panels/{ScreenshotEditor,RecorderWidget}`, `components/AnnotationCanvas`, `services/ShellState` capture delays | screenshot/Area/Window,captureClose,captureAnnotate,captureExport,captureLanguages,captureOcr,recordStart,recordStop,imageAnnotate | recordingEnabled,Folder,Audio,Encoder,Format,Codec,Fps,Bitrate, annotation settings | shell.capture, shared screenshot notifications/clipboard paths; Island recording state | `docs/CAPTURE_NIGHT_MOTION.md`,`docs/FEATURE_PORTS.md` | `tests/test_capture_night.py`,`tests/test_recording.py`,`tests/test_image_annotation_ui.py`,`tests/test_managed_commands.py` |
| Desktop canvas / ambient | `panels/{DesktopCanvas,DesktopWidgetWindow,DesktopCard,DesktopAmbient,DesktopPreview}`, `services/DesktopState` | setting(desktopWidgets),desktopEdit forwarded from Settings; notes/media capability reuse | desktopEnabled,desktopWidgets,desktopShapes,desktopShapeCount/Scale/Opacity/Speed/Style/Rotation | shell.desktopEdit, DesktopState.toggleEdit; output matching, bar insets | `docs/CONFIGURATION.md` | `tests/test_desktop_widgets.py`,`tests/test_desktop_ambient.py` |
| Overview / tray / power | `panels/{Overview,TrayMenu,PowerMenu}` | workspace,focusWindow,moveWindow,nativeOverview; native tray menu; lock/suspend/logout/reboot/poweroff after confirm | theme/bar settings only | shell.toggle overview/tray/power; Polkit/overlay coordination | `docs/CONFIGURATION.md`,`docs/TROUBLESHOOTING.md` | `tests/test_backend.py`,`tests/test_controls.py`,`tests/test_upgrade_ui.py` |
| Shared optics/motion/OSD | components inventory below; `services/{GlassState,OSDManager}` | OSD observes backend audio/backlight deltas; texture sharing via host window | surfaceStyle/liquidGlass + Theme motion and element prefs, osdEnabled/Position/Layout/Output/Margin | Shared in main and Settings; niri blur namespace config | `docs/CONFIGURATION.md`,`docs/PERSONALIZATION.md`,`docs/CAPTURE_NIGHT_MOTION.md` | `tests/test_liquid_style.py`,`tests/test_glass_controls.py`,`tests/test_glass_hover.py`,`tests/test_glass_geometry.py`,`tests/test_jelly_v2.py`,`tests/test_popup_entry.py`,`tests/test_popup_motion.py`,`tests/test_selection_lens.py`,`tests/test_motion_ports.py` |

## Appendix B — Settings page map

Commands below are actual ShellState.run calls or delegated page/service operations; ordinary preference controls use `setting`; domain actions also persist through the shared `Preferences` writer. Generic settings-page IPC is `settings.openPage(key)` and shell `toggle("settings")`; no per-page IPC target exists. Tests listed are the most direct coverage, not a claim of comprehensive runtime validation. All paths below are relative to the repository root.

| Page / files | Settings keys / state | Backend commands | Docs / direct tests |
|---|---|---|---|
| `elements`: ElementsPage.qml | themeOverrides, fontOverrides, fontSize, fontPicker, colorPicker; shared token catalog | setting (token patches) | PERSONALIZATION, CONFIGURATION; test_personalization, test_ports, test_glass_controls |
| `appearance`: AppearancePage.qml + LiquidGlassSettings.qml | shellName, surfaceStyle, liquidGlass, glassSelection, accent, opacity, animations, density, appearanceProfiles, paletteSource; springMotion, shapeMorph, animatedTabs, pointerRipple, mediaWave, mediaShapes, mediaStability, mediaControls, motionPreset/Speed/Bounce; activityCompactMaxWidth, activityPopupMaxWidth/Height; popupBlur, barBlur | appearanceSave/Apply/Delete, platformRefresh, glassBlurApply, setting; palette choice delegated PalettePicker | PERSONALIZATION, CONFIGURATION, CAPTURE_NIGHT_MOTION; test_personalization, test_liquid_style, test_glass_controls, test_island_size, test_jelly_v2, test_settings_startup |
| `topbar`: TopBarPage.qml | barStyle, barLayout, barGestures, barFontSize, barEdge/Margin, barSideMargin, barHeight, barBorderWidth, barCorners, barIslandStyles, themeOverrides barFill/barBorder; activityEnabled | setting (whole layout and token patches) | PERSONALIZATION, CONFIGURATION; test_settings, test_personalization, test_bar_styling, test_bar_gestures |
| `controlLayout`: ControlLayoutPage.qml | controlLayout, controlWidth; drag grid coordinates are edited in Control Center itself | setting | CONFIGURATION, CODE_REVIEW; test_control_grid, test_upgrade_ui, test_upgrades |
| `display`: DisplayPage.qml | snapshot.displays, displayLayout (saved on confirmed preview), saver active | displayRefresh, displayApply, displayConfirm, displayRevert | DESKTOP_UPGRADES; test_upgrades, test_battery_saver_backend |
| `nightLight`: NightLightPage.qml | nightLightEnabled/Mode/Temperature/Start/End | setting, nightLightRefresh | CAPTURE_NIGHT_MOTION; test_capture_night, test_upgrade_ui |
| `desktop`: DesktopPage.qml | desktopEnabled, desktopWidgets (through DesktopState), desktopShapes; desktopShapeCount/Scale/Opacity/Speed/Style/Rotation | setting; DesktopState.toggleEdit() uses desktopEdit IPC/backend bridge | CONFIGURATION; test_desktop_widgets, test_desktop_ambient |
| `wallpaper`: WallpaperPage.qml + WallpaperPlaylistSettings.qml + AwwwSettings.qml | wallpaper, wallpaperFolder, wallpaperOutputs; wallpaperPlaylist, Enabled/Paused/Shuffle/Interval/Output; wallpaperTransition/Duration/Fps/Step/Angle/Position/Bezier/Wave, wallpaperResize/Filter/FillColor; paletteSource/Scheme/Mode/Contrast | wallpaper, wallpaperResetOutput, wallpaperNext, wallpaperScan, wallpaperStatus, wallpaperEnsure, palettePreview/Apply/Reset, setting | CONFIGURATION, DESKTOP_UPGRADES; test_wallpaper_playback, test_wallpaper_playback_ui, test_image_utilities, test_palettes, test_upgrades |
| `utilities`: UtilitiesPage.qml + GowallSettings.qml + panels/LaunchpadEditor.qml | launchpadEnabled, launchpadEntries; Gowall operation preview state; selected wallpaper/output | gowallThemes/Generate/Save/Apply/Setup, setting; LaunchpadEditor invokes launchpadRun and token patches | CONFIGURATION; test_launchpad, test_image_utilities, test_utilities_ui |
| `weather`: WeatherPage.qml | weatherAutoLocation, weatherLocation (chosen via command), weatherUnit | weatherSearch, weatherDetect, weatherSelect, setting | CONFIGURATION, TROUBLESHOOTING; test_backend (weather), test_settings, test_upgrade_ui |
| `notifications`: NotificationsPage.qml | notificationWidth/Position/Margin/Radius/Padding/Opacity/BorderWidth/TitleSize/BodySize/IdleAnimation/IdleSpeed; themeOverrides notification roles | setting; preview calls shared Notifications.local, not a backend action | NOTIFICATIONS, CONFIGURATION; test_notification_appearance, test_notification_ids |
| `clipboard`: ClipboardPage.qml | clipboardEnabled, clipboardImages, clipboardLimit | setting | CLIPBOARD_ACTIVITY; test_clipboard, test_upgrade_ui |
| `idle`: IdlePage.qml | idleEnabled, idleProfiles.{ac,battery}.{display,lock,suspend}, idleLockBeforeSleep | setting, idleRefresh | LAPTOP_FEATURES; test_laptop_features, test_polling |
| `keybinds`: KeybindsPage.qml | niriConfigPath | setting, keybindRefresh | LAPTOP_FEATURES; test_laptop_features |
| `behavior`: BehaviorPage.qml | batterySaverBrightness and snapshot.batterySaver; lyricsEnabled/Online/Mode/Follow, activityLyrics; bluetoothPairing; peripheralBatteryAlerts/Threshold; quickNotes, audioVisualizer, batteryDetails, privacyIndicators, dndWhileSharing; recordingEnabled/Folder/Encoder/Audio/Format/Codec/Fps/Bitrate; captureEditor; fileSearchEnabled/Roots; launcherRanking, terminal; osdEnabled/Position/Layout/Output/Margin | batterySaver, launcherHistoryClear, setting, settingsExport, settingsImport | CONFIGURATION, FEATURE_PORTS, VALIDATION; test_battery_saver*, test_recording, test_lyrics_modes, test_launcher_history, test_ports, test_settings |
| `about`: AboutPage.qml | UpdateState.state, no persistent preference | separate updater process inspect/check/update/bootstrap (not DesktopBackend) | INSTALL, CONFIGURATION; test_shell_update, test_installation |

## Appendix C — IPC and shortcuts

**`shell` target** (`shell.qml:25–55`, 13 functions): `toggle(panel)`, `desktopEdit()`, `close()`, `mirrorStatus()`, `mirrorStart(source,target)`, `mirrorStop()`, `idleStatus()`, `mediaStatus()`, `nightLightStatus()`, `retryNightLight()`, `capture(mode)`, `refresh()`, `authenticationStatus()`. Mirror mutation functions return submission bool, not completed hardware result. Status functions return JSON string except authenticationStatus returns text.

**`settings` target** (`SettingsApplication.qml:18–28`, 2 functions): `openPage(page)` returns visible-window confirmation; `startupPending()` distinguishes loading instance from stale/broken handler. `scripts/settings.sh:35–70` relies on this exact contract: Quickshell 0.3.2 exit 0 alone is not success, and a cold loading instance must be reused rather than killed.

Fixture-only IPC, not public feature APIs: `authFixture` (authentication-demo.qml), `captureFixture` (capture-demo.qml), `featuresFixture` (native-features-demo.qml), `upgradesFixture` (upgrades-demo.qml). settings-demo uses the production settings target. Tests also inject temporary IPC handlers into copied QML.

**niri integration** (`config/niri/lme-shell.kdl:21–46`): Mod+Shift+A activity; Mod+V clipboard; Mod+Tab native niri overview; Mod+Shift+Tab shell workspace board; Mod+Space launcher; Mod+A control; Mod+N notifications; Mod+Comma standalone settings; Mod+Shift+E power. All shell actions invoke `quickshell -c lme-shell ipc call shell toggle ...`.

Optional `media-keys.kdl`: XF86AudioRaiseVolume/LowerVolume/Mute/MicMute → wpctl; XF86MonBrightnessUp/Down → brightnessctl; XF86AudioPlay/Next/Prev → playerctl; Super+L → swaylock; Print/Ctrl+Print/Alt+Print → native niri screenshots. Optional `capture-keys.kdl`: same Print keys → shell capture area/screen/window instead; these two fragments explicitly warn against duplicate Print definitions. SettingsView local shortcuts: Ctrl+F search, Alt+Left history, Escape clears search/closes. Topbar gestures are the configurable separate barGestures map, not niri keybinds.

## Appendix D — Python module boundaries

| File (lines) | Responsibility / current boundary | Internal dependencies |
|---|---|---|
| `audio_visualizer.py` (68) | Pure bounded spectrum `frame`; CLI owns temporary Cava config and child. | none |
| `battery_info.py` (38) | Telemetry calculations separated into `number`, `battery_details`, `aggregate`; read callback injected. | none |
| `battery_saver.py` (286) | Validated journal + reversible state machine, callbacks for hardware and direct display apply helper; cross-process lock. | `display_control`:13 |
| `bluetooth_agent.py` (283) | Separate Gio/GLib system-bus agent, async Pair/discovery; pure PIN/passkey validation; explicit dependency exception. | `peripheral_battery`:14 |
| `charge_control.py` (147) | Privilege boundary and sysfs controller; helper main accepts only85/100/status; controller validates/rolls back hardware writes. | none |
| `clipboard.py` (324) | Separate History + capture watcher management + JSON command server; content validation and bounded persistence. | none |
| `desktop_backend.py` (2221) | Composition, settings schema/storage, app desktop parsing, low-level probes, command dispatch, caches, state serialization and event loop. | `desktop_widgets`:32, `charge_control`:33, `weather`:34, `desktop_features`:35, `display_control`:37, `system_monitor`:38, `idle_control`:39, `niri_keybinds`:40, `night_light`:41, `screen_capture`:42, `privacy`:43, `clipboard`:44, `screen_recording`:45, `display_mirror`:46, `file_search`:47, `wallpaper_palette`:49, `battery_info`:50, `peripheral_battery`:51, `settings_transfer`:52, `liquid_glass`:53, `wallpaper`:54, `launcher_history`:55, `launchpad`:56, `image_utilities`:57, `battery_saver`:58 |
| `desktop_features.py` (203) | Generic calculator, appearance/theme/bar/control-grid validation and local wallpaper traversal colocated; JSON catalogs reused. | none |
| `desktop_widgets.py` (34) | Pure record validation and field-level merge helper. | none |
| `display_control.py` (203) | Pure output/layout parsing plus apply/preview/watchdog; also hosts generic atomic JSON/locks used by unrelated domains. | `desktop_backend`:197 |
| `display_mirror.py` (80) | Owned wl-mirror window lifecycle, output validation, child error logs. | none |
| `file_search.py` (39) | Root validation + bounded cancellable filesystem traversal; injected Event and hard bounds. | none |
| `idle_control.py` (166) | Pure profile validation/argv generation + owned swayidle, ready-fd lock handshake + child supervision. | none |
| `image_utilities.py` (179) | Pure gowall argv validation + isolated preview/cache lease, output export/apply, Launchpad setup bridge. | `wallpaper`:13 |
| `launcher_history.py` (93) | Local scoring/persistence with file lock and bounded cache; scoring and disk I/O in same class. | `display_control`:12 |
| `launchpad.py` (74) | Pure command-entry validation + detached user job execution/logging; intentionally independent of managed internal workers. | none |
| `liquid_glass.py` (45) | JSON controls schema/validator + explicit generated compositor-wide blur snippet (no niri config overwrite). | none |
| `lyrics.py` (132) | Pure LRC/track parsing + bounded embedded/local/cache/LRCLIB lookup; opener/time injectable; separate CLI. | `display_control`:15 |
| `managed_command.py` (59) | Linux parent-death/child-tree supervisor for long gowall calls. | `idle_control`:12 |
| `night_light.py` (107) | Pure clock/solar/schedule calculations + owned wlsunset lifecycle; parent-death helper reused from idle. | none |
| `niri_keybinds.py` (130) | KDL tokenizer/tree walker + bounded include filesystem reader. | none |
| `peripheral_battery.py` (66) | Pure identities/kind/merge + callback-based BlueZ normalization and kernel supply read. | none |
| `privacy.py` (37) | Pure PipeWire JSON classification; backend owns pw-dump sampling. | none |
| `screen_capture.py` (195) | Image/header validation + niri capture session; annotation editor selection, flatten/export/OCR lifecycle; uses clipboard image-type helper. | `clipboard`:13 |
| `screen_recording.py` (218) | Owned recorder preparation/state/validation, sysfs encoder candidates, external FFmpeg probes, audio routing, mux finalize; runner injected but direct child Popen. | none |
| `settings_transfer.py` (61) | Portable whitelist, validated document serialization/read/write; validator/defaults callback injection. | `desktop_features`:6 |
| `shell_update.py` (202) | Separate guarded Git/archive updater controller and CLI, stdlib. | none |
| `system_monitor.py` (83) | On-demand bounded proc sampler; clock/proc injectable, parser and reads mixed per row. | none |
| `wallpaper.py` (244) | Pure validator/query/argv helpers + awww startup, shared lock, per-output restore, playlist schedule; preferences object injected. | none |
| `wallpaper_palette.py` (49) | Pure Matugen color JSON mapping/validation + isolated dry-run subprocess adapter. | `desktop_features`:7 |
| `weather.py` (203) | Pure location validation + URL/network parsing, dedicated worker/cache/backoff; opener/clock/executor injectable. | none |

## Appendix E — Backend commands and state

<details>
<summary>89 explicit live action IDs and allowed Settings context</summary>

| Action | Source line | Allowed in standalone Settings |
|---|---:|---|
| `appearanceApply` | 1991 | yes |
| `appearanceDelete` | 1991 | yes |
| `appearanceSave` | 1991 | yes |
| `batterySaver` | 1609 | yes |
| `bluetoothDevice` | 1928 | no |
| `bluetoothToggle` | 1926 | no |
| `brightness` | 1918 | no |
| `calculate` | 1806 | no |
| `captureAnnotate` | 1660 | no |
| `captureClose` | 1650 | no |
| `captureExport` | 1655 | no |
| `captureLanguages` | 1654 | no |
| `captureOcr` | 1668 | no |
| `chargeMode` | 1816 | no |
| `controlsRefresh` | 1680 | no |
| `copyText` | 1809 | no |
| `desktopEdit` | 1971 | yes |
| `displayApply` | 1790 | yes |
| `displayConfirm` | 1796 | yes |
| `displayRefresh` | 1787 | yes |
| `displayRevert` | 1796 | yes |
| `fileOpen` | 1732 | no |
| `fileSearch` | 1721 | no |
| `focusWindow` | 1874 | no |
| `glassBlurApply` | 1689 | yes |
| `gowallApply` | 1767 | yes |
| `gowallGenerate` | 1767 | yes |
| `gowallSave` | 1767 | yes |
| `gowallSetup` | 1767 | yes |
| `gowallThemes` | 1767 | yes |
| `idleInhibit` | 1703 | no |
| `idleRefresh` | 1694 | yes |
| `imageAnnotate` | 1651 | no |
| `keybindRefresh` | 1686 | yes |
| `launch` | 1853 | no |
| `launcherHistoryClear` | 1871 | yes |
| `launchpadRun` | 1850 | yes |
| `lock` | 1940 | no |
| `logout` | 1949 | no |
| `micMute` | 1915 | no |
| `micVolume` | 1911 | no |
| `mirrorRefresh` | 1615 | yes |
| `mirrorStart` | 1615 | yes |
| `mirrorStop` | 1615 | yes |
| `monitor` | 1681 | no |
| `moveWindow` | 1877 | no |
| `mute` | 1908 | no |
| `nativeOverview` | 1886 | no |
| `nightLightRefresh` | 1636 | yes |
| `notesInit` | 1758 | no |
| `notificationSave` | 1801 | no |
| `openSettings` | 1976 | no |
| `paletteApply` | 1749 | yes |
| `palettePreset` | 1739 | yes |
| `palettePreview` | 1744 | yes |
| `paletteReset` | 1755 | yes |
| `platformRefresh` | 1691 | yes |
| `powerProfile` | 1936 | no |
| `poweroff` | 1955 | no |
| `reboot` | 1955 | no |
| `recordStart` | 1707 | no |
| `recordStop` | 1720 | no |
| `refresh` | 1843 | yes |
| `screenshot` | 1943 | no |
| `screenshotArea` | 1943 | no |
| `screenshotWindow` | 1943 | no |
| `setting` | 1964 | yes |
| `settingsExport` | 1759 | yes |
| `settingsImport` | 1762 | yes |
| `suspend` | 1955 | no |
| `volume` | 1900 | no |
| `wallpaper` | 1958 | yes |
| `wallpaperEnsure` | 1780 | yes |
| `wallpaperNext` | 1958 | yes |
| `wallpaperResetOutput` | 1958 | yes |
| `wallpaperScan` | 1785 | yes |
| `wallpaperStatus` | 1775 | yes |
| `weatherDetect` | 1831 | yes |
| `weatherRefresh` | 1834 | no |
| `weatherSearch` | 1828 | yes |
| `weatherSelect` | 1837 | yes |
| `wifiConnect` | 1814 | no |
| `wifiDisconnect` | 1814 | no |
| `wifiForget` | 1814 | no |
| `wifiSaved` | 1814 | no |
| `wifiScan` | 1814 | no |
| `wifiToggle` | 1922 | no |
| `wifiWatch` | 1674 | no |
| `workspace` | 1889 | no |

Internal automatically queued `wallpaperCycle` also appears in feature_jobs and completion handling, not as a public action.

Demo routing mirrors many live action names through a separate conditional tree, plus `action.startswith("appearance")` and `action.startswith("gowall")`; it is not derived from live routing. No audit assumption that demo must perform hardware effects.

</details>

The constructor initializes these 62 state/dependency fields (not all are public snapshot fields):

`demo`, `settings_only`, `shell_entry`, `manage_idle`, `runner`, `preferences`, `applications`, `weather`, `weather_fetch`, `charger`, `charge_executor`, `charge_job`, `feature_executor`, `feature_jobs`, `wallpapers`, `launcher_history`, `launchpad`, `image_utilities`, `wallpaper_daemon`, `wallpaper_library`, `displays`, `palette_preview`, `file_search`, `file_search_cancel`, `monitor_enabled`, `wifi_watching`, `monitor`, `idle_control`, `idle_state`, `keybinds`, `night_light`, `night_state`, `capture`, `recorder`, `mirror`, `mirror_state`, `platform`, `display_control`, `notification_path`, `notification_history`, `apps`, `last_app_scan`, `last_cpu`, `system_cache`, `last_system_sample`, `privacy_cache`, `last_privacy_sample`, `bluetooth_cache`, `peripheral_cache`, `last_bluetooth_sample`, `sampled_bluetooth_adapter`, `power_cache`, `last_power_sample`, `power_profile_provider`, `battery_saver`, `battery_saver_state`, `result_sequence`, `result_unemitted`, `last_result`, `niri`, `proc`, `sysfs`.

## Appendix F — Settings key inventory

These are the exact top-level default keys, grouped for review only. Nested schemas remain in their current validators/catalogs. This table does not change defaults or export policy.

| Domain | Keys |
| --- | --- |
| Identity / appearance | `accent`, `appearanceProfiles`, `density`, `glassSelection`, `language`, `liquidGlass`, `opacity`, `shellName`, `surfaceStyle` |
| Motion | `animatedTabs`, `animations`, `motionBounce`, `motionPreset`, `motionSpeed`, `pointerRipple`, `shapeMorph`, `springMotion` |
| Element / font controls | `colorPicker`, `fontOverrides`, `fontPicker`, `fontSize`, `themeOverrides` |
| Top bar | `barBlur`, `barBorderWidth`, `barCorners`, `barEdge`, `barEdgeMargin`, `barFontSize`, `barGestures`, `barHeight`, `barIslandStyles`, `barLayout`, `barSideMargin`, `barStyle` |
| Activity Island | `activityCompactMaxWidth`, `activityEnabled`, `activityPopupMaxHeight`, `activityPopupMaxWidth` |
| Media / lyrics | `activityLyrics`, `audioVisualizer`, `lyricsEnabled`, `lyricsFollow`, `lyricsMode`, `lyricsOnline`, `mediaControls`, `mediaShapes`, `mediaStability`, `mediaWave` |
| Notifications / privacy | `dndUntil`, `dndWhileSharing`, `notificationBodySize`, `notificationBorderWidth`, `notificationIdleAnimation`, `notificationIdleSpeed`, `notificationMargin`, `notificationMutedApps`, `notificationOpacity`, `notificationPadding`, `notificationPosition`, `notificationRadius`, `notificationTitleSize`, `notificationWidth`, `privacyIndicators` |
| Desktop / notes / tasks | `desktopEnabled`, `desktopShapeCount`, `desktopShapeOpacity`, `desktopShapeRotation`, `desktopShapeScale`, `desktopShapeSpeed`, `desktopShapeStyle`, `desktopShapes`, `desktopWidgets`, `quickNotes`, `tasks` |
| Wallpaper / palette | `paletteContrast`, `paletteMode`, `palettePreset`, `paletteScheme`, `paletteSource`, `wallpaper`, `wallpaperFillColor`, `wallpaperFilter`, `wallpaperFolder`, `wallpaperOutputs`, `wallpaperPalette`, `wallpaperPlaylist`, `wallpaperPlaylistEnabled`, `wallpaperPlaylistInterval`, `wallpaperPlaylistOutput`, `wallpaperPlaylistPaused`, `wallpaperPlaylistShuffle`, `wallpaperResize`, `wallpaperTransition`, `wallpaperTransitionAngle`, `wallpaperTransitionBezier`, `wallpaperTransitionDuration`, `wallpaperTransitionFps`, `wallpaperTransitionPosition`, `wallpaperTransitionStep`, `wallpaperTransitionWave` |
| Control Center | `controlGrid`, `controlLayout`, `controlWidth` |
| Displays / mirroring | `displayLayout`, `mirroringEnabled` |
| Night Light | `nightLightEnabled`, `nightLightEnd`, `nightLightMode`, `nightLightStart`, `nightLightTemperature` |
| OSD | `osdEnabled`, `osdLayout`, `osdMargin`, `osdOutput`, `osdPosition` |
| Idle / power | `batteryDetails`, `batterySaverBrightness`, `idleEnabled`, `idleLockBeforeSleep`, `idleProfiles` |
| Peripheral batteries | `peripheralBatteryAlerts`, `peripheralBatteryThreshold` |
| Recording / capture | `captureEditor`, `recordingAudio`, `recordingBitrate`, `recordingCodec`, `recordingEnabled`, `recordingEncoder`, `recordingFolder`, `recordingFormat`, `recordingFps` |
| Launcher / Launchpad / files | `fileSearchEnabled`, `fileSearchRoots`, `launcherRanking`, `launchpadEnabled`, `launchpadEntries`, `terminal` |
| Weather | `weatherAutoLocation`, `weatherLocation`, `weatherUnit` |
| Clipboard | `clipboardEnabled`, `clipboardImages`, `clipboardLimit` |
| Bluetooth | `bluetoothAdapter`, `bluetoothPairing` |
| Host configuration | `niriConfigPath`, `popupBlur` |

## Appendix G — Complete QML inventory

<details>
<summary>All 134 QML files under qml/</summary>

Ownership groups are descriptive, not a claim that each directory is already independent. Feature mappings above identify backend/settings/test interactions.

| File | Lines | Current role group |
| --- | ---: | --- |
| `qml/auth/AuthenticationAgent.qml` | 18 | Authentication UI |
| `qml/auth/AuthenticationDialog.qml` | 122 | Authentication UI |
| `qml/auth/AuthenticationWindow.qml` | 45 | Authentication UI |
| `qml/bar/ActivityButton.qml` | 34 | Bar registry / renderer / gestures |
| `qml/bar/BarGestures.qml` | 58 | Bar registry / renderer / gestures |
| `qml/bar/BarGroup.qml` | 53 | Bar registry / renderer / gestures |
| `qml/bar/BarModule.qml` | 152 | Bar registry / renderer / gestures |
| `qml/bar/BarRegistry.qml` | 33 | Bar registry / renderer / gestures |
| `qml/bar/BarSurface.qml` | 28 | Bar registry / renderer / gestures |
| `qml/bar/ModuleGestures.qml` | 32 | Bar registry / renderer / gestures |
| `qml/components/AnnotationCanvas.qml` | 70 | Shared component / visual primitive |
| `qml/components/AudioVisualizer.qml` | 30 | Shared component / visual primitive |
| `qml/components/BluetoothPairing.qml` | 67 | Shared component / visual primitive |
| `qml/components/ColorMotion.qml` | 9 | Shared component / visual primitive |
| `qml/components/ColorPicker.qml` | 69 | Shared component / visual primitive |
| `qml/components/ControlGrid.qml` | 164 | Shared component / visual primitive |
| `qml/components/ControlSlider.qml` | 70 | Shared component / visual primitive |
| `qml/components/ExpressiveField.qml` | 24 | Shared component / visual primitive |
| `qml/components/ExpressiveSwitch.qml` | 35 | Shared component / visual primitive |
| `qml/components/FontPicker.qml` | 63 | Shared component / visual primitive |
| `qml/components/GlassBackdrop.qml` | 53 | Shared component / visual primitive |
| `qml/components/GlassMaterial.qml` | 121 | Shared component / visual primitive |
| `qml/components/GlassOptics.qml` | 55 | Shared component / visual primitive |
| `qml/components/GlassPanel.qml` | 25 | Shared component / visual primitive |
| `qml/components/HistoryChart.qml` | 40 | Shared component / visual primitive |
| `qml/components/IconButton.qml` | 65 | Shared component / visual primitive |
| `qml/components/LabelText.qml` | 15 | Shared component / visual primitive |
| `qml/components/LiquidButton.qml` | 64 | Shared component / visual primitive |
| `qml/components/LiquidComboBox.qml` | 135 | Shared component / visual primitive |
| `qml/components/LiquidFeedback.qml` | 75 | Shared component / visual primitive |
| `qml/components/LiquidSlider.qml` | 45 | Shared component / visual primitive |
| `qml/components/LyricsSession.qml` | 105 | Shared component / visual primitive |
| `qml/components/LyricsView.qml` | 102 | Shared component / visual primitive |
| `qml/components/MediaActions.qml` | 62 | Shared component / visual primitive |
| `qml/components/MediaAmbient.qml` | 57 | Shared component / visual primitive |
| `qml/components/MediaPresentation.qml` | 28 | Shared component / visual primitive |
| `qml/components/MediaProgress.qml` | 92 | Shared component / visual primitive |
| `qml/components/MirrorControls.qml` | 90 | Shared component / visual primitive |
| `qml/components/MorphShape.qml` | 8 | Shared component / visual primitive |
| `qml/components/MotionAnimation.qml` | 9 | Shared component / visual primitive |
| `qml/components/MotionPopup.qml` | 83 | Shared component / visual primitive |
| `qml/components/MotionValue.qml` | 15 | Shared component / visual primitive |
| `qml/components/NotificationCard.qml` | 87 | Shared component / visual primitive |
| `qml/components/NotificationEmblem.qml` | 25 | Shared component / visual primitive |
| `qml/components/OSDWindow.qml` | 60 | Shared component / visual primitive |
| `qml/components/PalettePicker.qml` | 52 | Shared component / visual primitive |
| `qml/components/PopupBackdrop.qml` | 22 | Shared component / visual primitive |
| `qml/components/PopupElasticity.qml` | 56 | Shared component / visual primitive |
| `qml/components/PrivacyIndicator.qml` | 19 | Shared component / visual primitive |
| `qml/components/ShellIcon.qml` | 155 | Shared component / visual primitive |
| `qml/components/ShellText.qml` | 15 | Shared component / visual primitive |
| `qml/components/SlideLoader.qml` | 150 | Shared component / visual primitive |
| `qml/components/SpringMotion.qml` | 109 | Shared component / visual primitive |
| `qml/components/StatusWindow.qml` | 46 | Shared component / visual primitive |
| `qml/components/StretchIndicator.qml` | 54 | Shared component / visual primitive |
| `qml/components/SurfaceBlurRegion.qml` | 132 | Shared component / visual primitive |
| `qml/components/WaveProgress.qml` | 82 | Shared component / visual primitive |
| `qml/components/shapes/ShapeCanvas.qml` | 127 | Shared component / visual primitive |
| `qml/panels/ActivityCard.qml` | 105 | Feature surface / host |
| `qml/panels/ActivityIsland.qml` | 50 | Feature surface / host |
| `qml/panels/Agenda.qml` | 34 | Feature surface / host |
| `qml/panels/AudioMixer.qml` | 70 | Feature surface / host |
| `qml/panels/Bar.qml` | 39 | Feature surface / host |
| `qml/panels/CalendarWidget.qml` | 48 | Feature surface / host |
| `qml/panels/ChargingWidget.qml` | 55 | Feature surface / host |
| `qml/panels/ClipboardPanel.qml` | 174 | Feature surface / host |
| `qml/panels/ControlCenter.qml` | 125 | Feature surface / host |
| `qml/panels/ControlDashboard.qml` | 339 | Feature surface / host |
| `qml/panels/DesktopAmbient.qml` | 35 | Feature surface / host |
| `qml/panels/DesktopCanvas.qml` | 46 | Feature surface / host |
| `qml/panels/DesktopCard.qml` | 86 | Feature surface / host |
| `qml/panels/DesktopPreview.qml` | 57 | Feature surface / host |
| `qml/panels/DesktopWidgetWindow.qml` | 59 | Feature surface / host |
| `qml/panels/DeviceControls.qml` | 110 | Feature surface / host |
| `qml/panels/Launcher.qml` | 128 | Feature surface / host |
| `qml/panels/LaunchpadEditor.qml` | 91 | Feature surface / host |
| `qml/panels/LaunchpadPanel.qml` | 21 | Feature surface / host |
| `qml/panels/NotificationCenter.qml` | 145 | Feature surface / host |
| `qml/panels/NotificationToasts.qml` | 97 | Feature surface / host |
| `qml/panels/Overview.qml` | 170 | Feature surface / host |
| `qml/panels/PeripheralBatteryList.qml` | 52 | Feature surface / host |
| `qml/panels/PowerMenu.qml` | 133 | Feature surface / host |
| `qml/panels/QuickNotes.qml` | 34 | Feature surface / host |
| `qml/panels/RecorderWidget.qml` | 33 | Feature surface / host |
| `qml/panels/ScreenshotEditor.qml` | 141 | Feature surface / host |
| `qml/panels/SettingsPanel.qml` | 9 | Feature surface / host |
| `qml/panels/SystemMonitor.qml` | 120 | Feature surface / host |
| `qml/panels/TasksWidget.qml` | 69 | Feature surface / host |
| `qml/panels/TimerWidget.qml` | 42 | Feature surface / host |
| `qml/panels/TrayMenu.qml` | 107 | Feature surface / host |
| `qml/panels/WeatherWidget.qml` | 78 | Feature surface / host |
| `qml/panels/WifiPanel.qml` | 23 | Feature surface / host |
| `qml/panels/WifiWidget.qml` | 106 | Feature surface / host |
| `qml/services/ActivityState.qml` | 40 | Shared service / process lifecycle |
| `qml/services/BluetoothState.qml` | 57 | Shared service / process lifecycle |
| `qml/services/ClipboardState.qml` | 83 | Shared service / process lifecycle |
| `qml/services/ControlRegistry.qml` | 17 | Shared service / process lifecycle |
| `qml/services/DesktopState.qml` | 27 | Shared service / process lifecycle |
| `qml/services/FocusTimer.qml` | 45 | Shared service / process lifecycle |
| `qml/services/GlassState.qml` | 35 | Shared service / process lifecycle |
| `qml/services/NotesState.qml` | 51 | Shared service / process lifecycle |
| `qml/services/Notifications.qml` | 209 | Shared service / process lifecycle |
| `qml/services/OSDManager.qml` | 21 | Shared service / process lifecycle |
| `qml/services/PeripheralBatteries.qml` | 33 | Shared service / process lifecycle |
| `qml/services/PrivacyState.qml` | 31 | Shared service / process lifecycle |
| `qml/services/ShellState.qml` | 220 | Shared service / process lifecycle |
| `qml/services/UpdateState.qml` | 46 | Shared service / process lifecycle |
| `qml/services/VisualizerState.qml` | 34 | Shared service / process lifecycle |
| `qml/settings/AboutPage.qml` | 51 | Settings page / host / control |
| `qml/settings/AppearancePage.qml` | 228 | Settings page / host / control |
| `qml/settings/AwwwSettings.qml` | 50 | Settings page / host / control |
| `qml/settings/BehaviorPage.qml` | 253 | Settings page / host / control |
| `qml/settings/ClipboardPage.qml` | 32 | Settings page / host / control |
| `qml/settings/ControlLayoutPage.qml` | 92 | Settings page / host / control |
| `qml/settings/DesktopPage.qml` | 94 | Settings page / host / control |
| `qml/settings/DisplayPage.qml` | 124 | Settings page / host / control |
| `qml/settings/ElementsPage.qml` | 97 | Settings page / host / control |
| `qml/settings/GowallSettings.qml` | 88 | Settings page / host / control |
| `qml/settings/IdlePage.qml` | 67 | Settings page / host / control |
| `qml/settings/KeybindsPage.qml` | 54 | Settings page / host / control |
| `qml/settings/LiquidGlassSettings.qml` | 84 | Settings page / host / control |
| `qml/settings/NightLightPage.qml` | 67 | Settings page / host / control |
| `qml/settings/NotificationsPage.qml` | 125 | Settings page / host / control |
| `qml/settings/PreferenceSwitch.qml` | 23 | Settings page / host / control |
| `qml/settings/SettingsApplication.qml` | 69 | Settings page / host / control |
| `qml/settings/SettingsCard.qml` | 27 | Settings page / host / control |
| `qml/settings/SettingsRegistry.qml` | 27 | Settings page / host / control |
| `qml/settings/SettingsView.qml` | 155 | Settings page / host / control |
| `qml/settings/TopBarPage.qml` | 337 | Settings page / host / control |
| `qml/settings/UtilitiesPage.qml` | 22 | Settings page / host / control |
| `qml/settings/WallpaperPage.qml` | 150 | Settings page / host / control |
| `qml/settings/WallpaperPlaylistSettings.qml` | 68 | Settings page / host / control |
| `qml/settings/WeatherPage.qml` | 87 | Settings page / host / control |
| `qml/theme/Theme.qml` | 236 | Effective theme / tokens |

</details>

## Appendix H — JavaScript, catalogs and shaders

<details>
<summary>All 30 other files under qml/</summary>

`build-shaders.sh` compiles GLSL into the committed adjacent QSB packages. `check.sh` does not rebuild shaders. Binary packages are mapped to their source/consumer rather than treated as readable source.

| File | Bytes | Role / source | Integration / checks |
|---|---:|---|---|
| `qml/bar/qmldir` | 245 | Relative-import type catalog: BarRegistry/BarGestures singletons, BarModule/BarGroup/BarSurface/ActivityButton/ModuleGestures. | Consumed by panels/Bar and Settings TopBarPage; bar/gesture/styling native tests. |
| `qml/components/ControlGridLogic.js` | 1480 | Pure overlap, one-tile move/same-footprint swap and pack functions; widths from catalog. | components/ControlGrid.qml:5; tests/test_control_grid.py validates non-reflow moves. MIT DMS overlap attribution retained. |
| `qml/components/JellyGeometry.js` | 5423 | Pure normalized vertex/triangle warp, rounded outline and scanline strips for compositor blur. Explicitly matches 16x16 popup-jelly.vert mesh. | components/SurfaceBlurRegion.qml:8; tests/test_jelly_v2.py checks concave clipping and GL/native mask-to-shader consistency. Keep shader/model updates together. |
| `qml/components/shaders/liquid-glass.frag` | 12769 | Liquid rim/refraction/tint/lighting fragment GLSL with Serpantinum AGPL header. | GlassOptics.qml:54 consumes compiled counterpart; tests/test_glass_controls.py, test_liquid_style.py, test_glass_hover.py, test_selection_lens.py cover shader/material state or rendered pixels. |
| `qml/components/shaders/liquid-glass.frag.qsb` | 27555 | Committed Qt shader package compiled from liquid-glass.frag. | Runtime GlassOptics ShaderEffect; rebuild via scripts/build-shaders.sh; GPU assertions are opt-in private-session tests. |
| `qml/components/shaders/popup-jelly.frag` | 423 | Minimal source texture sampling/opacity fragment GLSL, matching jelly uniform layout. | PopupElasticity.qml:50 compiled source; tests/test_jelly_v2.py GL silhouette and bounds coverage. |
| `qml/components/shaders/popup-jelly.frag.qsb` | 1322 | Committed Qt shader package compiled from popup-jelly.frag. | PopupElasticity ShaderEffect fragment stage; rebuild via scripts/build-shaders.sh. |
| `qml/components/shaders/popup-jelly.vert` | 1182 | Vertex deformation/fit math and uniform layout for the Jelly popup layer. | PopupElasticity.qml:49 compiled source; JellyGeometry.js duplicates required CPU contour transform; tests/test_jelly_v2.py. |
| `qml/components/shaders/popup-jelly.vert.qsb` | 2559 | Committed Qt shader package compiled from popup-jelly.vert. | PopupElasticity ShaderEffect vertex stage; rebuild via scripts/build-shaders.sh. |
| `qml/components/shaders/ripple.frag` | 2128 | Rounded-clip pointer-origin ripple mask/color shader, retained DCommon MIT attribution. | LiquidFeedback.qml:44 compiled source; tests/test_personalization.py exercises ripple progress/opacity and cleanup; no dedicated fragment-pixel assertion was identified. |
| `qml/components/shaders/ripple.frag.qsb` | 4075 | Committed Qt shader package compiled from ripple.frag. | LiquidFeedback ShaderEffect; software path uses its Canvas fallback; rebuild via scripts/build-shaders.sh. |
| `qml/components/shaders/wave-progress.frag` | 2494 | Animated sinusoidal progress shader, retained DCommon MIT attribution. | WaveProgress.qml:42 compiled source; tests/test_activity.py real MPRIS waves and tests/test_media_controls.py control behavior. |
| `qml/components/shaders/wave-progress.frag.qsb` | 4734 | Committed Qt shader package compiled from wave-progress.frag. | WaveProgress ShaderEffect; rebuild via scripts/build-shaders.sh. |
| `qml/components/shapes/LICENSE` | 11357 | Retained Apache-2.0 license for imported rounded-polygon JS geometry. | THIRD_PARTY.md:95 and third_party/iNiR-NOTICE link provenance; preserve alongside library during moves. |
| `qml/components/shapes/Polygons.js` | 652 | Memoized circle/flower/square RoundedPolygon factories, consumes rounding and polygon library. | components/MorphShape.qml:3-6; tests/test_motion_ports.py shape/morph coverage. |
| `qml/components/shapes/shapes/corner-rounding.js` | 364 | CornerRounding radius/smoothing value object. | Polygons.js and rounded-polygon/rounded-corner; imported library; tests/test_motion_ports.py transitively. |
| `qml/components/shapes/shapes/cubic.js` | 11076 | Cubic and MutableCubic Bezier geometry; imports point and math utilities. | Rounded polygons, features, morph and measurement; tests/test_motion_ports.py transitively. |
| `qml/components/shapes/shapes/feature-mapping.js` | 4788 | Maps polygon corner/edge features and normalized progress between morph endpoints. | morph.js and polygon-measure.js; tests/test_motion_ports.py transitively. |
| `qml/components/shapes/shapes/feature.js` | 2110 | Feature/Edge/Corner cubic-group model. | rounded-polygon.js, polygon-measure.js, feature-mapping.js; tests/test_motion_ports.py transitively. |
| `qml/components/shapes/shapes/float-mapping.js` | 2288 | DoubleMapper and circular/normalized progress interpolation. | feature-mapping.js; tests/test_motion_ports.py transitively. |
| `qml/components/shapes/shapes/morph.js` | 3453 | Morph matches and interpolates rounded polygon endpoint cubics using measurement and feature mapping. | shapes/ShapeCanvas.qml:7, tests/test_motion_ports.py imports directly. |
| `qml/components/shapes/shapes/point.js` | 2874 | Point value/vector geometry and point factory. | cubic.js, measurement, rounded-corner, utilities and mapping; tests/test_motion_ports.py transitively. |
| `qml/components/shapes/shapes/polygon-measure.js` | 7739 | MeasuredPolygon, MeasuredCubic and LengthMeasurer for normalized curve-length matching. | morph.js; tests/test_motion_ports.py transitively. |
| `qml/components/shapes/shapes/rounded-corner.js` | 8358 | RoundedCorner curve construction for requested radius and smoothing. | rounded-polygon.js; tests/test_motion_ports.py transitively. |
| `qml/components/shapes/shapes/rounded-polygon.js` | 15269 | RoundedPolygon construction, normalization and feature/cubic geometry. | Polygons.js and morph.js; tests/test_motion_ports.py transitively. |
| `qml/components/shapes/shapes/utils.js` | 1996 | Geometry tolerances, convexity, interpolation, distances, radial conversion, clamping and modulo. | Internal rounded-polygon library; tests/test_motion_ports.py transitively. |
| `qml/services/LauncherSearch.js` | 2044 | Stateless fuzzy text ranking and usage/recency tiebreaks; .pragma library. | panels/Launcher.qml:8, panels/LaunchpadEditor.qml:8; tests/test_launcher_history.py, tests/test_local_qml.py. |
| `qml/services/qmldir` | 677 | Declares 15 services as singletons for relative QML imports. | Shell/settings/components imports; local QML fixtures exercise actual singleton scope. |
| `qml/settings/qmldir` | 944 | Declares SettingsRegistry singleton and 24 Settings view/application/page/control types. | Standalone settings.qml and embedded SettingsPanel; tests/test_settings_startup.py, tests/test_settings.py. |
| `qml/theme/qmldir` | 30 | Declares Theme singleton. | Shared shell and Settings styling; tests/test_liquid_style.py, tests/test_personalization.py. |

</details>

---

_This analysis was performed using the [Balanced Coupling](https://coupling.dev) model by [Vlad Khononov](https://vladikk.com)._
