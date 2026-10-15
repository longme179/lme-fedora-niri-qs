# Attribution and licenses

LME Shell is an original Fedora and niri implementation inspired by the desktop
interaction patterns of [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland).
The upstream reference inspected during development was commit
`c4f0582cbf4ad29607dbf3c20337815de8690b34`. Its root license is GNU GPL version 3.
No end-4 source code, wallpapers, bundled fonts, icons, or installation scripts
have been copied into this project. Original project source is distributed
under GPL-3.0-or-later; the motion adaptation below retains GPL-3.0-only.
The full GNU GPL version 3 license is in [LICENSE](LICENSE).

Quickshell, Qt, niri, and the desktop utilities are external runtime dependencies
with their own licenses. Installing this project does not redistribute them.

The color system follows Dracula Pro's dark, purple-led visual direction. It does
not include purchased Dracula Pro files, wallpapers, fonts, or branding assets.
Palette values are editable locally; users who own a preferred Pro variant can
enter their own color values. The project is unaffiliated with Dracula Pro.

The included wallpaper and hand-drawn shell icons are original artwork. Rounded-polygon geometry and the adapted Canvas are credited in the geometric morph section below. Application
icons are resolved from the user's installed icon theme, and are not bundled.

The modular bar, searchable settings registry and Material design direction also
reference [snowarch/iNiR](https://github.com/snowarch/iNiR), inspected at commit
`48cdcecb0f6089cfbb7019054602eab28e154b3b` (root license: GNU GPL version 3).
These interaction patterns have been implemented independently for LME Shell,
with the compatible motion adaptations described below. No iNiR shaders, bundled
fonts, wallpapers or installation scripts are redistributed.
See [docs/INIR_PORT.md](docs/INIR_PORT.md) for the settings/bar mapping.

Roboto is installed through Fedora's `google-roboto-fonts` package. The project
references it by family name and does not distribute the font files. Small shell
icons are original Canvas drawings; Material Symbols font assets are not bundled.


Wallpaper rendering uses the external [awww](https://codeberg.org/LGFae/awww.git)
client and daemon. No upstream binary or source is bundled. The CLI integration
was checked against release 0.12.1 at
`f66e12a76dbc4c669b2f1375f78bce49f5b19d66` (GNU GPL version 3).

Weather and city search are provided by [Open-Meteo](https://open-meteo.com/),
whose weather data requires attribution under CC BY 4.0. The widget displays
that attribution. Approximate automatic location uses [IPwho.is](https://ipwho.is/).
These are external network services; no provider dataset or assets are bundled.
The implementation uses the providers' public endpoints without an API key.

Clipboard history and the expandable Activity island also reference
[AvengeMedia/DankMaterialShell](https://github.com/AvengeMedia/DankMaterialShell),
inspected at `f372777829212f0db41dc623e7e495e63c8e4341` (MIT), and iNiR at the
revision above. All delivered history, storage, Activity and protocol-test code
is original. Those feature implementations do not redistribute upstream source,
assets or binaries. The later shared motion adaptations are described below.
`wl-clipboard` is an external GPL-3.0-or-later runtime dependency.

The desktop upgrade workflows were reviewed against iNiR notification grouping
and persistence, and DankMaterialShell launcher, network and niri display APIs.
Their implementation source was not vendored. The bundled emoji/symbol names
are generated with Python standard-library `unicodedata`; search aliases are
written for this project. The repository also includes the owner-supplied MIT
Ponytail skill, with its original license declaration preserved.

Shared motion now adapts these upstream implementations:

- [Caelestia StateLayer.qml](https://github.com/caelestia-dots/shell/blob/21a75375bb33123e481e796a74965038847c503d/components/StateLayer.qml),
  plus `components/Anim.qml` and `components/controls/ButtonBase.qml`, at
  `21a75375bb33123e481e796a74965038847c503d` (GPL-3.0). Press/hold/release
  sequencing is adapted in `qml/components/LiquidFeedback.qml` under
  GPL-3.0-only. The implementation uses a bounded flat pill ripple and LME's
  controls; it does not require Caelestia's plugin, shapes or assets.
- [DankMaterialShell Anims.qml](https://github.com/AvengeMedia/DankMaterialShell/blob/a1e6f6d6acae5e0688a4f04bd0e584b201ff6f68/quickshell/Common/Anims.qml)
  at `a1e6f6d6acae5e0688a4f04bd0e584b201ff6f68` (MIT). Expressive fast spatial,
  effects and exit Bézier curves are ported into `qml/theme/Theme.qml`; spatial
  overshoot is scaled by LME's existing bounce preference. Copyright (c) 2025
  Avenge Media LLC. The complete permission/copyright notice is preserved in
  [third_party/DankMaterialShell-LICENSE](third_party/DankMaterialShell-LICENSE).
- iNiR `modules/common/widgets/RippleButton.qml` at the revision above (GPL-3.0)
  informs the hue-preserving transparent hover state and shared feedback.

The ports reuse LME's preferences, controls and panel loader. No upstream binary,
plugin, font or wallpaper is bundled. Native blur remains implemented through
Quickshell/niri's existing compositor protocol.

Night Light also references iNiR's niri/wlsunset workflow. `wlsunset` and
`tesseract` are external runtime tools, not bundled binaries. Sunrise/sunset
calculation uses the approximate algorithm from *Almanac for Computers* (1990),
described in Ed Williams' [Sunrise/Sunset Algorithm](https://edwilliams.org/sunrise_sunset_algorithm.htm).
The Python implementation is original; it is not an astronomical ephemeris or
display calibration system.

`SpringMotion.qml` adapts DMS dank-qml-common at `bd90e4b6f2ec36035fc2cb560acdc0e418f669ac` (MIT, Copyright (c) 2025-2026 Avenge Media LLC). Modified for LME theme/loader lifecycle; full notice: [third_party/DankQmlCommon-LICENSE](third_party/DankQmlCommon-LICENSE).

### Geometric morph

Based on iNiR by snowarch (https://github.com/snowarch/inir), revision `48cdcecb0f6089cfbb7019054602eab28e154b3b`. `ShapeCanvas.qml` is modified for LME (GPL-3.0 with retained iNiR notice); rounded-polygon JS is retained under its Apache-2.0 license in `qml/components/shapes/LICENSE`. The library ports Knugel’s rounded-polygon-ts / AndroidX shape geometry, inherited through end-4. See [third_party/iNiR-NOTICE](third_party/iNiR-NOTICE) and [third_party/iNiR-LICENSE](third_party/iNiR-LICENSE). No upstream branding or assets are copied. Earlier no-vendoring descriptions apply only to the earlier feature implementations.

`StretchIndicator.qml` adapts the independent-edge movement of DCommon `DTabBar.qml` at the DCommon revision above; MIT notice retained. Navigation and controls remain LME implementations.

`FontPicker.qml` adapts installed-family enumeration from DMS `SettingsFontDropdownRow.qml` at `6640a943b30d11407bc868469910dcb0800f3254` (MIT, Copyright (c) 2025 Avenge Media LLC); notice: `third_party/DankMaterialShell-LICENSE`. Search, popup and live-preview integration use LME controls.

Pointer-origin feedback adapts DCommon `DRipple.qml` and retains `ripple.frag` at `bd90e4b6f2ec36035fc2cb560acdc0e418f669ac` (MIT ©2025-2026 Avenge Media LLC). Full notice: `third_party/DankQmlCommon-LICENSE`. Existing Caelestia GPL press/hold/release attribution is preserved.

The HSV/alpha picker workflow references DMS `ColorPickerContent.qml` and DCommon `DSaturationValuePicker.qml`; the LME implementation uses existing controls and does not vendor DMS screen-picking commands.

Privacy classification references DMS `PrivacyService.qml` (6640a943, MIT) and Noctalia `privacy_capture_classification.cpp` (8504aff8, MIT). LME aggregates active streams without the upstream early-return mute issue and reads niri cast events; implementation is original.

Settings transfer references DMS backup validation/rollback workflow (`core/internal/backup/backup.go`, 6640a943, MIT). LME uses validated JSON and existing atomic preference writes, not archive extraction or the Go backend.

Battery health/power/ETA presentation references Noctalia `battery_widget.cpp` / `upower_service.cpp` at 8504aff8 (MIT). LME retains its Linux sysfs backend, with original unit-aware calculation and explicit unavailable values.

OSD placement/output lifecycle references DMS `DOSD.qml` / `OSDManager.qml` (6640a943, MIT) and Noctalia `osd_overlay.cpp` (8504aff8, MIT). LME reuses its spring loader, theme and backend events.

The Cava visualizer lifecycle/configuration references DMS `CavaService.qml` at 6640a943 (MIT). The Python stdlib bridge and ref-counted QML integration are original; Cava is an external runtime package.

Quick notes references DMS `NotepadStorageService.qml` / `NotepadTextEditor.qml` (6640a943, MIT). LME uses an original single-buffer implementation with Quickshell atomic writes; no Markdown/highlighter plugin is bundled.

Wallpaper palette preview references DMS `MatugenPreviewService.qml` and isolated dry-run in `core/internal/matugen/matugen.go` (6640a943, MIT). LME maps validated dark Material roles into its theme, without DMS templates/daemon or Noctalia native renderer. Matugen is an external package.

Launcher file search references DMS `DSearchService.qml` (6640a943, MIT). LME uses original bounded/cancellable Python stdlib traversal and existing launcher results, without DSearch indexing daemon.

Recording workflow references iNiR `scripts/videos/record.sh` / `RecordingOsd.qml` (48cdcecb, GPL-3.0 with NOTICE). The LME manager adapts NVIDIA-first → VAAPI → software fallback for owned processes and existing IPC. Encoder probes run only when capture starts; upstream idle NVIDIA polling and global stop logic are not used. iNiR attribution remains in README/About and `third_party/iNiR-NOTICE`.

External screenshot annotation adapts DMS `quickshell/Services/NiriService.qml::handleScreenshotCaptured` at `a1e6f6d6acae5e0688a4f04bd0e584b201ff6f68` (MIT, Copyright ©2025 Avenge Media LLC; full notice in `third_party/DankMaterialShell-LICENSE`). LME saves its flattened PNG before passing an allowlisted Satty/Swappy argv, retaining edits after session cleanup. MIT and iNiR's GPL version 3 with retained section 7 notice can be combined with LME under GPL version 3; this does not relicense upstream material as "or later". Swappy/Satty and wf-recorder are external programs, not bundled source.


Display mirroring uses the external [wl-mirror](https://github.com/Ferdi265/wl-mirror)
client by Ferdinand Bachmann (GPL-3.0-or-later), inspected at
`89149973c57512b1a66aaf01a9783bd0275e2bc1` with its actual LICENSE. LME's integration follows its
fullscreen-output / fit-scaling examples; no wl-mirror source or binary is bundled.
The existing iNiR dynamic-cast toggle (`modules/bar/UtilButtons.qml`, revision
`48cdcecb0f6089cfbb7019054602eab28e154b3b`) and DMS Hyprland monitor mirroring
(`quickshell/Services/HyprlandService.qml`, revision
`a1e6f6d6acae5e0688a4f04bd0e584b201ff6f68`, MIT) were reviewed. Their backend code
is not copied: dynamic casting changes a portal stream source, while Hyprland's
monitor configuration does not run on niri. Noctalia (`02cb10745d6274e4a696a00308c8ef4cefa7416d`, MIT)
explicitly delegates mirroring to dedicated applications. LME owns one wl-mirror
child process and uses niri's supported xdg-toplevel fullscreen-output request.


Built-in color presets adapt the 35 palette arrays in
[Achno/gowall internal/image/themes.go](https://github.com/Achno/gowall/blob/d8c7e03c4b6844d459292a07dde724bec98f5a4e/internal/image/themes.go)
at `d8c7e03c4b6844d459292a07dde724bec98f5a4e`. Copyright (c) 2024 Achno,
MIT; the full notice is retained in [third_party/gowall-LICENSE](third_party/gowall-LICENSE).
The RGB arrays are adapted to LME's UI roles, with synthesized neutral surfaces
where an image palette has none and readable foregrounds for light/dark sets.
Gowall's PaleNight alpha values of 1 are normalized to opaque role colors; shell
transparency is controlled independently. No Gowall image-processing code or
binary is included. The catalog also retains LME's original Dracula palette.

Matugen's scheme/mode/contrast CLI was inspected at
`9f8c7fd583e44310a642772ff8f13b693949baf2` (4.2.0), with its actual GPLv2 LICENSE.
It remains an external optional dependency; no Matugen code is redistributed.
The integration uses an isolated template-free configuration and dry-run output.

The quick-control canvas adapts the rectangle overlap test from DankMaterialShell
[Common/GridLayout.js](https://github.com/AvengeMedia/DankMaterialShell/blob/d041ffccb0c95f2a4fd5a5d7e75512ce69cfa13d/quickshell/Common/GridLayout.js)
at `d041ffccb0c95f2a4fd5a5d7e75512ce69cfa13d`, Copyright (c) 2025 Avenge Media LLC,
MIT. The adapted JS retains that header; the full license is in
[third_party/DankMaterialShell-LICENSE](third_party/DankMaterialShell-LICENSE).
`Widgets/DEditableGridSlot.qml` informed the raised edit layer and input isolation;
its implementation is not copied. iNiR `modules/sidebarRight/quickToggles/AndroidQuickPanel.qml`
at `48cdcecb0f6089cfbb7019054602eab28e154b3b` (GPLv3) informed the one/two-cell
controls. Noctalia's C++ Control Center at `b6d1c44d44ebaafcc218b9b2e69d8c626278fdbf`
(MIT) was inspected but no C++ code was ported. These references were cloned
outside LME's checkout; they add no new runtime dependency.

The independent slider/control cleanup inspected fresh shallow checkouts of
DankMaterialShell at `c3e93ee39a3a4b79c59076176a44cde389458380` (MIT), particularly
`quickshell/Modules/ControlCenter/Widgets/CcSliderRow.qml` and `AudioSliderRow.qml`.
Their shared row, separate mute action and drag-safe value binding informed LME's
original `ControlSlider.qml`, which reuses its existing slider, IPC and theme.
iNiR's `modules/sidebarRight/quickToggles/androidStyle/AndroidPowerProfileToggle.qml`
at `48cdcecb0f6089cfbb7019054602eab28e154b3b` (GPLv3) informed capability-aware
profile cycling. These implementations were referenced, not copied; LME retains
its existing Fedora D-Bus/CLI backend and adds no runtime package dependency.

Notification appearance and wrapping were reviewed against DankMaterialShell
`quickshell/Modules/Settings/NotificationsTab.qml`,
`Modules/Notifications/NotificationMetrics.qml` and `NotificationCard.qml` at
`a1e6f6d6acae5e0688a4f04bd0e584b201ff6f68` (MIT; actual root LICENSE inspected).
The width-constrained text, wrapping actions and shared card metrics informed
LME's original `NotificationCard.qml`; no DMS notification implementation is copied.
The rotating, visibility-gated emblem references iNiR's
`modules/common/widgets/MaterialLoadingIndicator.qml` at
`48cdcecb0f6089cfbb7019054602eab28e154b3b` (GPLv3 with its retained notice).
LME reuses the already attributed iNiR shape renderer, keeps the bell/text still,
and uses a Qt render-thread rotation instead of upstream's shape/timer sequence.
See `third_party/iNiR-NOTICE` and the existing shape licenses for that renderer.
There are no new bundled libraries or runtime dependencies.

`qml/components/WaveProgress.qml` and `qml/components/shaders/wave-progress.frag` adapt
[DCommon M3WaveProgress.qml](https://github.com/AvengeMedia/dank-qml-common/blob/50ca5ccb4913098b0b67807d9ff7f642e79067b0/DCommon/Widgets/M3WaveProgress.qml)
and `DCommon/Shaders/frag/wave_progress.frag` at
`50ca5ccb4913098b0b67807d9ff7f642e79067b0`, the submodule revision used by the
inspected DMS checkout at `a1e6f6d6acae5e0688a4f04bd0e584b201ff6f68`.
Copyright (c) 2025-2026 Avenge Media LLC, MIT; the source headers and full notice
in `third_party/DankQmlCommon-LICENSE` are retained. LME uses its own theme/motion
settings, removes unused seek-preview segments, insets endpoint markers and adds
a Canvas renderer for Qt's software backend. The compiled shader is included;
developers can rebuild it with `bash scripts/build-shaders.sh`. The frame-based
MPRIS position refresh follows DMS `Widgets/DSeekbar.qml` at the DMS revision
above and reads Quickshell's local playback clock, without frame-rate D-Bus polls.
