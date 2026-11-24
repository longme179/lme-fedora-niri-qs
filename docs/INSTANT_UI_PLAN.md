# Instant panels and Settings pages — plan and results

Status: implementation on `perf/instant-panels-pages` (2026-11-24). Owner request:
opening the overlay panels (Control Center, notifications, launcher, ...) and switching
Settings pages must stop showing a load interval. Previous attempts (#192/#194 and
their reverts) were explicitly out of scope as references.

## 1. What the reference shells actually do

Verified in cloned sources (`dms`, `caelestia`, `end-4`, `iNiR`, `noctalia`, and
Quickshell 9b0f339), not assumed:

| Shell | Panel lifecycle | What makes a reopen fast |
|---|---|---|
| DMS | one `LazyLoader` per popout, `active:false` until first click | hover calls `PopoutService.prewarm()` = `Qt.createComponent(url, Asynchronous)` (types only); closed popouts unload after 3 s; Settings pages are parked at `x=width`, LRU 6, neighbours prewarmed, built in 4 ms slices |
| Caelestia | one always-mapped window per screen; `Loader` wrappers destroyed when the hide spring ends | services warmed at startup; 500 ms hide spring covers the next build; dashboard tabs keep a Loader per visible/current tab |
| end-4 | `PanelWindow` per panel, unmapped when closed | right sidebar `Loader active: open \|\| keepRightSidebarLoaded` defaults to true (~15 MB, documented) |
| iNiR | `PanelLoader` / `DeferredPanelLoader` / `OnDemandPanelLoader` with `resident = open \|\| keepLoaded`, 300 ms close grace | `retainAfterUse` + 5 min `retainIdleMs`; Settings page Loaders LRU 2 |
| Noctalia | C++ layer surfaces | objects persist, surface+scene destroyed on close, rebuilt on open — no warm cache |
| Quickshell 0.3.2 | `PanelWindow` deletes the `QQuickWindow`/surface on hide; QML items survive | asynchronous `Loader` incubation budget is **1/3 frame per rendered frame**, not configurable from QML; no QML disk cache |

Nobody "preloads off-screen" in the literal sense. The winning pattern is:
keep **built item trees** alive, start the build **before** the click, and reveal only
when a frame exists. The owner's guess (preload + cache) was right; LME was missing
multi-instance retention and synchronous build-on-request.

## 2. Root causes measured in LME

- `PageHost` had exactly two Loaders (`loaderA`/`loaderB`) and set
  `previous.sourceComponent = null` on every switch: every revisit recompiled/rebuilt the
  page. Control Center tabs: 213–730 ms per lap, identical on the second lap.
- The panel stage had one content slot; opening another panel destroyed the previous one.
  Switching back to Control Center cost 888 ms.
- `SlideLoader` parks by off-screen offset, but the pages themselves were toggled with
  `Item.visible`. Visibility propagation through a large built tree costs ~500 ms; the
  park offset costs nothing. (First implementation of the park used `anchors.fill` on the
  Loader, which silently overrides `x`; pages overlapped at x=0 and only the newest
  creation order won. The Loader now sets `width`/`height`/`y` explicitly.)
- `onResolveChanged: show()` fired from the lazy first evaluation of `resolve` while the
  first `show()` was still inside `resolve()`: re-entrant `show()` built the same key
  twice. No caller rebinds `resolve`, so the handler is gone.
- The 4 s prewarm mounted the panel stage with `Loader.asynchronous: true`. Incubation is
  paid from rendered frames, and an idle scene swaps none, so the warm stayed in
  `Loading` indefinitely (observed: still `Loading` at 9 s) and the first open paid the
  whole build after all. `asynchronous:false` does not affect a load already in flight.
- The standalone Settings process called `Qt.quit()` on close, so every reopen was a cold
  engine + backend start (~1 s).

## 3. Design

### PageHost (keyed retained pages)
- `key` + `resolve(key) -> Component`; one `Loader` per visited key, created
  synchronously on request (`asynchronous:false`). A sync build is 2–3× faster than
  Quickshell's async incubation, which is the only budget available while a page animates.
- Hidden pages are parked at `x = width + 8` inside a clipping host; `Item.visible` is not
  toggled per page. `active:false` hides all pages and stops `visible`-bound timers when a
  window closes.
- `maxPages` (default 6) is an LRU: least recently shown, non-visible pages are destroyed
  first. `0` disables eviction for diagnostics.
- `pageLoaded(item)` keeps the Control Center's `embedded` flag working.

### Panel stage
- One `PageHost` (`qml/panels/PanelStage.qml`) is the permanent `SlideLoader` content,
  keyed by `ShellState.panelKind`, `maxPages: 4`. All visited panels stay built.
- The stage loader is **synchronous** (`asynchronous:false`): the one-time build happens
  in the existing 4 s prewarm timer (or on the first click if the user beats it), instead
  of stalling in `Loading` until the first open.
- Focus forwarding on `panelOpenChanged` keeps Escape/launcher search working with the
  stage in place; the blur region follows `(panelLoader.item as PageHost).item`.

### Settings
- `SettingsView` uses the same PageHost (`maxPages: 6`); page IDs/routes unchanged.
- `SettingsApplication` hides instead of quitting: `shown=false`, `SettingsView.active`
  false, and a `LME_SETTINGS_LINGER_MS` timer (default 60 s) quits the process after the
  linger window. `scripts/settings.sh`'s IPC `openPage` path re-shows the same instance
  (it no longer assigns `window.visible`, which broke the binding).

## 4. Results (private headless Sway, gles2, demo, median of one scenario run)

Harness: a private copy-patching script kept outside the repo (sessions sandbox
`tools/lme-latency/measure.py`; it never touches the live session). Relative comparison
only — software-ish GL is slower than the real GPU.

| Action | main | branch |
|---|---|---|
| First Control Center open (content frame) | 986 ms | **102 ms** |
| Panel → Control Center switch back | 888 ms | **84–98 ms** |
| First launcher / clipboard / power open | — | 147–183 ms |
| Control Center tab revisit (audio/devices/agenda/monitor) | 200–730 ms every lap | **0–16 ms** |
| Settings page revisit (retained) | 400–1100 ms | **21–27 ms** |
| Settings page after LRU eviction | — | ~450 ms |

First visits are still compile/build bound (Control Center tabs 127–407 ms, Settings pages
113–837 ms); they are paid once per key and retained afterwards.

## 5. Memory and risks

- The harness process reaches ~603 MB because it runs demo mode and retains four panels
  plus six Settings pages in one engine (down from ~740 MB once the duplicate-first-page
  build was removed). The real topology is main shell + separate
  Settings process; caps bound the retained set (panels 4, Settings pages 6). Real-session
  PSS measurement is still required against the 400/500 MB targets.
- The synchronous stage prewarm blocks the main thread once, ~4 s after login. On the
  harness (software GL) it is ~1 s; the real GPU duration needs a real-session check. If
  it is noticeable, move the timer later or gate it on user idle.
- Settings linger keeps one QML engine + backend alive for up to 60 s after close. Set
  `LME_SETTINGS_LINGER_MS=0` to restore quit-on-close.
- Page/panel retention changes lifetime, not content: pages must keep working while
  hidden (timers are gated on `visible`, pages are parked, not hidden individually).
- `PanelWindow` still destroys its surface on hide; the first frames after a show include
  surface configure. Item trees are what is retained.

## 6. Verification

- `./scripts/check.sh` on the final tree: 1500 tests, one known flaky backend-shutdown
  timeout (`test_prefs_hot_reload`) that passed twice on rerun; architecture/catalog/bash
  checks green.
- `./scripts/run-gates.sh --gates G0,G1,G2,G3,G4,G6`: qmllint clean. G1–G6 report the
  same failures on clean `a38a4e2` in this environment (missing private pointer helper,
  absent private capture/annotation test modules, stale native catalog fixtures, the
  polling snapshot check) — no new failures from this branch. No gate is claimed green
  beyond that comparison.
- Harness scenarios with `LME_SHELL_PREWARM=1` (the prewarm is skipped in demo mode by
  default; the override exercises the real path).
- Real-session checks still owed: first-open prewarm hitch, Settings re-show via niri
  window rules, aggregate PSS.
