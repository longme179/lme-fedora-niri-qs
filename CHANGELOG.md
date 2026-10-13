# Changelog

## Unreleased

- Handle null or malformed weather/search responses with readable errors. Keep
  the last good forecast after a failed refresh and allow missing daily data.
- Move Power/Settings into independent 1×1 canvas tiles, power-profile cycling
  into 2×1, and speaker/microphone/brightness into three 4×1 slider tiles. Add an
  optional Power bar module and follow advertised profile capabilities.
- Share button/card metadata and slider handling; remove the superseded slider
  card and duplicate actions. Keep five card loaders stable across canvas edits,
  lazily instantiate visible controls, and migrate old visibility/positions.
- Keep unrelated canvas controls fixed when editing. Move onto empty cells or
  swap equal-size tiles; incompatible occupied drops cancel instead of repacking.
- Edit quick controls directly in the Control Center with a 4/8 column and 4/8
  row canvas. Snap drag/drop, collision handling, keyboard movement and edge
  scrolling save atomically; Edit mode blocks actions. Keep detailed cards and
  their visibility/size settings, and include canvas layout in portable presets.
- Stop clipboard watchers even when Quickshell kills their Python service during
  reload. Reuse the existing Linux parent-death supervisor instead of leaving
  orphan capture processes behind.
- Generate Matugen 4 wallpaper palettes without an interactive terminal by
  selecting its highest-ranked source color. Keep the Matugen 3 command intact
  and remove terminal color escapes from backend error messages.
- Independently customize Left/Center/Right island corners, fill and outline.
  Connected-bar geometry no longer reshapes the islands; settings transfer keeps
  each surface, and one shared editor switches between the four targets.
- Preview/apply 35 Gowall-derived palettes plus LME Dracula without a Gowall
  runtime dependency. Add Material scheme, dark/light and contrast options;
  reject stale previews and retain manual colors/fonts and island overrides.
- Persist recording audio selection with System audio as the default. Verify
  requested audio tracks with ffprobe before remuxing, retaining videos on failure.
- Share snapshot fields between shell and Settings. Keep preset data in a static
  catalog loaded once rather than sending it in every backend state update.
- Remove fixed release links/badges from README; release publication remains the
  maintainer's decision.

- Mirror an active niri display onto a connected monitor/projector using the
  optional Fedora `wl-mirror` package. Source/destination and Start/Stop controls
  live in Settings → Displays and Control Center → Devices; the shell owns its
  child, handles disconnects and uses the existing sharing/DND preference.
- Customize topbar outline thickness, alpha/hex color and all four corner radii.
  Pill, square and square-left/right presets apply to connected bars and islands.
  Defaults retain the existing appearance; portable presets include the geometry.

## 2.0 — 2026-10-12

### Added

- NVIDIA-first screen recording with integrated VAAPI and CPU startup fallback.
  Explicit NVIDIA, Radeon and CPU modes remain available.
- MKV, MP4, MOV and WebM; video codec, 24/30/60/120 fps and bitrate controls.
  Recordings start as private MKV files and are remuxed on stop. Failed conversion
  retains the original, and existing files are never replaced.
- External Satty/Swappy annotation from Screenshot studio. A saved, flattened PNG
  preserves strokes/redactions and remains available after closing the studio.
- Recording and annotation settings in portable presets; helper diagnostics and
  updated Fedora package guidance.

### Fixed

- Rediscover commands installed after shell startup and handle minimal niri PATHs.
- Use desktop-sized NVENC preflight frames instead of 128×128 frames rejected by
  the RTX's minimum dimensions; retain leading errors rather than cleanup tails.
- Select workspaces with one stable-ID IPC action instead of a redundant
  `focus-monitor` action that recenters the pointer.

### Improved

- Cava now emits 60 fps with `noise_reduction=20`; spectrum heights follow frames
  without a second 50 ms easing animation. The visible/playback lifecycle remains.
- README includes the maintainer's current demo, a clearer installation path,
  customization overview, dependency map and update instructions.

### Validation and upgrading

- 187 tests passed with every private Wayland opt-in enabled, no skips; QML lint
  passed for changed components. Fixtures include recorder failures, real FFmpeg
  remux/decode, workspace socket requests and immediate spectrum attack/release.
- The maintainer confirmed H.264 NVENC preflight at 1920×1080, 30 fps and
  12,000 kbps with exit code 0 and supplied the release demo recording.
- Saved preferences remain separate from the checkout. Older CPU defaults saved
  before recording-format controls migrate once to Auto; explicitly selecting
  CPU with the new controls is preserved.
- niri 26.04+ is needed for recording/native popup blur. NVENC/VAAPI codec support
  depends on the local FFmpeg and GPU driver. Niri cursor-warp rules remain under
  compositor control. No drivers or system packages are installed automatically.

[Compare 1.9 → 2.0](https://github.com/longme179/lme-fedora-niri-qs/compare/1.9...2.0)
· [Detailed behavior and hardware limits](docs/FEATURE_PORTS.md)

## 1.9

[Previous release](https://github.com/longme179/lme-fedora-niri-qs/releases/tag/1.9)
· [Changes from 1.0](https://github.com/longme179/lme-fedora-niri-qs/compare/1.0...1.9)
