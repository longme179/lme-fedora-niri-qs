# Reference study: instant panels and settings in Quickshell shells

Research, 2026-11-24. Target: LME Shell `main` at `f234268`, Quickshell 0.3.2
(Fedora COPR), Qt 6.11.2, niri 26.04. This document authorizes no runtime
change.

Method: shallow clones, source reading and grep at the pinned commits below.
No reference shell was launched or benchmarked on this machine. Similar UI is
not evidence of lower latency. Values copied from a reference are labelled as
reference values; they are not LME measurements.

| Reference | Repository | Commit | Commit date |
| --- | --- | --- | --- |
| Caelestia | `caelestia-dots/shell` | `1e44367c34ee36607b1d3d5f93cd28c35c3aaa8c` | 2026-11-23 |
| DMS | `AvengeMedia/DankMaterialShell` | `291f4c58786a4fa38832a3267e66b889748c7c40` | 2026-11-23 |
| end4 | `end-4/dots-hyprland` | `21733c3ca7f4edc20faafedea844dc96002c6f7f` | 2026-11-15 |
| Noctalia | `noctalia-dev/noctalia-shell` | `b912cad300073bc9bc49a5f9747a69896aa5101a` | 2026-11-23 |
| Serpantinum | `ilyamiro/serpantinum` | `6e181487219fc626446aa4f46c71ca78cb502d4d` | 2026-11-23 |
| Quickshell | `quickshell-mirror/quickshell` | `9b0f339b19057f4731bf3b48293307d7ef241671` | 2026-10-21 |

## 1. What LME does today

### 1.1 One arbitrary-panel slot

`shell.qml` hosts the arbitrary panel in one `SlideLoader` (`panelLoader`) and
keeps a second, dedicated `SlideLoader` for the activity island. The panel
loader's content is a function of `ShellState.panelKind`
([shell.qml:187-195](../shell.qml#L187-L195)). `SlideLoader` keeps the built
tree after close (`keepAlive`, [SlideLoader.qml:16](../qml/components/SlideLoader.qml#L16))
and parks it off-screen instead of toggling `Item.visible`
([SlideLoader.qml:37-42](../qml/components/SlideLoader.qml#L37-L42)).

`SlideLoader.onContentChanged` assigns the new component to
`retainedContent` while shown ([SlideLoader.qml:187-189](../qml/components/SlideLoader.qml#L187-L189)).
Because the loader has one `sourceComponent`, assigning a different panel
replaces the built item. The previous panel's tree is destroyed; only the last
panel remains warm. Opening Wi-Fi after Control Center therefore makes the
next Control Center open cold again.

Documented LME values:

- PR #107 body: the table reports the first Control Center open after login
  460 -> 33 ms, while the prose and commit `c66dda7` describe 460 ms cold
  dim->arrival vs ~70 ms retained reopen. Both are in the same PR but measure
  different conditions; 33 ms is not a retained-reopen baseline.
- current source comment: 300-450 ms asynchronous incubation, ~70 ms on the
  retained path ([shell.qml:220-223](../shell.qml#L220-L223)).
- the invisible warm pass is #109 (`3074262`); the island warm pass is #110
  (`6c1dc3c`).

### 1.2 Two-slot page host

`PageHost` keeps the visible page and one incoming page. `activate()` hides the
previous page, sets `active = false` and `sourceComponent = null`
([PageHost.qml:20-33](../qml/components/PageHost.qml#L20-L33)). `dispatch()`
does reuse an already-current or already-incubating component
([PageHost.qml:35-46](../qml/components/PageHost.qml#L35-L46)). The host is
useful only for an immediate A -> B switch where B is already incubating; it is
not a cache. `activate()` nulls the retired page immediately, so A -> B -> A
already re-instantiates A.

Both page consumers use it:

- Control Center tabs: `tabComponents` and `PageHost`
  ([ControlCenter.qml:19](../qml/panels/ControlCenter.qml#L19),
  [ControlCenter.qml:141-145](../qml/panels/ControlCenter.qml#L141-L145)).
- Settings pages: `PageHost` and six built-in page components
  ([SettingsView.qml:142-167](../qml/settings/SettingsView.qml#L142-L167)).
  Catalog pages add a second layer: `catalogPage` is a `Loader` that resolves
  `FeatureCatalog.url(...)` ([SettingsView.qml:154-160](../qml/settings/SettingsView.qml#L154-L160)).

### 1.3 Settings is a separate process that quits on close

The live shell launches `scripts/settings.sh --daemonize --page <page>`
([ShellState.qml:128-132](../qml/services/ShellState.qml#L128-L132)). The script
first tries `ipc call settings openPage` against a live instance, then a
`startupPending` probe, then `list`, and only then starts a new Quickshell
process ([settings.sh:63-112](../scripts/settings.sh#L63-L112)).

The Settings process quits when its window closes:
`FloatingWindow.onClosed: Qt.quit()`
([SettingsApplication.qml:52](../qml/settings/SettingsApplication.qml#L52));
the close button also calls `Qt.quit()`
([SettingsApplication.qml:56-58](../qml/settings/SettingsApplication.qml#L56-L58)).
The window is only shown once the whole view is `Loader.Ready`
([SettingsApplication.qml:43](../qml/settings/SettingsApplication.qml#L43)).
After a normal close there is no instance left for the IPC path to reuse, so
the next open is a cold Quickshell process with a cold QML engine, a cold
backend and a cold page host. STATE records a ~1.0 s Settings launch-to-visible
in the M4 sanity run; that is a process-start measurement, not a reopen
measurement.

### 1.4 Compile cache is not a lever on this Quickshell

Quickshell 0.3.2 does not recognize the `DiskCache` or `RenderControl` pragmas.
A direct probe printed `Unrecognized pragma "DiskCache"` and
`Unrecognized pragma "RenderControl"`. The launch code comments out the
disk-cache environment path because the engine refuses to cache
`qsintercept` paths ([quickshell/src/launch/launch.cpp:91-129,233-242](https://github.com/quickshell-mirror/quickshell/blob/9b0f339b19057f4731bf3b48293307d7ef241671/src/launch/launch.cpp#L91-L129)).
The source pin `9b0f339` is 11 commits after the `v0.3.2` tag; `launch.cpp`
differs only by moving `setDesktopFileName`, `lazyloader.hpp` is unchanged, and
the disk-cache block at lines 235-240 is commented-out code. The relevant
behavior is the 0.3.2 behavior.
A probe with a local component and `QML_DISK_CACHE=1`,
`QML_FORCE_DISK_CACHE=1` and an explicit `QML_DISK_CACHE_PATH` produced zero
`.qmlc` files. The live cache directory held one 688-byte `.qmlc` at probe
time; the Qt pipeline cache is present and about 160 KB.

Consequence: on this binary, a new Quickshell process recompiles its user QML.
Inside one process, compiled types and components stay in the QML engine;
destroying a page and re-instantiating its component does not recompile the
QML source. Bytecode caching would help the Settings process start; it is not
the cause of a tab switch inside an already-running process.

### 1.5 Data-plane work on open is secondary

Control Center calls `controlsRefresh` when a tab with `refresh: true` becomes
visible ([ControlCenter.qml:27-31](../qml/panels/ControlCenter.qml#L27-L31)).
The backend handler is a no-op that invalidates Bluetooth and power caches
before the next poll ([desktop_backend.py:1401](../scripts/desktop_backend.py#L1401),
[desktop_backend.py:1473](../scripts/desktop_backend.py#L1473)); the 2 s
snapshot poll remains the data source. Display, idle and equalizer refreshes
route natively. These actions can update values after the panel is visible,
but they do not explain the dead interval before the panel's item exists.
UI construction and the first render of that item are the dominant cost.

## 2. Reference implementations

### 2.1 DankMaterialShell: prewarm the type, grace-unload the instance, cache settings pages

DMS is the closest analogue to the Settings problem.

- Popout hosts are `Loader`s. On pointer hover, the widget calls
  `PopoutService.prewarm(loader)` ([SurfaceWidgetFactory.qml:187,264,387,777](https://github.com/AvengeMedia/DankMaterialShell/blob/291f4c58786a4fa38832a3267e66b889748c7c40/quickshell/Modules/SurfaceWidgets/SurfaceWidgetFactory.qml#L187)).
  `prewarm()` deduplicates by source and calls
  `Qt.createComponent(url, Component.Asynchronous)`; it does not instantiate
  the item ([PopoutService.qml:137-146](https://github.com/AvengeMedia/DankMaterialShell/blob/291f4c58786a4fa38832a3267e66b889748c7c40/quickshell/Services/PopoutService.qml#L137-L146)).
  The type is compiled and loaded off the click path; the loader still builds
  the item on open.
- Closed surfaces are not destroyed immediately. `_scheduleUnload()` records
  the popout and a single timer flushes deferred unloads after
  `Timing.holdMedium`; a quick reopen keeps its tree
  ([PopoutService.qml:82-104](https://github.com/AvengeMedia/DankMaterialShell/blob/291f4c58786a4fa38832a3267e66b889748c7c40/quickshell/Services/PopoutService.qml#L82-L104)).
- Settings pages are hosted as full page hosts, not as one reusable loader.
  The host keeps `_cache`, `_cacheOrder` and `_doomed`
  ([SettingsContent.qml:233-236](https://github.com/AvengeMedia/DankMaterialShell/blob/291f4c58786a4fa38832a3267e66b889748c7c40/quickshell/Modals/Settings/SettingsContent.qml#L233-L236)).
  `_takePage()` reuses a cached host or creates one as a child of the stack at
  `x: pageStack.width`, so it is laid out and drawn out of sight before it is
  moved in ([SettingsContent.qml:241-270](https://github.com/AvengeMedia/DankMaterialShell/blob/291f4c58786a4fa38832a3267e66b889748c7c40/quickshell/Modals/Settings/SettingsContent.qml#L241-L270)).
  `_release()` stores an invisible host in the cache and evicts the oldest
  entry over `pageCacheLimit` ([SettingsContent.qml:273-286](https://github.com/AvengeMedia/DankMaterialShell/blob/291f4c58786a4fa38832a3267e66b889748c7c40/quickshell/Modals/Settings/SettingsContent.qml#L273-L286)).
  `_doom()` and `_reap()` tear down one page per `pageTeardownInterval` while
  the stack is quiet instead of blocking a switch
  ([SettingsContent.qml:288-316](https://github.com/AvengeMedia/DankMaterialShell/blob/291f4c58786a4fa38832a3267e66b889748c7c40/quickshell/Modals/Settings/SettingsContent.qml#L288-L316)).
- `anticipate()` builds the page under the pointer ahead of the click after a
  delay; `_nextAhead()` also builds sidebar neighbours while the cache has
  room ([SettingsContent.qml:379-437](https://github.com/AvengeMedia/DankMaterialShell/blob/291f4c58786a4fa38832a3267e66b889748c7c40/quickshell/Modals/Settings/SettingsContent.qml#L379-L437)).
  The reference constants are 6 cached pages, 90 ms anticipation and 50 ms
  teardown ([SettingsMetrics.qml:90-97](https://github.com/AvengeMedia/DankMaterialShell/blob/291f4c58786a4fa38832a3267e66b889748c7c40/quickshell/Modules/Settings/Widgets/SettingsMetrics.qml#L90-L97)).
- The host is a `StackView` declared at `SettingsContent.qml:881`; each page
  is a host item with its own `Loader` and
  `StackView.onRemoved: _release(host)`
  ([SettingsContent.qml:559-604](https://github.com/AvengeMedia/DankMaterialShell/blob/291f4c58786a4fa38832a3267e66b889748c7c40/quickshell/Modals/Settings/SettingsContent.qml#L559-L604)).

DMS is on a different Quickshell build and its `@pragma DiskCache` and
`@pragma RenderControl` are not available in 0.3.2. Only the instance and
policy patterns transfer, not the pragmas or the constants.

### 2.2 Caelestia: resident panel wrappers, lazy heavy content

Caelestia instantiates its modules at shell start
(`Background {}`, `Drawers {}`, ...) ([shell.qml:43-45](https://github.com/caelestia-dots/shell/blob/1e44367c34ee36607b1d3d5f93cd28c35c3aaa8c/shell.qml#L43-L45)).
`Drawers` creates one `ContentWindow` per screen
([Drawers.qml:20](https://github.com/caelestia-dots/shell/blob/1e44367c34ee36607b1d3d5f93cd28c35c3aaa8c/modules/drawers/Drawers.qml#L20)).
`Panels.qml` declares every wrapper (osd, notifications, session, launcher,
dashboard, bar popouts, utilities, toasts, sidebar) as a child of that
resident layer-shell window
([Panels.qml:41-155](https://github.com/caelestia-dots/shell/blob/1e44367c34ee36607b1d3d5f93cd28c35c3aaa8c/modules/drawers/Panels.qml#L41-L155)).
Opening a panel changes offsets and opacity; it does not build a new panel
tree.

This is not "everything is always rendered". The heavy launcher and dashboard
contents sit behind a `Loader` whose `active` is
`shouldBeActive || visible` ([launcher/Wrapper.qml:25-52](https://github.com/caelestia-dots/shell/blob/1e44367c34ee36607b1d3d5f93cd28c35c3aaa8c/modules/launcher/Wrapper.qml#L25-L52)).
The wrapper is resident, the content loads on first open and is released when
the closing animation finishes. Resident wrappers give the panel chrome and
geometry for free; the largest content remains lazy.

### 2.3 end4: load the whole panel family at startup

`shell.qml` declares one `PanelFamilyLoader` per family; each is a
`LazyLoader` with `active: Config.ready && selected family`
([shell.qml:44-58](https://github.com/end-4/dots-hyprland/blob/21733c3ca7f4edc20faafedea844dc96002c6f7f/dots/.config/quickshell/ii/shell.qml#L44-L58)).
`PanelLoader` repeats `active: Config.ready && extraCondition`
([PanelLoader.qml:6-8](https://github.com/end-4/dots-hyprland/blob/21733c3ca7f4edc20faafedea844dc96002c6f7f/dots/.config/quickshell/ii/panelFamilies/PanelLoader.qml#L6-L8)).
The family then declares the bar, background, dock, lock, media controls,
notification popup, OSD, overview, polkit, region selector, sidebars,
wallpaper selector and more, all in one place
([IllogicalImpulseFamily.qml](https://github.com/end-4/dots-hyprland/blob/21733c3ca7f4edc20faafedea844dc96002c6f7f/dots/.config/quickshell/ii/panelFamilies/IllogicalImpulseFamily.qml)).
The loaders activate after `Config.ready`, not on the first frame, but they
are startup preloads, not click-time loads.

Small popups use `FadeLoader` with `active: opacity > 0` and
`visible: opacity > 0` ([FadeLoader.qml](https://github.com/end-4/dots-hyprland/blob/21733c3ca7f4edc20faafedea844dc96002c6f7f/dots/.config/quickshell/ii/modules/common/widgets/FadeLoader.qml)):
they build on fade-in and unload after fade-out. That is the opposite trade-off
from a retained panel and is used for small, cheap surfaces.

### 2.4 Serpantinum: hidden item cache plus StackView replacement

Serpantinum creates widget items in a hidden `preloaderContainer`
(`Main.qml:351-354`) and stores them in `widgetCache`
(`Main.qml:356`). `ensureWidgetItem()` compiles the component once, creates
the object in the hidden container, marks it invisible and caches it
(`Main.qml:366-387`). A switch calls
`widgetStack.replace(cachedItem, {}, StackView.Immediate)` and toggles the
other cached items invisible (`Main.qml:673-750,797-804`). The tree is built
once and reused; the stack only changes which item is presented.

### 2.5 Noctalia: compiled C++, not a QML reference

Noctalia has no `.qml` and no `.luau` files in the tree at the pinned commit.
Its shell is C++ under `src/shell` (311 `.h` / 294 `.cpp`); the 645/576 totals
are for all of `src/`. The Luau runtime is vendored under `third_party/luau`
(125 files). It is useful only as a counter-example: a shell can remove runtime
QML compilation entirely, but that is an architecture change, not a retention
tweak.

### 2.6 Quickshell `LazyLoader` semantics

`LazyLoader` is the engine primitive designed for this problem: it creates the
component in the gaps between frame rendering, `loading: true` starts that
background work immediately, `active` forces completion (blocking if it is not
ready), and `active: false` destroys the item
([lazyloader.hpp:12-84](https://github.com/quickshell-mirror/quickshell/blob/9b0f339b19057f4731bf3b48293307d7ef241671/src/core/lazyloader.hpp#L12-L84)).
The header explicitly warns that `Variants` does not support asynchronous
loading; wrapping a variant in a loader blocks like no loader at all. Any warm
path added to LME must not put `Variants` (or another synchronously-built
container) inside the component being incubated.

## 3. Comparison

Columns: resident wrappers, lazy heavy content, prewarm type on hover,
offscreen warm render, multi-instance cache, LRU eviction, grace unload,
async teardown, settings page cache, settings process reuse.

| Mechanism | Caelestia | DMS | end4 | Serpantinum | LME today |
| --- | --- | --- | --- | --- | --- |
| Resident wrappers | yes | no | family at startup | yes (stack) | one panel |
| Lazy heavy content | launcher/dashboard | per popout/page | no | no | yes |
| Prewarm type on hover | no | yes | no | no | no |
| Offscreen warm render | no | page host parked | no | hidden container | CC/island only |
| Multi-instance cache | n/a (resident) | per popout + 6 pages | per family | widget cache | no |
| LRU eviction | no | pages (6) | no | no | no |
| Grace unload | no | yes | no | no | no |
| Async teardown | no | 50 ms/card | no | no | no |
| Settings page cache | no | yes | no | no | 2 slots |
| Settings process reuse | n/a | in-process | n/a | n/a | IPC only if alive |

## 4. Conclusions for LME

1. The owner's hypothesis is directionally correct, but "preload offscreen" is
   not one technique. The references combine: resident wrapper, lazy content,
   type prewarm on hover, instance cache, offscreen warm render, LRU/grace
   eviction and asynchronous teardown.
2. LME already has the expensive part: `SlideLoader` parks a retained tree
   off-screen and can render a warm pass invisibly. It is missing
   multi-instance retention and a page cache.
3. A tab switch inside an already-running process is not a QML compilation
   problem. Retention and anticipation are the levers.
4. Settings open is a separate problem: 0.3.2 does not use a user-QML disk
   cache, and the Settings process quits on close. Linger, a warm stub or
   in-process hosting must be evaluated separately from tab caching.
5. Never toggle `Item.visible` on a large retained panel: LME measured about
   800 ms for that visibility propagation and parks off-screen instead
   ([SlideLoader.qml:39-42](../qml/components/SlideLoader.qml#L39-L42)). Use
   off-screen parking for page-sized trees too; visibility toggling only after
   measuring it.
6. Do not copy reference constants blindly. DMS's 6 pages, 90 ms and 50 ms are
   reference values; LME must measure its own page sizes, memory and frame
   budget.

## References

Reference links are pinned to the commits in the table at the top. LME links
are relative to this checkout at `f234268`. `9b0f339` is 11 commits after the
`v0.3.2` tag; the disk-cache and `lazyloader.hpp` code is unchanged (only
`setDesktopFileName` moved).
