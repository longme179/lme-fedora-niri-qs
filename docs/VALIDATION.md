# Validation and platform limits

## Launchpad, Gowall and awww controls — 2026-10-19

Default `scripts/check.sh`: **390 tests, 306 passed, 84 opt-in checks skipped**;
Bash syntax and demo snapshot checks passed. After final audit guards for partial
exports, PNG output and relative Launchpad executables, all **11 affected
backend/QML cases passed again**. Python compilation and whitespace checks
passed. `qmllint`: **139 QML files, zero errors, 67 metadata warnings**.

Launchpad tests cover atomic per-entry merges, rename/delete, private backup
versus portable preset behavior, payload limits, literal arguments, explicit
Bash, background logs/exit status, relative working directories, terminal argv,
duplicate active runs, disabled/demo execution, editor persistence and launcher
search. Actual Quickshell `shell.qml` loaded on private Wayland and opened,
closed and reopened Launchpad. `settings.qml` opened Shell utilities and its
captured layout was checked. Logs contain no QML type/reference/assignment or
binding-loop errors. The manual IPC probe initially ran before configuration
loading completed; waiting for `Configuration Loaded` resolved that startup
probe. No production timeout or existing assertion was relaxed.

The Gowall adapter is checked against the real **v0.2.4** command source, with
backend fixtures for batch output, every supported operation's arguments,
validation, failure retention, exclusive export, partial-write cleanup,
durable wallpaper copies and explicit terminal setup. The UI test invokes a
local CLI fixture through the real JSON backend, loads themes, generates a
valid PNG preview and persists an awww FPS edit. It does **not** verify image
quality, real Gowall processing or Vulkan/Real-ESRGAN execution. An official
binary was downloaded outside the repository; this cloud's read-only home
prevented its config initialization. No user system packages or models were
installed.

A real **awww 0.12.1** daemon ran on the private Wayland output. The test applied
an initial PNG, started a two-second wave with explicit FPS/Bezier/resize flags,
and reconciled a second backend without sending an instant replacement.
Both the empty namespace prefix and target image were checked against its real
query output. Regressions cover missing/changed images, independent outputs,
reconnect, playlists, reduced motion, validation and saved transition options.
The daemon started with `--no-cache`, avoiding its cached restoration race.
The private Sway session cannot verify native niri blur, physical refresh rate
or Radeon/RTX visual performance. The earlier expanded-suite limits below were
not re-audited as part of this feature work.

## White Liquid labels — 2026-10-19

The automatic foreground contrast change described in the earlier entry below
has been removed at the owner's request. Liquid labels remain white for selected
and unselected controls, hover and press, including close glyphs. Smoked restores
the original color bindings. The custom-background glass fixes remain in place;
no preferences, shader parameters or animation behavior are changed.

Default `scripts/check.sh` completed **377 tests: 293 passed, 84 opt-in checks
skipped**, plus Bash syntax and demo snapshot checks. The removed test covered
the discarded contrast helper. The updated OpenGL material/white-label case,
selection-lens checks and existing input/color-restoration case passed. The tab
geometry case timed out on backend readiness during the concurrent run, then
passed in isolation without changing its assertions or deadline. An initial
larger material fixture also timed out; the focused fixture retains the actual
Agenda, calendar, Power, close-button hover and texture lifecycle checks.

`qmllint` checked **127 QML files under `qml/`: zero errors, 42 metadata
warnings**. The Power/Control Center capture was visually checked: labels,
Calendar/current-day text and close glyphs are white. This private Wayland/Mesa
session does not validate niri blur or physical Radeon/RTX performance. The
expanded suite's earlier failures below were not re-audited in this correction.

## Selected controls and custom button glass — 2026-10-19

Default `scripts/check.sh`: **378 tests, 294 passed, 84 opt-in checks skipped**;
Bash syntax and the demo snapshot passed. The nine focused contrast/material,
selection-lens, tab geometry, pointer-lighting, input and texture-lifecycle checks
also passed on private Wayland. `qmllint`: **134 files, zero errors, 67 existing
metadata warnings**. Python compilation and whitespace checks passed.

The expanded run is **not fully green**: **372 passed, four failures, one error,
one optional Matugen skip**, out of 378 tests. The remaining cases concern initial
bar IPC timeout, BlueZ startup readiness, a popup-close wall-time deadline,
spring-settling sampling and the long Settings keyboard-input flow. An untouched
`710b11c` replay also hit the same initial bar IPC timeout and popup-close deadline;
its Settings flow failed to receive an earlier profile-name edit. BlueZ readiness
passed in isolation. These results do not prove every expanded failure has the
same cause or erase the failures; no deadlines or assertions were relaxed to
obtain a green result. They remain broader validation limits for this environment.

Selected/filled buttons keep their preferred foreground when it reaches a 4.5:1
contrast ratio against the estimated plate; otherwise they use black or white.
Opaque light/dark, midgray and saturated fills are checked numerically. Alpha
plates use the panel tint as an estimate, and material-backed controls account
for glass brightness. This is not a guarantee against every live application
behind a transparent surface. Flat controls do not inherit material dimming.

Ordinary Liquid labels keep their white-text behavior. Contrast-managed button
labels opt out explicitly, including Agenda, Calendar's current day, Settings
navigation, workspace pills and notification actions. No font or saved theme
preferences are rewritten. Existing spring motion and input handlers are retained.

The button owns one shared material parented to its background, so a custom
background no longer removes glass. Power's alpha calculation now retains the
surface color's alpha rather than replacing it with 55% opaque white. The
duplicate quick-tile material is removed. Dropdown triggers get the same glass;
raw color swatches, flat hit areas and transparent resting bar controls retain
their intended appearance. No per-button capture or additional blur pass is added.

The native OpenGL case covers all five Power actions, Agenda/Calendar selection,
custom backgrounds, dropdowns, raw swatches, flat/transparent exclusions,
brightness changes, one shared backdrop, hiding/reopening and Smoked restoration.
A captured Power/Control Center frame was visually checked: selected text is dark
on the pale Calendar/tab fill, Power plates are transparent with visible rims,
and labels fit their controls. The private Sway/Mesa session does not reproduce
the owner's niri compositor blur or Radeon/RTX presentation performance.

Input validation keeps its existing assertions and 15-second deadline. A 150 ms
QtTest click, longer than its timer interval, reproduced reentrant input and
premature phase changes before the guard. The test now advances its phase before
entering QtTest's nested event loop and retains that delayed click as a regression.
The broad Settings fixture also waits for stable positions across rendered frames
and completed parent motion before sending a real pointer click. Its four-second
interaction budgets and functional assertions remain unchanged. A previous broad
run's four-second IPC timeout did not recur in the focused Settings replay; its
original cause was not established.

## Selection lens, wallpaper playback and launcher ranking — 2026-10-19

Expanded private Wayland `scripts/check.sh` completed **376 tests: 375 passed,
one optional real Matugen check skipped**. Bash syntax and the demo backend
snapshot passed. The three earlier native-QML timeout cases completed within
their unchanged deadlines; the intermittent timeout's original cause was not
reproduced. `qmllint` checked **134 QML files: zero errors, 67 existing
type-metadata warnings**. Python compilation and whitespace checks passed.

After that full run, a follow-up launcher case reproduced a multiword-name tie:
usage put “Visual Studio Code” before an exact “Visual Studio” query. Complete
name matching now precedes the per-word score and usage tie-breaker. The eight
launcher/history/search checks, including native click dispatch, passed after
this correction; the new regression failed before it. Other application code
is unchanged since the full run.

The selection lens adds the shared glass material to the existing stretching
plate. Its four spring edges retain their response and velocity on reversal;
there is no additional geometric animation or backdrop renderer. The native
OpenGL fixture covers travel, reversal, press, opt-out, reduced motion and texture
release. Smoked selection keeps its previous appearance.

Wallpaper playback uses the existing backend executor and `awww` daemon. Tests
cover ordered/shuffled advancement, missing/corrupt/single images, pause/resume,
sleep gaps, transition arguments, disabled motion, disconnected outputs,
reconnect restoration, concurrent writers and shutdown. Queued automatic jobs
recheck pause, enable and target preferences before applying an image. Failure
to decode every alternative preserves the current image. Image validation follows
symlinks and rejects invalid canonical targets; oversized/non-finite duration
values are also rejected without damaging saved preferences. Three private
Wayland checks exercise the actual Settings
controls, list edits and per-output rim source.

Launch history is local and bounded; only successful command dispatches count.
Tests cover seven-day score decay, restart, concurrent writers, corrupt and
oversized data, private atomic writes, history clearing and disabled recording.
History-write failure leaves a successful launch successful. QML/native launcher
checks retain exact-name priority, stable snapshots and the existing non-app
search modes. No favorites or focused-window duration tracker was added.

Liquid floating-window rim sampling now uses niri's window geometry when it can
identify one window on the relevant output. A native niri 26.04 replay moved the
test window to `(100, 140)` and `(500, 280)`; the shared sampler reported those
exact coordinates. Missing/ambiguous geometry retains the centered fallback.
Settings subscribes to the existing niri event stream only in Liquid mode.

The audit also corrected test synchronization races without changing
production animation or relaxing deadlines/pixel assertions. Glass captures now
wait for a submitted frame after image status changes. Popup-resize observations
are recorded inside QML so an IPC round-trip cannot miss an intermediate spring
value. Six repeated pixel captures and five repeated native popup-entry/resize/
close checks passed after these corrections. Phase/backend/frame diagnostics
remain available for the earlier intermittent 15-second QML fixture timeouts.
Layer-release checks wait for both travel and Jelly deformation to stop; the
deformation has its own spring and can outlast positional settling. Five repeated
native texture/reversal/teardown checks passed with this readiness condition.

Manual checks on the installed desktop:

1. In Liquid mode, switch Settings/Control Center tabs rapidly, reverse direction
   mid-flight, then disable Refractive selection or Animations. Check that the
   selected label stays readable and Smoked restores its normal selection.
2. Add three images in Wallpaper settings. Try order/shuffle, a 30-second interval,
   pause across an interval and Next while paused. Assign an external display its
   own image, change the shared image, then reconnect that display. Check that its
   assignment and the Liquid rim image agree.
3. Launch apps from LME, reopen an empty launcher query and type another app's
   exact name. Disable usage ranking, then clear history from Behavior settings.
   Normal name search should still work and private usage should be gone.

No packages or installed desktop configuration were changed. Actual `awww`
transitions and physical display hotplug were not run in this cloud environment;
their command/state paths were tested with controlled runners and the current
upstream CLI source was inspected. The native GL checks use Mesa software
rendering, not the owner's Radeon/RTX hardware or a 120 Hz presentation budget.

## Pointer-responsive Liquid reflections — 2026-10-18

Glass now adds a localized rim glint and a softer opposite reflection in its
existing fragment pass. The white reflection uses premultiplied coverage so it
does not flatten lens colors or break group-opacity fades. No texture samples,
render layers, blur passes or settings keys were added. The resting material
strips in the panel/pill/button comparison remain pixel-identical.

Pointer coordinates use the existing spring engine with critical damping and
retain velocity on retarget. Initial entry starts at the actual pointer; exit
and disable-after-click keep the last point through the fade. Coordinate mapping
shares the material's existing render callback, including when its parent moves
under a stationary pointer. Springs stop at rest, when hidden or with reduced
motion. Spring-off tracking remains immediate; the software fallback stays
static. Real pointer-event, input, idle-driver and screenshot checks cover these
cases, rounded clipping, text contrast and half-opacity compositing.

A native niri 26.04/Mesa software-OpenGL replay used external Wayland pointer
motion during repeated popup entry/exit. In baseline → changed → baseline order,
Quickshell used 12.32 → 11.15 → 12.52 all-thread CPU seconds and niri used
24.64 → 24.95 → 26.87, over 18.83 → 17.48 → 17.66 seconds of wall time.
Renderer-call CPU medians stayed around 1 ms and peak native mask delegates
stayed at 160. These observations show no consistent increase beyond run
variation; they are not hardware GPU timings or presentation FPS. Animation
driver intervals vary considerably even between unchanged baselines and are
not used as an FPS measurement.

The menu-reversal fixture now reopens on a closing frame rather than assuming
IPC plus an external sleep completes before exit. Its position/mount assertions
are retained and now also require an intermediate progress value. The Settings
gear fixture allows its deliberately slow entrance to settle before clicking
fixed destination coordinates. No production popup or Settings routing changed.

The final expanded private Wayland `scripts/check.sh` run completed **354 tests:
353 passed, one optional real Matugen check skipped**. Bash syntax and the demo
snapshot passed. The 22 focused Liquid, hover, popup and Settings launch checks
also passed. `qmllint` checked **133 QML files: zero errors, 67 existing
type-metadata warnings**. The new disable-after-click regression failed before
the final fade guard and passes with it.

Hardware Radeon/RTX frame presentation and multi-output behavior remain
unmeasured. No packages, drivers or installed desktop configuration changed.

## Separate Liquid material controls — 2026-10-18

`config/liquid-glass.json` supplies the control labels, bounds and defaults to
both the backend and Settings. The `liquidGlass` preference merges field edits
under the existing writer lock, survives restarts and transfers in presets or
backups. It does not overwrite Material preferences or appearance profiles.
The shared glass layer exposes tint, opacity, brightness, lens blur, feather,
smearing, rim width and highlights without adding textures, layers or timers.

The expanded private Wayland `scripts/check.sh` run completed **352 tests:
351 passed, one optional real Matugen check skipped**. Bash syntax and the demo
snapshot passed. The focused updater/glass suites were repeated after final
status and opacity corrections. Six glass-control checks cover invalid hex,
booleans, huge/non-finite/out-of-range numbers, independent concurrent writers,
persistence/export/reset, real hex/picker/slider input and Smoked restoration.
Ten OpenGL screenshots exercise individual shader controls and half-opacity
dimming; foreground text stays white and the dimmed rim respects group opacity.
The default shader comparison across six sizes/hover/press cases has **zero
pixel difference** from the previous revision.

The opt-in niri snippet is written atomically only after its button is clicked;
demo actions do not write it. User-owned files and symlinks are refused. Native
niri 26.04 validates the include and observes later writes: application edge
energy beneath a glass panel changes from **27.73 to 4.96** for passes/spread
1/0.5 versus 4/8, then returns to **27.73** after restoration. This verifies real
compositor blur and automatic include reload, rather than wallpaper-only blur.
Strength is compositor-wide, including Smoked and other requesting clients.

Native Control Center checks at scales 1 and 2 retain sharp outside pixels,
blur the application beneath the surface, restore it on close and open the
actual Settings window. A visual check confirms the new card fits and scrolls.
`qmllint` reports **133 files, zero errors, 67 existing type-metadata warnings**.
No packages, drivers or installed desktop settings were changed. Radeon/RTX
presentation FPS and multi-output hardware behavior remain unmeasured; larger
blur and rim settings can cost more GPU time.

## Git source-install recovery — 2026-10-18

The updater now identifies ZIP/source directories and Git folders without a
valid HEAD commit, including an unborn `master` with no remote. It persists the
new source status so FileView cannot restore an earlier raw HEAD error.
The explicit Enable Git updates action clones official `main` into a sibling
directory and reuses `install.sh --replace` to keep a timestamped source backup
and preserve the original startup path through a link. Existing histories,
tracked edits, untracked files and divergent branches retain their guards.

Eleven updater checks cover real local Git remotes, detached bootstrap after
moving its own source, network failures, destination collisions, stale status,
backups, separate preferences, merge-hook suppression and the existing About
page update buttons. A separate real About-page fixture starts with the owner's
unborn-master/no-remote layout and a saved fatal HEAD error; clicking Enable Git
updates completes the migration, preserves a personal file in the backup and
reads the updated state through the new canonical source path. No installed
desktop files or system packages were changed by these checks.

## Liquid popup frame work and native surface size — 2026-10-18

QML profiling identified repeated scan conversion and per-button ancestor
bindings during Jelly-v2. The shared blur component now caches the unwarped
outline, samples each affine mapping once, reuses scanline buffers and publishes
at most one deformed mask after Qt's animation step, before scene-graph sync.
Glass materials sample their final scene transforms at the same point instead
of rebuilding ancestor dependency chains. Hidden/resting masks release their
delegates; no idle animation driver is added.

Niri's non-xray implementation captures a texture for the native surface, even
when the requested blur region is small. Liquid's main overlay now reserves
the destination and flight envelope in a smaller surface, keeping its original
output-coordinate layout. Blur and Jelly remain on that same surface; a
separate, input-aware surface carries the full-screen dim layer. In the real
Control Center fixture this reduces the native allocation from **1916 × 1053
to 796 × 964**, about **62% fewer pixels**. Smoked keeps its full-screen route.
Blur passes, optical shader, texture resolution, mesh, spring and strain limits
are unchanged.

A controlled single-popup 600 × 900 Control Center benchmark on nested niri
26.04 / Mesa software OpenGL measured median Qt animation-step intervals of
**74.9 → 55.3 ms**, with the 95th percentile **120.2 → 73.7 ms**. These are
laboratory timing observations, not hardware FPS or GPU-utilization readings.
In particular, a multi-window FrameAnimation can follow another window's clock
while the popup render thread waits; its tick rate is not a presentation-rate
measurement. The owner's log confirms OpenGL and 8.33 ms vsync, but does not
identify the rendering GPU.

The expanded private Wayland `scripts/check.sh` run completed **343 tests:
342 passed, one optional real Matugen check skipped**. Bash syntax and the demo
backend snapshot passed. The new 20-frame regression applies multiple position
changes, rotation, scale and spring retargets, then checks the blur mask and
optical coordinates against the current frame, coalesced publication and idle
release. Existing pixel coverage and edge-tolerance assertions are retained.
Real pointer clicks test the bounded Control Center and outside-click closure;
bottom-bar placement, switching to Launcher, nested menu registration and
Liquid/Smoked restoration are covered too. The strengthened menu flight check
also passed after the full run.

Native niri checks at scales 1 and 2 still blur the application below the actual
Control Center, leave outside edges unchanged, restore the application after
closing and display Settings. Eight deformed-mask cases retain the earlier
9–12% inside-edge energy / unchanged-outside results. A separate native run opens
and closes Control Center, Launcher, notifications, clipboard, Wi-Fi, overview,
tray and power with both top and bottom bar placement: all 16 cases reach their
settled state, fit their reserved surface, release the scrim and log no QML errors.
`qmllint` checked **132 QML
files: zero errors, 67 warnings**. Five additional diagnostics concern the same
incomplete Quickshell PanelWindow/margins type metadata; the new native surface
and margins were exercised at runtime.

Actual Radeon/RTX frame presentation, GPU load, power use and multi-output
hardware behavior remain unmeasured. No driver, GPU selection or niri blur
configuration changes were made.

## Popup rendering cost and GitHub updates — 2026-10-18

The local Jelly-v2 mask now scans only polygon edges crossing each row, merges
identical adjoining bands and reuses native Region delegates during motion.
The two-pixel inset geometry and rounded mask at rest are unchanged. Liquid's
clear-interior shader path skips unused lens calculations; the refractive rim
and lighting remain intact. Old/new shader screenshots across six surface sizes
and hover/press combinations produced zero pixel difference in that fixture.

A repeated 600 × 900 Control Center open/close benchmark, with Liquid and
Jelly-v2 at 1920 × 1080, measured transition frame times as follows:

| Measurement | Before | After |
| --- | ---: | ---: |
| Median frame time | 69.1 ms | 25.6 ms |
| 95th percentile | 178.1 ms | 35.8 ms |
| Maximum native mask delegates | 450 | 192 |

This measures the render pipeline under Mesa software OpenGL on private
Wayland, not hardware GPU utilization or laptop FPS. Native niri 26.04 checks
at scales 1 and 2 still pass all eight bent-mask cases: high-frequency edge
energy inside falls to 9–12% of baseline; outside remains unchanged. Existing
pixel regressions retain their >97% mask coverage and outside-edge tolerance.
Hidden/resting surfaces release the pooled delegates.

Eight updater tests use real temporary Git repositories and cover checking,
fast-forwarding, clean-branch requirements, local edits during fetch, divergence,
locking, interrupted status, unavailable Git/remotes and credential redaction.
The native About-page test clicks both buttons and closes its Quickshell process
during fetch; the detached update completes and the checkout reaches the target
commit. Preferences are preserved and merge hooks are not executed. A separate
clean copy also fetched and fast-forwarded successfully from the actual GitHub
remote. No system packages or installed desktop configuration were changed.

The expanded private Wayland `scripts/check.sh` run completed **342 tests:
341 passed, one optional real Matugen check skipped**. Bash syntax and the demo
backend snapshot passed. The double-speed lyrics latency fixture now seeks
after QML/lyrics readiness, excluding process startup from its measurement;
the existing 35.0–35.5 second cue-position bound is retained. Production lyrics
code is unchanged. `qmllint` checked **132 QML files: zero errors, 62 warnings**.
One additional warning is the existing Quickshell `QProcess::ExitStatus` metadata
limitation on the new updater handler; its runtime path was exercised.

Radeon/RTX frame pacing, GPU load and power use still need measurement on the
owner's Fedora session. Git updates apply source only; restart both shell and
Settings afterward and review new package requirements separately.

## Combined Fedora installation — 2026-10-18

`scripts/setup.sh` reuses the package, configuration-link, Settings launcher and
optional charge-helper installers. Six isolated tests cover read-only preview,
repeat installation, backup/replacement, saved preferences, package failure,
conditional `awww` selection, repository lookup errors and explicit COPR opt-in.
File installation uses the real helpers in temporary directories; sudo/RPM/DNF
and the privileged charging step use stubs and do not change the host system.

`scripts/check.sh` completed **334 tests: 263 passed, 71 opt-in checks skipped**.
Bash syntax and the demo backend snapshot passed. No QML or rendering code was
changed, so the private Wayland suites were not rerun. The upstream `v0.12.1`
awww tag resolves to the commit documented in INSTALL.md. Actual Fedora DNF
transactions and the Fedora source-build commands remain unverified here.

## Deforming local blur and darker Liquid surfaces — 2026-10-18

Local blur now follows Jelly-v2's rounded, bent and tapered silhouette instead
of sliding as an undeformed rectangle. Scan conversion uses the same 16×16
triangle mesh as the vertex shader. Inset two-logical-pixel bands exist only
while GPU deformation is active; the mask returns to one rounded region at
rest and is released on hide, unload or leaving Liquid. Software rendering
continues to use the existing scale transform without applying the warp twice.

A native pixel regression compares the region against the rendered shader on
both axes, positive/negative strain, bounded deformation and asymmetric
corners. It requires over 97% coverage and rejects protrusion beyond a two-pixel
antialias allowance. Geometry checks cover concave cutouts, viewport clipping,
empty/off-screen shapes and the identity transform. Lifecycle regressions also
cover closing/reopening, switching presets and reduced motion in software and
OpenGL.

Actual niri 26.04 blur was checked separately at scales 1 and 2 on a fine-grid
application: high-frequency edge energy within all eight deformed masks fell
to 9–12% of baseline, while the area outside the silhouette retained 100%.
The application and actual background layer used deliberately different images.
Settings and notification toasts were then tested with xray enabled, the current
non-xray rules, and after reopening. Xray reproduced wallpaper bleed-through;
`xray false` restored blur of the application. The include must follow generic
background-effect rules because later matches win. The Wayland protocol does
not let the client override this compositor setting.

Liquid's shared outer tint is darker, including bars and toasts; inner cards,
refraction and white typography remain translucent. A real Settings window over
a white application produced an empty background gutter around RGB 105/112/120,
with about 5.0:1 contrast to white text at that sampled location. This is a
specific pixel check, not a contrast guarantee for every control or wallpaper.
Saved Smoked colors and opacity are unchanged.

`scripts/check.sh` completed **328 tests: 327 passed, one optional real Matugen
skip**, with the expanded private Wayland suites enabled. Bash syntax and the
demo backend snapshot passed. `qmllint` checked **131 QML files: zero errors,
61 warnings** (unchanged from the preceding revision). The niri fragment also
passes `niri validate`.

The compositor checks use nested Wayland and Mesa software OpenGL. Radeon/RTX
frame pacing, power use and long-session performance remain unmeasured. The
wallpaper-only rim and niri's experimental non-xray limitations still apply;
see [Surface style](CONFIGURATION.md#surface-style).

## Local frosted Liquid surfaces and white text — 2026-10-18

Liquid now blurs the area beneath each rounded panel or popup, instead of
leaving its body clear or blurring the entire desktop. White text, cool
translucent tints and softer refractive rims replace the black typography below.
Saved palettes, fonts, layout and the Smoked full-screen blur preference remain
intact. No feature from the supplied visual references was added.

`scripts/check.sh` completed **326 tests: 325 passed, one optional Matugen skip**
with the expanded private Wayland suites below. Bash syntax and the demo
snapshot passed. The final menu-background adjustment was followed by **17
passing UI regressions**, covering Liquid, popup motion, Settings font/color
input, launch/reuse and Wi-Fi/notification flows. Lint covers **131 QML files:
zero errors, 61 warnings**. The four additional warnings concern the same
incomplete Quickshell `BackgroundEffect.blurRegion` type metadata as existing
attachments; their runtime paths were exercised.

New checks cover local region selection in the real shell, rounded corners,
ancestor translation/scale, reparenting, hidden/transparent surfaces, menu
registration and teardown, switching back to Smoked, native white-text pixels
and retained input/color bindings. The relocated Settings fixture includes the
new component import. Its keyboard test now seeds a valid persistent keymap,
preventing Qt focus loss when transient virtual keyboards disconnect.

Actual compositor blur was rendered on **niri 26.04**, using a signature-verified
Fedora 42 package under nested Wayland with Mesa software OpenGL. A separate
application supplied a fine grid behind the shell. At scales **1 and 2**, edge
differences inside the panel fell to **8.6% and 6.6%** of baseline; outside stayed
at **87%**, consistent with dimming rather than blur. Closing restored the sharp
background. Control Center and Activity Island captures at both scales were
inspected. The floating Settings window was also inspected, including the rule
that prevents niri's focus-ring backing from filling its transparent body.
The updated niri fragment passes `niri validate`.

Radeon/RTX frame pacing and power use remain unmeasured. The wallpaper-only rim
and in-window menu limits are documented in
[Surface style](CONFIGURATION.md#surface-style).

## Black Liquid text and paused popup blur — 2026-10-18

Liquid labels, headings, button captions, menus and input text now use black
without an outline. This replaces the outlined typography described below.
Native inputs retain Qt selection/IME support with a light translucent fill.
Switching back restores each label's original color binding. Full-screen popup
blur is paused in Liquid without changing the saved preference; local bar blur,
popup dimming and motion remain independent.

`scripts/check.sh` completed **324 tests: 323 passed, one optional Matugen skip**,
with the expanded private Wayland suites below. Bash syntax and the demo
snapshot passed. Lint covers **130 QML files: zero errors, the same 57 warnings**.
Nine Liquid regressions cover rendered black glyphs without an outline,
Control Center labels and selected tabs, native input, late-created labels,
restored live color bindings, blur mode/support guards and saved preferences,
shader rendering and resource teardown. An OpenGL capture of Activity Island
and Control Center was inspected under private Sway.

The existing motion UI test now waits for the Settings entrance to settle
before locating and clicking Replay preview. Its earlier missed click also
reproduced on the unchanged baseline; the overshoot assertion remains intact.

Live blur requests on niri and Radeon/RTX rendering on the target laptop remain
unverified here. The wallpaper-rim rendering limits below still apply.

## Clearer Liquid surfaces and outlined labels — 2026-10-18

`scripts/check.sh` completed **323 tests: 322 passed, one Matugen skip**, with
the expanded private Wayland suites below. Bash syntax and the demo snapshot
passed. Lint covers **130 QML files: zero errors, 57 existing warnings**. The
changed shader was rebuilt and rendered through Mesa OpenGL in private Sway.

New checks verify near-clear active/inactive tile fills, translucent selected
tabs with readable text, outlined labels across Control Center, and restoration
of normal text when switching back to Smoked. Pixel assertions on a white
backdrop confirm that the black glyph outline actually renders and disappears
in Smoked mode. Activity Island and Control Center captures were inspected.
Existing checks still cover real rim refraction, missing wallpapers, corner
clipping, spring reversal/resize and texture release. Final input-contrast
adjustments were checked again with all eight Liquid regressions, including
native keyboard entry, and 18 capture/Night Light checks also pass after those
adjustments. Text fields/editors keep Qt input rendering and a dark translucent
fill. No new runtime dependency or per-label shader was added.

Target niri blur, GPU frame pacing and power use on the user's Radeon/RTX laptop
remain unmeasured; the existing wallpaper-rim rendering limits still apply.

## Optional Liquid glass — 2026-10-17

`scripts/check.sh` completed **321 tests: 320 passed, one skipped**, with the
expanded private Wayland suites listed below. The skip requires a real Matugen
binary. Bash syntax and the demo snapshot passed. Whole-tree lint covers
**129 QML files: zero errors, 57 existing warnings**; changed/new glass components
pass focused lint without diagnostics. The bundled shader was rebuilt with Qt
6.8.2's `qsb` for the existing cross-platform targets.

Six new regressions cover preference validation, persistence and portable
presets/backups; separation from Material profiles; all neutral color roles;
exact restoration of saved colors, opacity and per-island styles; retained font,
corner and motion settings; native Settings input and software fallback. GPU
checks use Mesa OpenGL under private Sway and exercise one shared texture per
window, separate windows, destruction, hidden consumers, ten repeated mode
cycles, resize, Jelly-v2 reversal/settling, live geometry mapping and button
input. The lifecycle/motion check also passes at output scale 2.

Rendered-pixel assertions check a transparent center, rounded corners, visible
refraction affected by the actual texture and a safe missing-image fallback.
A portrait wallpaper with spaces and `#` in its path verifies URL handling and
center cropping. Actual shell/Settings entry points rendered Activity Island,
Control Center and Appearance; their images were inspected. The final topbar
Settings capture loads without warnings after guarding temporarily negative
preview dimensions. No package, desktop screencopy or polling loop was added.

Tests use Quickshell 0.3.2 / Qt 6.8.2. Live niri blur, Radeon/RTX frame pacing,
power use and Vulkan/Metal rendering have not been measured here. Refraction
uses the saved wallpaper only at the rim; live apps remain compositor-owned.
Moved floating windows and wallpaper transitions have the approximations
described in [Surface style](CONFIGURATION.md#surface-style).

## Always-on wallpaper shapes and visual controls — 2026-10-17

The desktop layer now depends only on `desktopShapes`, independently of media.
It keeps moving with no player, during pause and through player disconnects;
the global Animations switch still stops motion. Turning the feature off
destroys all its surfaces. Media-card shapes retain their playback behavior.

`scripts/check.sh` completed **315 tests: 314 passed, one skipped**, with the
same expanded private Wayland suites as below. The skip requires a real Matugen
binary. Bash syntax and the demo snapshot passed. Whole-tree lint covers
**125 QML files: zero errors, 57 existing warnings**; all three changed QML
components pass focused lint without diagnostics.

New tests validate all six visual settings, reject nonfinite/out-of-range values
and wrong types, and check saved/preset round trips. Native pointer and keyboard
input adjusts all four sliders and the shape-style dropdown. Rendering checks
cover 12 shapes, size/opacity/speed changes, stopped rotation with continuing
drift, shrinking back to one shape and retaining the same desktop surface.
MPRIS tests confirm startup without a player and uninterrupted motion through
Chromium-style playback/pause/disconnect/reconnect. Shared media-card and desktop
widget regressions also pass.

Separate private-Sway checks confirm real click-through, coverage by an opaque
application, a second output, scale 2 and output disable/enable, then complete
surface release when the feature is disabled. The Settings desktop page was
rendered and inspected with saved custom options; logs contain no QML runtime
errors. No package or backend polling was added. Enabled shapes can animate
behind opaque apps even without media; target Fedora/niri GPU frame pacing and
power consumption have not been measured.

## Floating wallpaper shapes — 2026-10-17

This records the initial media-linked version, superseded by the section above.

`scripts/check.sh` completed **313 tests: 312 passed, one skipped**, with the
native desktop, media, lyrics, motion, polling, Bluetooth, Settings, clipboard,
annotation/OCR, authentication, idle and display-watchdog checks enabled. The
skip requires a real Matugen binary. Bash syntax and the demo snapshot passed.
Whole-tree lint covers **125 QML files: zero errors, 57 existing warnings**;
MediaAmbient, DesktopAmbient and DesktopPage pass focused lint without warnings.

New regressions exercise strict boolean validation, saved settings and portable
presets, full-output geometry, empty input regions, no keyboard focus or reserved
space, playback/pause, reduced motion, independent media-card/widget toggles and
surface destruction/recreation. A native Chromium-style MPRIS fixture also
checks no-player startup, pause, disconnect and reconnect.

A separate private-Sway check rendered the shapes, delivered a real virtual
pointer click to the wallpaper beneath them and confirmed an opaque application
covers them. Adding a second output, changing its scale to 2, disabling and
reenabling it, then turning the feature off preserved screen-sized surfaces and
released them when no longer needed. Rendered images were inspected; the test
log contains no QML runtime errors. Tests use Quickshell 0.3.2 / Qt 6.8.2 and
software rendering. GPU frame pacing, niri-specific layer behavior and the
owner's wallpaper have not been checked on the target laptop. The motion guard
does not detect application occlusion; enabled shapes can keep animating behind
an opaque app while music plays. No additional packages were installed.

## Whole-shell stability and Jelly-v2 — 2026-10-17

The baseline completed **305 tests: 274 passed, 31 skipped**. Expanded validation then enabled native clipboard, annotation/OCR, authentication, idle, Settings/personalization, Control Center drag/drop and detached display-watchdog suites in addition to media, lyrics, desktop, Bluetooth, polling and motion. The final run completes **310 tests: 309 passed, one skipped**, plus Bash syntax and the demo snapshot. The skipped test needs an actual Matugen binary; mocked Matugen v3/v4 and native palette UI checks pass. Whole-tree lint covers 124 QML files with **zero errors and 57 existing warnings**; changed motion/Island/settings components pass focused lint without diagnostics.

The stricter QML helper found `DeviceControls` assigning an undefined initial adapter-power value to Scan's boolean enabled property. It now defaults to false; all seven Bluetooth tests and the expanded suite pass after the fix. Static review also followed settings validation/atomic updates/imports, IPC dispatch, process teardown, notification/clipboard history and active-view subscriptions; the tests exercise their error/reconnect paths. This audit does not establish correctness for every external application or hardware driver.

Island size regressions validate old/default settings, profile and preset/backup round trips, live spring resizing, viewport fitting with large edge margins, bottom-bar placement and reduced motion. Native rendering was inspected at 700×560 with font size 18 and both lyric modes; longer content remains scrollable. Popup layout limits preserve the selected maximum; transient Jelly-v2 deformation is a visual effect around that layout.

Jelly-v2 tests exercise software and OpenGL/RHI, interrupted closing/reopening without position reset, preset changes during flight, bounded finite strain, prompt teardown and reduced motion. Pixel checks confirm an actual rendered bowed silhouette on both travel axes, expanded dimensions while deforming, fitting inside tight native bounds and release of the effect layer at rest. Legacy popup/Activity, menu-hover and resize regressions pass. The included shaders were built with Qt qsb; implementation references are linked in CONFIGURATION.md.

Two separate OpenGL/Mesa llvmpipe stress runs each open 210 panels: warmup followed by four 50-open bursts at speed 0.5×/2× and bounce 0/1, with rapid reversals and panel replacement. After every burst, overlay/loaders/effect layers are inactive, file descriptors remain at 37 and the direct backend child count remains one. Logs have no TypeError, ReferenceError, assignment, binding-loop or shader-pipeline failure diagnostics. Private Sway reports unsupported compositor background effects; this does not validate niri blur.

RSS samples (MiB, after warmup and each burst) were **329 → 438 → 456 → 472 → 433** for Expressive and **353 → 519 → 474 → 462 → 507** for Jelly-v2. Software GL/compiler caches are not separated from application allocations in these measurements. They show variation and additional Jelly-v2 rendering cost, and do not prove absence of a leak or predict laptop RAM/FPS. No memory-saving claim is made. Jelly-v2 is opt-in; its per-popup texture is disabled at rest. Measure long-session memory and 120 Hz frame pacing on the actual Radeon/niri session before treating performance as verified.

Target checks: try both bar edges, the largest/smallest Island limits, long labels, dropdowns, repeated open/close and Escape, changed outputs/scales and Animations off. Verify native niri blur, real device reconnects and GPU frame pacing; cloud tests use private Sway, Qt 6.8.2 and Quickshell 0.3.2. No runtime package was installed or added.

## Lyric modes and Island captions — 2026-10-17

The final private suite completes **305 tests: 274 passed, 31 skipped**, plus Bash syntax and the demo backend snapshot. Native media/Activity, desktop, lyrics, Bluetooth, polling and popup-motion checks were enabled. Whole-tree lint covers 123 QML files with **zero errors and the same 57 existing warnings**; changed lyric components, state and Behavior page pass focused lint without diagnostics.

Lyrics regressions cover saved defaults and preset/backup round trips; shared Island/view readers; transcript/current-line switching; default follow, manual scroll and reopening; pause/resume, seeking and cue boundaries; 2× playback with no visible timeline; player disconnect/reconnect; disabling lyrics/Island captions; plain lyrics, missing timing and title fallback. Disconnect testing exposed a stale timing binding reading a null player; the scheduler now checks the current player before reading it. Lookups remain bounded and offline/local/cache tests still pass. No runtime package was added.

A private native Wayland render was inspected for both lyric modes in the actual Activity popup and for Settings → Behavior. The popup resized from 897 px for the transcript to 741 px for the current line, with content inside the card and the popup heading retained. The compact title was confirmed to contain the current cue. Render logs contain no TypeError, ReferenceError, assignment or binding-loop diagnostics. Source attribution and the inspected end4-pC revision/license are recorded in THIRD_PARTY.md.

Target checks: play a timed local song, then a browser song; select both lyric modes, scroll manually and press Follow, seek, pause/resume and change tracks. Close all panels and confirm Island lines continue, then disable its lyric switch and confirm the track title returns. Enable online lookup only if wanted; live LRCLIB coverage and browser metadata matching were not validated against the user's music. Fedora/niri blur composition and perceived motion on the 120 Hz laptop remain hardware checks.

## Restored edge popup motion — 2026-10-17

The full private suite completes **300 tests: 269 passed, 31 skipped**, plus Bash syntax checks and the demo snapshot. Native bar clicks verify the first Control Center and Activity Island frame starts outside the actual output with opaque content. Motion checks cover all four edges, top/bottom Island placement, reversal without reset, prompt closure, resize while open, repeated openings and reduced motion. Legacy settings/import regressions preserve colors, fonts and appearance profiles while dropping the retired connected-surface flag. Focused changed-control lint has no errors; ShellState retains two existing ExitStatus metadata warnings. The connected-surface checks below describe the preceding implementation, now removed.

Private Sway/Qt 6.8.2/Quickshell 0.3.2 validates lifecycle and geometry. Fedora/niri blur composition and perceived motion on the 120 Hz target display still need a hardware check.

## Activity media layout and desktop canvas audit — 2026-10-17

Final validation completed **302 tests: 271 passed, 31 skipped**, plus Bash syntax and the demo backend snapshot. Native media/Activity, desktop, lyrics, Bluetooth, polling and popup-motion checks were enabled. Whole-tree QML lint reports zero errors and the same 57 warnings as the preceding revision; ordinary changed controls pass focused lint without diagnostics. The native Activity render was inspected after the layout fix.

The nested media layout reproduced a 93 px control group inside a 400 px card. Explicit standalone widths in the earlier regression missed this parent-layout constraint. The shared control now accepts the parent width; a regression checks wide → narrow/24 px font → wide reflow, bounds and horizontal transport rows.

Desktop resize was reproduced moving a widget from `(320, 296)` to `(300, 272)` while resizing 320×220 to 420×300. The origin is now frozen before resizing. Moving on a small viewport no longer persists clipped dimensions or fails the 180 px schema minimum; explicit resize saves the requested bounded dimensions. An unrelated settings update while a grip was held reproduced clearing both draft coordinates; active gestures now retain them.

Native checks exercise pointer move/resize, top-left anchoring, click-through masks, bottom/overlay layer transitions, constrained viewport geometry, concurrent gesture/settings updates, stable canvas instances, hide/show, named-output absence/reassignment, disable/re-enable and deletion. Output absence and small viewport dimensions are simulated; physical monitor hotplug, actual scaled niri outputs and pointer delivery through the native input mask still require target-machine checks.

## Lyrics, desktop and popup integration — 2026-10-17

The full private validation command completes **298 tests: 267 passed, 31 skipped**, plus Bash syntax and the demo backend snapshot. Enabled native suites include lyrics, desktop widgets, media controls, Activity, Bluetooth, controlled polling and popup motion. The connected-popup check also verifies spring resizing after the Island has opened. Ordinary changed components/pages pass focused lint without diagnostics; whole-tree lint reports zero errors and 57 warnings, including existing demo typing diagnostics and Quickshell native-window/attached-type/ExitStatus metadata limitations. New desktop layer windows were exercised at runtime. No runtime package was added or installed.

## Connected popup surfaces — 2026-10-17

Focused checks cover source geometry, reversal without progress reset, repeated openings, frozen closing anchors, spring resizing while open, prompt unloading, disabled mode, reduced motion and top/bottom bar offsets. A private Wayland test clicks the actual root-shell bar and opens both Control Center and Activity Island, then verifies settled backgrounds and closure. Both software rendering and OpenGL/RHI lifecycle checks pass; the compiled shader also rendered sample frames without shader/pipeline errors. Ordinary changed QML controls pass focused lint without diagnostics.

On the target machine, click different modules on each output, open/close quickly, switch between connected/island bar styles and test both bar edges. Compare with Connected popups off and Animations off. Check that background blur fades normally, text remains sharp after settling and the source/connector is absent when fully closed. Cloud tests use private Sway with Qt 6.8.2/Quickshell 0.3.2; Fedora/niri blur composition, scaled multi-monitor placement and Radeon 120 Hz frame pacing remain unverified. The Canvas fallback intentionally has simpler joins than the GPU shader.

## Desktop widget canvas — 2026-10-17

Validation covers bounded schemas/portable presets, atomic per-field edits from stale writers, deletion without resurrection and demo isolation. A private Wayland test verifies bottom/overlay layer transitions, pointer-driven move/resize and an empty input mask in click-through mode. Native resize commits the requested dimensions instead of waiting for a compositor configure event. niri multi-monitor hotplug/scale changes and compositor blur need target-machine checks.

## Synchronized lyrics — 2026-10-17

Parser/cache checks cover fractional/multiple timestamps, translations at identical times, offsets, plain text, oversized/expanded data, local/embedded precedence, offline and negative caches, instrumental tracks and corrupt data. A real private MPRIS/QML fixture loads embedded LRC, follows seek while paused, closes/reopens and clears lyrics on track change. Changed QML passes lint. LRCLIB catalogue coverage and timing of real browser players remain provider/player-dependent.

## Media interaction review — 2026-10-17

Final validation: `scripts/check.sh` completed **285 tests: 248 passed, 37 skipped**, with the private MPRIS, Bluetooth, Activity and polling-UI opt-ins enabled. All 19 changed QML files pass focused lint without diagnostics; Bash syntax, demo state and diff whitespace checks pass. Whole-tree lint has zero errors and the same 40 toolchain warnings as baseline. No Bluetooth helper remains after panel shutdown.

A new native MPRIS regression first reproduced a seek sent to the new track when a track changed during a pointer drag. The release now checks the player/track captured on press and the card/window visibility. Keyboard seeks are handled separately; ordinary click/drag/keyboard, shuffle and repeat still pass. Another QML check sets 24 px body text in a 200 px media card and verifies that all five controls stay within its bounds; controls stack when their measured widths do not fit. The demo progress follows play/pause consistently. Native root smoke checks opened eight panels and Settings → Top bar on private Sway without QML runtime errors.

## Native Bluetooth pairing — 2026-10-17

Seven focused checks pass against an isolated D-Bus daemon and a Gio BlueZ fixture: scan/stop, PIN and numeric passkey entry, numeric confirmation, authorization/service requests, keyboard display codes, invalid/stale replies, rejection/cancel, scan/prompt deadlines, adapter changes and BlueZ owner loss/re-registration. A Qt-input UI test scans, pairs with a leading-zero PIN, connects, closes/reopens Devices and handles a rapid reopen without leaving the agent stopped. Closing stops owned discovery and cancels pairing. The agent is on demand and does not request default-agent ownership.

`python3-gobject-base` is listed in requirements/install instructions and doctor; its Fedora package page was verified. No package was installed during this change. New QML passes focused lint (with a narrow suppression for Quickshell 0.3.2 unexported ExitStatus metadata). Whole-tree lint reports zero errors and the same 40 warnings as the original f2e53ef baseline in this toolchain. Real MT7921/headset pairing, firmware behavior and Fedora system-bus policy remain untested here.

## Ambient media shapes — 2026-10-17

Four Material polygons use LME geometry, with no new QML/C++ plugin. Native QML checks confirm movement while visible/playing, frozen coordinates while paused, unloading while hidden/disabled, and no animation with reduced motion. The toggle is portable and participates in appearance profiles. Two focused checks and changed-file lint pass. Radeon frame-time/power measurements are not available in this cloud environment.

## Stable media cards — 2026-10-17

QML checks cover partial metadata retention, coherent title/artwork replacement, the 500 ms metadata grace, 250 ms player-loss grace, eventual clearing, immediate cross-player switching and disabled mode. Transport/capability guards remain bound to the live player. Artwork uses Qt 6.8 retainWhileLoading with bounded thumbnails. The two new focused tests and changed-file QML lint pass; the three MPRIS control checks remain green. Hardware/browser-specific metadata sequences are not exhaustive.

## Extended media controls — 2026-10-17

Native MPRIS checks exercised pointer click/drag seeking, deferred seek during dragging, keyboard seeking, writable Shuffle and all three LoopStatus states. The private player logs confirm actual SetPosition/property writes. Unsupported controls are guarded and the feature is a boolean portable preference. All three focused tests passed; the existing five Activity/media/timer lifecycle checks also passed on private Sway, including a Chromium-like player without Position. Changed QML passes lint. Real browser/player capability differences remain dependent on their MPRIS implementation.

## Topbar gestures — 2026-10-17

Per-module left/right/middle click and vertical scroll mappings are validated, persisted and included in portable presets. Focused checks cover default/disabled/overridden actions, real Qt mouse-button and wheel delivery, primary-click isolation, DND, middle click and two-notch relative volume. The full check completed 269 tests (230 passed, 39 skipped); QML lint passed for the changed controls and settings. No additional polling or package is required. Fedora/niri hardware behavior remains to be checked.

## Backend audit fixes — 2026-10-16

Text copy no longer captures pipes inherited by wl-copy's clipboard owner.
A real forked-owner regression checks successful Unicode transfer and nonzero
exit handling; a separate private Wayland check returned successfully in 0.007 s
with the exact text available through wl-paste.

Volume, mute, microphone and brightness actions invalidate only their own
telemetry field, including partial failures. Readback remains immediate without
resetting the regular system-sample deadline. Ten volume updates inside one
sample window need ten writes and ten sink reads, with no nmcli commands.
Tests cover all five actions, failure/recovery and the next regular network
sample. Native QML/backend checks verify acknowledged values and cleared pending
states. The fixture retains acknowledgements per action so automatic mirror
refreshes cannot hide an operation's result.

The niri event stream retries after five seconds on startup failure or EOF.
An isolated test runs the actual backend loop and real child processes with a
simulated niri boundary: initial compositor unavailability, failed startup,
bounded retries, responsive commands, child reaping, resumed events and shutdown.
Malformed actions now return structured errors; unit and real stdin-protocol
tests verify that demo and Settings processes still accept subsequent commands.

The final `scripts/check.sh` run completed **265 tests: 230 passed, 35 skipped**,
with polling integration, native clipboard and clipboard UI opt-ins enabled.
A separate pointer-driven slider/mute/profile test also passed. Bash syntax and
demo snapshot checks passed. No dependency was added. Validation used private
Sway, Quickshell 0.3.2 and Qt 6.8.2; niri and hardware control boundaries were
simulated. Live Fedora/niri device behavior and resource savings remain
unverified. Other optional GUI suites, including the broad Settings integration,
were not rerun.

## Controlled polling — 2026-10-16

PipeWire privacy, BlueZ and power-profile reads now use separate five-second
caches. They are checked on each snapshot; with the default two-second poll,
background reads normally occur every six seconds. Opening Control Center's
Controls/Devices tabs, selecting a Bluetooth adapter and performing relevant
actions force fresh BlueZ/profile reads. Failed Bluetooth/profile actions also invalidate
their cache, since a device may have changed before reporting an error. Active
profile and advertised profiles are refreshed together, including provider
fallback and recovery after a service restart.

Disabling both privacy preferences clears captures at the next snapshot; re-enabling
them queries PipeWire again. Recording, mirroring, microphone mute and explicit
refresh invalidate capture data. Niri screencast events still update sharing
state through the existing event stream. External PipeWire/BlueZ/profile
changes can take approximately six seconds to appear at the default poll rate.

Network summary sampling uses two nmcli calls, retaining the actual active AP's
SSID and signal rather than substituting a connection profile's name. Periodic full AP
details and saved profiles are queried only while a Wi-Fi widget is visible;
the last widget closing removes those lists from live snapshots. Multiple
widgets share one watch, and a backend restart restores it. Wi-Fi operations
read fresh detailed state independently of the watch, so removed adapters and
stale network IDs are still rejected. Late operation completions refresh the
summary without re-enabling a closed widget's watch.

`test_polling.py` covers cadence, invalidation, device replacement, service
failure/recovery and command-count bounds. `test_local_qml.py` covers visible,
hidden and destroyed widgets, shared watches, tab changes and backend restart.
The opt-in `LME_TEST_POLLING_UI=1` test connects actual QML to the backend's real
main loop on private Wayland; only command/hardware boundaries are simulated.
It exercises close/reopen, adapter changes, Wi-Fi disconnect/reconnect,
Bluetooth power, profile changes, service recovery and backend restart.
The final `scripts/check.sh` run with `LME_TEST_POLLING_UI=1` completed **259
tests: 221 passed, 38 skipped**. Seven QML regressions also passed on private
Wayland. Changed QML files passed qmllint without errors; two existing Qt 6.8
`QProcess::ExitStatus` metadata warnings remain. Other optional GUI suites,
including the previously unstable broad Settings integration, were not rerun.
No runtime dependency was added. Physical MT7921/BlueZ/tuned behavior, resource
savings and battery impact still require checking on the owner's Fedora laptop.

## Dynamic Island captions and shared browser playback waves — 2026-10-16

The compact caption again follows the focused window when no higher-priority
activity exists; an unfocused desktop and the expanded popup use **Activity
Island**. Native regression checks cover two window titles, the empty desktop,
timer selections and the unchanged popup heading.

The five focused activity tests passed on both the software renderer and OpenGL
RHI. They cover known timing, missing duration, a second browser-shaped MPRIS
service without Position, player selection in both panels, pause/resume, hidden
panels and reduced motion. OpenGL screenshots of both indeterminate waves were
inspected. A separate actual `shell.qml` overlay check used the supplied Chromium
duration/position values in a private MPRIS fixture: both panels rendered a
moving played segment with the correct timing. The new read-only `mediaStatus`
IPC was checked with that player and with no native player.

The latest full `scripts/check.sh` run completed **236 tests: 233 passed, two
failed and one skipped**. The failures were the Settings gear integration and a
popup-close timing check (0.93 s against its 0.7 s limit). Both passed when rerun
individually without changing their assertions. Earlier full runs also had
intermittent IPC timeouts; this is not a consistently green full-suite result.
The skipped test requires the unconfigured external Matugen binary. Six changed
QML controls/services passed qmllint; Python compilation, shader compilation,
Bash syntax, demo state and diff checks passed.

Validation used private Sway, Quickshell 0.3.2 / Qt 6.8.2 and Mesa software GL.
Hardware backend actions were simulated; the final full run additionally used
`DBUS_SYSTEM_BUS_ADDRESS=unix:path=/workspace/.lme-dev/runtime/no-system-bus`.
No runtime dependency was added. Actual Chromium playback on the owner's
Fedora/niri/Radeon session remains unverified: playerctl reports valid timing,
so missing metadata alone does not establish the reported failure's cause.
After updating and restarting `gpt`, use
`qs -c gpt ipc call shell mediaStatus` to inspect the running shell's player,
timing capabilities and motion settings.

## Activity Island selection and wavy playback progress — 2026-10-16

`scripts/check.sh` completed **236 tests: 235 passed, one skipped**, with all
private Wayland opt-ins enabled. The skipped check requires the absent external
Matugen binary. The five focused activity tests also passed with Qt's OpenGL
RHI, explicitly checking that the shader path was active. Six changed QML
controls/services passed qmllint without warnings. Shader compilation, Python
compilation, Bash syntax, demo snapshot and diff checks passed.

Native pointer/keyboard checks verify the fixed Activity Island heading, all
three selected timer modes and the Start button's background against its card.
A private D-Bus MPRIS player exercises the real Quickshell service: advancing
position, play/pause, seeks to 0/50/100%, missing track duration, player removal,
close/reopen and stopping animation while hidden. Disabling the wave or all
motion leaves a straight timeline whose position still updates. Backend tests
cover boolean validation, appearance profiles and portable preset export.

The rendered OpenGL popup was inspected: whole-second time labels, visible
played wave and remaining track, and distinct Focus/Start backgrounds. Tests use
Quickshell 0.3.2 / Qt 6.8.2 under private Sway; OpenGL runs through Mesa software
rendering, not a physical Radeon. Actual browser/player integrations and 120 Hz
smoothness on Fedora/niri remain unverified. No runtime package was added.

## Custom shell identity and smoked glass terminology — 2026-10-15

`scripts/check.sh` passed **235 tests: 234 passed, one skipped**, with all private
Wayland opt-ins enabled. The skipped check requires the absent external Matugen
binary. Python compilation, Bash syntax, demo snapshot and diff checks passed.
Changed Settings controls/services passed qmllint without warnings; SettingsView
retains its existing repeater-item type warning.

The new native test exercises the real standalone Settings implementation:
Unicode names submitted through the input's accepted handler, live heading and
window-title updates, new local-notification senders, restart persistence,
another client's settings-file update, a 48-character wrapped heading and reset.
It verifies the stable Quickshell app ID and Settings focus routing against a
fake niri IPC executable returning a renamed window. Unit coverage rejects
empty/oversized/control-character/non-string names, preserves the previous value
after rejected edits and round-trips the name through a portable preset.

Validation used private Sway with Quickshell 0.3.2 / Qt 6.8.2. niri's supplied
app-ID rule was checked against its configuration source, but `niri validate`
and live floating/focus behavior on Fedora/niri were not run. Existing installs
need the updated Settings rule from `config/niri/lme-shell.kdl`; close and reopen
Settings once so its new AppId pragma takes effect. No package was installed.

## Notification appearance and adaptive cards — 2026-10-15

`scripts/check.sh` passed: **233 tests, 232 passed and one skipped**. All private
Wayland opt-ins were enabled; only the unrelated real portable Matugen test was
skipped because its external binary is absent. Bash syntax, Python compilation,
demo state and diff checks passed. The new card, emblem, settings page,
notification center and registry passed qmllint without warnings. Layer-window
files retain Quickshell's known attached-type metadata warnings; SettingsView
also retains its existing repeater-item type warning. Native loading succeeded.

New regressions cover long unbroken URLs, complete multiline text, wrapping
action labels, scrolling to the end, width-dependent height, all six popup
positions, output height limits, dynamic shell-status height, color/radius/border
updates, preset round-tripping and rejected preference values. Idle rotation
stops for hidden cards, its own toggle and disabled shell animations. The actual
Settings route and preview width are checked. Existing live screenshot-toast
annotation, retained closing cards, same-edge entry/exit, clipboard, font/color
editing and authentication tests pass.

The Settings preview was inspected in a private 1920×1080 Sway software-rendered
session with Quickshell 0.3.2 / Qt 6.8.2. No package was installed. Live rotation
smoothness, compositor blur and performance on Fedora/niri with Radeon at 120 Hz
were not assessed on the maintainer's hardware.

## Bar blur and same-edge popup travel — 2026-10-14

`scripts/check.sh` passed **231 tests, no skips**, with every private Wayland
opt-in and portable Matugen 4.2.0 enabled. Eleven changed control/bar/motion QML
files passed qmllint without warnings. Window/singleton files retain the known
Quickshell attached-type metadata warnings; their native runs loaded correctly.
Python compilation, Bash syntax, demo state and diff checks passed. No package
was installed.

Native geometry checks cover connected/custom-corner bar regions, independent
islands and their empty gaps. Bar blur is independently validated, persists and
round-trips through a portable preset. Native popup checks verify complete
off-screen entry, the same exit edge, spring/curve fallback, frame-observed
reversals, reduced motion, top/bottom Island and configured OSD positions.
Menus resolve actual placement before their first visible frame and preserve
position on reversal. Existing keyboard Wi-Fi, dropdown, font/color editing and
annotation-toast checks pass.

A real-shell startup test verifies that hidden loaders never mount during
construction. Both first and repeated layer-surface openings start beyond the
real output dimensions. Stable viewports avoid seeding against Quickshell's
unconfigured window size. Frame inspection exposed the initial hidden-Island
flash before this fix; settled Launcher/Control Center and entry/exit renders
were also inspected.

Notification checks retain closing content, preserve existing card objects when
another toast arrives, cap burst retention, release input and clear retired
entries. Status text survives its exit; authentication still focuses, cancels
and clears input. A stationary pointer no longer changes dropdown selection
during travel. Settings restart checks cover delayed shutdown and Quickshell
0.3.2's plain-text empty `list --json` result.

The cloud terminal transport disconnected during final work. A temporary helper
started through the already-running private preview completed validation in the
same sandbox. The preview hook was restored. An initial recovery run hit the
old preview's IPC; stopping that exact preview instance cleared the conflict
and the subsequent full run passed. Recovery files stay outside the repository.

Tests use Quickshell 0.3.2 / Qt 6.8.2 and private software-rendered Sway.
Live niri blur and Radeon/120 Hz frame pacing remain unverified, and `niri
validate` could not run without a niri binary. On the target desktop, include
the updated blur fragment (or add `lme-bar` to the merged namespace rule), run
`niri validate`, compare both bar layouts and open/close each panel rapidly under
Jelly. Native blur radius remains binary; backdrop dimming animates.

## Launcher feedback and shared spring motion — 2026-10-13

`scripts/check.sh` passed **229 tests, no skips**, with all private Wayland
opt-ins and portable Matugen 4.2.0 enabled. The 17 changed/new production motion
QML files passed qmllint without warnings using the private Quickshell import
path. Python compilation, Bash syntax, demo state and diff checks passed. No
system package was installed.

The Launcher previously drew a rounded selected row beneath a capsule-shaped,
scaled transparent hit target. Native pointer tests now verify matching 16 px
corners, scale 1 and first-row scroll gutters during hover and press. The same
flat feedback fix applies to wallpaper tiles; Font Picker, Audio and Devices
controls gain space inside their scroll viewports. Launcher, Control Center and
Settings renders were inspected after the changes.

The shared spring follows a changed target without resetting value or velocity
and settles exactly, including deterministic 120 Hz stepping. Real pointer
checks cover tab fill alignment through offset, resize, hover and press, and
reduced motion. Popup checks cover content replacement both during entrance and
fully open, rapid close/reopen, all four exit edges, spring/curve fallback,
backdrop dimming, Island/OSD lifecycle and motion disabled. Existing Settings,
grid drag/drop, clipboard, notification and capture-window checks also pass.

An initial full run had four window-discovery failures: the private environment
paired one Sway instance's Wayland display with the other instance's IPC socket.
Unix peer credentials confirmed the mismatch. The private helper now pairs them
by compositor PID; the affected checks and subsequent full suite passed. This
changed no shell code or host-session configuration.

On the target desktop, check the following under **Settings → Appearance**:

- Hover and press Launcher rows and installed-font options, including the first
  and last visible rows. Their feedback should stay inside a single outline.
- Switch Control Center/Settings tabs rapidly, interrupt popup exits by reopening,
  and switch between popup contents while opening. Motion should continue from
  the current position.
- Compare Smooth, Expressive and Jelly, then turn Spring motion and Motion off
  separately. Slider values should follow the pointer immediately in every mode.

Tests/rendering use Quickshell 0.3.2, Qt 6.8.2 and software-rendered private Sway.
The 120 Hz spring stepping is a logic check, not a GPU/frame-pacing benchmark.
Live Fedora/niri/Radeon smoothness and native compositor blur remain unmeasured;
blur radius is still binary while the existing dim layer animates.

## Clipboard/screenshot annotation and Favorites removal — 2026-10-13

`scripts/check.sh` discovered **228 tests: 204 passed, 24 skipped**, with private
clipboard, annotation and upgrade UI checks enabled. Changed clipboard,
notification, launcher and settings views plus the native fixture passed qmllint
without warnings. The shell entry and ShellState retain the previously documented
Quickshell metadata warnings. Python compilation, Bash syntax, demo state and
diff checks passed.

Real pointer tests verify clipboard-image annotation, right-click previews,
explicit image copying through wl-clipboard, pin/delete/clear behavior and
text-search/keyboard copying. Real private D-Bus notifications verify niri's
screenshot app-icon URI, ordinary icons remaining non-actionable, and annotation
through the Notification Center button and card body.

A click on the actual shell's screenshot toast launches a substitute Satty
executable through the live Python backend. The executable records its argv;
checks confirm `-f`, a private copied image under the isolated Pictures/Screenshots
directory and an unchanged source. Unit checks cover Satty-first selection,
explicit Swappy selection, local URI decoding, invalid/missing editors and image
input, persistence of notification image paths and demo isolation.

Existing Settings/Launcher/Wallpaper UI checks pass after removing Favorites.
Legacy settings and backup fixtures retain unrelated preferences and ignore the
two retired favorite fields; unknown fields still fail import validation.

Actual Satty/Swappy windows, their save/copy UI and target Fedora/niri behavior
remain unverified. No package was installed. The native tests use a private Sway
session and an editor substitute, not the owner's desktop or real editor UI.

## External audit follow-up — 2026-10-13

`scripts/check.sh` discovered **221 tests: 189 passed, 32 skipped**. Python
compilation, Bash syntax, demo state and diff checks passed. Six new regression
tests reproduced failures before the fixes and passed afterward.

Weather fixtures cover absent/null search results, malformed response types,
null daily data and arrays, invalid weather codes and keeping the last valid
forecast after a failed refresh. Clipboard subprocess checks read actual commands
and EOF through pipes and regular files, and exit cleanly with `/dev/null` stdin.
Capture is disabled and storage/configuration use temporary directories.

The package reference removes unused `grim`; installer dry-run already omitted
it and retains `slurp` for recording-region selection. The blur fragment adds
upstream's non-xray limitation as a comment; rendering settings are unchanged.

Private Wayland and hardware checks were not rerun for these changes. Weather
responses are fixtures, not live requests to Open-Meteo. No QML or layout changed.

## Independent slider/actions and stable card models — 2026-10-13

`scripts/check.sh` passed **215 tests, no skips**, with all private Wayland
opt-ins and the checksum-verified portable Matugen 4.2.0 enabled. Changed QML
passed qmllint without warnings; Python compilation, Bash syntax, demo state
and diff checks passed. No system package was installed.

Native QML exercises **5,628 cell scenarios**, accepting empty/matching-size
drops and rejecting incompatible ones while checking that unrelated controls
never move. Real pointer tests move speaker/microphone levels to 100% and
brightness to its 1% minimum, mute both channels, cycle the three demo profiles,
block actions in Edit mode, toggle independent visibility in Settings and open
the Power menu through its optional bar module. Hardware commands remain mocked
in that action test. Existing backend tests verify actual command arguments;
new fixtures verify two-profile capability discovery through D-Bus and CLI.

A private real Settings backend verifies persistence, card-order/size changes
leaving grid coordinates untouched, and the same card QObject instances after
a canvas move. Migration checks preserve old visibility, all eleven saved tile
positions, colors/fonts through unchanged preferences, and scattered layouts
that need extra rows. Updated 480 px and 900 px views were rendered and inspected.

Live Fedora speaker/mic/backlight and power-profile cycling still need the
owner's check; screenshots use demo data and software-rendered Sway with
Quickshell 0.3.2 / Qt 6.8.2. No RAM, GPU or 120 Hz benchmark was performed.
See [the scoped cleanup review](CODE_REVIEW.md) for what changed and what stayed
outside this pass.

## Editable Control Center and clipboard ownership — 2026-10-13

`scripts/check.sh` passed **211 tests, no skips**, with all private Wayland
opt-ins and the portable Matugen 4.2.0 check enabled. An initial run found that
the previous `/tmp` Matugen binary was absent after environment restoration;
the checksum-verified portable binary was restored and the full run passed.
No system package was installed. After final icon/edit-contrast adjustments,
all **six related native grid/upgrade checks** passed again. Changed QML files
passed qmllint without warnings; Python compilation, Bash syntax, demo state
and diff checks passed.

The QML engine tested **4,392 legal drop scenarios** across 4/8 columns and
4/8 rows, with no overlap or out-of-bounds placement. Real pointer/keyboard
tests use a private Settings backend: drag an occupied cell, cancel an outside
drop, block DND during editing, preserve readable edit opacity, resize, move to
the last row with focus scrolling, hide a control and restart to read the same
saved layout from disk. Validator tests reject malformed/overlapping data before
writing and round-trip the layout through portable presets. The earlier card
editor, responsive controls, launcher, Wi-Fi and notification checks still pass.
480 px and 900 px panels, including 8×8 editing, were rendered and inspected.

The native clipboard regression reproduced watchers surviving a SIGKILL before
the fix, then verified both terminate after it. Text/image capture, copy, pause
and settings disable/enable checks also pass. Existing orphans from older
versions are not killed automatically; log out/in once to clear them.

These checks use Quickshell 0.3.2 / Qt 6.8.2 on private software-rendered Sway.
Live niri edge-drag behavior, hardware toggles and 120 Hz GPU motion still need
the owner's session. Detailed cards remain below the quick-control canvas,
with their existing visibility, order and size settings. See
[the review and manual checklist](CODE_REVIEW.md).

## Noninteractive Matugen generation — 2026-10-13

Reproduced the reported multiple-source-color/no-terminal error with the real
Matugen 4.2.0 binary and the repository's multicolor wallpaper. After adding
`--source-color-index=0`, all nine schemes in both dark and light mode generated
complete, valid role colors without a terminal. The portable upstream release
was downloaded to `/tmp` and checked against its published SHA-256; no system
package was installed. Matugen 4.0/4.1 argument sources also expose this flag;
their binaries and the owner's exact wallpaper were not tested.

`scripts/check.sh` passed **206 tests, no skips**, with all private Wayland
opt-ins and the real Matugen test enabled. Regression checks preserve Matugen 3's
legacy arguments and verify ANSI removal and input redaction in error messages.
Bash syntax, demo state and diff checks passed. Matugen 3 compatibility was
checked through its argument source and a CLI fixture, not its actual binary.

## Independent islands, palette catalog and audio defaults — 2026-10-12

`scripts/check.sh` passed **203 tests, no skips**, with all private Wayland
opt-ins enabled on Quickshell 0.3.2 / Qt 6.8.2. Changed QML controls/pages passed
lint; Bash syntax, demo state and diff checks passed. Native checks apply a
preset to one island while keeping the other surfaces unchanged, test isolated
settings writers/reset/export, and switch Rose Pine, Catppuccin Latte and Gruvbox
through actual palette UI clicks. Preview leaves the active theme unchanged;
manual color overrides remain after Apply. Light/dark Settings and a bar with
three distinct island styles were rendered and visually checked.

Catalog checks cover all 35 Gowall registered palettes plus LME Dracula, valid
role colors and readable text against opaque base surfaces. These checks do not
measure contrast over every translucent wallpaper/application background.
Matugen options/config isolation and stale-preview rejection use a CLI fixture;
3.1.0/4.2.0 argument sources were inspected, but no Matugen binary was installed
or run in this environment.

Real FFmpeg/ffprobe tests preserve an audio track across MP4 remux and retain a
video with a clear error when requested audio is absent. The owner confirmed
System audio already works with the Bluetooth sink: the reported issue was the
widget resetting to No audio. The source/capture path stays unchanged; selection
now persists across openings/restarts. Live Bluetooth recording after this
update still needs the owner's check. No system package was installed and no
release/tag was created or moved.

## Display mirroring and topbar styling — 2026-10-12

`scripts/check.sh` passed **196 tests with no skips** with all private Wayland
opt-ins enabled, using Quickshell 0.3.2 and Qt 6.8.2 on private Sway. QML lint
passed for the changed bar surfaces, Top bar page, mirror controls, Displays
page and device panel. Bash syntax, demo snapshot and diff checks passed.

New coverage rejects invalid/inactive/identical mirror outputs, missing tools
and disabled mirroring. Real fixture child processes verify Stop, disconnect,
disable and close cleanup while another instance remains alive. Settings IPC is
checked without spawning a second owner; real virtual-pointer clicks exercise
the demo's Source/Destination and Start/Stop UI. Capture errors clear on restart.

Native QML checks exercise square-left/right presets, independent corners,
automatic roundness, height clamping, 0–4 px outlines, alpha colors and connected
versus island surfaces. Validation/export tests preserve old pill defaults and
round-trip the new settings. Rendered Settings pages were also visually checked.
The existing display-preview and Control Center drag checks still pass with the
demo's additional projector.

No new system package was installed. `wl-mirror` CLI/fullscreen support, its
actual GPL license and Fedora package availability were inspected; actual output
capture, projector hotplug and hybrid Radeon/RTX rendering were **not** tested
on the owner's Fedora/niri hardware. Follow [the hardware checklist](MIRRORING.md)
before relying on it for a presentation.

Cloud development and the target Fedora desktop are different environments.
The repository includes useful checks that work without controlling the user's
computer, and a separate real-session checklist.

## Development checks

The backend needs Python 3 and no third-party Python packages. The QML runtime
needs Quickshell and matching Qt packages. A useful check sequence is:

```bash
python3 -m compileall -q scripts
bash -n scripts/install.sh scripts/install-fedora.sh scripts/start.sh scripts/doctor.sh
python3 scripts/desktop_backend.py --demo --once
./scripts/install-fedora.sh --optional
./scripts/install.sh --dry-run
```

Run the backend tests with Python's standard library test runner:

```bash
python3 -m unittest discover -s tests -v
```

Installation safeguards can be checked with isolated
temporary `--target` directories; never test replacement against your actual
desktop config unintentionally.

Use a running Wayland compositor for QML runtime checks. Qt's `offscreen`
platform does not load Quickshell's `PanelWindow` backend and is not a substitute
for a compositor. A nested, headless Sway compositor with software rendering
can exercise the shell without controlling the host desktop. On a real Wayland
desktop, `scripts/start.sh --preview` opens a sample-data window safely.

During cloud development, the original five panels were rendered both as previews and
in the normal layer-shell layout at 1920×1080 under headless Sway 1.10.1,
Qt 6.8.2, and Quickshell 0.3.2. The final normal runtime log contained no QML
errors or warnings. The images in [previews](previews) show the actual QML;
their captions distinguish sample desktop state from native-service captures
with test notifications and mock applications.

The expanded control center and workspace board were also rendered at
1920×1080 with the same Qt/Quickshell toolchain, with its PipeWire module enabled.
Native Bluetooth tests use a private BlueZ D-Bus adapter fixture. Native mixer
checks use a private PipeWire 1.4.2 / WirePlumber 0.5.8 session, virtual devices
and a `pw-play` stream; they do not control physical audio hardware. Workspace
drag/drop in QML was exercised with virtual pointer input and simulated niri
state; the backend's stable-ID request was checked on a temporary Unix socket.

The following checks passed:

| Area | Verification |
| --- | --- |
| Backend | All 75 Python backend tests, including authentication cancellation, BlueZ failures/confirmation/rfkill, stable workspace ordering/movement, task validation, modern and legacy TuneD/PPD interfaces, and application metadata |
| Installation | Dry run, repeated install, overwrite refusal, backup preservation, broken symlinks, unsafe-target rejection |
| Startup | Demo/preview avoids desktop mutations; argument quoting and saved-wallpaper restoration |
| Shell scripts | Bash syntax and Fedora package preview; non-Fedora installation refused |
| Notifications | Native D-Bus capability negotiation, bodies/actions, replacement IDs, plain-text markup, action-button callbacks |
| Notification lifecycle | Action and clear-all dismiss with reason 2; expiry sends reason 1; app closure sends reason 3 and removes history |
| Do Not Disturb | Actual UI switch suppresses popups and retains session history |
| Media | Actual native MPRIS UI Play/Pause/Next/Previous callbacks and metadata updates against a mock application |
| Top bar geometry | 42 px bar with 8 px top margin; a borderless test app starts at y=50 under Sway, with no bottom reservation |
| System tray | Dropdown renders 18 px icons; native Activate and D-Bus menu action callbacks; outside click and Escape dismiss, including after a native menu |
| Power profile menu | All three labels readable on a dark popup; right edge stays onscreen; pointer and Down/Enter selection work with simulated backend state |
| Launcher keyboard | Typing `kitty` returns one matching demo app; arrow/Enter launches through the simulated backend; Escape closes |
| Demo isolation | Native media/tray actions and notification ownership disabled in demo/preview; normal native mode remains functional |
| Reusable cloud setup | Signed package installation and pinned Quickshell build repeated successfully; startup instructions use a private headless Wayland session |
| Bluetooth power | Real widget turns a private BlueZ adapter fixture on/off, verified with D-Bus property reads; no physical radio writes |
| Workspace board | Pointer drag moves a simulated window from workspace 1 to 3; selectors use stable IDs and show output names |
| Native audio mixer | Device/stream discovery, output preference metadata, and per-stream volume/mute confirmed in the private PipeWire session |
| Agenda | Calendar rendering, keyboard task add, checkbox completion, and focus timer/stopwatch state retained across panel closure |
| Expanded QML | New components pass `qmllint`; rendered panels and native fixture runs load without QML errors or warnings |

The Material/settings update passed eight additional tests covering layout
validation, nested-default isolation, stale-writer merging, external reload,
settings-only backend restrictions, demo isolation, desktop-entry installation and symlink-target protection.
All 51 tests passed. The six main panel previews, five standalone settings pages
and three alternate control-center tabs rendered without QML warnings/errors.
Roboto was resolved through fontconfig rather than replaced by a fallback.

The actual Settings window was exercised under the private Wayland compositor:
row reorder and cross-zone drag wrote the expected module arrays; changing the
shape was reflected by the separate running shell; repeated launch selected the
requested page through IPC. Its 800×600 minimum size remained usable with page
scrolling. Notification ownership stayed with the original shell while Settings
was open. These are cloud UI checks, not physical-device tests.

Package installation commands for Fedora 44 were not executed on the Debian
cloud machine. Niri configuration snippets were checked against upstream source
and documentation, but were not parsed by a running niri binary.

A nested compositor does not establish real niri positioning, laptop graphics
acceleration, output refresh rates, device control, or power-management behavior.
Use the target laptop for those checks below.

## Authentication popup validation

The native Polkit agent registered successfully when the real shell was started
without a controlling terminal on a private D-Bus authority fixture. The test
used a process-local login-session lookup fixture because the headless cloud
process is not in a real logind desktop session. It did not use the host Polkit
service, run PAM, submit a real password or grant privileges.

Six additional dialog tests exercise the actual QML window under headless
Wayland using virtual keyboard input: masked entry, failure/retry and Enter
success, Escape cancellation, Tab/Space on Cancel, account changes, a new
conversation clearing old input, and visible (non-password) challenges.
These use a simulated conversation in `authentication-demo.qml` and verify
that response text does not appear in its logs. The backend cancellation test
confirms that pending charging clears and the actual threshold remains unchanged.

To repeat all checks inside a **private Wayland test session** with `wtype` and
Quickshell installed:

```bash
LME_TEST_AUTHENTICATION_UI=1 ./scripts/check.sh
```

Without that environment variable, the six GUI tests are skipped; ordinary
backend checks remain usable without a compositor. For a manual isolated dialog
preview, run `quickshell -p authentication-demo.qml`. It accepts only the dummy
response `test-only`; do not enter a real password into a demo. It never starts
an authentication agent or performs a privileged operation.

The target laptop still needs verification of actual Polkit/PAM authentication,
successful helper execution, and its firmware's charging read-back. Check
[AUTHENTICATION.md](AUTHENTICATION.md) for the real-session setup.

## Wallpaper, weather and charging update

On 2026-10-11 (Asia/Saigon), `scripts/check.sh` passed **74 tests**. The new
contracts cover awww daemon startup/readiness, missing/failed commands, safe
path arguments, restoration without preference changes, numerical charge
thresholds, fixed IdeaPad conservation, modern `charge_types` enums, rollback,
readback rejection, asynchronous charge acknowledgements, weather geolocation,
forecast/search parsing, units, refresh/backoff/stale state, atomic manual
location selection and demo isolation.

Native `awww` **0.12.1**, pinned to
`f66e12a76dbc4c669b2f1375f78bce49f5b19d66`, was built with Rust 1.89.0 and
Cargo.lock. Its real daemon started automatically on the private Sway output.
The restoration CLI applied the bundled PNG; `awww query` confirmed the image
path and 1920×1080 output. The Settings backend action applied a fade and saved
its temporary preference file only after success. The upstream build emitted
three unnecessary-unsafe warnings; it completed successfully.

Live HTTPS requests successfully detected approximate IP location, parsed
current weather and a three-day forecast, and returned city-search results.
The native Settings UI searched for Da Nang and selecting a result saved its
normalized coordinates with automatic mode disabled. All preference writes
for that check used an isolated temporary config directory. No cloud location
is included in published preview images.

Control Center and Weather settings rendered under Qt 6.8.2 / Quickshell 0.3.2.
Weather remained usable at the Settings window's 800×600 minimum size with
scrolling. Clicking the demo charging button changed the displayed limit from
85% to 100%. Topbar labels were readable at 13 and 16 px, and Overview and
Applications opened after a one-second hover with no tooltip. New weather and
charging QML and the updated bar passed `qmllint`. ShellState retains two known
Quickshell metadata warnings about `QProcess::ExitStatus`; native/preview
runtime logs contain no QML errors or warnings.

Charge writes were tested against synthetic sysfs files only. The privileged
helper was previewed, never installed on the cloud host. Fedora package
availability, Polkit authentication and the Lenovo's physical charging cutoff
still need target-machine validation. The niri startup fragment was updated to
use the wallpaper wrapper but was not parsed by a niri binary in this cloud.
Reusable cloud install/start instructions now include pinned awww activation
and the Codeberg/Open-Meteo/IPwho.is network destinations. Saving that draft
does not prove publication or restoration into a fresh task.

## Target machine checklist

| Check | Expected result |
| --- | --- |
| `scripts/doctor.sh` in niri | Required tools and session connections are available |
| `niri validate` | Existing config plus shell bindings parses successfully |
| Launcher | Search, arrow navigation, Enter launch, Escape close |
| Top bar | Workspace/title updates, aligned pills, compact tray dropdown, and application spacing follow the configured niri gap |
| Control center | Volume/mute, backlight, radios, supported power profiles work |
| Audio mixer | Output/input selection and per-device/app sliders change the intended PipeWire nodes |
| Bluetooth | Correct adapter; power and known-device connection work; failures show service/rfkill details |
| Overview | Native live previews and drag/drop; board focus/movement on each output, including cross-output moves |
| Agenda | Tasks survive shell restart; focus timer/stopwatch persist across panel closure; timer completion respects DND |
| Motion and idle | Panels slide smoothly; disabled motion is immediate; Stay awake inhibits idle and resets on shell restart |
| Notifications | `notify-send` popup, notification center, DND work |
| Media | Compatible MPRIS player metadata and controls update |
| Charging | Supported thresholds or firmware conservation mode are detected; both choices are read back after authentication; verify physical cutoff on AC |
| Weather | Automatic IP location resolves, forecasts load, manual city and units update, offline errors preserve stale data |
| Settings | Independent window opens from launcher/bar/Super+Comma; changes reach the shell without restart; search, keyboard navigation and selected states work; wallpaper applies |
| Modular bar | Add/remove modules, reorder arrows, position menus and cross-zone drag/drop persist; connected pill is the default; crowded groups remain usable |
| Displays | Correct placement on internal panel and any external output |
| Laptop graphics | Integrated GPU is suitable; idle shell stays responsive |
| Lock and suspend | Lock authentication, suspend/resume, radios after resume |
| Native screenshot | Capture succeeds and uses configured screenshot location |

Power-off, reboot, logout, suspend, hardware radio toggles, and backlight writes
must not be exercised automatically in a cloud test or during read-only
diagnostics. Perform those checks deliberately on the laptop after saving work.

No cloud result certifies MediaTek MT7921 firmware behavior, NVIDIA driver
integration, exact 120 Hz output modes, battery consumption, thermal limits, or
sleep/resume reliability. Those depend on the real Fedora installation.

## Clipboard and Activity update

On 2026-10-11, all **98 checks** passed under the private Sway 1.10.1 session
with Quickshell 0.3.2, Qt 6.8.2 and wl-clipboard 2.2.1. This includes 89 backend
checks and nine optional native/dialog checks. The new tests cover Unicode and
multiline round trips, deduplication, full-text search, filters, image MIME/cache,
persistence, permissions, pause, pin limits, oldest-first/content-budget cleanup,
stale IDs, sensitive hints and validated settings. Supported recorder detection
uses synthetic proc fixtures, including other-user and zombie rejection.

A real `wl-paste --watch` / `wl-copy` integration test captured and restored
both text and PNG bytes, then exercised pause/resume and clear with/without pins.
The actual Clipboard QML was driven with virtual keyboard and pointer input:
search/Enter copied the intended bytes, including Enter before search debounce;
image preview, pin, confirmed clearing with retained pins and delete worked.
History for these tests lives in temporary directories. Updating the shared
Settings preferences also stopped/restarted capture while retaining history.

A private-bus MPRIS player exercised actual Play/Pause, Next and Previous button
callbacks and metadata updates. The Activity QML test started/paused/reset the
shared timer, verified stopwatch persistence across panel closure, reached timer
completion, closed with Escape/Close and disabled motion. A normal layer-shell
smoke check opened both new panels; expanding Activity left the application's
compositor geometry unchanged. All GUI checks run sequentially to avoid focus
conflicts between test windows.

Clipboard and Activity demo previews and the new Settings page rendered without
QML errors. Clipboard Settings was also inspected at its 800×600 window minimum;
navigation and page content scroll. New feature QML passed `qmllint` with the
Quickshell import path; ClipboardState retains the toolchain's existing
`QProcess::ExitStatus` metadata warning. Public previews use sample content.

Repeat the complete checks **only in a private Wayland session**:

```bash
LME_TEST_AUTHENTICATION_UI=1 LME_TEST_CLIPBOARD_NATIVE=1 \
LME_TEST_CLIPBOARD_UI=1 LME_TEST_ACTIVITY_UI=1 \
LME_TEST_POINTER=/path/to/virtual-pointer-click ./scripts/check.sh
```

The click driver accepts absolute X/Y coordinates and must match the test
output size. The MPRIS fixture uses PyGObject, configurable with
`LME_TEST_GI_PYTHON`; it is a test dependency only. Without native flags, the
nine integration cases skip. Do not overlap fixture instances, normal shell
panels or automatic screenshots during GUI checks.

Target Fedora/niri still needs validation with the user's actual clipboard
sources, MPRIS players, multiple outputs and supported recording application.
See [CLIPBOARD_ACTIVITY.md](CLIPBOARD_ACTIVITY.md) for the update checklist.


## Seven desktop upgrades (October 11, 2026)

The complete existing/new suite passed **114 tests without skips**, including
11 private-session integrations. Subsequent clock-adjustment and wired-versus-Wi-Fi regression checks
also passed, bringing the validated total to **116 tests**. The native upgrade
flow was rerun successfully with actual display-mode selection and monitor drag
before Apply and Keep. Backend contracts
cover appearance save/apply/delete, modular layout validation, private persistent
notification snapshots, bounded wallpaper scanning, arithmetic restrictions,
Wi-Fi identity/password handling and asynchronous acknowledgements.

Native QML pointer/keyboard checks cover profile saving, display confirmation,
wallpaper loading, module dragging, 480 px controls, fuzzy/typo app matching,
calculator errors/results, emoji/window search, Wi-Fi password popup cancellation,
notification groups/rules and DND expiry. The independent display integration
used a fake niri executable and verified a real 20-second rollback after the
initiating process exited. The safety timeout also uses a monotonic clock so
wall-clock changes cannot postpone recovery.

All changed feature components passed qmllint without warnings. Seven refreshed
QML previews rendered without runtime warnings. Settings was inspected in its
actual native window at the 800 × 600 minimum size, and every Control Center
card was inspected at half width. Icon-only controls use IconButton to avoid
padding clipping. Required Fedora package command generation and Bash syntax
checks passed. Preview/sample data never changed host settings or hardware.

Physical Lenovo MT7921 connectivity, actual panel/external-monitor commits and
Fedora package installation remain local verification steps. The runtime
watchdog and UI protocol tests cannot prove driver/display compatibility.
See [Desktop upgrades](DESKTOP_UPGRADES.md) for feature use and limits.


## Monitor, laptop idle, keybindings and popup blur — 2026-10-11

The full private Wayland suite passed 128 tests without skips. After the final lifecycle fix, all 13 laptop regressions passed (including the additional real Quickshell shutdown test), bringing the verified coverage to **129 distinct tests** across the full run and final targeted reruns. All seven authentication checks also passed after adding blur requests to that overlay.

```bash
source /workspace/.lme-dev/wayland-env.sh
LME_TEST_AUTHENTICATION_UI=1 LME_TEST_CLIPBOARD_NATIVE=1 \
LME_TEST_CLIPBOARD_UI=1 LME_TEST_ACTIVITY_UI=1 LME_TEST_UPGRADE_UI=1 \
LME_TEST_DISPLAY_WATCHDOG=1 LME_TEST_IDLE_NATIVE=1 \
LME_TEST_POINTER=/workspace/.lme-dev/pointer-click \
LME_TEST_DRAG=/workspace/.lme-dev/pointer-drag ./scripts/check.sh
```

Final coverage:

- CPU/network delta sampling, counter resets, CPU thread loads, process RSS, tricky process names, reused PIDs, bounded history and on-demand sampling. A real read-only `/proc` sample also succeeded.
- AC adapter online detection despite a full battery, validation and persistence of both idle profiles, profile switching, Stay awake and owned process cleanup.
- swaylock ready-fd success/failure and reuse with a controlled fake locker. Lock failure prevents both the backend's suspend and the idle CLI's sleep request.
- Actual swayidle on private Wayland: timeout, pointer-triggered resume and display-resume command on termination. Temporary niri commands log actions; no host display/lock/suspend is performed.
- Actual Quickshell Process shutdown: its backend can be killed without normal cleanup, so the Linux parent-death signal prevents an orphan idle daemon. Direct backend SIGTERM cleanup also passes.
- KDL includes/cycles, disabled binds/properties, nested comments, raw strings, Unicode escapes, strings containing braces, source line numbers and partial errors.
- Actual QML clicks/keyboard entry in System, process search, idle timeout selection, keybinding search and automatic refetch after Use path, alongside the existing launcher/Wi-Fi/notification/display/layout checks.
- New feature views, settings pages and chart components passed qmllint. shell.qml has Quickshell attached-type metadata warnings, and ShellState.qml has pre-existing QProcess::ExitStatus metadata warnings in this toolchain; both were validated at runtime. The unsupported-compositor fallback loaded correctly. 480 px Control Center and an 800 px Settings window were inspected; lists and longer content scroll rather than overflowing their cards.
- Demo actions report success without host commands or saved preference changes. Scripts passed Bash syntax checks and the diff passed whitespace validation.

The cloud compositor is Sway/software rendering, not niri on Radeon. **Native full-screen blur remains unverified on the target Lenovo**; its niri 26.04+ protocol/config requirements are documented in LAPTOP_FEATURES.md. Fedora PAM/logind suspend, physical AC switching and the actual AMD temperature sensors still need target-machine checks. No GPU telemetry, privileged charging write, real suspend/lock, or Fedora DNF transaction was performed in cloud validation.

Setup now retains signed swayidle 1.8.0 and swaylock 1.8.2 packages in the private toolchain and saves their installation/start instructions in the cloud configuration draft. The native tests run sequentially and clean up only their own processes.

## Night Light, Screenshot studio and motion — 2026-10-11

The final full suite passed **141 tests without skips** in 90.928 seconds,
including the private Wayland integrations. Bash syntax checks and the demo
backend contract also passed.

```bash
source /workspace/.lme-dev/wayland-env.sh
LME_TEST_AUTHENTICATION_UI=1 LME_TEST_CLIPBOARD_NATIVE=1 \
LME_TEST_CLIPBOARD_UI=1 LME_TEST_ACTIVITY_UI=1 LME_TEST_UPGRADE_UI=1 \
LME_TEST_DISPLAY_WATCHDOG=1 LME_TEST_IDLE_NATIVE=1 LME_TEST_CAPTURE_UI=1 \
LME_TEST_POINTER=/workspace/.lme-dev/pointer-click \
LME_TEST_DRAG=/workspace/.lme-dev/pointer-drag ./scripts/check.sh
```

- Night Light checks cover local-time boundaries, midnight schedules, disabled
  and manual modes, approximate sunrise/sunset, polar/location failures,
  temperature validation, owned worker cleanup and gamma failures. Standalone
  Settings never starts a second controller and clears stale active status
  when the desktop shell stops.
- Private native QML checks select the motion preset, edit Night Light times,
  reject invalid input, and measure Jelly overshoot followed by settling.
  Disabling animations removes both the transition and deformation. Old
  appearance profiles and Control Center layouts preserve saved values and
  receive the new defaults/module.
- Screenshot checks cover the three niri command forms, private paths,
  cancellation timeout, PNG limits, stale sessions, language validation,
  exclusive saves, rapid repeated saves and removal of partial failed writes.
  Late OCR completions cannot leak into the next screenshot.
- Actual pointer/keyboard input exercises Pen, Highlight, Rectangle, Arrow,
  Redact, Undo/Redo, Save PNG, Copy image and local OCR. The exported PNG keeps
  its 960 × 540 dimensions; covered pixels are opaque black, other pixels retain
  the source image, and copied/saved bytes match the flattened export.
  Text-field shortcuts still copy text. The native editor also works at its
  850 × 700 minimum size.
- The real shell opens its independent editor and can close/reopen it twice.
  This integration uses a controlled fake niri executable, not a real desktop
  capture. Real Tesseract recognizes the sample image; English and Vietnamese
  models were also exercised together for the published sample preview.
- Production feature views and motion components pass qmllint without warnings.
  The reused upgrades fixture has two existing dynamic-QObject metadata warnings;
  shell.qml and ShellState.qml retain the earlier attached-type/ExitStatus
  metadata warnings. Real runtime entry points show no corresponding errors.
  Three new preview images contain only project-generated sample content.

The owner confirmed that native popup blur works as expected on **niri 26.04**
after including `config/niri/popup-blur.kdl`: applications and the bar remain
visible behind the blur and the popup stays sharp. This supersedes the target
blur limitation in the earlier laptop validation section.

The private cloud session uses Sway and software rendering. Real `wlsunset`
0.3.0 reports gamma rejection on its virtual output; this is correctly surfaced
as a failure, not an active filter. **Gamma on the Lenovo panel and actual niri
screen/area/window capture still need target-machine verification.** The niri
`--path` API was checked against official IPC source, including v25.11. Fedora
DNF installation and 120 Hz hardware motion smoothness were not measured here.
Niri also copies the original screenshot; redaction does not erase that earlier
clipboard/history item. See [setup and usage](CAPTURE_NIGHT_MOTION.md).

The saved cloud configuration draft retains signed `wlsunset` and Tesseract
language packages, selects the live Sway socket instead of stale sockets, and
documents the complete private validation command. Saving the draft does not
publish the environment configuration.

## Settings, element theming and liquid feedback — 2026-10-11

The full private Wayland command completed **147 tests with no skips or
failures**, plus Bash syntax checks and the demo backend snapshot. Enable the
earlier native flags and `LME_TEST_PERSONALIZATION_UI=1`; see the saved cloud
start instructions. After the bar height boundary and semantic hover adjustments,
all six focused personalization checks were rerun, including both native cases.

- The actual root shell starts as `quickshell -c gpt` through an installed
  symlink. It opens Settings, reuses its instance, accepts Elements navigation,
  closes it through the window manager and opens it again. This uses private
  config/runtime paths and a fake niri executable without hardware mutations.
  A separate check covers a PATH with only the `qs` binary name.
- Real pointer/keyboard input exercises hover scale, press/hold/release ripple,
  Motion off/on, valid/invalid hex edits, body/bar font inheritance, bottom-edge
  geometry and the 36/64 px bar height boundaries. Panels retain their position
  during exit, can reopen mid-exit, unload after exit and close immediately with
  Motion disabled. These checks also inspect runtime logs for QML errors.
  A danger confirmation retains its red palette during hover after ordinary
  button colors are customized; the fixture does not activate that action.
- Backend checks reject malformed/unknown tokens, preserve different edits from
  stale clients under the existing file lock, reset individual overrides,
  migrate older profiles and preserve demo isolation.
- All shared controls, Settings pages/application, bar components, Theme and
  changed Activity/DesktopPreview components pass qmllint without warnings.
  Actual Settings was also inspected at 800 × 600 with 20 px body text; sidebar
  labels wrap without cutting words. The three new previews render project sample
  state and contain no user application pixels, credentials or location data.
- Caelestia/iNiR motion patterns and the ported DMS curves are attributed in
  `THIRD_PARTY.md`; the DMS MIT notice is retained. The private pointer tools can
  now be recreated by the saved cloud setup script. The setup update is a draft
  for review and is not automatically published.

These checks use Qt 6.8.2 / Quickshell 0.3.2 on private Sway with software
rendering. **Real Fedora/niri bar reservation, Lenovo gamma/capture and Radeon
120 Hz animation performance remain untested here.** Existing owner-confirmed
niri 26.04 blur behavior is preserved. The supplied main-shell log alone does
not establish the exact original Settings failure on the owner's installation;
the binary alias and native close/reopen paths are now covered directly.

## Settings IPC false success — 2026-10-11

The owner's Bash trace stopped in the Settings reuse branch after IPC returned
status `0`, with no window. On Quickshell 0.3.2, a missing IPC target also
returns `0` and prints "Target not found"; a legacy handler can acknowledge
`openPage` while its native window remains hidden. Both failures were reproduced
under private Wayland before the fix, and both regression cases failed with the
old launcher.

Settings now returns a boolean confirming its window is visible and not
minimized. The launcher checks this reply rather than the IPC exit status. An
unconfirmed existing instance is stopped by its exact Settings config path and
restarted, preserving saved preferences and the main shell.

`scripts/check.sh` passed **149 tests with no skips**, including the three native
personalization checks. Real virtual-pointer clicks on the root shell's bar gear
and Control Center gear opened Settings through the `gpt` symlink. Repeated
launches reused one window; window-manager close followed by reopening worked.
Recovery tests preserved saved accent/color overrides, and a failed stop did
not launch a duplicate. QML lint, Bash syntax and diff whitespace checks passed.

These checks use Quickshell 0.3.2 / Qt 6.8.2 on private Sway. The exact stale
instance on the owner's Fedora/niri session was not inspected; its IPC output
was suppressed by the old launcher. The target desktop still needs a check
after updating the installed `gpt` configuration.

## Target-machine checks for gestures, media and pairing

1. In Settings → Top bar, assign a gesture and restart the shell to confirm persistence. Scroll audio, right-click mute and right-click notifications/DND; verify that secondary clicks do not open the primary panel.
2. Play browser and desktop-player media. Click/drag the timeline, use arrow keys/Home/End, and try shuffle/repeat where supported. Change tracks during a drag; releasing must not seek the new track.
3. Switch players and rapidly change tracks while watching both media cards. Metadata retention is bounded; controls must immediately follow the live player's capabilities.
4. Pause, close the media panel, disable animations and toggle Moving media shapes. Check that motion stops and the controls stay readable with the configured font size.
5. With `python3-gobject-base` installed, scan in Control center → Devices. Test a headset and, if available, a PIN/passkey keyboard. Confirm, reject and cancel a request, switch adapters if present, and close/reopen Devices while scanning or pairing. Check that only the shell's discovery/pairing session stops. These hardware tests have not been performed in the cloud.
