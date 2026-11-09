# Changelog

## Unreleased

- Fixed a startup regression from the native audio devices and network
  connections port: the shared command-running component was missing its
  declaration in the services qmldir, so Quickshell could not load the
  configuration at all ("CommandRunner is not a type"). Declaring it restores
  startup; no behavior change.
- The audio devices panel (ports, profiles, application outputs) and the
  saved network connections popup (VPN/WireGuard/ethernet/hotspot, activation
  and cancel) now run natively instead of over the backend JSON-lines path.
  The same pactl/nmcli/busctl commands run with the same validation, bounds,
  confirmation and cancellation behavior and the exact user-facing messages;
  ids are server-scoped exactly like the backend (the same SHA-256
  identities, so panels served by either world during the transition
  interoperate). Results install the observed state on success and failure
  alike, and the hotspot warning/confirmation flow keeps its plan-token
  check. Missing tools keep their install hints; a missing
  nm-connection-editor is now silent where the backend toasted a generic
  failure. Fixture modes keep the backend round-trip.
- Volume, mute, microphone, brightness, Bluetooth radio/device and charge-mode
  controls now run through native Quickshell calls (PipeWire node writes,
  BlueZ adapter/device writes) or the same external tools the backend used
  (brightnessctl, the administrator charge helper via pkexec) instead of the
  backend JSON-lines path. Messages, bounds, confirmation behavior and the
  polkit prompt flow are unchanged; results for these routine controls stay
  toast-silent exactly like before. Turning Bluetooth on through an rfkill
  block still uses the backend's unblock-and-retry path, and sessions without
  the native backends fall back to the registry. The charge-mode admission
  (helper availability, busy state) reads the backend-sampled sysfs state
  while its discovery needs an API quickshell 0.3.2 does not have.
- The Wi-Fi panel now reads its scan list and saved profiles natively and its
  actions run through Quickshell's NetworkManager bindings instead of the
  backend JSON-lines path (the migration's first write phase). The scan list
  keeps the exact backend shape (SSID-deduped, connected first, 60-entry cap)
  with the 0-1 signal rescaled to percent; saved profiles enumerate every
  wifi connection the adapter exposes. The scanner runs only while the panel
  is open, and the explicit scan re-arms it (rate-limited ~10 s). Connecting
  matches by SSID (quickshell exposes no BSSID), updates the saved profile's
  password when one is given and activates stored credentials otherwise;
  completion is event-driven with the same 45-second ceiling, password
  validation and user-facing messages as the backend. Toggle/disconnect/
  forget route natively too; fixture modes keep the backend round-trip and
  sessions without the native NetworkManager backend fall back to the
  registry. The backend keeps emitting its lists during the validation window
  (count drift warns on scan timing and hotspot-mode saved profiles, which
  quickshell 0.3.2 does not enumerate).
- The launcher app list, launch history and the cpu/memory system fields now
  come from native reads (Quickshell DesktopEntries + FileView on
  /proc/stat, /proc/meminfo, /proc/net/dev) instead of the backend JSON-lines
  path, at the same 2-second cadence. Launching an app resolves the desktop
  entry natively and detaches it from the shell process (terminal apps still
  use the configured terminal); the usage store keeps its exact decay,
  validation and atomic-write semantics on the same launcher.json, now with an
  event-driven file watch. The Python backend still computes its copies during
  a validation window; section shapes and all public facades are unchanged.
  Temperature, brightness and the process table stay backend-sourced for now
  (Quickshell 0.3.2 has no directory-listing API for the hwmon/backlight
  globs or /proc/<pid> iteration).
- Fix the battery module reading 1% at roughly 80% charge (Q1 regression).
  Quickshell 0.3.2 normalizes the UPower `Percentage` D-Bus property (0-100)
  into a 0-1 fraction — the same convention as PipeWire volume, Wi-Fi signal
  strength and Bluetooth battery, which Q1 already rescaled — but
  `PowerState` rounded it as if it were 0-100, so 79% became
  `Math.round(0.79)` = 1. Both UPower read sites (the battery percent and
  the UPower peripheral supplies) now go through `percent100()`. The
  real-machine A/B audit showed backend 79 vs native 1 on all 27 battery
  drift lines and no other drift beyond Wi-Fi strength sampling jitter.
- Audio, microphone, battery, power-profile, Bluetooth and Wi-Fi summary state
  now comes from Quickshell's native PipeWire, UPower, BlueZ and NetworkManager
  services (event-driven) instead of the 1.5-5 s backend polling, with identical
  values in the bar, control center and widgets. The volume/mute on-screen
  display reacts immediately instead of on the next poll. The Python backend
  still computes its copies during a validation window; section shapes and all
  public facades are unchanged.
- Add an informational language-mix summary to the architecture check: every
  `./scripts/check.sh` run now prints runtime QML/JS vs runtime Python, plus
  dev-tooling and test line counts (total lines, `wc -l` parity), tracking
  the phased QML-first migration (docs/QML_FIRST_MIGRATION_PLAN.md). The
  classification lives in `config/architecture.json` (`toolingFiles`); no
  gates or thresholds were added and exit codes are unchanged.

- Fix the activity island reopening as an invisible sliver instead of
  popping open. `SpringMotion.snapTo()` imperatively assigned `target`,
  and QML severs a declarative binding on imperative assignment, so the
  first dormant park of the retained island broke its size springs'
  `target:` bindings: every later reopen kept them at the compact size
  and the island surfaced as a ~180x30 nub with no animation. The
  island springs also gated `enabled` on `mounted`, so on a fresh mount
  the target binding could re-evaluate while `enabled` was still false
  and `retarget()` took the disabled snap path — the very first open
  teleported to full size too. `snapTo()` now writes only
  value/velocity (targets move through `retarget()`), which also
  protects `MotionPopup`'s `target: root.requested` binding from the
  same severance in combo boxes and pickers, and the island size
  springs inherit MotionValue's constant `enabled: Theme.springMotion`.
  Reopens animate compact -> expanded in lockstep with the exit slide
  and jelly progress again; the island size motion test now waits for
  the dormant retained state instead of an unmount.
- Fix micro-freezes when opening panels and switching Settings pages. Panel
  trees mounted fully synchronously on the UI thread (the control center built
  ~55 glass materials and ~2000 objects in one ~900 ms block, again on every
  open because closing destroyed the tree), Settings pages swapped the same
  way, and every 2 s backend snapshot re-evaluated bar and panel bindings.
  SlideLoader now incubates content asynchronously (`Loader.asynchronous`) so
  heavy panels build across frames without blocking input or animation, keeps
  the last panel mounted after close (`keepAlive`, hidden by the host window)
  for instant reopens, and remembers the loaded size so the overlay reserves
  the right area while incubating. Settings pages use a new SettingsPageHost
  that double-buffers two asynchronous loaders, so the current page stays
  visible while the next one incubates: pages never blank and never block.
  The control center tab loader, the catalog page loader, and the Settings
  application view loader incubate asynchronously too. Backend snapshots now
  keep stable references for the `system` and `displays` sections (the same
  Identity.keep mechanism as apps/niri/preferences), so unchanged polls no
  longer re-evaluate every bar and panel binding. Also fix a TypeError on the
  Liquid glass settings page: Quickshell's FileView exposes text as a method,
  and the blur snippet check called `.indexOf` on the function instead of its
  result.
- Fix selected controls being unreadable on light glass. In Liquid glass the
  selected button, tab and chip fill was a fixed light scheme color (the same
  value as the switch track and slider fill) while labels stayed white, so on
  a light-tuned shell selected pills had a background close to the text color.
  The saved accent now flows into Liquid glass selection highlights (selected
  buttons and tabs, switch tracks, slider fills, notification accents) and
  every selected fill pairs with a luminance-derived label color, so selected
  controls stay readable with any accent on light or dark glass. The Accent
  color card in Appearance settings is enabled while Liquid glass is on.
- Fix bar pill drop shadows being clipped by the bar layer surface: the bar
  window ended exactly at the pills, so the top/left/right shadow halos were
  cut by the surface bounds and only a bottom sliver rendered. The window now
  reserves a shadow flight envelope (`Theme.barShadowPad`) inside the surface
  on every side while pills keep their screen position; the envelope collapses
  to zero when shadows are disabled. Add a **Pill shadows** toggle
  (`barPillShadow`, default on) in Top Bar settings to turn the effect off.
- Replace the wallpaper-sampling liquid-glass lens with simple transparent
  glass: panels now render only a translucent tint layer (governed by Panel tint
  opacity), procedural grain, and a geometry-based edge highlight/rim. The shell
  no longer reads, samples, caches, or paints the desktop background/wallpaper;
  blur comes only from the niri compositor (`~/.config/lme-shell/liquid-blur.kdl`,
  `xray false`). Lens blur, adaptive contrast, frosted/true backdrop presets,
  `appliedBlur`, and the glass snapshot cache were removed. Compositor blur
  passes/offset remain configurable.
- Fix True-backdrop glass revealing the desktop wallpaper (“xray”): with the
  True backdrop preset the lens yields to compositor blur, but the yield
  branch hard-capped its tint at alpha 0.15/0.22 so panels stayed ~85%
  transparent and the blurred desktop wallpaper showed through (bar ~0.91
  correlation with the wallpaper; Settings over the bare desktop ~0.55). The
  Panel tint opacity preference was ignored in that path. Feed
  `Theme.panelOpacity` into `liquid-glass.frag` as `yieldOpacity` and add it
  to the capped yield tint (alpha up to 0.92), so the Panel tint opacity
  slider now controls how much of the frosted backdrop shows through in True
  backdrop mode (0 = fully transparent yield, 1 ≈ 0.9 frosted; default 0.65
  gives a properly frosted panel). Shader kept at 221 nonblank lines.

- Add Liquid glass settings presets with one-line descriptions at the top
  of the material card, regroup sliders under Lens (blur, rim, edge width,
  grain, tint opacity) and Compositor (passes, spread), and show a derived
  compositor blur status line (applied/pending save snippet/unsupported).
  Add `docs/GLASS.md` (hybrid model, presets, niri requirements, measured
  perf facts, troubleshooting) linked from configuration, troubleshooting and
  the README, and update Serpantinum attribution/notices for #87–#91
  renderer refinements and the Lens 2.0 timing derivation (issue #78).

- Add idle-frame elimination, env-gated glass telemetry, reduced
  transparency and a text contrast floor (Liquid Glass 2.0 C1): the
  per-frame glass JS is now dirty-gated (zero calls when unhovered and
  static); FrameLogger (LME_GLASS_TELEMETRY=1) logs p50/p99; the
  Accessibility reduced-transparency switch swaps to opaque Smoked
  surfaces live (same path as battery saver, blur off) and the contrast
  floor raises tint to keep white text above 3:1 on bright backdrops.

- Fix the islands bar blur following the full strip (follow-up to the
  compositor-yield fix): the islands blur region is now the pill shapes
  only (no full-strip band), matching islands vs continuous behavior;
  bar pills and their module controls yield with the bar flag, popups
  keep the popup flag.

- Fix glass panels showing the stale wallpaper snapshot over app windows:
  when a true-backdrop (xray false) preset is applied on niri 26.04+ the
  lens now yields to the compositor frost (transparent base, tint capped at
  0.15, alpha capped at 0.85, rim/tint/grain kept) so apps behind panels
  appear frosted instead of the wallpaper snapshot; the gates are the applied
  preset, the niri version and the per-surface blur region (bar vs popups),
  with Frosted preset / older niri keeping the wallpaper lens. The bar
  gains a full-strip blur region so app chrome in the gaps between islands
  pills is frosted too, closing the sharp-pierce gap.

- Add the compositor blur strategy (Liquid Glass 2.0, issue #75): two named
  presets in Liquid glass settings, generated by the existing glassBlurApply
  action — Frosted (new default, xray true: wallpaper-only blur, cheap on
  the iGPU) and True backdrop (xray false, today's behavior, experimental).
  The generated snippet keeps the include-after-generic-rules ordering and
  true reproduces the popup-blur rules byte-for-byte. glassBlurApply probes
  the niri version (mockable `probe_niri_version`) and refuses with a
  readable message below 26.04 without writing anything; the settings page
  hides the compositor controls on older niri and doctor.sh gained the same
  check. Applying a preset records the applied preset in liquidGlass, and
  while one is applied glass panels and bar pills draw a 1px hairline in
  the glass border token (absent without compositor blur, Smoked untouched).
  Native BackgroundEffect.blurRegion was already in use; SurfaceBlurRegion
  stays for jelly-deforming surfaces.

- Add the Serpantinum soft drop shadow for bar pills (follows #84 edge
  optics): GlassMaterial gains `shadow` + `Theme.glassShadowPad (12px)`
  inflated optics frame, `glassPad`/`shadowAmt` wired into GlassOptics,
  backdrop `sampleRect` expanded by pad, software fallback kept pill-sized;
  GlassPanel forwards `shadow`; BarSurface uses
  `Theme.glassPillShadow (3.0)`; shell.qml extends the bar window by the
  shadow strip (`exclusiveZone` unchanged) with `mask: Region { item: bar }`
  for a click-through halo; TopBarPage preview gains breathing room.
  Shader untouched. Desktop check: ~28% max darkening at the pill edge,
  monotonic 12px falloff.

- Restore Serpantinum edge optics (follow-up to #79-#83): liquid-glass.frag
  returns to upstream formulas exactly (finite-difference edge gradient,
  Fresnel env reflection, inner shadow, broad spec, meniscus, fringe,
  lens zoom with lensK, blur falloff 0.9, GRAIN 0.004), GlassMaterial
  adopts upstream production wiring (frost 2.2, rim 0.45, bezel
  3..14 x 0.28, thickness bezel x 0.8, tint 0.35 x 0.5, clear only when
  nested) and the QML 1px border is gated off in glass mode so the shader
  hairline is the border. The brightness/feather/smearing knobs and their
  shader deviations go away; the only kept infra is the snapshot-image
  neutral base when no backdrop is ready.
- Fix the equalizer band intro stagger crashing the delegate: the Repeater
  delegate read `index` inside its nested Translate transform without
  declaring `required property int index`, producing "ReferenceError: index
  is not defined" in the live shell log. The delegate now declares the
  property and the transform reads it explicitly as `bandDelegate.index`.
- Add the glass backdrop snapshot cache (Liquid Glass 2.0, A2 part 2): the
  backend snapshots awww's live per-output state to
  $XDG_CACHE_HOME/lme-shell/glass/<output>.png with a revision counter —
  image wallpapers are copied atomically, color wallpapers become a 1x1 tile
  in the exact per-output awww color — and every window on the output binds
  the same URL plus `?rev=`, so one decode is shared and a revision bump
  reloads all backdrops within a frame. Writes run in the existing feature
  workers (wallpaper actions, restores and a transition-completion refresh on
  the next poll cycle), skip entirely when glass is off, fall back to the
  direct-file path when the awww surface differs, bound the cache directory
  (64 MiB / 32 files, oldest first) and prune disconnected outputs.
  `windowOrigin` now resolves anchors-first, then the niri IPC window id
  where Quickshell exposes it, then the shell-owned unique QsWindow title as
  a single-match last resort, so duplicate titles never sample the wrong
  region. The snapshot behavior follows Serpantinum's WallpaperBlur cache
  pattern as an original implementation; no upstream source is vendored.

- Harden the glass backdrop sampling surface (Liquid Glass 2.0, A2 part 1): a
  flat fill tile now stands in when no image is set for an output (color
  wallpapers have no image path), keeping `sourceAvailable` at 1 so rim and
  grain render over a flat field instead of the dead flat rim; `cache: true`
  plus the per-output source size makes every window on an output share one
  decode instead of re-decoding the wallpaper for each popup window; and
  outputs with a scale above 1 sample at up to a 1440p equivalent (capped by
  their physical resolution) so frosted interiors stay smooth at 2x, while 1x
  outputs keep the previous <=720p/0.5x cap. The awww snapshot cache and live
  color-state invalidation remain for A2 part 2.

- Wire glass-on-glass nesting into the glass material (Liquid Glass 2.0, G1):
  every stacked glass layer used to render a full-strength rim and bevel,
  compounding into the "chrome sandwich" look. The material now walks its
  ancestors (bounded to 48 levels, stopping below the stratum that hosts the
  shared backdrop, or the window content root without one) to count the glass
  surfaces it is stacked on — a marked glass container counts through its own
  embedded layer, never as itself, so nested content is not double-counted —
  and attenuates the nested optics: rim and frost
  follow upstream's nested-input formulas while the renderer's `nest` uniform
  already softens bevel, veil, bulge and grain. The level recomputes only on
  tree events (parent/backdrop changes and `childrenChanged` on watched
  ancestors, coalesced through a 0 ms child timer — a `Qt.callLater` closure
  would outlive destroyed materials and fire in an invalid context) and never
  per animation frame.
  `GlassMaterial` and `GlassPanel` carry the upstream `isGlassFill` marker so
  `background:`/sibling hosts count as a glass stratum. `glassNesting.js` is
  an AGPL-attributed port; see `third_party/Serpantinum-NOTICE`.

- Fix a shell-wide startup failure introduced with the equalizer port: the
  ported `EqualizerState` singleton used the Quickshell `Singleton` root type
  without importing `Quickshell`, so the file failed to compile with
  "Singleton is not a type" and took the whole `qml/services` singleton import
  chain down with it. It now imports `Quickshell` like every other service
  singleton, restoring startup.

- Re-implement the Serpantinum equalizer as a faithful port of Serpantinum
  Shell's equalizer (AGPL-attributed; see `third_party/Serpantinum-NOTICE`).
  The panel now shows ten vertical band sliders (31 Hz-16 kHz) with an animated
  lightning sweep on apply, per-band pulses, preset chips with active-state
  highlight, a dimming Dynamic EQ overlay whose toggle lives outside the dimmed
  area, and an Audio view with a notched balance scale, center-origin fill,
  L/R readouts, mono/swap toggles, a three-mode dynamic range selector and a
  channel test tone through the equalizer sink. Band edits are staged and
  committed with Apply; presets and audio settings apply immediately, and
  switching views reverts uncommitted band edits. Equalizer state moved
  backend-side into a persisted `eq_state` document (seeded from the daemon on
  first use), giving every surface one apply contract; `eqGet` no longer probes
  the daemon and cannot fail on default installs. New granular actions:
  `eqSetBand`, `eqRevert`, `eqPreset`, `eqBalance`, `eqMono`, `eqSwap`,
  `eqDyneq`, `eqDynamics`, `eqReset`, `eqTest`, `eqTestStop`; pushes auto-start
  the stopped daemon and retry once. `pw-play` joins the managed tool allowlist.

- Add the optional Serpantinum equalizer: a centered equalizer panel from the
  top-bar module, Control Center tile and Audio mixer, plus a Settings page.
  Ten band gains, balance, mono, channel swap, dynamics modes, bypass and
  dynamic EQ; presets and daemon state round-trip through `eqGet`. Installing
  and starting the external `serpantinum-audio` daemon is required; disabling
  it routes audio directly again.

- Add a default-off fcitx5 input-method indicator (P-16): a top-bar module
  shows the active IME and a change OSD, without polling when disabled.

- Add saved network connections (W2): Wi-Fi/Devices gains VPN, Ethernet and
  hotspot profiles with exact-adapter activation, a system IP/DNS editor and
  confirmed secure hotspot activation.

- Avoid false Battery saver conflicts when starting a recording after restore.
  Share status-read locks and briefly retry guarded writes while a status probe
  finishes; continue rejecting overlapping hardware transitions.

- Open Settings with its saved appearance from the first visible frame. Wait for
  the initial theme/runtime snapshot and theme resources before creating the view,
  detect Liquid blur support before mapping, and reuse queued Gear requests during
  startup. Keep the existing window through backend reconnects.

- Recognize fractional nominal 60 Hz display timings in Battery saver, including
  60.003 Hz panels previously left at 120 Hz. Send the exact advertised timing,
  confirm mode changes and restores, and retain recovery data if niri ignores a
  request. Report partial hardware support instead of an unconditional success.

- Add a reversible Battery saver switch and Control Center canvas tile. Temporarily
  use opaque Material surfaces without shell blur, motion, spectrum or floating
  shapes; cap supported active display modes at 1080p/60 Hz, apply a configurable
  one-time brightness cap and use the existing power-saving profile. Preserve
  saved preferences and journal changed hardware values for restore/retry. Keep
  startup display restore and recording from racing transitions; resume Cava
  correctly after rapid toggles.

- Avoid a second shell success toast when connecting or disconnecting Bluetooth devices. Keep application notifications, connection errors and device-state updates intact.

- Reclaim abandoned Gowall preview sessions using ownership leases; keep previews in other running instances, bound cache-lock waits and clean owned previews on close. Preserve exported/applied images and prune legacy unleased jobs only after 24 hours.

- Cancel owned command process groups and reject new commands during backend shutdown. Supervise Gowall even if Quickshell kills its backend directly; preserve detached Launchpad jobs, large stdin payloads, command error redaction and clipboard pipe handling.

- Ignore device-scoped power supplies when detecting laptop AC power, including the status fallback used when adapter readings are unavailable.

- Give local notifications a sequence-based ID suffix, so notices created in the same millisecond can be dismissed independently.

- Unregister niri event-stream pipes before closing them. Keep Settings alive through repeated Liquid/Smoked switches and stream reconnects, and reap the stream child on shutdown.

- Refine Liquid's directional rim with exact rounded-box normals, a narrower caustic and shallow inner shading that separates glass from bright apps. Preserve clear interiors, white labels and the existing texture/render-pass budget.

- Show connected peripheral batteries in Control Center → Devices, with a saved alert switch and 5–50% threshold in Behavior. Preserve unknown/0% readings, merge Bluetooth/kernel duplicates and prevent repeated alerts across reconnects within a shell session. Keep device batteries out of the laptop battery aggregate.

- Add Gowall image utilities with installed-theme search, batch palette previews, 2×–4× upscale, color extraction and basic image effects. Export PNGs exclusively or keep a durable copy before applying a wallpaper; setup downloads stay in gowall's explicit terminal prompt.
- Expose awww FPS, Bezier, direction/origin, wave, scaling/filter and padding controls. Parse empty namespace prefixes in 0.12.1, prevent another backend from cancelling a transition during restore, and disable cache auto-restore only when starting an owned daemon.

- Add a local Launchpad for named binaries and Bash scripts, background/terminal dispatch, per-command logs and launcher search. Expose an optional top bar module and an editor in Shell utilities; keep commands out of portable appearance presets.

- Keep all Liquid labels white, including selected tabs, calendar dates and close buttons on hover. Remove automatic black/white foreground switching; preserve Smoked colors and the shared glass material.
- Keep the shared glass material when a button supplies its own background. Fix Power's opaque gray fill, cover dropdown triggers, and preserve raw color swatches and intentionally flat hit areas. Reuse existing spring/hover behavior and remove the duplicate tile material.
- Keep a complete multiword app-name match ahead of more frequently launched apps with longer matching names.
- Reject oversized wallpaper transition numbers before float conversion. Record popup resize intermediates inside QML so slow IPC reads cannot miss the spring trajectory; keep off-screen entry and settling assertions. Wait for both travel and deformation to settle before checking Jelly layer release.
- Audit queued wallpaper playback: recheck pause/disable/target changes before starting a scheduled job, validate canonical symlink targets and preserve the current image when all alternatives fail. Ignore malformed launch-history IDs and keep history serialization errors from failing successful launches. Native pixel comparisons wait for a submitted frame after image-state changes.
- Rank launcher apps by local recency/frequency with seven-day decay, preserving exact/prefix match priority. Add opt-out and clear-history controls; retain at most 256 apps/60 days, without favorites or window tracking.
- Add ordered/shuffled wallpaper playlists with pause/resume, intervals and awww transitions. Preserve independent display images, restore them after reconnect, and share the same per-output image with Liquid's rim sampler. Wallpaper jobs run in the existing executor with a cross-process lock; no second renderer or polling loop is added.
- Add an optional refractive selection lens to Settings and Control Center tabs. Reuse the existing velocity-preserving spring edges, shared glass backdrop and press feedback; leave Smoked selection unchanged.
- Follow niri's floating-window geometry for Liquid rim sampling instead of assuming Settings is centered. Keep geometry tracking off in Smoked and add native-fixture progress diagnostics without relaxing test deadlines.
- Refine Liquid pointer lighting with localized rim highlights, a soft opposite reflection and velocity-preserving tracking. Fade from the last pointer position and stop its motion drivers when hidden, resting or motion is disabled.
- Recover ZIP and uncommitted Git installations through an explicit Git-updates button. Keep the original source as a backup, preserve startup paths and preferences, and clear stale HEAD errors.
- Add independent Liquid glass tint, brightness, opacity, lens blur and rim feather/smearing/width/highlight controls. Preserve the default rendering, include them in shared presets, and expose an opt-in niri blur snippet with compositor-wide scope.

- Audit native UI lifecycle and reject runtime assignment/binding-loop diagnostics in QML regressions. Fix Bluetooth Scan reading an undefined power state before the first backend snapshot.

- Add opt-in Jelly-v2 popup motion: velocity-driven spring deformation, bowed/tapered mesh surfaces, bounded native-window rendering and a software fallback. Keep edge entry/exit and release the effect layer after settling.

- Add independent maximum widths for the compact Activity pill and expanded popup, plus a height limit/Auto fit. Preserve defaults, save limits in appearance profiles and bound live spring resizing to the viewport.

- Add saved full-transcript/current-line lyric modes and default follow in Behavior settings. Show synchronized lines on the compact Activity Island with track-title fallback; share its lookup with media views and replace lyric polling with cue-boundary scheduling adapted from end4-pC.

- Restore spring-driven edge entry and exit for all bar popups. Remove the connecting surface and its setting while preserving custom appearance profiles and old settings imports.

- Fix nested media controls collapsing into a narrow column in Activity Island, Control Center and desktop media cards. Use the available width and reflow when fonts/card sizes change.
- Keep desktop resize anchored, preserve saved dimensions on smaller outputs and retain drag drafts through unrelated settings updates. Add canvas lifecycle/output and geometry regressions; document setup and shared notes behavior.

- Add synchronized lyrics to media panels with embedded/local LRC support, a bounded disk cache and opt-in LRCLIB lookup. Follow playback or scroll manually without background polling when hidden.
- Add an optional desktop canvas with per-output clock, notes and media widgets. Persist drag/resize edits independently; support click-through mode and preserve disconnected-output layouts.

- Blur beneath the actual bar glass on supported niri, matching the connected
  bar or independent island corners and leaving gaps clear. Add a separate,
  default-on Bar blur preference with preset/backup support.
- Fly shell panels, Island, authentication, OSD, toasts and QML menus in and out
  through the same edge. Preserve spring momentum during reversals, prepare menu
  placement before showing its first frame and bound long-distance bounce.
- Retain outgoing notification/status content until its exit completes, keep
  live notification cards stable when others arrive and cap retained toast exits.
  Closing authentication releases keyboard/input capture immediately.
- Wait for loader bindings before mounting hidden panels and use stable viewport
  sizes before Wayland configures each fresh surface. Prevent startup ghosts and
  keep first/repeated openings on the same complete off-screen path.
- Keep a flying dropdown from highlighting rows beneath a stationary pointer.
  Wait for a stale Settings instance to exit before restarting its configuration.
- Extend the existing frame-clock spring to shared hover/corner feedback, switch
  thumbs, slider handles and stretching tab indicators. Centralize preset tuning;
  preserve velocity on target changes and keep indicators/thumbs within bounds.
- Continue popup motion when its content changes, tween open-panel sizes and
  unify Island sizing with the same springs. Animate font menus/dropdowns, use
  monotonic color/hover easing and restore active icon tint. Retain reduced motion
  and curve-based fallback without adding runtime dependencies.
- Align Launcher/Wallpaper hover feedback with their selected card corners.
  Flat hit targets stay inside their frames; scroll gutters protect first/last
  rows and full-width Font Picker, Audio and Devices controls from clipping.
- Remove app/wallpaper Favorites controls, ranking and preferences. Older backups
  still import their remaining settings while retired favorite fields are ignored.
- Open clipboard images and screenshot notifications in the chosen Satty/Swappy
  editor. Preserve originals through private saved copies, retain right-click
  previews and an explicit Copy button, and recognize niri's screenshot icon URI.
- Remove unused `grim` from the package reference; retain `slurp` for recording
  regions. Note niri's experimental non-xray blur limits in the config fragment.
- Let the clipboard service read commands from regular files and exit cleanly
  with `/dev/null` stdin, using the same selector fallback as the desktop backend.
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
