# QML-first migration plan — retiring the Python backend gradually

**Date:** 2026-11-09 · **Baseline:** `8ebc597` (`main`, after #112) · **Status:** plan accepted by the owner 2026-11-09 (PR #113). Q0 authorized and delivered on `qml/q0-metric-baseline`: the §1 numbers are now reproduced automatically by the `check_architecture.py` language mix printed in every G0 summary. Q1 authorized with A6 (event-driven wake model) and delivered on `qml/q1-native-read-state`: audio/microphone/battery/power-profiles/bluetooth/network-summary state is native, the backend sections are deprecated for the A/B window, and `batterySaver` re-homes to the write phases (its state machine and toggle move together); same-day hotfix #116 rescaled Quickshell's 0–1 UPower percentage. Q2 authorized and delivered on `qml/q2-native-files`: launcher apps/history and cpu/memory monitor are native (DesktopEntries + FileView at the unchanged 2 s cadence), with tempC/brightness/monitor-processes documented as backend-fed transitional keys (no directory-listing API in quickshell 0.3.2). Q3-Q7 still need per-phase owner authorization.

## 1. Goal and metric

The owner's direction: move the codebase gradually to QML as the majority, instead of mostly Python as it is today. This plan turns that direction into phased, gate-checked work items that retire the Python JSON-lines backend family by family, replacing it with Quickshell-native services and QML-side logic, while keeping the repo's compatibility facades, memory targets and test discipline intact.

**Metric definitions** (counted with `wc -l`, verified at the baseline commit; since Q0 the same slices are printed by `scripts/check_architecture.py` as the `Architecture: language mix` line in every G0 summary):

- **Runtime shell code** — code that runs inside the live shell or the standalone Settings entry: `qml/` (QML + JS), root `*.qml`, and the `scripts/` modules those two spawn.
- **Dev tooling** — everything else in `scripts/`: the deploy chain (`deploy*.py`, 693), `check_architecture.py` (170), catalog/schema generation (`feature_catalog.py`, `settings_schema.py`, `catalog_metadata.py`, 460), `memory_report.py` (178), `niri_keybinds.py` (136) = **1,637 lines**. Plus `tests/`.

| Slice | Lines | Share |
|---|---|---|
| QML + JS runtime (`qml/` + root) | 16,228 | 63.6% of runtime |
| Python runtime (`scripts/` minus tooling) | 9,277 | 36.4% of runtime |
| Python dev tooling | 1,637 | — |
| Python tests | 26,161 | — |
| Whole-repo totals | Python 37,075 (69.5%) · QML-side 16,228 (30.5%) | |

So the *runtime* split is already QML-majority; the Python majority the owner sees is the whole repo, dominated by the 26k test lines, plus the fact that every system state and action flows through the backend. Both move together: each migrated family deletes its Python implementation **and** its Python tests in the same authorized scope.

**Targets:**

- **T1 (phases Q1–Q6):** runtime share ≥ 85% QML-side, `desktop_backend.py` retired; stretch: 100% of runtime code QML-side (excluding dev tooling).
- **T2 (phase Q7, optional):** whole-repo QML majority. Reached only if family test suites retire as the families migrate; needs an explicit owner decision because it changes how coverage is written.

## 2. Why this is worth doing

1. **One runtime, not two.** The backend's measured PSS is ~24 MB of the ≤400 MB budget (PR #110 sanity samples: 24,263 KiB). Retiring it removes a process, its JSON-lines protocol, snapshot diffing (`SnapshotIdentity.js` identity tricks) and the restart/backoff supervisor surface.
2. **Event-driven state instead of polled snapshots.** Quickshell services push property changes; the backend polls and re-serializes. This strictly reduces wakeups — but it *changes the polling model*, so each phase that touches it is flagged for A6-style owner approval rather than smuggled in.
3. **Native coverage we already trust.** Mpris, Notifications, SystemTray and Polkit already run natively in this shell; the same integration quality is available for audio, battery, power profiles, Bluetooth, Wi-Fi and desktop entries (§3).
4. **Feature velocity.** New features currently need QML + descriptor + Python provider + registry entry + tests in two languages. Post-migration, one.

Honest counterweights (why *gradual*, not a rewrite): the backend is stdlib-only, unprivileged, well-tested (1,073 unit checks at the last full `check.sh` run), and its Preferences class has lock/merge/fsync/atomic-write semantics the QML side must reproduce exactly before retirement. A big-bang rewrite would put all of that at risk at once.

## 3. Grounding — what Quickshell 0.3.2 already provides natively

Verified 2026-11-09 against the installed runtime (`quickshell-0.3.2-1.fc44`, `/usr/lib64/qt6/qml/Quickshell/`) and the upstream clone at `9b0f339` (2026-10-21). Capability matrix, backend section → native replacement:

| Backend today (Python) | Quickshell 0.3.2 native | Coverage | Source (clone) |
|---|---|---|---|
| `audio_*` — wpctl volume/mute/devices, routes | `Quickshell.Services.Pipewire`: `defaultAudioSink/Source`, `PwNodeAudioIface.muted/.volume`, node model, link groups, peak | full | `src/services/pipewire/qml.hpp`, `node.hpp` |
| `battery_info`, `ac_online`, `power_profile(s)` — sysfs + `powerprofilesctl` | `Quickshell.Services.UPower`: `displayDevice`, `onBattery`, `PowerProfiles` (list + set) | full | `src/services/upower/core.hpp`, `powerprofiles.hpp` |
| `bluetooth_agent` + backend `bluetooth()` — `bluetoothctl` wrappers | `Quickshell.Bluetooth`: adapter `enabled/discoverable/pairing`, device model, `connect/pair/forget`, per-device battery | full (since 0.2.0) | `src/bluetooth/bluez.hpp`, `adapter.hpp`, `device.hpp` |
| `wifi_actions`, `network_inventory/profiles/plans` — `nmcli` wrappers | `Quickshell.Networking`: device/network models, `connectWithPsk`, `NMSettings.read/write`, connectivity check | full for state+connect; hotspot/AP via `NMSettings` needs real-session check (Q-4) | `src/network/qml.hpp`, `wifi.hpp`, `nm/settings.hpp`; added 0.3.0 |
| `Applications.scan` + `desktop_exec` — desktop-file parsing (in `desktop_backend.py`) | `Quickshell.DesktopEntries`: applications model, `byId`, `heuristicLookup`, `execute()`, actions, keywords, live monitor | full | `src/core/desktopentry.hpp` |
| `storage.py` / `Preferences` | `Quickshell.Io.FileView`: `atomicWrites`, `watchChanges`, JSON adapter | partial — no cross-process lock/merge protocol (Q-2) | `src/io/fileview.hpp`, `jsonadapter.hpp` |
| `niri_events.py` — niri IPC event stream | `Quickshell.Io.Socket` on `$NIRI_SOCKET` (unix path, line-oriented via `SplitParser`) | full; JSON parsing in JS | `src/io/socket.hpp` |
| `system_monitor.py` — `/proc`, thermal | `FileView` reads on `/proc/stat`, `/proc/meminfo`, `/sys/class/thermal/*` at the existing cadence | full | — |
| brightness read (sysfs) | `FileView` on `/sys/class/backlight/*` | read full; **writes** keep `brightnessctl` through `Process` | — |
| `idle_control.py` inhibit | `Quickshell.Wayland` idle-inhibit (`IdleInhibitor`), idle-notify monitor | full | `src/wayland/idle_inhibit/`, `idle_notify/` |
| capture preview / ambient screen | `ScreencopyView` (`live`, `paintCursor`, `captureSource`) | alternative path; current grim/wf-recorder flows stay unless a family opts in | `src/wayland/screencopy/view.hpp` |
| `weather.py`, `lyrics.py` — urllib HTTP | QML `XMLHttpRequest` (QtNetwork is installed) | full; no Quickshell HTTP object exists | — |
| `command_runner.py` — CLI subprocess allowlist | `Quickshell.Io.Process` (`stdout/stderr` parsers, `stdinEnabled`, env, `startDetached`) | full, same argv allowlists | `src/io/process.hpp` |
| Mpris / Notifications / SystemTray / Polkit | already native in this shell | unchanged | — |

**Not available natively (stays external or Python):** generic D-Bus client API (internals only), an HTTP client object (use `XMLHttpRequest`), and privileged sysfs writes (charge thresholds keep the existing Polkit/charge-helper path).

## 4. Constraints restated (binding, from AGENTS.md / STATE.md)

1. No tree reorganization; new files ≤ 250 nonblank lines; existing large files may not grow; ratchet ceilings down when shrinking.
2. Public facades stay compatible until zero consumers + owner-approved retirement: `ShellState.run/accept`, snapshot shape, `pendingActions`/`lastResult`, the Preferences semantics, demo/settings contexts.
3. A6: polling-cadence and power-policy changes need explicit approval. Event-driven services change the wake model (fewer wakes) — each such phase is marked *(needs A6 approval)* and reports measured before/after wake rates.
4. Memory targets unchanged: ≤400 MB steady / ≤500 MB ordinary active, aggregate PSS. Retiring the ~24 MB backend helps; per-widget Process spawning would hurt — actions reuse a bounded pool.
5. Batches of 3–6 families per branch, one review stop per branch; owner merges.
6. Tests first, then implementation, then docs; never edit an existing assertion without asking; revert a failed commit rather than fixing forward.
7. Disposable sessions only; hardware-dependent items are "needs real-session check".
8. `Process` lifetime trap: Quickshell 0.3.2 destroys `Process` with SIGKILL; long-lived children (wl-paste watchers) need the parent-death-signal helper pattern or `startDetached` with explicit cleanup (CODE_REVIEW finding).

## 5. Phases

Each phase = one branch + one review stop. Sizes are the Python runtime lines the phase removes (verified with `wc -l` at the baseline, see §1); they sum to 9,277 across Q1–Q6. QML absorbs roughly 60–70% of them; the rest is protocol/registry/supervisor plumbing that simply disappears.

### Q0 — Decision, metric automation, baselines *(docs + checks only)*

- Add a classification counter to `check_architecture.py`: runtime vs tooling vs test lines per language, printed in the G0 summary so every future PR shows the ratio trend (no new gates, no thresholds yet).
- Record the §1 baseline table in `docs/STATE.md` and this plan; refresh `WORKSPACE_MAP.md` edges that this plan will change (none change yet).
- Exit: G0 green with the counter output; owner accepts T1/T2 definitions (or amends them).

### Q1 — Read-only native state: audio, battery, power, bluetooth, network *(needs A6 approval)*

- Families (5): audio state, battery/AC + battery-saver reads, power profiles, bluetooth state, network state — 1,134 Python lines across 9 modules (`audio_pipewire`/`audio_inventory`/`audio_devices` 275, `battery_info`/`battery_saver`/`peripheral_battery`/`peripheral_values` 402, `bluetooth_agent` 283, `network_inventory` 174), plus the matching read-only sections inside `desktop_backend.py`.
- Mechanism: new/extended singletons in `qml/services/` (`AudioState`, `PowerState`, `BluetoothState`, `NetworkState`) bind directly to the Quickshell singletons and **expose the existing snapshot property names**, so panels/bar keep working unchanged. `ShellState` stops reading those sections from the backend but keeps `accept()` whole-snapshot validation for the remaining sections.
- The backend keeps emitting the sections for one phase (marked deprecated in code comments), then Q6 removes them; this gives a live A/B check on the owner's machine ("needs real-session check": compare native values vs backend values for a day).
- Tests: characterization first (freeze current value shapes per section), then native-harness cases asserting the new singletons against fixtures; Python unit tests for those sections are deleted with the deprecation commit only after the A/B window closes.
- Exit: G0 + G1 + relevant natives; bar/panels show identical values on the owner's session; snapshot sections marked deprecated.

### Q2 — Read-only files: system monitor, brightness read, launcher apps + history

- Families (4): `system_monitor` 85 + `launcher_history` 97, brightness read, and the desktop-entry block of `desktop_backend.py` (`Applications.scan`, `desktop_exec`, `locale_candidates`, ≈ 130 lines).
- `LauncherSearch.js`/launcher models switch to `DesktopEntries.applications` (id/name/icon/keywords/actions/`execute()`); `launcher_history` becomes a `FileView` JSON store with the same atomic-write guarantees.
- CPU/memory/temperature via `FileView` on the same `/proc` paths at the same cadence (no A6 change); brightness read via `/sys/class/backlight`.
- Exit: launcher parity checklist (same apps, same ordering rules, same history semantics) verified in preview + G3.

### Q3 — First write families: audio, power, bluetooth, wifi actions

- Families (4): audio actions (`audio_actions`/`audio_device_actions` 134), network plans/profiles (saved connections, 231), `wifi_actions`/`wifi_auth` 270, charge/power writes (`charge_actions`/`charge_control` 187).
- Mechanism: a QML-side dispatch table (`qml/services/ActionRouter.js`-style, behind the existing `ShellState.run()` facade) routes these action names to native calls (`PwNodeAudioIface` writes, `PowerProfiles`, `BluetoothDevice.connect/pair`, `WifiNetwork.connectWithPsk`); `Pending.js` sequencing is reused unchanged so status/pending UX is identical.
- The backend registry keeps the same action names registered as a fallback for one phase; the router prefers native, falls back to `run()` while the A/B window is open, then the fallback is deleted.
- Exit: G0–G4 + G6 once; action-by-action parity checklist; secure Wi-Fi/hotspot and Bluetooth pairing marked "needs real-session check" (Q-4).

### Q4 — Media, capture, display, session families

- Families (5–6): `screen_capture` + `capture_actions` 294, `screen_recording` + `recording_actions` 264, `display_control`/`display_actions`/`display_mirror`/`display_layout` 346, `night_light`/`night_light_actions` + `idle_actions`/`idle_control` 369, `ime_actions`/`keybind_actions`/`window_actions`/`niri_events` 318 (niri IPC moves to `Socket`).
- External CLIs (grim, wf-recorder, satty annotation chain) are invoked through `Process` with the **same argv allowlists** as `command_runner.py` enforces today; the allowlist table ports to QML/JS once, shared.
- `mirror`/`display_layout` keep their plan→apply shape, ported to JS.
- Exit: G0–G4 + G6 once; capture/recording flows on real hardware; annotation chain unchanged for the user.

### Q5 — Content families: weather, lyrics, wallpaper, file search, equalizer, clipboard

- Families (6): `weather`/`weather_actions` + `lyrics` 393, `wallpaper`/`wallpaper_actions`/`wallpaper_palette`/`gowall_actions`/`palette_actions` 486, `file_search` + actions 72, `equalizer_actions` + `audio_visualizer` 494, `clipboard` 315.
- `weather`/`lyrics` move to `XMLHttpRequest` with the same endpoints, caching and error shapes.
- `equalizer` ports its DSP math to JS; the equalizer curve/FFT fixtures port to the native harness.
- `clipboard` is the delicate one: its wl-paste/wl-copy watchers are long-lived children — reuses the parent-death-signal helper via `Process.startDetached` + explicit cleanup, or the family stays Python until Quickshell fixes destroy semantics (Q-3). Owner picks per the review stop.
- Exit: G0–G4 + G6 once; clipboard orphan-safety native test (the CODE_REVIEW regression must not return).

### Q6 — Storage, settings coordination, backend retirement *(public protocol change — owner approval)*

- Families: backend core (`desktop_backend.py` 1,712, `backend_actions` 80, `backend_providers` 41, `action_pending` 46, `command_runner` 137, `managed_command` 64, `command_output` 46, `detached_log` 136, `shell_update` 214, `storage` 79), settings coordination (`settings_transfer` 86, `desktop_features`/`desktop_widgets` 247), and the remaining small domains (`privacy`, `content_types`, `image_utilities`, `local_content_actions`, `launchpad`/`launchpad_actions`, `appearance_actions`, `mirror_actions`, `saver_actions`, `lock_actions`, `memory_workload`, `liquid_glass` — 900 lines; each re-homes to its owning phase if the owner prefers).
- Preferences: `FileView` with `atomicWrites` + `watchChanges` + a JSON adapter; cross-process safety via **single-writer coordination** — the standalone Settings instance forwards writes to the live shell over `Quickshell.IpcHandler` (both are Quickshell instances), or, if the owner prefers, a minimal privileged-free prefs helper stays (Q-2 decision). Lock/merge/fsync equivalence tests port from `tests/` fixtures before any retirement.
- `shell_update` becomes a detached `Process` (it already runs detached from hot-reload).
- Retire: `desktop_backend.py` spawn in `ShellState`, the JSON-lines protocol, `Pending.js` host side, backend restart supervisor; delete the deprecated snapshot sections and their tests.
- Exit: G0–G4 + G6 once; 10-launch medians + RSS at 10 s per the standing sanity rule (expect an improvement from backend removal — report honestly); `WORKSPACE_MAP.md` and all REL tags for the IPC boundary rewritten in the same commit.

### Q7 — (optional, owner decision) Test-suite rebalance for T2

- Per migrated family, its Python unit suites retire **in the same authorized scope** (already assumed above) — this phase additionally ports the cross-family contract tests to the native/local-QML harness (`LOCAL_QML_RESULT` pattern, `tests/test_local_qml.py`) and sets a whole-repo ratio target.
- Without Q7, the end state is: Python = tests for remaining facades + dev tooling (~26k shrinking to roughly the tooling/facade coverage), QML-side = all runtime code. T1 achieved, T2 only partially.
- Exit: owner accepts the new coverage map; whole-repo ratio printed by the Q0 counter.

## 6. What deliberately stays Python

- The deploy chain and its niri KDL graph validation (dev tooling, runs outside the shell, already battle-tested).
- `check_architecture.py`, catalog/schema generation and the gate scripts (they *check* QML; being Python is fine and keeps stdlib-only discipline).
- `memory_report.py` (diagnostics).
- Any privileged helper the owner keeps for charge control (Polkit path).

## 7. Risks and open questions

| ID | Risk / question | Mitigation / decision needed |
|---|---|---|
| Q-1 | A6: event-driven state changes the wake model (fewer wakes, different shape) | Per-phase approval + measured before/after wake counts; phases are severable — Q1 can land backend-polling-fallback first |
| Q-2 | Preferences cross-process safety (shell + Settings concurrent writes) today: lock/merge/fsync in Python | Either IpcHandler single-writer or a minimal prefs helper; equivalence tests ported first; owner decision at Q6 review stop |
| Q-3 | `Process` SIGKILL-on-destroy orphans long-lived watchers (clipboard regression already seen once) | `startDetached` + explicit cleanup, reuse parent-death-signal helper, or family stays Python; native orphan-safety test required |
| Q-4 | Hotspot/AP mode, secure Wi-Fi, Bluetooth pairing, charge thresholds on real hardware | "needs real-session check" items listed per phase; owner validates on the laptop before each phase's merge |
| Q-5 | Worker-shape change: backend worker threads → per-action `Process` could raise peak memory/PSS | Bounded shared pool on the QML side (same rule as today's shared workers); G6 + RSS sanity gate catches regressions |
| Q-6 | Demo/settings contexts must keep working (`--demo`, `--settings` backend flags disappear) | Demo projections already exist QML-side (demo snapshot); router carries context checks mirroring `ActionRegistry.check_context` |
| Q-7 | 250-line cap pressure when porting large Python modules (equalizer 424) | Split by concern into feature files under existing dirs; no tree reorganization needed |

## 8. Verification and bookkeeping per phase

- QML changes: G0 + G1 + relevant native cases; runtime branches: full G0–G4 + G6 **once** before the review stop; docs-only (this plan): G0 only.
- The Q0 counter's ratio trend goes into each PR body.
- CHANGELOG `## Unreleased` entry per merged phase (user-visible: "audio state now comes from PipeWire directly", etc.).
- `WORKSPACE_MAP.md` + REL/INVARIANT/GOTCHA tags updated in the same commits that move a family; the IPC-boundary invariants get rewritten at Q6, not before.
- Memory: `memory_report.py --label steady` before/after each runtime phase; backend PSS removal reported at Q6.

## 9. Expected end state

- `scripts/` = dev tooling only (~1.6k lines, unchanged in spirit).
- `qml/` + JS ≈ 21–23k lines (absorbing ~6k of ported logic; ~3k of protocol/registry/supervisor plumbing deleted outright).
- Runtime ratio ≈ 100% QML-side against the §1 metric (T1 stretch); ≥85% even if Q-3/Q-2 families stay Python.
- One process, one language for feature work, event-driven state, and the same gates, facades and memory budget the repo already enforces.
