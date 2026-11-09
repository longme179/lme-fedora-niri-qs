# Agent state (2026-11-06)

Read this file at task start; consult ARCHITECTURE.md for contracts.
Do not read archive/ unless answering a specific historical question.
## Merged and authorized

- M0-M3, M4a/M4b, M5/M6, M4c-1/2/3, M7a/b/c/d, F1-F5, resource/lifecycle, Capture, Display preview, Mirroring and selection/application merged; registry including W2: 86/100 IDs (50 sync entry calls + 36 workers).
  Ten catalog pages; 79 descriptor keys/68 legacy; Clipboard bar converted; tab/bootstrap adapters implemented (19 catalog records, nine with empty startup UI metadata).
- D1 startup optimization CLOSED; further async conversions need authorization; M8 deferred.
- Roadmap accepted 100% (10/10) by owner on 2026-11-01: normal-use functionality tested, aggregate shell/process RAM reported at or below 400 MB in btop. This replaces the pending laptop/PSS acceptance gate; no new quantitative PSS/GPU measurement or RAM-saving fix is claimed. PR #42 is merged. W1 Audio/headset (PR #44) adds four on-demand workers and observed ports/profiles/routes; native revisions approved/applied, physical headset checks remain. PR #44 is merged (bcbb359). Launcher Gio lifetime fix PR #45 is merged (4e5fbf1); restart the shell after updating. W2 review branch feature/network-connections adds on-demand saved connections and confirmed secure hotspot activation; physical NM/keyring/AP/wired checks remain. W3+ is unauthorized. See AUDIO_HEADSET.md and NETWORK_CONNECTIONS.md.
- M1 (P-01…P-06) merged via PR #48; the G0/G1 follow-up merged via PR #49. M2 (P-07/P-09) merged via PR #50. M3 (P-10…P-12) merged via PR #51. M4 (P-13…P-15) merged via PR #52 (`bc15922`). P-16 IME indicator merged via PR #53 (`97aae1e`). Serpantinum equalizer merged via PRs #56–#63 (`e9dd83f`); the 2026-11-06 audit (#64–#67) replaced the undisplayable bootstrap popup with the registered catalog panel, unified apply auto-start, hardened finish_features/capture snapshot paths and refreshed docs.
- A6 remains out of scope: no polling-cadence or power-policy changes. The owner-requested M4 niri event-stream cache (P-14) is the only authorized cache exception; it reuses the already-running stream and reseeds through the existing polling path.
- Development skills: Ponytail full + .agents/skills/modularity/SKILL.md; use proportionately, without extra ceremony.
- Total-shell memory target: <=400 MB steady / <=500 MB ordinary active use, including workers and open Settings.
  Prefer aggregate PSS, label summed RSS limitations and temporary-job peaks; individual PID samples are not the total.

## In progress

- M4 (P-13…P-15) on fix/m4-runtime-efficiency: backend snapshots carry per-section revisions and QML reuses unchanged apps/niri/preferences/launcher usage objects (stringify fallback and drag pin kept); niri workspace/window state is cached from the already-running event stream and falls back to `niri msg` whenever the stream is unavailable or an event is unknown/malformed/out of order; P-15 attributed the idle CPU to the MediaAmbient drift loop without changing the 12 shapes or motion.
- M4 verification: G0 851 passed / 0 failed / 184 skipped with qmllint 153 files 0 errors/warnings; G1 9/0/0; G6 polling 1/0/0. G2/G3/G4 reproduce the identical 4/4/4 baseline failures on clean main (missing `wtype`, Sway/portal window checks), so they are not branch regressions. Ten cold launches: preview 1.001→0.993 s, Settings 0.991→1.010 s; PSS at 10 s stayed within +1.2% (preview QS 255,863→258,798 KiB, backend 24,274→24,263 KiB; Settings QS 201,285→202,749 KiB, backend 24,232→24,255 KiB). Real niri/Radeon idle soak remains a hardware check.

## Compatibility adapters and retirement

- Runner/errors/TOOLS, storage/content-type/image-path/peripheral-value/display-layout re-exports: retain until zero consumers plus owner-approved retirement.
- F3 legacy pending reducer retains old-peer/fixture fallback; retire only at zero legacy consumers plus owner approval. pendingActions and emit/handle/snapshot stay public facades.
- Integer controlTab/named env mapping: public compatibility; internal adapters retire after all callers/fixtures use stable IDs.
- Hybrid registry projections, legacy lists, legacy_ids() source bridge and panel
  allowlist: retire per namespace after its final legacy registration/fixture.
- ClipboardFeature -> ClipboardState.start(): retain until equivalent bootstrap
  preserves main-only once semantics and Settings/demo/preview guards.
- ClipboardButton -> ActionBarButton: retain until an equivalent entry preserves
  geometry, gestures and screen context. No Clipboard implementation files moved.
- Eight descriptor-provider domains (light + controller batches + audio + wifi): explicit fallback factories/narrow capabilities remain; disabled/missing entries keep actions, broken references retain legacy UI + diagnostic. W2 composes existing WifiCapabilities/provide; disabled wifi hides W2 UI only and retains legacy Wi-Fi/data. Others stay explicit. Retire fallbacks/import facades only with equivalent fault/withdrawal coverage + owner approval. PreparedWork/complete/presentation retain host scheduling/Future tags; Weather/Saver/Mirror keep lifecycle, journals and child ownership. Public perform/perform_demo/wifi_action facades retain their zero-consumer retirement rule and cadence.
- PageNavigation forwards navigateRequested(pageId); retain old page signals until owner-approved retirement.
- W1 audio composes the existing AudioCapabilities/provider facades and descriptor fallback; retain until zero consumers and owner-approved retirement. Demo projection excludes legacy launchpadJobs until an approved contract change. No new daemon/poller; routing requires verified server/object identity and read-back.
- Notifications.start/demo readiness and legacy bar availability guards retire only with equivalent catalog composition/worker isolation; public flags/IDs stay.
- DEFAULT_PREFERENCES/validate_preference and PORTABLE/APPEARANCE_KEYS are schema
  facades; retain public names until explicit owner-approved compatibility changes.
- Legacy fragment (68 keys), validator/default bindings, inventory, bar-layout resolver
  and bundled-fragment fallback retire at their last consumer/fault contract. Worker policy is separate.
- Architecture exceptions/size ceilings: remove vanished edges, lower shrunken
  large-file ceilings; no new cross-feature edges or cycles.

## Gates and working rules

- `./deploy.sh`: deployment plan/apply/rollback (DEPLOYMENT.md). `./scripts/check.sh`: architecture/catalog + unit discovery + Bash/demo checks.
- `python3 scripts/memory_report.py --label steady`: read-only PSS inventory; review ownership/partial counters before accepting totals.
- `./scripts/run-gates.sh --gates G0` isolates XDG, Sway/Wayland and D-Bus;
  optional `--env-file FILE --pointer-dir DIR`. Gate cases: tests/migration_checks.py.
- During work: Python = G0 + relevant units; QML = G0 + G1 + relevant native case.
  Runtime branches: full G0-G4 + G6 polling ONCE before merge review; explicit task scope overrides.
  Docs/skills-only: G0 only, no GUI gates/sanity. Report actual pass/fail/skip counts and reasons.
- Tests first, then implementation, then docs. No assertion edits without asking;
  revert a failed commit, never fix forward. Refactors preserve behavior; authorized fixes/QoLs may improve it (2026-10-23), with tests and reported differences.
- Disposable sessions only; never real config/session. Hardware: needs real-session check.
- Runtime branch sanity once before merge: 10 preview/Settings launches each,
  main vs head medians; QS/backend RSS at 10 s. Ask if Settings >+100 ms or RSS >+10%.
- No more D1 profiling, CIs, A/A, seeds, aggregate c or validation scheduling.
- Priorities: modularity, scalability, functionality, stability, memory footprint.
- Future family batches: 3-6 features per branch; one review stop per branch.
- Ask only for unapproved behavior/API/data-format changes, unclassifiable baseline failure,
  or sanity flags. Never start an unauthorized milestone or merge/push main.
- Replies <=40 lines; report ROADMAP acceptance % and current branch delivery %. One MIGRATION entry <=30 lines, laptop checklist <=6 lines.
  Commit only final gate summaries; no raw evidence directories.
- Preserve stdlib/unprivileged backend, English text, Preferences lock/merge/atomic
  writes, preview/standalone Settings and non-destructive installers.

## QML-first migration (Q0)

- Owner accepted the phased QML-first plan (docs/QML_FIRST_MIGRATION_PLAN.md, PR #113) and authorized Q0 on 2026-11-09. Targets: T1 = runtime >= 85% QML-side with `desktop_backend.py` retired (Q1-Q6); T2 = whole-repo QML majority (Q7, optional, explicit owner decision).
- Q0 on `qml/q0-metric-baseline`: `config/architecture.json` gains `toolingFiles` (the 12 dev-tooling modules); `check_architecture.py` prints an informational language mix in every G0 summary (wc -l parity; exit code and gates unchanged); `tests/test_architecture.py` characterizes the classification and slice arithmetic.
- Baseline frozen at `8ebc597` (pre-Q0): runtime QML+JS 16,228 (63.6%) vs Python 9,277 (36.4%); tooling Python 1,637; tests Python 26,161; whole-repo 69.5% Python. Post-Q0 actual: tooling 1,672 and tests 26,198 (Q0's own added lines), whole-repo 69.6%.
- Next: Q1 (audio, battery/AC, power profiles, bluetooth, network read-only native state) needs A6 approval before its branch exists; each event-driven phase reports measured before/after wake rates.

## QML-first migration (Q2, owner approved)

- Owner approved Q2 on 2026-11-09 after validating the #116 battery hotfix ("GREAT RESULTS, Q2 can start now"). Branch `qml/q2-native-files` (tests, implementation, docs commits).
- Read-only file families now flow natively: `LauncherState.qml` (DesktopEntries app list in the exact backend apps shape — ids keep the `.desktop` suffix so existing launch history and quick-tie rankings survive; native launch via `DesktopEntries.byId` + `execute()` for GUI apps and the configured terminal `-e` command for Terminal=true entries, both detached from the shell process; usage store = FileView JSON on the same `launcher.json` with launcher_history.py's exact constants, validation bounds and atomic writes, now event-driven via file watch instead of the per-emit stamp poll) and `MonitorState.qml` (aggregate cpu + per-core rows from one /proc/stat read, memory fields from /proc/meminfo, interface rates and the 60-sample history from /proc/net/dev gated to the panel being open — all at the backend's 2 s `--interval` cadence, so **no A6 change**; ElapsedTimer windows reproduce the Python monitor's persisted-interval behavior across panel reopenings).
- Wiring: `NativeState.apps()/usage()/monitor()` gate the top-level keys (fixture modes pass the backend through — the demo backend owns its demo apps); the cpu/memory system fields join `baseSections` (keying the SystemMerge cache to the monitor tick); `SystemMonitor` subscribes `MonitorState.enabled` alongside the backend `monitor` action; the launcher's app activation routes through `LauncherState.launch` (fixture modes round-trip `run("launch")` inside).
- Transitional backend-fed keys (documented in `NativeState.compose`): `tempC` and `brightness` — the hwmon/backlight sensors need directory globs and quickshell 0.3.2 has **no directory-listing API** — and the monitor `processes`/`processCount` (/proc/<pid> iteration); they move when the Q4 Process/allowlist machinery lands or quickshell gains the API (decision for the Q4 review stop). Five backend emit sites marked `DEPRECATED(Q2->Q6)`.
- Two cycle edges recorded with reasons (LauncherState→ShellState launch fallback + status surface; NativeState→LauncherState gating) — runtime-safe, user-activated or pure-function paths, no binding loops.
- Known fidelity edges for the A/B window (compareSections warns on apps-count and memoryTotalGiB drift): the native list can be a **superset** — quickshell exposes no OnlyShowIn/NotShowIn/TryExec to filter with, and invalid-Exec entries are not dropped; Exec field codes are stripped rather than expanded (backend expanded %c/%k/%i).
- G0: architecture green (2 new cycle edges allowlisted); 1103 tests (16 new), 3 known quickshell-absent errors; language mix 64.7% QML-side runtime (16,582 → 17,002 runtime QML/JS lines).
- Needs real-session check (owner, before merge): launcher parity checklist per plan §5 Q2 — same apps (review the A/B superset), same ordering, same history semantics (existing launcher.json untouched values), launch a GUI and a terminal app, monitor panel values vs before.

## QML-first migration (Q1, A6 approved)

- Owner approved starting Q1 and the wake-model change (polling -> event-driven) on 2026-11-09. Branch `qml/q1-native-read-state` (tests, implementation, docs commits; stacked on the Q0 plan branch because #114 merged into `docs/qml-first-migration-plan` after #113 squash-merged to main — this PR carries the Q0 re-land).
- Read-only state for five families now flows natively: `AudioState` (Pipewire default sink/source + PwObjectTracker; volume/mute OSD is event-driven now), `PowerState` (UPower displayDevice + aggregate + PowerProfiles + peripheral supplies), `BluetoothState.sectionFor` (Quickshell.Bluetooth; pairing agent untouched), `NetworkState` (Networking summary), composed by `NativeState.merge` into `ShellState.system` with reference-stable caching (`SystemMerge.js`). Consumers unchanged — sections keep the exact backend shapes, frozen by `tests/test_native_state.py`.
- Transitional backend-fed keys (documented in NativeState.compose): bluetooth rfkill soft/hard-block flags (no native API) and wifi `networks`/`saved` lists (bssid-keyed connect; Q3 moves them). `batterySaver` stays backend-sourced until its state machine and toggle move together (re-homed from Q1's module list to the write phases).
- A/B window: the backend still emits the migrated sections (marked `DEPRECATED(Q1->Q6)`); `NativeState.compareSections` counts and rate-limited-warns drift between backend and native values; demo fixtures in NativeState deep-equal the backend demo snapshot (test-frozen).
- Recorded 4 cycle edges with reasons (NativeState composition; BluetoothState preference reads now cyclic) — runtime-safe, different properties.
- G0: architecture green; 1082 tests on this branch (Q0 re-land + 9 new), 3 known quickshell-absent errors; gated demo-merge QML case needs a Quickshell machine.
- Real-session A/B audit (2026-11-09, remote agent on the owner's desktop, deployed `f607734`, quickshell 0.3.2 fc44): battery drifted on every line — backend percent 79 vs native 1 while `upower` and D-Bus report 79%. Root cause: Quickshell normalizes the UPower D-Bus Percentage (0-100) to a 0-1 fraction (`DBusDataTransform<PowerPercentage>` applies *0.01), and `PowerState` rounded it as 0-100. Same-day hotfix (`fix/q1-upower-percentage-scale`): both UPower read sites go through `percent100()` (the *100 Q1 already applied to Pipewire volume, wifi signalStrength and Bluetooth battery was missing only here); `healthPercentage` (D-Bus Capacity) is untransformed and stays as-is. Everything else in the audit was clean: audio/microphone/bluetooth/powerProfile/peripheralBatteries zero drift; network only ±2 strength sampling jitter while the backend poll lags the event-driven value (expected during the A/B window).
- Still needs real-session check (owner): post-hotfix bar/CC battery value, volume-key OSD, bluetooth/network toggles, measured idle wake-rate delta vs main.
