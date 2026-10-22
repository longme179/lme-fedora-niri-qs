# Migration summaries

Historical records moved unchanged to `archive/migration/`; start at `STATE.md`.

## Agent state and architecture guard — 2026-10-21
- Branch: `chore/agent-state`, based on merged main `b751f67`.
- Commits: `169cfc4` archive/state; `9fa207f` tests; `52bbd52` guard;
  this final documentation commit records verification.
- Archived 184 files with identical SHA-256 contents; no new raw evidence committed.
- STATE: 56 lines; AGENTS: 78 lines. No shell/backend runtime code changed.
- Characterization before guard: 3 passed, 16 guard contracts N/A (not implemented).
  The additional ES-import contract failed before support; final focused run: 20/0/0.
- G0 before: not run; this task explicitly requested one final G0 execution only.
- G0 after: 587 tests = 459 passed / 0 failed / 128 skipped, 114.092 s.
  Command: `scripts/run-gates.sh --env-file /workspace/.lme-dev/env.sh
  --pointer-dir /workspace/.lme-dev --gates G0 --output /tmp/lme-agent-state-g0`.
- G0 used disposable XDG, private Sway/D-Bus; opt-in flags disabled as usual.
  Skips: 116 UI/Wayland/D-Bus/OpenGL; 5 BlueZ; 5 MPRIS; 1 Matugen; 1 fake-niri.
  These skipped cases are NOT reported as passed. No other gate was run.
- qmllint: 146 QML files, 0 errors / 71 warnings; Bash/demo/catalog checks completed.
- Guard: Python AST imports, QML/JS literal imports/types/entry URLs; descriptor
  ownership plus temporary legacy map; 10 exact legacy edges, 12 existing cyclic
  edges with reasons. No new edges/cycles; stale exceptions must be removed.
- Size cap: 250 nonblank lines for new source/config files; 26 existing large-file
  ceilings must ratchet downward. Checker + shell wrapper: 168 lines, stdlib only.
- Adapters unchanged; STATE lists retirement conditions. Guard baseline exceptions
  retire with their exact edge; legacy ownership retires as descriptors cover it.
- Behavior differences: none on exercised contracts; existing assertions untouched.
- Startup/RSS sanity not run: this docs/tooling task requests G0 only; D1 stays closed.
- Laptop checklist: none required for runtime behavior; hardware needs real-session check.
- STOP: await the next owner prompt; no M5/M6/conversion or merge performed.

## M5 — shared preference schema — 2026-10-21
- Branch `refactor/m5-settings-schema`, base main `a7f73bf`; no merge or M6 work.
- Tests: `b0d882e`, `19c075f`, approved assertions `b6c1280`, `ba0abf5`, `b9d7991`.
- Effective source: `a49994b`, `64d1898`, `c345995`, `6ea4ed7`, `0cdf18d`; harness `97bb735`; final docs commit records this summary.
- Immutable schema owns Clipboard 3, weather 2, OSD 5; 137 keys retain legacy bindings. Weather/OSD UI stays legacy, with empty startup projections.
- Baseline goldens: all 147 defaults/types/order, 2,707 validation outcomes, exact export/profile membership; old flat file, tokens and worker/main fault policies covered.
- Before refactor: focused units 41/0/5; G0 466/0/130 (pass/fail/skip). Other native gates were not run on unmodified main.
- Latest results: G0 474/0/128; G1 3/0/0; G2 4/0/0; G3 53/0/0; G4 34/0/0; G6 polling 1/0/0. Final focused units plus catalog contracts: 55/0/3.
- G0 skips: 116 opt-in UI/Wayland/D-Bus/OpenGL, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 fake-niri. Two initially N/A schema ownership contracts now execute; six tests added after baseline.
- Full gates ran once; affected G0/G1/G3/G4 retried after reverts, then G0/units after resolver support. G2/G6 results precede these unaffected changes.
- Initial G0 467/1/128 required the approved three assertion updates; failed extraction reverted (`db1ae69`) before retry.
- Initial full G3 49/3/0 and G4 32/2/0 exposed a mistyped harness target and eager schema-only descriptor loads; harness/group commits reverted (`e66e615`, `522b987`, `1ed0e89`) before retry. No other existing assertions changed.
- qmllint: 146 files, 0 errors/71 warnings. Architecture guard passes; Preferences class AST identical to main; no persistence protocol or exercised public behavior difference.
- Sanity, private software-rendered session, 10 launches/path/arm: preview main/head 812.56/792.90 ms; Settings 818.85/822.22 ms; no threshold flags.
- RSS at 10 s (KiB, main/head): preview QS 281360/280968, backend 25504/25548; Settings QS 234784/234636, backend 25452/25500. Earlier collector attempts aborted on PID lookup, not counted as completed checks.
- Adapters DEFAULT_PREFERENCES/validate_preference/PORTABLE/APPEARANCE_KEYS retain public names until owner-approved retirement; legacy callbacks/order/bar-default bridge retire with their last consumer.
- Bundled-fragment discovery preserves schema on UI-catalog fallback; revisit with authorized descriptor moves. Worker preferences() retains its separate malformed-file policy.
- Remaining groups (137): appearance/motion/palettes/profiles 27 high; wallpaper/playlist/outputs 20 high; bar/layout/gestures 12 high; idle/display/night-light 10 high.
- Activity/media/lyrics 13 medium; notifications/privacy 14 medium; desktop canvas/shapes 9 medium-high; capture/recording 9 medium.
- Laptop/Bluetooth/mirroring 7 medium; weatherLocation 1 medium; identity/search/Launchpad/tasks/general/control 15 low-high (control layout is high).
- Laptop checklist (real hardware needs real-session check):
  1. Change Clipboard capture/images/limit (20 and 500); confirm history/annotation access.
  2. Change weather automatic location and temperature unit.
  3. Change OSD enabled/position/layout/margin/output and trigger an OSD.
  4. Export a preset, change values, import; confirm private fields stay excluded.
  5. Restart shell and standalone Settings; confirm all changed values persist.
  6. Check settings/lock/import-backup mode 0600, parent 0700; one backup per import, no unexpected backups.
- STOP after M5; no startup optimization, polling change, other UI conversion or file move.

## M6 — Launchpad synchronous action pilot — 2026-10-22
- Branch `refactor/m6-launchpad-actions`, base main `948c371` (M5 already merged); no dependency on its review branch.
- Tests: `396524f`, `9c7c1d3`, `80e21dc`; extraction/routing: `fc17698`; final docs commit records this summary.
- Re-found baseline live branch 1735, separate demo branch 1331, launchpadJobs projection 1056 in desktop_backend.py.
- Explicit provider list binds provide(capabilities) in the composition root; catalog currently rejects backend fields and exports UI projections only. Discovery would also need broken/disabled-index ownership policy, beyond a small validated field.
- Only launchpadRun is registered; provider receives current-preference, controller-run and controller-snapshot callbacks. Registration reads no preferences/state and starts nothing.
- Characterization on unchanged production: focused 52/0/4; verified G0 481/0/132 (pass/fail/skip). Initial uncommitted fixture leaked disabled state across subtests (G0 480/1/132); corrected the fixture before the tests commit.
- Four registry contracts were N/A in baseline G0; five later registry-only cases also proved N/A against unmodified main. Delegate checkpoint 56/0/0; final focused tests plus existing completion regression 62/0/0.
- Final gates: G0 490/0/128; G1 3/0/0; G2 4/0/0; G3 53/0/0; G6 polling 1/0/0. G4/G5 not run: outside the explicit M6 gate scope.
- G0 skip change: four existing N/A registry cases now execute, plus five new cases; 128 remain opt-in (116 UI/Wayland/D-Bus/OpenGL, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 fake-niri). No skips count as passes.
- Full requested gates ran once after the source commit, in disposable XDG/Sway/D-Bus. qmllint 146 files, 0 errors/71 existing warnings; architecture guard passes without new exception/ceiling growth.
- Sanity: 10 launches/path/arm, private software-rendered session; preview main/head 812.36/789.08 ms, Settings 838.89/822.49 ms. No +100 ms/+10% threshold flag.
- RSS at 10 s (KiB, main/head): preview QS 282336/282148, backend 25564/26240; Settings QS 234728/234284, backend 25524/26192 (backend maximum +2.65%).
- Controller source unchanged; literal argv/Bash/terminal, detached jobs/logs/eight-job limit, disabled-live/permissive-demo, exact errors/results/order and acknowledgement/completion contracts preserved. Existing test assertions untouched.
- Compatibility: public JSON-lines actions/results/snapshots stay unchanged; unregistered live/demo trees (including prefixes) remain. Retire their branches per ID only with provider parity and same-commit registration removal.
- Explicit provider binding retires when Launchpad UI/catalog conversion supports backend discovery with covered ownership/fallback semantics. execution/complete/presentation fields exist; worker execution is rejected, not migrated.
- Assessment: cheap for further synchronous domains (53-line registry, 23-line provider); each needs narrow callbacks, one composition entry, live/demo characterization and its state projection.
- Best second candidate: launcherHistoryClear, with history clear/snapshot callbacks; app launch itself additionally needs app lookup, terminal runner and usage recording contracts.
- Appearance profiles need preference reload/update/validation capabilities and prefix parity; Wi-Fi/recorder require a separately authorized async completion contract first. No second domain implemented.
- Laptop checklist (real hardware needs real-session check):
  1. From the launcher, run a saved literal-argv Launchpad entry in the main shell without a terminal; inspect its log/job status.
  2. Run the same entry in a terminal and verify cwd, arguments and exit status.
  3. Run from the shell Launchpad panel and standalone Settings Utilities; verify both background/terminal choices.
  4. Disable Launchpad: live must show the existing disabled error; re-enable and retry.
  5. In preview/demo (including Settings demo), request that entry; verify no command, log or output file is created.
- STOP after M6; no async, executor, queue, cache, polling or power-policy changes; no merge performed.

## M4c-1 — four light catalog features — 2026-10-22

- Branch refactor/m4c1-light-features, base main d9a7211 (M5/M6 merged). Tests c0d9c0c, cd7e8c7, 20b9f9d; final docs commit records verification.
- One conversion commit each: Night Light 951ae17; Idle 190869b; Keybinds ee39333; Weather 806e9fd. No files moved or features added.
- Five catalog Settings pages now include Clipboard; exact sidebar/search order and CLI admission retained. Schema owns 20 keys; 127 remain legacy (Night +5, Idle +3, Keybinds +1, Weather +1).
- Baseline G0 495/0/132, G1 3/0/0; focused/native 50/0/2 (ownership/withdrawal N/A). All counts are pass/fail/skip; production was unchanged during characterization.
- Night/Idle/Keybinds each: G0 496/0/131, G1 3/0/0; focused/native 52/0/0. Weather focused/native plus existing Settings cases: 63/0/0; its G0/G1 ran within the one final full set.
- Final gates: G0 496/0/131; G1 3/0/0; G2 4/0/0; G3 53/0/0; G4 34/0/0; G6 polling 1/0/0. Disposable XDG/Sway/D-Bus; no gate failure/revert.
- G0 skips: 116 other opt-in UI/Wayland/D-Bus/OpenGL, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 fake-niri, 3 light native cases. Ownership N/A now runs; all three new native cases ran separately with zero skips.
- Legacy CLI fixtures now derive the remaining list/use Behavior instead of Weather; existing assertions and frozen JSON goldens unchanged. Full 147-key defaults/validation/export parity passed after every conversion.
- Withdrawal preserves exact settings/grid/schema/data bytes and IDs, hides pages/card/tiles, disables the Night Light -> Weather link, rejects withdrawn CLI keys and restores access on re-enable.
- Fifth-page copied fixture adds only own QML/schema descriptor and one index record; no host edit. Action-provider capability bindings remain the explicit host adapter, not automatic discovery.
- Preferences class AST and all four worker/controller files unchanged; enabled behavior, public facades/results/snapshot shape, privacy exclusions and worker policy preserved. No new dependency exceptions/cycles; backend ceiling ratcheted downward.
- Sanity: ten launches/path/arm; preview main/head 891.88/884.28 ms, Settings 885.55/901.42 ms (+15.87 ms); no +100 ms/+10% flag.
- RSS T+10 s (KiB, main/head): preview QS 281076/280624, backend 26240/26184; Settings QS 234836/234520, backend 26184/26160. Private software-rendered session.
- Retain settingsPageAvailable/control-grid availability guards while surface factories remain legacy; retire per namespace when catalog surface entries cover the same routes/IDs.
- Explicit sync providers retain host night_state/idle_state/keybinds facades and projection slots; retire with covered controller/state-consumer migration and backend-discovery ownership/fallback parity. Public import facades need owner-approved retirement.
- Weather search/detect/select/refresh stay legacy: its controller owns asynchronous requests/cache. No registry worker/complete extension, sampling, cache or power-policy change.
- M4c-2 plan, Notifications: preserve NotificationServer/history/annotation bootstrap and the fontSettingsRequested -> Elements route via a common navigation adapter; page-only loading cannot forward that signal today.
- Desktop: preserve per-output layer/input/geometry lifecycle, DesktopState/notes bootstrap, edit IPC and Notes/media services; characterize withdrawal without deleting widget data.
- Wallpaper/Utilities: retain scan/palette/awww/gowall async completion/cancellation, playlist/output state, managed/detached jobs, Utilities -> Wallpaper route and Launchpad editor composition; no async conversion without authorization.
- Expected dependency work: retain or replace existing DesktopCard -> QuickNotes, UtilitiesPage -> GowallSettings, image_utilities.py -> wallpaper.py seams with shared APIs/composition. Do not create a new Utilities owner that imports Launchpad/Gowall implementations or add exceptions to bypass the rule.
- Laptop checklist (hardware needs real-session check):
  1. From Gear, open each of the four pages; verify headings and normal layout.
  2. Run settings.sh --page nightLight/idle/keybinds/weather separately; repeat through Settings search and verify sidebar order.
  3. Change temperature/schedule, idle profile, keybind config path and weather unit/location; restart and confirm persistence.
  4. Use weather-card Gear and Night Light's Weather link; confirm they reuse the expected page IDs.
  5. Disable one index entry in a copy, restart shell/Settings; confirm page/UI/CLI withdrawal and graceful links with saved grid/data unchanged.
  6. Re-enable the entry, restart and confirm access/settings return; check real gamma/idle behavior without competing daemons.
- STOP after M4c-1; M4c-2/M7 are not authorized; no merge or main push performed.

## M4c-2 — stateful pages and local navigation — 2026-10-22

- Branch refactor/m4c2-stateful-features; base main f5b5bda (M4c-1 merged). No main push or merge.
- Commits: characterization aaeeb40/4eedd69; navigation aae273e; fixture-only 06ea4ca/a0ffa77; Wallpaper a28ca9e; Utilities e652aaa. Failed conversion commits cae954f/f3be258 were reverted by ae4597c/e32027c before retrying.
- Converted Wallpaper page +21 keys; Utilities page +2 keys under existing launchpad ownership. Seven catalog pages, 43 descriptor keys, 104 legacy; sidebar/search/CLI order unchanged. Shared palette controls remain with Appearance legacy bindings.
- Wallpaper/Utilities scope is pages/schema only: scan/palette/awww/gowall, playlist/output state, managed/detached jobs, Launchpad editor/actions and all async/live/demo routing remain unchanged. No backend Python code changed.
- Notifications SKIPPED: complete center withdrawal needs preservation of numeric tab 4, which current catalog metadata/projection cannot express. No server/history/mute/DND/toast policy changes; see the ten-line M4C2_NOTIFICATIONS.md addendum.
- Desktop SKIPPED LAST: current canvas runs in non-preview demo as well as live; FeatureBootstrap is main-live-only. An equivalent context-aware bootstrap needs a separately scoped metadata/guard contract. Canvas/ambient/input/geometry/edit IPC/notes files unchanged; copied native lifecycle passes; hardware needs real-session check.
- No new dependency exceptions/cycles. Utilities keeps its existing Launchpad composition owner and exact Gowall edge; navigation removes no static implementation edge, so no stale exception was removed. No file moves.
- Unmodified-main baseline: G0 497/0/136, G1 3/0/0; focused 35/0/2 (ownership/withdrawal N/A). Fixture adaptation baselines: Wallpaper native 3/0/0; CLI/model fixtures 10/0/0 before retrying conversions. Counts are pass/fail/skip.
- One full G0-G4/G6 run: G0 488/2/135 (Utilities-first test selectors), G1 3/0/0, G2 4/0/0, G3 53/0/0, G4 34/0/0, G6 polling 1/0/0. After revert/fixture correction/retry: affected G0 498/0/135 and G1 3/0/0; final production config/scripts/qml is byte-identical to f3be258, where G1-G4/G6 ran. The full set was not repeated.
- Focused final native/domain/schema suite: 42/0/0; post-selector correction 37/0/0. Ownership N/A now executes (+1 G0 pass/-1 skip). G0 skips: 123 opt-in UI/Wayland/private-session cases (including four new stateful native cases), 5 BlueZ, 5 MPRIS, 1 Matugen, 1 fake-niri. All four new native cases executed separately. qmllint: 147 files, 0 errors/71 warnings.
- Withdrawal tests preserve exact settings/history/notes bytes and saved IDs, hide pages/search/CLI, disable Utilities -> Wallpaper when unavailable and restore access on re-enable. Fifth-entry copied fixture still needs only own QML/descriptor/index. Notifications/Desktop withdrawal is deferred, not claimed tested.
- Existing assertions (AST comparison), timeouts and frozen fixtures unchanged. Existing Wallpaper QML fixture now loads its retained file URL; two CLI/model fixture selectors read the actual legacy list. Early navigation prototypes were discarded on failed checks; the new fixture waits for closed-popup unmount.
- Adapters: PageNavigation locally forwards navigateRequested(pageId) to SettingsView; old fontSettingsRequested/wallpaperRequested signals remain public facades. Retire only with owner-approved public compatibility removal. settingsPageAvailable/hybrid legacy lists retire per namespace after their final surface/fixture migrates.
- Schema legacy validator/resolver callbacks, default/export facades and bundled-fragment fallback remain until their last consumer/fault policy migrates. Preferences transactions, schema data format, defaults, limits, privacy membership and CLI messages unchanged. No observed enabled-UI difference beyond the authorized local navigation seam.
- Sanity ONCE, ten launches/path/arm, private software-rendered session: preview main/head 1049.22/927.96 ms; Settings 989.87/946.64 ms. No +100 ms/+10% flag; these are medians, not a performance claim.
- RSS at T+10 s (KiB main/head): preview Quickshell 281048/281148, backend 26216/26208; Settings Quickshell 234524/233644, backend 26172/26172. No raw logs/evidence committed.
- M4c-3 plan: Appearance/Elements need ownership of palette/theme/font tokens, runtime default/profile resolvers, picker dialogs and platformRefresh/reconnect characterization; keep handwritten UI and token-patch persistence unchanged.
- Top bar/bar modules need catalog layout/default/gesture/visibility parity, saved IDs and per-screen/window contexts. Convert simple ActionBarButton families first; keep workspace/tray/media/privacy service lifecycles legacy until separately characterized.
- Behavior is a composite of battery saver, lyrics, peripherals, recording/capture, launcher, OSD and transfers: move only page/scalar ownership with clear fragments; keep async/hardware actions legacy. Display should keep apply/confirm/revert/watchdog and reconnect routing legacy; About needs UpdateState inspect/check/update/bootstrap process-lifecycle tests.
- Controls/Launcher/Activity panels are best left legacy pending composition/refresh leases, numeric-tab compatibility, ranking/search workers and MPRIS/lyrics/focus/notes seams. Expected dependency work: explicit host composition/shared APIs for cross-feature cards, then retire exact QuickNotes/Gowall edges; no new exceptions, event bus, async registry, polling or power-policy changes. Notifications/Desktop need their deferred contracts before conversion.
- Laptop checklist (needs real-session check):
  1. Open Wallpaper/Utilities from Gear, CLI and search; verify sidebar/order and close/reopen.
  2. Change wallpaper transition/playlist and a Launchpad entry; restart, confirm persistence and run the entry in terminal/background.
  3. Check Notifications Font families -> Elements and Night Light -> Weather; verify DND/history and screenshot annotation still work.
  4. In a copy disable wallpaper, restart: page/search/CLI disappear and Open awww controls is disabled; existing engine/output data stays.
  5. Disable the launchpad index record: only Utilities page withdraws in this batch; Launchpad runtime/saved entries remain. Re-enable both records and confirm access/data return.
  6. Check unchanged Desktop clock/notes/media, edit drag/resize, input/layers and multiple outputs on the laptop.
- STOP after M4c-2; M4c-3/M7 and later are not authorized.
