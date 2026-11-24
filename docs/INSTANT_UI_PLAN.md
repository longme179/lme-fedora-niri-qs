# Instant panel opens and Settings tab switches: technical plan

Planning, 2026-11-24. Target: LME Shell `main` at `f234268`, Quickshell 0.3.2,
Qt 6.11.2, niri 26.04. This document authorizes no runtime change. It defines
the mechanism, the measurements and the gates for a follow-up implementation.

Owner ask: opening a panel (especially Control Center) and switching between
Settings tabs still shows a loading interval; make it feel instant. Reference
research is in [INSTANT_UI_RESEARCH.md](INSTANT_UI_RESEARCH.md).

**Recommendation in one paragraph.** Stop rebuilding built UI on click. Keep a
bounded pool of built panel trees and page hosts, park them off-screen, render
each one once invisibly to warm layout/pipelines, and make the click only swap
the visible instance. Add hover/idle anticipation so a first visit is usually
already built, and bound the cache with an LRU plus asynchronous teardown. Do
this first for pages (PageHost v2), then for panels (PanelStage), then keep the
Settings process alive/linger or move it in-process. Bound every step by
aggregate PSS and idle CPU, because retention without suspension turns open
latency into idle cost.

## 0. Definitions and success criteria

- **Open latency**: input event (bar click, tab click, IPC call) to the first
  frame that contains the final panel or page content. The end of the motion
  animation is not part of this number.
- **Retained open**: the tree is already built and parked; only visibility,
  geometry and the entrance motion remain.
- **Cached page**: a page host exists in the page LRU and has been laid out and
  drawn at least once.
- **Anticipated page**: a page host built in the background because the pointer
  rested on its navigation row or it is adjacent to the current page.
- **Cold open**: first instantiation in this process; unavoidable on the very
  first use unless a prewarm completed.

Provisional acceptance (Phase 0 measures the real baseline before these are
ratified; see section 4):

| Path | Target (p95) | Hard failure |
| --- | --- | --- |
| Retained panel open | <= 2 frames (33 ms at 60 Hz) | any blank/dead frame or > 100 ms |
| Cached page switch | <= 1 frame (16.7 ms) | previous page visible for > 2 frames |
| First visit after anticipation | <= 2 frames | > 100 ms |
| First Control Center open after login, prewarm complete | <= 100 ms | > 300 ms |
| Settings reopen inside the linger window | <= 100 ms to a mapped visible window | cold process restart |
| Idle cost | no continuous frame callbacks; CPU delta <= 1% of one core | visible repaint or timer at rest |
| Memory | aggregate PSS stays within 400 MB steady / 500 MB active | cache pushes the shell over budget |

The `33 ms` retained-open row is a two-frame interaction budget, not a
restatement of PR #107. #107's body table separately reports the first Control
Center open after login dropping 460 -> 33 ms, while its prose and commit
`c66dda7` describe 460 ms cold arrival vs ~70 ms retained reopen. Both #107
numbers are real but measure different conditions. The 400/500 MB cap is from
AGENTS.md; #107 measured +132 MB RSS (148 -> 280 MB) for retaining only the
Control Center tree, so the cache limits below are starting points, not
promises.

These are interaction targets, not a return to D1 startup profiling. D1 remains
closed; this plan does not reopen bootstrap measurement or general profiling.
Phase 0 instrumentation and its 10-run p50/p95 method still need the explicit
owner decision in section 7.

## 1. Root causes in the current code

### F1. One arbitrary-panel slot

`shell.qml` hosts all arbitrary panels in one `SlideLoader`
([shell.qml:187-195](../shell.qml#L187-L195)). The panel component is chosen
from `ShellState.panelKind`; `SlideLoader` keeps the built tree after close
(`keepAlive`) and parks it off-screen
([SlideLoader.qml:16](../qml/components/SlideLoader.qml#L16),
[SlideLoader.qml:37-42](../qml/components/SlideLoader.qml#L37-L42)). Changing
panel assigns a different `content`, and `retainedContent = content` replaces
the built item ([SlideLoader.qml:187-189](../qml/components/SlideLoader.qml#L187-L189)).
Only the most recently opened panel stays warm. Control Center -> Wi-Fi ->
Control Center makes Control Center cold again. Baseline: 460 ms cold arrival
and ~70 ms retained reopen (PR #107 body; commit `c66dda7`). The same PR table
reports 460 -> 33 ms for the first open after login, while its prose calls the
retained path ~70 ms; both are real but measure different conditions, and the
2-frame target in section 0 is an independent budget. The activity island has
its own retained loader and is not affected; the plan must not merge the two.

### F2. The page host is a two-slot staging area, not a cache

`PageHost` keeps the current page and one incoming page; `activate()` destroys
the retired page (`active = false; sourceComponent = null`)
([PageHost.qml:20-33](../qml/components/PageHost.qml#L20-L33)). An immediately
following page that is already incubating is reused
([PageHost.qml:35-46](../qml/components/PageHost.qml#L35-L46)), but
`activate()` nulls the retired page immediately (`active = false;
sourceComponent = null`), so even A -> B -> A rebuilds A. There is no two-page
retention; the two-slot path only helps a switch to a page that is already
incubating. Control Center has five tab components
([ControlCenter.qml:19](../qml/panels/ControlCenter.qml#L19)) and Settings has
six built-in pages plus catalog pages
([SettingsView.qml:142-167](../qml/settings/SettingsView.qml#L142-L167)). A
tab round trip re-instantiates and re-renders a page that was used seconds
ago. Catalog pages add a nested `Loader`
([SettingsView.qml:154-160](../qml/settings/SettingsView.qml#L154-L160)), so the
first visit pays two asynchronous creations.

### F3. Settings is a cold process after every close

The live shell starts `scripts/settings.sh --daemonize --page ...`
([ShellState.qml:128-132](../qml/services/ShellState.qml#L128-L132)). The script
reuses a live instance via IPC when one exists
([settings.sh:63-112](../scripts/settings.sh#L63-L112)), but the Settings window
quits its process on close ([SettingsApplication.qml:52](../qml/settings/SettingsApplication.qml#L52))
and the close button does the same
([SettingsApplication.qml:56-58](../qml/settings/SettingsApplication.qml#L56-L58)).
A normal close therefore removes the only reusable instance. The next open
starts a new Quickshell engine, a new backend, a new feature catalog and a new
page host. STATE records ~1.0 s launch-to-visible for Settings; that number is
a cold process measurement, not a reopen measurement.

### F4. Prewarm is a fixed-timer special case

The shell prewarms Control Center at 4 s and the activity island at 6.5 s
([shell.qml:220-250](../shell.qml#L220-L250)). Opening Control Center before
4 s, or after another panel replaced it, is cold. No other panel or page is
prewarmed. There is no pointer anticipation.

### F5. QML bytecode caching is not available on this binary

Quickshell 0.3.2 rejects the `DiskCache` and `RenderControl` pragmas and its
launch code disables the disk-cache environment path for `qsintercept` files
(`quickshell/src/launch/launch.cpp:91-129,233-242` at commit `9b0f339`). The
pin `9b0f339` is 11 commits after the `v0.3.2` tag; `launch.cpp` differs only
by moving `setDesktopFileName`, `lazyloader.hpp` is unchanged, and the
disk-cache block at lines 235-240 is commented-out code, so the relevant
behavior is the 0.3.2 behavior. A probe with `QML_DISK_CACHE=1`,
`QML_FORCE_DISK_CACHE=1` and an explicit cache path produced no `.qmlc` files;
the live cache contained one 688-byte file at probe time. A new Quickshell
process recompiles user QML. Inside one process, destroying and re-instantiating
a page does not recompile its QML, so this is a Settings process-start problem,
not the tab-switch bottleneck.

### F6. On-open data work is not the dead interval

`controlsRefresh` is a backend no-op that invalidates caches and lets the 2 s
poll refresh them ([desktop_backend.py:1401](../scripts/desktop_backend.py#L1401),
[desktop_backend.py:1473](../scripts/desktop_backend.py#L1473)). Display, idle
and equalizer refreshes route natively. These can change values after the
panel appears, but they do not explain the time before the panel item exists.
Prewarming a page also runs its `Component.onCompleted` effects off the click
path, which is a useful side effect.

## 2. Design

### 2.1 Principles

1. **Retain, do not rebuild.** A closed panel or visited page keeps its item
   tree; closing parks it out of sight.
2. **Park off-screen; do not toggle `visible` on a large panel.** LME measured
   about 800 ms of visibility propagation on a large retained panel
   ([SlideLoader.qml:39-42](../qml/components/SlideLoader.qml#L39-L42)). Page-
   sized trees may use `visible` after a measurement; panels use the existing
   park-offset mechanism.
3. **Warm the first render, not just the object.** A build that has never been
   laid out or drawn still pays layout, polish, shader/pipeline selection and
   the first frame. The existing invisible warm pass is the proven primitive
   ([SlideLoader.qml:104-114](../qml/components/SlideLoader.qml#L104-L114)).
4. **Warm in idle or anticipation, never on the click.** The click path only
   performs a visibility/geometry change on a ready tree.
5. **Bound the cache.** LRU limits, per-kind classes, asynchronous teardown,
   idle unload, and a measured memory budget.
6. **Keep one overlay window mapped.** Re-mapping the layer surface re-attaches
   every retained item; the current design already keeps it mapped
   ([shell.qml:112-116](../shell.qml#L112-L116)).
7. **Separate UI retention from data caching and polling.** This plan adds no
   polling cadence, no backend data cache and no A6 change.
8. **Keep the dormant tree quiet.** A retained tree must suspend timers,
   animations and effects; retention without suspension converts open latency
   into idle CPU.

### 2.2 PanelStage: a bounded multi-panel cache

New `qml/components/PanelStage.qml` (target under 250 nonblank lines) replaces
the single `panelLoader` block in `shell.qml`. It owns a pool of
`SlideLoader`s, one per panel kind, created lazily and retained per policy.

Public API:

```qml
Item {
    id: stage
    property string activeId: ""          // ShellState.panelKind
    property bool open: false             // ShellState.panelOpen
    property var componentFor: id => null // FeatureCatalog/legacy component
    property int heavyLimit: 2            // active + previous heavy
    property bool warmEnabled: true

    readonly property Item activeItem: ...
    readonly property bool surfaceLive: open || exiting || warming
    readonly property rect viewportRect: union of mounted, non-dormant loaders
    function warm(id)                     // build + invisible warm pass
    function anticipate(id)               // type warm on hover; optional instance
    function show(id)                     // present a ready/loading loader
    function evict(id)                    // async destroy
    function flush()                      // diagnostics/tests
}
```

Retention policy:

| Panel kind | Class | Default |
| --- | --- | --- |
| `control` | heavy | always retained after first build; prewarmed at startup |
| `overview` | heavy | retain while recent; binary window previews make it expensive |
| `launchpad`, `launcher` | heavy | retain while recent; app models are shared |
| `notifications` | medium | retain while recent |
| `wifi`, `tray`, `power` | light | retain for the session after first build |
| catalog panels | medium | LRU with the heavy budget; unbounded kinds are not allowed |

`heavyLimit = 2`, the page cache of 6 and the 90 s linger are starting points,
not promises. They are bounded by the #107 +132 MB RSS prior (one retained
Control Center tree, 148 -> 280 MB) and AGENTS.md's 400 MB steady / 500 MB
active aggregate PSS cap (section 0); Phase 0 captures the PSS baseline and
Phase 2/3 ratchet the limits down if the cap is hit. Eviction is asynchronous
(one loader per 50 ms while the stage is quiet), so a cache miss never tears
down the panel the user is opening. A never-used warm (hover anticipation or
startup prewarm) expires after a short idle window to avoid retaining a panel
the user only hovered.

Per-kind geometry is mandatory. Today `shell.qml:190-201` derives `centered`,
`direction`, `x`, `y`, `width`, `height` and the tray anchor from
`ShellState.panelKind` / `trayAnchorX`. A pool with one loader per kind must
freeze each loader's geometry from its own kind (and screen) at creation and
update only the active loader; otherwise changing `activeId` recomputes every
parked loader's geometry and its park offset. The stage owns `centered`,
`direction`, `travelEdge`, `width`/`height` and the x/y bindings per loader,
and passes live screen/tray changes only to the loader for the current kind.

Warm path (the existing `SlideLoader` contract):

```qml
function warm(id) {
    const l = ensure(id);                 // SlideLoader { keepAlive: true }
    if (l.item || l.controlWarmupDone) return;
    l.controlWarmupPending = true;
    l.dormant = true;
    l.retainedContent = componentFor(id);
    l.mounted = true;
    l.startControlWarmup(open, false);    // deferred while the stage is busy
}
```

`startControlWarmup` already defers when a panel or the island is open, runs
three invisible layer frames and parks
([SlideLoader.qml:104-114](../qml/components/SlideLoader.qml#L104-L114)).
The stage must call it only when `!open` and no other loader is transitioning,
and it must connect each loader's `onLoaded`/`onDormantChanged` to the warm
call exactly as `shell.qml` does: `startControlWarmup` requires a loaded item
and returns early while `item` is null.

Present path:

```qml
function show(id) {
    if (activeId !== id) {
        const previous = loaders[activeId];
        if (previous) previous.shown = false;   // exit; snapOut on atomic swap
    }
    activeId = id;
    const l = ensure(id);
    l.content = componentFor(id);              // retained tree if already built
    l.shown = open;
    if (l.status === Loader.Ready) l.move(1);
}
```

When a different panel replaces the current one, use the existing atomic swap
(`ShellState.panelSwap`) to `snapOut()` the outgoing loader so its exit flight
does not play next to the newcomer. The stage exposes one `activeItem` for
focus and for the popup/backdrop layer; inactive loaders keep `enabled` false
(`SlideLoader` already does `enabled: shown`) and stay parked.

Overlay integration (the risky part):

- `overlay.surfaceLive` becomes
  `stage.surfaceLive || islandVisible || islandWarmup`
  ([shell.qml:118](../shell.qml#L118)).
- `overlay.viewport` reserves one frame per mounted, non-dormant loader plus
  the island, using the existing `reserve()` helper
  ([shell.qml:120-146](../shell.qml#L120-L146)). Do not union parked loaders;
  their rectangles can be outside the output.
- `SurfaceBlurRegion` points at `stage.activeItem` for the panel, and the
  island keeps its own region. Nested popups remain in
  `GlassState.popupsFor(overlay)`.
- The input mask stays the overlay's full content while a panel is open, so a
  click outside still closes it; inactive loaders must not receive input.
- `WlrLayershell.keyboardFocus` and `popupBackdrop` remain driven by
  `ShellState.panelOpen`.
- The overlay window remains mapped and shrinks to 1x1 when nothing is live;
  eviction does not unmap it.

Do not grow `shell.qml` beyond its 291-nonblank ceiling. The stage logic lives
in the new component; `shell.qml` only passes state, the component factory and
the viewport/blur bindings. `qml/services/ShellState.qml` is also at its
398-nonblank ceiling (`config/architecture.json:largeFiles`). Do not add
`openSettingsPage`, `anticipatePanel`, Settings-window flags or any other new
field/function to it; put the new state in dedicated components/singletons and
let ShellState call them. A ceiling ratchet is an explicit owner decision
(section 7.8), not an implementation detail.

### 2.3 PageHost v2: a keyed page cache with anticipation

Keep `qml/components/PageHost.qml` as the API name; add `contentKey`,
`cacheLimit`, `anticipate(key, component, properties)` and `release(key)`.
The current enter motion remains.

Structure:

- One `Item` stage with `clip: true`.
- Page hosts are created lazily with a `Component`:
  each host is an `Item` containing a `Loader` (`asynchronous: true`) and a
  `FrameAnimation` used for the first-render warm pass.
- Hosts are keyed by a stable string, not by the `Component` object. Two
  catalog pages can share the same wrapper `Component`; keying by component
  would collide.
- Cached hosts are parked at `x = stage.width` (past the clip) with `visible`
  left `true`; the stage clip prevents rendering. `visible = false` is a later,
  page-specific optimization only after a measurement, because the ~800 ms
  visibility-propagation cost in principle 2 applies to large trees. The
  visible page is `x = 0`, `visible = true`.
- Switching to a cached host is a parking swap, not a new loader. Switching to
  a loading host keeps the previous page visible until `Loader.Ready`, then
  swaps; the click is acknowledged immediately by the navigation state.
- `cacheLimit = 6` is the DMS reference starting point
  ([SettingsMetrics.qml:90-97](https://github.com/AvengeMedia/DankMaterialShell/blob/291f4c58786a4fa38832a3267e66b889748c7c40/quickshell/Modules/Settings/Widgets/SettingsMetrics.qml#L90-L97)).
  Phase 1 measures the real page costs and the owner ratifies the value.
- Eviction is asynchronous: one page per 50 ms while no transition is running,
  using `destroy()` after clearing `sourceComponent`/`active`. Never evict the
  current or an in-flight page.
- `anticipate()` is called from navigation hover/focus and after a 90 ms
  timer; it builds the page at the parked position, warms it for one to three
  frames, then caches it. If the user clicks before the warm pass starts, the
  page is presented as soon as it is `Ready`; the warm pass is cancelled.
- Idle neighbor prewarm builds the next/previous page after the current page
  settles, one at a time, only while the cache has room. This mirrors DMS's
  `_nextAhead()` but is optional in Phase 1.

Sketch:

```qml
Item {
    id: root
    property Component content: null
    property string contentKey: ""
    property int cacheLimit: 6

    Item { id: stage; anchors.fill: parent; clip: true }

    Component {
        id: hostComponent
        Item {
            id: host
            required property string pageKey
            property Component pageComponent
            property bool warmDone: false
            width: stage.width; height: stage.height
            visible: true             // parked past the clip
            property bool warming: false
            Loader {
                id: loader
                anchors.fill: parent
                asynchronous: true
                sourceComponent: host.pageComponent
            }
            FrameAnimation {
                id: warm
                running: host.warming
                property int frames: 0
                onTriggered: {
                    frames++;
                    if (frames >= 3) {
                        host.warming = false; host.warmDone = true;
                        host.layer.enabled = false;
                        host.opacity = 1; host.x = stage.width; host.z = 0;
                    }
                }
            }
        }
    }

    function ensure(key, component, properties) {
        if (hosts[key]) return hosts[key];
        const host = hostComponent.createObject(stage, Object.assign({
            pageKey: key, pageComponent: component,
            x: stage.width, y: 0, visible: true
        }, properties || {}));
        hosts[key] = host;
        return host;
    }

    function warm(host) {
        if (host.warmDone || host.warming) return;
        // Draw once behind the current page, transparent, then park.
        host.x = 0; host.z = -1;
        host.opacity = 0; host.layer.enabled = true;
        host.visible = true; host.warming = true;
    }
}
```

The sketch is illustrative, not final code. The implementation must handle
`Loader.Error`, `Component.onCompleted` order, and the case where a cached host
is re-presented while its page data changed while hidden.

Consumer changes:

- `ControlCenter.qml`: `PageHost { contentKey: root.selectedTab.id; content:
  root.componentFor(...); cacheLimit: 5 }`; tab delegates call `anticipate` on
  `hovered`/`activeFocus`.
- `SettingsView.qml`: `contentKey: root.page`; a `pageComponent(key)` helper
  returns the built-in component or a per-key catalog component; nav delegates
  call `anticipate` on hover/focus. The current `catalogPage` wrapper becomes a
  per-key component or a generic component with an explicit `pageUrl`
  initial property.
- `PageHost` must preserve the current focus/scroll behavior. A cached page
  keeps its Flickable position; re-entering does not jump to the top unless the
  navigation contract says so.

Hidden-page hygiene: a cached page is parked past the clip with `visible`
left `true` by default; do not rely on `visible` to stop its work. Timers bound
to global services keep running, so audit the six built-in pages and the
catalog pages for unconditional timers/animations and gate them on a new
`pageActive` property. The display page already gates its timer on
`root.visible`; keep that pattern.

Scope boundary: this page cache lives inside the owning `PageHost`. It
survives tab switches but not a Control Center teardown or a Settings process
exit. Phase 2 keeps the Control Center tree alive across panel switches;
Phase 3 keeps the Settings process alive across closes. The phases are
complementary: Phase 1 removes the per-tab rebuild, Phase 2/3 preserve the
cache across the larger lifetime boundary.

### 2.4 Settings warm session

Options, in increasing scope:

| Option | Reopen latency | Memory | Complexity | Isolation |
| --- | --- | --- | --- | --- |
| A. Status quo | cold process, ~1 s | lowest when closed | none | strong |
| B. Hide + linger | ~50-100 ms while alive | Settings PSS while lingering | low | strong |
| C. Stub process | ~200-300 ms view rebuild | lower than B | medium | strong |
| D. In-process Settings window | ~0-50 ms after idle warm | shares engine/backend; likely lower total than B | medium-high | weaker |

Recommended sequence: implement **B** first as the low-risk win, measure it, and
prototype **D** behind `LME_SHELL_INPROCESS_SETTINGS=1` if the memory numbers
support it. C is only needed if B's memory is unacceptable and D is rejected.

B implementation:

- Add `property bool shown` to `SettingsApplication`; bind
  `window.visible: shown && view.status === Loader.Ready`. Do not assign to
  `window.visible` directly, because that breaks the existing binding.
- `onClosed` and the close button call `hideWindow()`: set `shown = false`,
  start a linger timer (`LME_SETTINGS_LINGER_MS`, default proposed 90 s, 0
  disables and quits immediately).
- IPC `openPage` stops the timer, sets `shown = true`, raises/unminimizes and
  keeps the existing page navigation. `startupPending()` returns false while
  the view is Ready.
- The linger timer quits the process. A second timer may optionally destroy the
  `SettingsView` (frees the page cache) and keep the process as a stub; that is
  option C and is not part of the first implementation.
- If the backend dies while hidden, keep the current restart behavior; do not
  quit the Settings process solely because the backend is reconnecting.
- Keep `scripts/settings.sh` unchanged: its IPC path already finds a live
  instance and focuses it.

Measure: aggregate PSS with the Settings process lingering for 10 s, 60 s and
5 min after close; reopen latency from IPC to first mapped frame; behavior of
the niri window close button, Escape, and the desktop entry. If the default
linger breaks the memory target, reduce it or move to C/D.

D implementation (prototype only):

- Add a `SettingsWindow.qml` `FloatingWindow` to the main shell, hidden by
  default, hosting the same `SettingsView` and `FeatureBootstrap` services.
  A new `SettingsWindowController` (not `ShellState.qml`, which is at 398/398)
  toggles it in-process when the env flag is 1; `settings.sh` remains the
  standalone path when the shell is not running.
- Prewarm the window's `SettingsView` in idle and cache pages as in section
  2.3. This removes the second QML engine, second backend and cold process.
- Risks: a shell reload closes Settings; a shell crash takes Settings with it;
  the settings window must remain a normal niri toplevel; the existing IPC and
  desktop-entry behavior must keep working. Measure aggregate PSS vs B before
  recommending it.

### 2.5 Prewarm scheduler

Replace the two fixed timers with `qml/components/PrewarmScheduler.qml`:

- Gate on `ShellState.backendReady && Theme.ready && FeatureCatalog.settled &&
  !demo && !preview && !ShellState.authenticationActive`.
- Yield between steps with `Qt.callLater` or a 0 ms timer; never run a warm
  pass in the same frame as the bar's first paint.
- Order: Control Center, activity island, then any panels listed in
  `LME_SHELL_PREWARM_PANELS` (default empty). Settings page prewarming belongs
  to the Settings process and is handled by its own page host.
- Defer or cancel if a panel opens, the island opens, or the compositor is
  under load. `SlideLoader.startControlWarmup` already defers; the scheduler
  must not spin.
- Battery-saver gating is proposed, not authorized: AGENTS.md keeps A6
  (polling/cache/power policy) out of scope. Keep the Control Center warm; let
  section 7.6 decide whether secondary prewarm is skipped when
  `ShellState.batterySaverActive` is true.
- Hover anticipation on the bar: `BarModule`, `ActionBarButton` and the
  network/audio widgets call the new prewarm policy's `anticipatePanel(id)` (not
  `ShellState.qml`, which is at 398/398). Level 1 only
  compiles the component (`FeatureCatalog.component`), which is cheap. Level 2
  (optional, measured) warms the panel instance after 150 ms of hover and
  expires it after 30 s if never opened. DMS prewarms the type on hover
  ([PopoutService.qml:137-146](https://github.com/AvengeMedia/DankMaterialShell/blob/291f4c58786a4fa38832a3267e66b889748c7c40/quickshell/Services/PopoutService.qml#L137-L146)).

### 2.6 Cache, compile and pipeline guardrails

- Do not add `@pragma DiskCache` or `@pragma RenderControl` on 0.3.2; both are
  unrecognized. Do not add `QML_DISK_CACHE` expecting a win; the probe
  produced no `.qmlc`.
- Keep the Qt pipeline cache directory persistent. The warm pass is what
  selects and compiles the shader/pipeline state for a page or panel; this is
  why an object-only prewarm is insufficient.
- Evaluate a Quickshell upgrade separately. DMS uses `@pragma DiskCache` on a
  newer engine; a newer Quickshell would reduce Settings process start. That
  is a system/package change and needs owner approval; it is not part of this
  plan's code scope.
- In-process Settings (option D) is the code-only way to avoid a second cold
  QML engine.

### 2.7 Dormant-tree contract

Retention is only free if a parked tree is quiet. `SlideLoader` parks with
`visible` still true and only the transform off-screen
([SlideLoader.qml:37-42](../qml/components/SlideLoader.qml#L37-L42)), so
`visible`-bound timers keep running. The existing Control Center clock uses
`SystemClock { enabled: root.visible }`
([ControlDashboard.qml:37](../qml/panels/ControlDashboard.qml#L37)); while the
panel is parked, that is still true.

Implement an explicit activity property:

- `PanelStage` sets `item.panelActive = (id === activeId && open)` on each
  panel root after creation and on every active change. Panel roots that need
  it declare `property bool panelActive: true`.
- Bind timers, clocks, media loops and shader `layer.enabled` to
  `visible && panelActive` (or `enabled: panelActive` for animations).
- For catalog panels, pass the same property through the component wrapper;
  do not assume every descriptor root has it (guard with
  `"panelActive" in item` / `item.setProperty`).
- Do the same for page hosts: a cached page is parked past the clip and stays
  `visible`; timers that do not follow the park must be gated on a `pageActive`
  property.

Audit list for Phase 1/2: `ControlDashboard` (`SystemClock`, `MediaAmbient`,
`AudioVisualizer`), `SystemMonitor` (monitor process/timer),
`DeviceControls`, `AudioMixer`, `Agenda`, `AppearancePage`, `DisplayPage`
(existing visible gate), `EqualizerPage`, `IdlePage`, `WallpaperPage`,
`AboutPage` (update check), and any catalog page with a `Timer` or `Process`.

## 3. Implementation phases

Each phase is one branch and one review stop, tests first, per AGENTS.md. The
plan itself is docs-only and needs only G0.

### Phase 0: latency instrumentation and baseline (no behavior change)

- This phase is proposed only. D1 startup profiling is closed; do not commit a
  latency probe or a 10-run p50/p95 methodology to a runtime branch until the
  owner approves section 7.7. A local, non-committed baseline may be measured
  first.
- Add `qml/components/LatencyProbe.qml` or a tiny shared JS helper behind
  `LME_SHELL_LATENCY_TRACE=1`. Record monotonic `Date.now()` timestamps for:
  input/state change, page-host creation, `Loader.Ready`, first frame after
  present, panel creation, first frame after open.
- Add `tests/test_latency_probe.py` using the local, untracked `run_qml`
  harness (`tests/test_local_qml.py:13-56`; `tests/` is gitignored, commit
  `022ad7a`, so it is not in the published repo) to assert the probe emits one
  well-formed record per transition and stays silent when the env flag is off.
- Add a headless-Sway render measurement modeled on the local, untracked
  `tests/test_island_motion_render.py`: open and close panels and pages, parse
  the probe logs, report p50/p95. Do not commit raw CSV/log directories.
- Capture the aggregate PSS baseline before any cache is enabled; #107's
  +132 MB RSS prior (148 -> 280 MB for one retained CC tree) and the 400/500 MB
  cap are the bounds. Measure the latency baseline: first CC open at 1 s and
  10 s after shell start, CC reopen after Wi-Fi, page A->B->A in Settings and
  Control Center, Settings open/close/reopen, idle CPU with a panel parked.
- Gate: G0 + G1 + the new focused tests, if the owner approves this phase. No
  runtime behavior change.

### Phase 1: PageHost v2 and page anticipation

- Replace the two-loader staging with the keyed LRU cache, parked hosts, warm
  pass, hover anticipation and idle neighbor prewarm.
- Update `ControlCenter.qml` and `SettingsView.qml` to supply keys and
  per-key catalog components, and to call `anticipate` on hover/focus.
- Add `qml/components/PageCachePolicy.qml` (or constants in `Theme`) for the
  cache limit, anticipation delay and teardown interval; keep them overridable
  for tests (`LME_PAGE_CACHE_LIMIT`, `LME_PAGE_ANTICIPATE_MS`).
- Add hidden-page hygiene to the audited pages.
- Tests: `tests/test_page_host_cache.py` (identity preservation across
  A->B->A, LRU eviction, anticipation, no errors), a Settings/Control Center
  render case, and the existing QML gates.
- Metrics: cached switch p95, first-visit-after-anticipation p95, PSS delta per
  page, idle CPU with a cached page hidden.

### Phase 2: PanelStage and multi-panel retention

- Add `PanelStage.qml` and `PanelCachePolicy.qml`; replace the single
  `panelLoader` in `shell.qml` without growing `shell.qml` past its ceiling.
- Wire `surfaceLive`, viewport union, active blur region, focus and the
  existing atomic swap. Keep the input mask behavior.
- Add the `panelActive` dormant contract for Control Center, the island (which
  already has its own visible guard), and the heavy panels in the retention
  table.
- Tests: `tests/test_panel_stage.py` (open A, open B, reopen A; identity
  preserved; inactive parked; per-kind geometry/direction unchanged across
  active changes; viewport excludes parked loaders; eviction does not evict the
  active loader), a headless render case for CC->Wi-Fi->CC, and memory/idle
  checks.
- Metrics: retained panel open p95, cold first open after prewarm, PSS delta
  per retained panel, idle CPU with all retained panels parked.

### Phase 3: Settings warm session

- Implement option B (hide + linger) with `LME_SETTINGS_LINGER_MS` and a test
  override; keep `settings.sh` IPC reuse.
- Route the hide/linger state through `SettingsApplication` or a new
  `SettingsWindowController`; do not add fields to
  `qml/services/ShellState.qml` (398/398). The in-process option D follows the
  same rule.
- Add `tests/test_settings_linger.py`: open, close, reopen via IPC; assert the
  same PID, a visible window and a latency budget; set a short linger and
  assert the process exits; cover WM close, Escape and the close button.
- Measure PSS while lingering and decide the default. If the owner approves,
  prototype option D behind `LME_SHELL_INPROCESS_SETTINGS=1` and compare.
- Gates: G0 + G2 + the focused startup/linger tests.

### Phase 4: Prewarm scheduler and hover anticipation

- Replace the 4 s/6.5 s timers with the readiness-driven scheduler; add bar
  hover type warm and optional instance warm.
- Put `anticipatePanel` in the new prewarm policy object, not
  `qml/services/ShellState.qml` (398/398).
- Respect the section 7.6 decision (battery-saver gating is A6 power policy
  and is not authorized by this plan) and the existing deferral in
  `startControlWarmup`.
- Tests: first CC open at the earliest readiness point, prewarm cancellation
  when a panel opens, hover-driven component load, no repeated warm loops.
- Metrics: first-open latency at 1 s/10 s after login; login CPU/memory burst;
  hover-to-open latency.

### Phase 5: Eviction, memory and documentation

- Ratchet the retention table and limits from Phase 1/2 measurements; add
  idle unload; verify the aggregate PSS target and idle CPU.
- Update STATE, ROADMAP, README and the relevant REL/INVARIANT tags. Add one
  MIGRATION_LOG entry. Do not claim a memory saving; report the measured delta.
- Final gates: G0-G4 + G6 once. Before any runtime merge (Phases 1-4), the
  owner's standing rule applies regardless of whether the branch targets
  startup: 10 cold launches each of preview and Settings, main vs head, medians
  only, and Quickshell/backend RSS at 10 s. The docs-only PR does not run
  those.

## 4. Measurement methodology

- Use the existing local, untracked `run_qml` harness for object/identity/
  eviction contracts (offscreen, software renderer, no desktop session;
  `tests/` is gitignored, commit `022ad7a`).
- Use the headless-Sway render harness for first-frame and pixel checks; keep
  the existing retry-once policy for compositor timing. Software rendering is
  slower than the Radeon session; use it for relative before/after, then run
  the final acceptance on the real niri session.
- Measure 10 runs per scenario; report p50/p95 and the run count. This is a
  proposed methodology: D1 startup profiling is closed, so the committed
  10-run probe requires the section 7.7 owner decision. If it is not approved,
  keep the measurement local and out of the branch. Do not commit raw logs/CSV;
  commit only the summary numbers in the phase report.
- Memory: `python3 scripts/memory_report.py --label <label>` with aggregate
  PSS; sample after 10 s of quiet with the cache warm. Start from PR #107's
  +132 MB RSS prior (148 -> 280 MB for one retained Control Center tree) and
  the 400 MB steady / 500 MB active cap. Report the baseline and the delta,
  and label transient warmup peaks separately.
- Idle: one minute with all retained panels/pages parked; require no continuous
  `FrameAnimation` and a CPU delta <=1% of one core. A parked tree that still
  runs a clock or a visualizer fails the phase.
- Perceived latency: the first frame with final content, not the animation
  end. A 200 ms entrance animation on an already-built panel is acceptable; a
  200 ms blank interval before it starts is not.

## 5. Risks and mitigations

| Risk | Why | Mitigation |
| --- | --- | --- |
| Memory growth | Retained panels/pages plus hidden trees | Heavy limit 2, page limit 6, per-kind table, idle unload, PSS gate |
| Idle CPU | Parked trees keep timers/animations | `panelActive`/`pageActive` contract; audit; idle test |
| Visibility propagation | LME measured ~800 ms on a large panel | Panels and pages stay parked off-screen; `visible=false` only after a page-specific measurement |
| Input/focus regressions | Multiple loaders in one overlay | Only the active loader is enabled; mask/backdrop unchanged; focus active item on open |
| Blur/viewport wrong | Multiple mounted rectangles | Union only non-dormant loaders; active item for the panel blur region |
| Settings linger memory | A full Settings process stays alive | 90 s default, measured; option C/D if it breaks the budget |
| In-process Settings lifetime | Shell reload/crash closes Settings | Prototype behind a flag; keep standalone path; measure isolation trade-off |
| Cache eviction hitch | Destroying a big tree on the UI thread | One eviction per 50 ms while quiet; never evict current/in-flight |
| Stale cached data | A hidden page miss a refresh | Data services keep polling; page effects rerun on present if the page contract requires it; do not add a second data cache |
| QS version drift | `DiskCache`/`RenderControl` not in 0.3.2 | No unsupported pragmas; reference limits are not LME constants |
| Test flakiness | Software compositor + timing | Retry-once policy, p95 not max, real-session final check |

## 6. Flags, rollout and rollback

- `LME_SHELL_LATENCY_TRACE=1`: structured latency records; off by default.
- `LME_SHELL_PREWARM=0`: disable startup prewarm (existing
  `LME_SHELL_NO_PREWARM` stays compatible).
- `LME_PANEL_CACHE_LIMIT`, `LME_PAGE_CACHE_LIMIT`,
  `LME_PAGE_ANTICIPATE_MS`, `LME_SETTINGS_LINGER_MS`: test/tuning overrides.
- `LME_SHELL_INPROCESS_SETTINGS=1`: prototype only, after option B.
- Rollout: phase branches behind defaults that can be disabled without a
  rebuild; the first release keeps the existing visual behavior. No preference
  UI is added until the measured defaults are stable.
- Rollback: each phase is a separate branch; disabling the env flag restores
  the old single-loader/page-host path until the old code is removed. Do not
  remove the old path in the same PR that introduces its replacement.

## 7. Owner decisions requested

1. **Retention budget**: approve the starting table (heavy limit 2, light for
   the session, page limit 6) or set a stricter memory preference.
2. **Settings default**: 90 s full linger (instant reopen, memory held) versus
   0 s (always cold) versus the stub/in-process prototype. The measurement in
   Phase 3 will report all three.
3. **In-process Settings**: authorize the flag-gated prototype after B, or
   keep the separate process as a hard isolation boundary.
4. **Secondary prewarm**: keep only Control Center + island, or allow the
   configured `LME_SHELL_PREWARM_PANELS` list and hover instance warm.
5. **Quickshell upgrade**: decide separately whether to evaluate a newer
   Quickshell with `@pragma DiskCache`; this plan does not change the package.
6. **Battery-saver prewarm (A6)**: authorize skipping secondary prewarm when
   `ShellState.batterySaverActive`, or keep prewarm independent of power
   policy. A6 power policy is currently out of scope.
7. **Phase 0 profiling (D1)**: authorize a committed latency probe and the
   10-run p50/p95 methodology, or keep Phase 0 local-only. D1 startup profiling
   is closed; this plan does not reopen it by default.
8. **Size-ceiling integration**: keep `shell.qml` at 291 and
   `qml/services/ShellState.qml` at 398 nonblank lines by routing new state
   through new components, or approve a specific ratchet. The plan assumes the
   former.

## 8. File and test map

| Change | Files |
| --- | --- |
| Panel pool | `qml/components/PanelStage.qml` (new), `qml/components/PanelCachePolicy.qml` (new), `shell.qml`, `qml/components/SlideLoader.qml` (hooks only) |
| Page cache | `qml/components/PageHost.qml`, `qml/components/PageCachePolicy.qml` (new), `qml/panels/ControlCenter.qml`, `qml/settings/SettingsView.qml` |
| Settings session | `qml/settings/SettingsApplication.qml`, `qml/settings/SettingsView.qml`, a new Settings-window controller, `scripts/settings.sh` (only if IPC changes). Do not grow `qml/services/ShellState.qml` (398/398). |
| Prewarm | `qml/components/PrewarmScheduler.qml` (new), `shell.qml`, `qml/bar/BarModule.qml`, `qml/bar/ActionBarButton.qml` |
| Activity contract | panel/page roots with timers: `ControlDashboard.qml`, `SystemMonitor.qml`, settings pages with timers/processes |
| Tests | `tests/test_latency_probe.py`, `tests/test_page_host_cache.py`, `tests/test_panel_stage.py`, `tests/test_settings_linger.py`, render cases modeled on `tests/test_island_motion_render.py`. All of `tests/` is local and untracked (`.gitignore:14`, commit `022ad7a`). |
| Docs | this plan, `INSTANT_UI_RESEARCH.md`, STATE/ROADMAP/README after measurement |

New source files must stay under the 250-nonblank-line cap. `shell.qml` must
not grow past its 291-nonblank ceiling, and `qml/services/ShellState.qml` must
not grow past its 398-nonblank ceiling (`config/architecture.json:largeFiles`).
Move logic into the new components; a ceiling ratchet is an explicit owner
decision (section 7.8).

## 9. References

- Caelestia `1e44367`: `shell.qml`, `modules/drawers/Drawers.qml`,
  `modules/drawers/Panels.qml`, `modules/launcher/Wrapper.qml`.
- DMS `291f4c5`: `quickshell/Services/PopoutService.qml`,
  `quickshell/Modules/SurfaceWidgets/SurfaceWidgetFactory.qml`,
  `quickshell/Modals/Settings/SettingsContent.qml`,
  `quickshell/Modules/Settings/Widgets/SettingsMetrics.qml`.
- end4 `21733c3`: `dots/.config/quickshell/ii/shell.qml`,
  `panelFamilies/PanelLoader.qml`, `panelFamilies/IllogicalImpulseFamily.qml`,
  `modules/common/widgets/FadeLoader.qml`.
- Serpantinum `6e18148`: `src/quickshell/Main.qml`.
- Quickshell `9b0f339` (11 commits after `v0.3.2`; relevant disk-cache and
  `lazyloader.hpp` code unchanged): `src/core/lazyloader.hpp`,
  `src/launch/launch.cpp`.
- Noctalia `b912cad`: compiled C++, no `.qml`/`.luau` in the tree; used only
  as a counter-example.
