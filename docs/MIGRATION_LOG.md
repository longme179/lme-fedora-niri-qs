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

## M4c-3 — catalog capabilities and stateful bootstrap — 2026-10-22

- Branch refactor/m4c3-capabilities; base main 37ab8ac. Review branch only; no merge/main push.
- Commits: tests f2758f1/e39a57d/c186ca6; fixture b37da99 reverted dcddefc → 5882838; capabilities da03d5d/e0922c3; withdrawal contract 431b74a; Notifications 760c270, Desktop f06a9cc, About 95ab3db.
- Converted Notifications (page/tab/toasts/server), Desktop (page/canvas/ambient/widgets) and About (page only); none skipped. All other requested legacy families stay legacy.
- A: explicit unique int32 legacyIndex for controlTab/agendaTab; original six tab mappings/order and numeric/ID/env routes preserved. Unnumbered entries follow reserved indices.
- B: contexts live-main/demo/preview/settings, omitted = live-main. Clipboard remains main-live-only/once; Desktop runs live/demo, never preview/Settings.
- Schema: moved Notifications 14 + Desktop 9 keys unchanged; 66 descriptor/81 legacy keys; About owns no keys. No file moves, new exceptions, async registry, cadence/power changes.
- Withdrawal preserves exact settings/history/notes/widget bytes and saved IDs; no notification server/UI or desktop surfaces; edit IPC returns false. Re-enable restores access. Ten-line policy: M4C3_NOTIFICATIONS.md.
- Enabled history/mute/DND/annotation/toast suppression, canvas geometry/layer/input/media/notes seams and updater lifecycle pass native tests; hardware needs real-session check.
- Baseline on unmodified production: G0 499/0/139, G1 3/0/0; initial capability/domain suite 26/0/4 and feature suite 2/0/1 (extension/withdrawal N/A).
- Affected final runs: Notifications 71/0/1, Desktop 41/0/1, About 30/0/0; each G0 501/0/141 + G1 3/0/0. N/A skips were About withdrawal before its conversion; CLI fixture baseline 6/0/0.
- Full G0-G4/G6 at final tested head 5882838 (production identical to 95ab3db): G0 501/0/141; G1 3/0/0; G2 4/0/0; G3 53/0/0; G4 34/0/0; G6 1/0/0 (pass/fail/skip); following docs only record results. qmllint 148 files, 0 errors/71 warnings.
- G0 skips: 129 opt-in UI/private-session cases (six new native); 5 BlueZ, 5 MPRIS, 1 Matugen, 1 fake-niri; the six new native cases run in affected private sessions. No skipped gate is reported passed.
- Discarded failed uncommitted prototypes (import/JSON/readiness/CLI). Preliminary full G3 was 52/1/0: helper hard-coded six legacy tabs; b37da99 was reverted, corrected as 5882838, native probe 2/0/0. No assertions/timeouts relaxed.
- Existing assertion ASTs and frozen JSON unchanged. Fixture diffs: [5882838](https://github.com/longme179/lme-fedora-niri-qs/commit/5882838.diff), [c186ca6](https://github.com/longme179/lme-fedora-niri-qs/commit/c186ca6.diff); new probe wait: e39a57d.
- Fixture-only diff: `- DesktopPage/AboutPage {…}` → `+ Loader {source: retained file URL; …}`; tab probe strips after/maps URL to original type ID, legacy expected bars exclude withdrawn owners; reordered fixture relocates the catalog record; `- tabs>=6` → `+ tabs>=len(remainingLegacyTabs)` (readiness helper only).
- CLI fixture diff: `- ('appearance','behavior','controlLayout','about')` → `+ current legacy admission list`; copied reader gains catalog_metadata.py. All original success/error assertions remain exact.
- Adapters: public integer/env/page/panel/flag/schema facades remain; internal projections retire at zero callers/legacy entries. Notifications.start/demo-ready and bar guards retire with equivalent composition/worker isolation; KINDS/FIELDS stay re-exported.
- Behavior differences: none on exercised enabled user paths; authorized catalog withdrawal/context/index capabilities added. Demo annotation ready now waits for its bootstrap; persistence formats/transactions and worker policies unchanged.
- Sanity ONCE, 10 launches/path/arm, private software-rendered session: preview main/head 909.04/932.13 ms; Settings 889.43/941.16 ms. No timing/CI/profiling study or raw evidence committed.
- RSS T+10 s (KiB main/head): preview QS/backend 281140/279764; 26216/26228; Settings 233008/231128; 26172/26196. Settings +51.73 ms; maximum backend RSS +0.092%; no +100 ms/+10% flag.
- M7 inventory/plan: 89 IDs = 59 sync (5 registered), 29 worker/async, 1 conditional suspend; domain counts and lifecycle qualifications in [M4C3_M7_PLAN.md](M4C3_M7_PLAN.md).
- Proposed M7 order: local content → audio/palette → launcher; separately authorize async wallpaperScan pilot → remaining workers → display/power lifecycle last. No M7 implementation or merge authorized; STOP here.
- Laptop checklist (needs real-session check):
  1. Open Notifications/Desktop/About by Gear, CLI and search; verify order, close/reopen and updater controls.
  2. Receive native notifications; check history, mute/DND, center/toast suppression and screenshot click → annotation.
  3. Check Desktop clock/notes/media, edit drag/resize, input/layers, reconnect/multiple outputs and saved geometry.
  4. In a copy disable Notifications/Desktop/update entries; restart shell/Settings: UI/server/surfaces withdraw, saved bytes/IDs stay.
  5. Re-enable/restart; confirm data/access return and the Clipboard worker starts once live and never in Settings/demo/preview.

## M7a — synchronous coordinator providers — 2026-10-23

- Branch refactor/m7a-sync-actions, base main add26d5; review only, no merge/main push. Final runtime tree 70f2af9; subsequent changes are documentation only.
- Tests 1ec793c/a78b9aa; fixture 26f60ce; providers: local 98ee7b4, audio f80f164, windows e156f3f, appearance 70f2af9.
- Reverted audio 07a0355 with f72ce29 after G0 513/1/141 exposed a stale perform mock; corrected fixture before retry. Reverted appearance 82a7071 with f0c4542 after direct demo-return reproduction; one corrected extraction per affected provider.
- Registered all 24 requested IDs: local content 4, audio/backlight/Bluetooth 7, windows/launcher 6, appearance/transfer 7. None skipped; 29/89 IDs registered including the existing 5; unlisted actions remain legacy.
- Discovery reuses the M6 explicit composition list. Four flat providers receive narrow callbacks, never DesktopBackend; no registry extension, worker/complete hook, second executor, new dependency exception or schema migration.
- Host retains context admission before demo/live, acknowledgement/sequence/query/result publication, explicit read-back invalidation and existing snapshot slots. Registered errors do not fall back; unknown IDs/prefixes retain both legacy trees.
- perform: 344 → 233 lines; perform_demo: 187 → 139 (AST function spans, physical/nonblank equal). Existing source ceiling ratcheted down; new files below 250 nonblank lines.
- Characterization on unmodified production: G0 513/0/142; focused backend/contracts 51/0/1. Golden matrices freeze live/demo × shell/Settings results, commands/kwargs, state and preference changes; UTF-8 byte bounds and private-file bytes/modes are asserted separately.
- Additional direct demo-facade characterization passed 1/0/0 on unmodified main; reproduced 3 profile subtest failures on the first extraction, then passed after revert/re-extraction. Retained facade now preserves None.
- Affected G0 after local/audio retry/windows/initial appearance: each 514/0/141. Focused final suites: local 64, audio 66, windows 82, appearance 76 passes, no failures/skips.
- Full final G0-G4/G6 at runtime head 70f2af9: G0 515/0/141; G1 3/0/0; G2 4/0/0; G3 53/0/0; G4 34/0/0; G6 polling 1/0/0 (pass/fail/skip). Earlier preliminary full run was interrupted in G3 for facade review and is not counted as complete.
- G0 skips: unchanged 141 baseline cases (129 opt-in session/UI, 5 BlueZ/PyGObject, 5 MPRIS, 1 Matugen, 1 detached fake-niri). The initial extra ownership N/A skip now executes; one added facade test accounts for the other pass. No skipped gate is called passed.
- qmllint: 148 files, 0 errors, 71 existing warnings. Architecture dependency/cycle/size checks pass; all existing assertion ASTs and frozen fixtures remain unchanged.
- Fixture-only diff in test_polling.py: `- FakeRunner({("pw-dump",): "[]"})` → `+ FakeRunner({("pw-dump",): "[]"}, available=("wpctl",))`; assertions/timeouts and production polling stay untouched.
- Behavior differences: none on exercised enabled user paths; detached jobs/history/literal argv/terminal choice, Bluetooth projection, demo no-I/O, profile transactions and Settings backup/permissions retain their contracts. No public CLI/IPC or persisted-format change.
- Sanity ONCE: 10 fresh-process/fresh-XDG launches per path/arm, private Sway/D-Bus software rendering; mapped-window endpoint, warm OS page cache. Preview median main/head 678.68/682.08 ms; Settings 748.90/741.60 ms. No startup profiling/CIs/raw evidence committed.
- RSS T+10 s, KiB main/head: preview QS 281644/279324, backend 26256/25944; Settings QS 231240/230820, backend 26212/25896. Neither Settings +100 ms nor process RSS +10% flag triggered.
- Adapters: explicit provider bindings retire only with descriptor discovery ownership/disabled/fault parity; direct perform/perform_demo facades require zero direct callers plus owner-approved retirement. Domain helper/public import facades remain while existing consumers or prefix contracts need them.
- Existing prepare_notes/valid_notifications/set_bluetooth/appearance_action helpers, state projections and Preferences lock/reload/merge/fsync/replace remain authoritative. M7b/async work is not authorized.
- Laptop checklist (needs real-session check):
  1. From the shell adjust volume/mute/microphone/brightness; confirm HUD and device read-back, including Bluetooth connect/disconnect.
  2. Launch apps normally and in the configured terminal; focus and move a window; confirm launcher history and literal arguments.
  3. Switch workspaces, including another output, and check focus/overview behavior.
  4. In Settings save/apply/delete an appearance profile and apply/reset a palette; confirm unrelated overrides remain.
  5. Export/import a preset, restart, verify values and private backup; confirm preview/demo runs no system commands.

## M7b — wallpaperScan asynchronous pilot — 2026-10-23

1. Baseline main 411cc9f: handle (1282) admits wallpaperScan in shell and the Settings legacy allowlist; process context precedes demo/live selection.
2. Live perform (1593) calls start_feature('wallpaperScan', lambda: wallpaper_library(request.get('folder'))); it does not scan synchronously.
3. start_feature (1112) rejects an existing owner with 'This operation is already running'; otherwise submit uses the existing two-worker feature_executor and feature_jobs.
4. handle returns {ok:true, action:'wallpaperScan', message:'Working…', pending:true, sequence:N}; no new result shape is needed.
5. snapshot (1025) uses result_unemitted to publish the input acknowledgement before inspecting completed jobs; emit (1780) retains JSON-lines publication.
6. finish_features (1117) chooses the first done job, increments sequence, obtains job.result(), installs wallpaper_library and publishes 'Wallpaper library refreshed'.
7. Completion removes that feature_jobs owner, invalidates system_cache and breaks; each later completion receives its own result/sequence.
8. CommandError/ValueError/OSError retain the old list, add error=str(error)[:400] and publish the same truncated error result; pending is absent.
9. Snapshot field remains wallpaperLibrary at feature_snapshot (1088); entries/folder/truncated/error and all other snapshot slots stay unchanged.
10. ShellState.accept (195) clears pendingActions[action] on a non-pending result; backend.onExited (216) clears all UI pending ownership.
11. Scan has no action-specific cancellation; shutdown (1933) calls feature_executor.shutdown(wait=False, cancel_futures=True), without a final completion emission.
12. Running futures finish normally; queued futures cancel. Manually finishing a cancelled future raises CancelledError today; that policy is not redesigned.
13. Demo perform_demo (1381) ignores the requested folder and synchronously reads assets/wallpapers; it never scans the user's folder or starts a job/process.
14. Demo handle returns the ordinary demo message without pending; the bundled library installs immediately, including in standalone Settings demo.
15. Minimal extension: worker specs delegate to start_feature; complete(value or caught error) only installs domain state; existing presentation supplies the success text and the host emitter retains publication/cancellation.

- Commits: flow b5b4d29, characterization 9430b33, extraction d5b9b47; base main 411cc9f, branch refactor/m7b-async-pilot. Full set ran on the final runtime tree d5b9b47; subsequent changes are docs only. No reverts or second action.
- Baseline G0 524/0/145 and focused 76/0/4; after extraction focused 85/0/0 (including existing routing contracts). Four worker N/A cases now execute. Existing assertions/frozen fixtures unchanged; rejected incomplete specs retain the old diagnostic.
- Final gates (pass/fail/skip): G0 528/0/141, G1 3/0/0, G2 4/0/0, G3 53/0/0, G4 34/0/0, G6 polling 1/0/0. G0's 141 baseline skips remain (129 opt-in/session, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 fake-niri); qmllint 148 files, 0 errors/71 existing warnings.
- Sanity ONCE, 10 launches/path/arm, private software-rendered Sway/D-Bus, fresh XDG/processes, warm OS cache: preview median main/head 806.17/809.12 ms; Settings 854.65/843.70 ms. RSS at T+10 s KiB main/head: preview QS 280072/280332, backend 25944/25956; Settings QS 231112/231100, backend 25888/25936. No +100 ms/+10% flag; no profiling/CIs/raw logs committed.
- Extension proven: ActionSpec('wallpaperScan', {'shell','settings'}, scan, demo, execution='worker', complete=complete, presentation='Wallpaper library refreshed'); only installs state on completion. Explicit binding retires with descriptor backend ownership/fallback parity; direct perform/invoke_live facade at zero direct callers plus owner approval; scheduler/emitter remain shared infrastructure.
- Behavior differences: none on exercised paths. 30/89 IDs registered (29 sync + this worker); perform 233→231, perform_demo 139→136, finish_features 34→35 lines. Other legacy handler bodies are byte-identical (53 live/40 demo/9 completion); start_feature, snapshot/feature_snapshot and main lifecycle ASTs unchanged. No queue/timer/executor, polling/cache/power, public JSON/CLI or persisted-format changes.
- Assessment: the same extension fits 9 more IDs without a new registry phase: wallpaperStatus, wallpaperEnsure, imageAnnotate, recordStop, wifiScan/wifiConnect/wifiSaved/wifiDisconnect/wifiForget. Recommend wallpaperStatus/Ensure next only with owner authorization and their own characterization; none converted here.
- Remaining 19 need more: fileSearch (replacement/cancellation); palettePreview (preflight/options snapshot); captureExport/captureAnnotate/captureOcr (tokens/leases); recordStart/lock (preflight); wallpaper/wallpaperNext/wallpaperResetOutput, gowallThemes/gowallGenerate/gowallSave/gowallApply, batterySaver (group admission/guards); chargeMode and weatherSearch/weatherDetect/weatherRefresh (separate executor/controller contracts). Conditional suspend/internal wallpaperCycle are outside the 28-ID inventory.
- Laptop checklist (needs real-session check):
  1. Open Wallpaper Settings from Gear/CLI/search; confirm the current library and controls render.
  2. Rescan a real folder; confirm Scanning → sorted image list with the expected folder and no stuck pending.
  3. Try a missing folder, then rescan a valid one and restart Settings; confirm the error clears, no stuck pending and no settings/history loss.

## Development skills and async follow-up plan — 2026-10-23

- Branch chore/modularity-skill, base main 16de00e (M7b merged); docs/skills only, no new async action authorized or converted.
- Added repo-local Modularity + Ponytail guidance; pinned vladikk/modularity bcdca9a595764b9aa88d5d8d6020f52e7f5f1f52 with provenance and CC BY-NC-SA 4.0 documentation license. Seven upstream files are byte-identical; runtime licensing unchanged.
- Local adapter overrides upstream approval/report ceremony; use cohesive boundaries, narrow shared contracts and the smallest complete change. No plugin installer or runtime dependency/service added.
- Aggregate memory target: <=400 MB steady / <=500 MB ordinary active use, including Settings/backend/workers; prefer PSS and label RSS shared-memory limits and temporary-job peaks. No new profiling or memory-saving claim.
- ASYNC_ACTIONS.md records all 28 remaining async IDs and proposed batches. Correction to M7b: imageAnnotate captures the editor before enqueue, so eight (not nine) fit the worker hook directly; twenty need additional contracts. Wallpaper status/ensure are the recommended next pair, not implemented.
- Verification: G0 528 passed / 0 failed / 141 skipped; qmllint 148 files, 0 errors / 71 existing warnings; integrity/local links, line caps and diff checks passed. Existing assertions/fixtures unchanged.
- G0 skips remain 129 opt-in session/UI, 5 BlueZ, 5 MPRIS, 1 Matugen and 1 detached fake-niri. No skipped case is called passed.
- GUI gates and runtime launch/RSS sanity not run: docs/skills-only scope, zero runtime/config/test changes; this limited check policy is recorded explicitly in STATE/AGENTS. No raw gate logs committed.
- Adapters/retirement: existing runtime adapters unchanged; the local skill adapter remains while LME uses the upstream references and owner-specific workflow. STATE now records M7b merged.
- Behavior differences: none; no measured whole-shell memory result or laptop/hardware guarantee. No merge/main push performed.

## M7c — Wallpaper daemon worker pair — 2026-10-23

- Branch refactor/m7c-wallpaper-daemon, base main 7d56552; tests 483ba0d, extraction 27d05a7. Final full gates ran on runtime head 27d05a7; later changes are documentation only. No reverts or additional action conversions.
- Registered wallpaperStatus/wallpaperEnsure (32/89 IDs: 29 sync + 3 workers). Existing wallpaper_actions module/explicit composition list, narrow available/run/ready/install callbacks; no registry extension or new executor/queue/timer/process.
- Removed both live/demo legacy branches, Settings legacy admission IDs and status completion branch; scheduler, result/sequence/pending/snapshot and daemon lifecycle remain authoritative in the host/controller.
- Preserve status RuntimeError as a successful unavailable-daemon report with its full error field; other caught errors leave old state intact and truncate result text as before. Ensure only waits for existing readiness and installs no completion state. Demo is command/job/write-free.
- Characterization on unmodified production: new cases 7/0/1 N/A; focused suites 97/0/2; G0 535/0/142. Initial uncommitted fixture prototype used the wrong ManualExecutor.complete API; corrected before baseline, without production changes.
- After extraction focused suites 98/0/1; the worker ownership N/A now executes. Final gates pass/fail/skip: G0 536/0/141; G1 3/0/0; G2 4/0/0; G3 53/0/0; G4 34/0/0; G6 polling 1/0/0. qmllint 148 files, 0 errors/71 existing warnings.
- G0 skips unchanged: 129 opt-in session/UI, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 detached fake-niri. Focused skip is the same detached display opt-in. No skipped case is called passed; laptop/real daemon checks remain below.
- Owner-approved test data diff: `('wallpaperStatus', 'wallpaperUnknown')` → `('wallpaperNext', 'wallpaperUnknown')` in action_registry_workers.py. All existing assertion ASTs/timeouts and frozen fixtures unchanged; no QML change.
- perform 231→221, perform_demo 136→135, finish_features 35→34 lines; backend nonblank ceiling ratcheted 1849→1841. Dependency/cycle/size checks pass; wallpaper.py and backend_actions.py are unchanged.
- Sanity ONCE: 10 fresh-process/fresh-XDG launches per path/arm, private software-rendered Sway/D-Bus, warm OS cache, mapped-window endpoint. Preview median main/head 795.22/799.50 ms; Settings 834.50/825.55 ms. No profiling/CIs/raw evidence committed.
- RSS T+10 s KiB main/head: preview QS 279880/281492, backend 25960/25968; Settings QS 230876/231000, backend 25952/25896. Largest increase 0.576%; no Settings +100 ms/process RSS +10% flag.
- Existing T+10 s sample also sums PSS of each launch's two owned processes: preview 287785/289405 KiB main/head; Settings 238817/238885 KiB. These separate private instances do not prove total live-shell + open Settings/workers memory or hardware rendering performance.
- Adapters: explicit provider bindings retire with descriptor backend ownership/withdrawal/fault parity; direct perform/perform_demo facades require zero direct callers plus owner-approved retirement. WallpaperScanCapabilities/provide remain compatible; shared scheduler/emitter stay.
- Behavior differences: none on exercised paths. No public IPC/CLI/data/schema, cadence/cache/power or visual change. Remaining async: six simple candidates (Wi-Fi five + recordStop), twenty with extra contracts; further conversion needs authorization.
- Laptop checklist (needs real-session check):
  1. Open Wallpaper Settings; Check daemon reports the existing awww state/query and clears pending.
  2. Start if needed with awww stopped/running; confirm readiness or the existing useful error, then retry.
  3. Check daemon from the shell and standalone Settings; preview/demo must start no daemon and leave saved settings/wallpapers unchanged.

## M7d — Wi-Fi worker provider — 2026-10-23

- Branch refactor/m7d-wifi-actions, base main 130600b; characterization 97ef647; extraction ef4434e reverted e46d9e6; fixture-only repair 18d7f86; identical extraction reapplied as 2afc0b1. Later changes are documentation only.
- Registered wifiScan/wifiConnect/wifiSaved/wifiDisconnect/wifiForget: 37/89 IDs (29 sync + 8 workers). Discovery remains the M6 explicit composition list; network/run/demo_network callbacks only, never DesktopBackend. No registry extension/executor/queue/timer/process added.
- Moved both legacy dispatch branches and command logic to wifi_actions.py; wifi_action remains a synchronous compatibility facade. Shell-only admission still precedes demo/live; validation/current-adapter lookup still occurs inside the existing worker, not at enqueue.
- Host keeps network parsing, sampling/subscription/caches, completion/result/sequence/ack/pending and snapshot projection; generic completion hook installs no state. Commands/argv/timeouts/messages, stdin-only password handling and demo no-op/state/no-I/O behavior remain identical.
- Characterization on unmodified production: nine new cases pass, one registry N/A; focused 102/0/2; G0 545/0/142. After extraction/retry focused 103/0/1 (only detached fake-niri opt-in skipped); ownership N/A now executes.
- Initial full G0 was 545/1/141: LiquidThemeCase.test_liquid_pauses_only_global_blur_and_preserves_the_saved_preference printed two identical all-true results. Its repeating fixture timer did not stop after readiness; finish/Qt.quit does not prevent another emission. This failure is not counted as passed.
- Classification: test-fixture race, unrelated to Wi-Fi. Main case passed 5/5 individually; a timer-driven double-finish probe on main reproduced the exact len=2 assertion without importing product features. Reverted extraction before repair; stopped only that fixture timer after readiness; assertions/timeouts/size ceiling unchanged. Fixed fixture passed 5/5 on baseline before re-extraction.
- Existing assertion ASTs and frozen fixtures unchanged; no product QML change. The moved command body is AST-identical after capability binding; network/handle/start_feature/finish_features/snapshot/main lifecycle remain unchanged.
- Final full gates on runtime head 2afc0b1 (pass/fail/skip): G0 546/0/141; G1 3/0/0; G2 4/0/0; G3 53/0/0; G4 34/0/0; G6 polling 1/0/0. qmllint 148 files, 0 errors/71 existing warnings. Temporary execution transport disconnect preserved files/processes; completed gate artifacts and exit status were checked after reconnect.
- G0 skips unchanged: 129 opt-in session/UI, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 detached fake-niri. No skipped case or the initial failing run is reported as passed. No raw gate logs committed.
- Sanity ONCE: 10 fresh-process/fresh-XDG launches per path/arm, private software-rendered Sway/D-Bus, warm OS cache, mapped-window endpoint. Preview median main/head 788.09/777.97 ms; Settings 798.79/820.28 ms; no profiling/CIs/raw samples committed.
- RSS T+10 s KiB main/head: preview QS 279616/280116, backend 25968/25832; Settings QS 231552/231280, backend 25924/25800. Largest increase 0.179%; Settings +21.49 ms; no +100 ms/+10% flag.
- PSS of each separate launch's two owned processes, KiB main/head: preview 287527/287893; Settings 239465/239067. This existing sanity sample does not establish total live-shell + open Settings/workers memory or real hardware performance.
- perform 221→219, perform_demo 135→131, wifi_action 32→2 lines; backend nonblank ceiling 1841→1809. Added Wi-Fi source ownership, no new dependency exceptions; all new source files <250 nonblank lines.
- Adapters: explicit provider binding retires with descriptor ownership/withdrawal/fault parity; wifi_action and direct perform/perform_demo facades require zero callers plus owner-approved retirement. Host network reader remains authoritative; this milestone does not redesign its lifecycle.
- Behavior differences: none on exercised user paths; only the test fixture stops repeating after readiness. No public API/IPC/CLI/settings format, visuals, polling/cache/power-policy changes. Remaining async: recordStop plus twenty needing extra contracts; further conversion needs authorization.
- Laptop checklist (needs real-session check):
  1. Open Wi-Fi from the bar/Control Center; rescan, connect with a password, disconnect, reconnect a saved network, then forget a disposable saved network.
  2. Try an incorrect password and a stale/disconnected adapter; confirm useful errors, no secret in notifications/logs and no stuck pending; close/reopen the panel.
  3. Switch/reconnect adapters, then restart the shell; confirm summary/read-back and saved networks. Preview/demo must make no network change; standalone Settings still denies these actions.

## Wi-Fi authentication feedback and ported-feature review — 2026-10-23

- Branch fix/wifi-auth-feedback, base merged M7d main a963481; tests 4ce404c/2b9aade, backend 9f82891, UI 4041470. Final documentation is a separate commit; no further action migration or main merge.
- Owner authorized feature fixes/QoLs on 2026-10-23; STATE/AGENTS/Modularity now distinguish these from behavior-preserving refactors. Public JSON/IPC/settings/schema, registry contexts/ack/sequence/pending, worker ownership and polling/cache/power policies stay unchanged.
- Characterization: the old runner's ignored repeated prompt is reproduced with a fake process; baseline initial contract run 1 pass/6 N/A, expanded run 1 pass/8 N/A. Two new native regressions fail as expected against unmodified main UI (closed error dialog; stale-adapter submit). A late-activation cleanup regression also failed before its guard was completed.
- Implementation: optional cumulative-output observer reuses the runner's existing loop/teardown. Domain-owned nmcli --pretty parsing rejects repeated/empty password prompts, caps authentication at 15 s and preserves 45 s nmcli/50 s runner budget for IP configuration. Bounded state queries cover missing progress/late ActiveConnection paths; cleanup skips changed paths, DHCP/success and unavailable state.
- Known fresh WPA/WPA2 PSKs validate 8–63 bytes or 64 hex digits; SAE/WEP/unknown/saved-profile validation remains with NM. Passwords remain literal stdin-only memfd input with existing redaction, never command argv/disk/log fields.
- Dialog keeps selection on failure, displays an inline retry error, immediately clears submitted secrets, closes on success, disables duplicate/stale-adapter submission and handles backend loss/hidden panels. Closing a pending dialog lets the existing attempt continue; no new cancellation API is implied.
- Only approved existing expectations changed: two --pretty/observe expected-call cases and one password-boundary kwargs case in test_wifi_actions (plus ANY import). All other existing assertion ASTs and frozen fixtures are unchanged. New tests may be N/A on baseline, never counted as passed.
- Focused final: 106 pass/0 fail/1 skip (detached fake-niri opt-in). Authentication cases 10/0/0; native Wi-Fi 2/0/0, copied checkouts/fake backend/private Sway/D-Bus, including error/retry, saved profile, fast result, backend loss, changed adapter, close/reopen and secret clearing. No physical radio exercised.
- Affected prototype gates: G0 555/0/143 and G1 3/0/0; final full set ONCE on runtime head 4041470: G0 556/0/143, G1 3/0/0, G2 4/0/0, G3 53/0/0, G4 34/0/0, G6 polling 1/0/0. qmllint 148 files, 0 errors/71 existing warnings. Ratchet/dependency checks pass; no new exceptions or source moves.
- Compared with merged M7d G0 546/0/141, +10 authentication units execute and +2 native Wi-Fi opt-ins skip by default (both executed separately). G0 skips: 131 session/UI opt-ins, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 detached fake-niri; no skipped case is called passed. No raw logs committed.
- Sanity ONCE: 10 fresh-process/fresh-XDG launches per path/arm, private software-rendered Sway/D-Bus, warm OS cache, mapped-window endpoint. Preview median main/head 872.59/860.86 ms; Settings 936.36/935.73 ms (−0.63 ms); no +100 ms flag. No CIs/profiling/raw samples committed.
- T+10 s RSS KiB main/head: preview QS 279324/278836, backend 25852/25856; Settings QS 230468/231020, backend 25812/25816. Largest increase 0.240%, no +10% flag. Memory collection alone was repeated after the scratch helper missed thread-spawned backend children; startup medians were not repeated.
- PSS for each separate launch’s QS/backend pair, KiB main/head: preview 287086/286602; Settings 238242/237401. These are not combined live shell + open Settings/workers totals and do not establish the 400–500 MB whole-shell target or hardware GPU performance.
- Adapters unchanged: wifi_action/direct dispatch facades retire only at zero callers plus owner approval; explicit providers retire with descriptor ownership/withdrawal/fault parity; shared scheduler/emitter and public runner facades remain. The optional observer defaults off; it is shared infrastructure, not a second domain scheduler.
- Review: PORTED_FEATURES_REVIEW.md records five findings and fixes, including mocked reproductions of sync Bluetooth blocking, notification memory-before-write, and export failure/retry. Next prioritize those, then adapter-scoped Wi-Fi admission; only afterward plan recordStop. No other reported finding is silently fixed here; no RAM saving is claimed.
- Laptop checklist (needs real-session check):
  1. Rescan; try a wrong then correct password in the same dialog; verify useful early feedback, no stuck pending, and successful saved-network reconnect.
  2. Close while connecting; reopen; test adapter removal/radio off and a slower DHCP network. Confirm no unexpected disconnect of an already successful or different connection.
  3. Restart the shell; confirm normal Wi-Fi summary/controls and that preview/demo makes no network change; inspect notifications/logs for accidental secret exposure.

## Device-action reliability QoLs — 2026-10-23

- Branch fix/device-action-reliability, base merged Wi-Fi feedback main ace2744. Runtime commits ec09774 (Bluetooth), d7bfd6f (persistence), 3e167ad (Wi-Fi); separate characterization/regression commits and final docs. No new action ID or registry extension: 37/89 registered, 28 sync + 9 workers.
- Unmodified production: 90 existing relevant tests pass; initial new suite 5 pass/6 expected regression failures/3 worker N/A. The additional export portability tests also expose failure/retry behavior before implementation. These expected failures/N/A are not counted as passing gates.
- Test fixture 22372ab omitted a Bluetooth batteries field and made its command mock reject snapshot readbacks. Reverted as 80bd822; corrected characterization ce3ab92 reran on unchanged production before implementation. Export follow-up coverage c4202cb; no product fix-forward commit.
- Owner approved DEVICE_QOL_TEST_REVIEW.md: existing Bluetooth tests observe final worker results; the old sync golden normalizes only Bluetooth result sequence, while new tests assert real ack/completion sequences. Wi-Fi concurrency/shutdown tests expect Scan + one mutation. No timeout increases or frozen JSON changes. Extracted the unchanged BlueZ test fixture to keep the existing file under its cap.
- Bluetooth Connect/Disconnect uses the existing worker spec/pool, not the coordinator. Context/demo, command argv/15 s command limit, errors and snapshot fields stay; live validation/errors now follow the initial pending ack. Completion invalidates Bluetooth read-back on success/error, including caches refilled midflight. Power toggle/pairing retain their paths.
- Notification history now installs in backend memory only after atomic persistence succeeds. Failed replace/fsync preserves old memory/file and permits retry; QML history/debounce and Preferences lock/reload/merge/token/fsync/replace/backup remain unchanged.
- Export stages a private file, flushes/fsyncs, and publishes without overwrite. Failed writes clean the stage; EEXIST text/filename, JSON bytes and 0600 remain. No-hardlink filesystems retain exclusive direct-write fallback with owned-inode cleanup; fallback preserves the old partial-visibility window rather than claiming atomic publication.
- Wi-Fi rejects competing connect/saved/disconnect/forget/radio changes against the existing job table before network I/O/enqueue. The current selected-adapter controller is conservatively serialized, including global profile/radio writes and direct wifi_action; Scan stays independent. Finished-but-unpublished jobs keep ownership. No second job table/executor/queue/timer or sampling/TTL/power-policy change.
- Relevant units after each change: Bluetooth 83/0/0; persistence 76/0/3 (personalization UI opt-ins); Wi-Fi/backend/polling 97/0/1 (detached fake-niri opt-in). All 16 new cases execute successfully in final discovery.
- Full set ONCE on final runtime head 3e167ad: G0 572/0/143, G1 3/0/0, G2 4/0/0, G3 52/1/0, G4 32/2/0, G6 polling 1/0/0. Unchanged-head fresh-session recheck: G3 53/0/0, G4 34/0/0; initial failures remain recorded. qmllint 148 files, 0 errors/71 existing warnings.
- G0 skips unchanged from main: 131 session/UI opt-ins, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 detached fake-niri. +16 executed tests, no new skips; no skipped/failed case is called passed and no raw logs/evidence are committed.
- Initial native flakes were not reported green: UpgradeInterfaceCase.test_settings_launcher_wifi_notifications_and_responsive_cards timed out in recordingFormat IPC/termination; G4's live screenshot-toast and independent-editor checks timed out. On unchanged main the same UI test missed virtual typing (empty niriConfigPath submitted), while both capture checks passed. QML, handle/perform_demo/demo_snapshot are unchanged; this supports a private-session fixture/input/IPC flake, with the precise stall cause unverified. No assertion/timeout workaround or product change was applied for it.
- Sanity ONCE: 10 fresh-process/fresh-XDG launches per path/arm, private software-rendered Sway/D-Bus, warm OS cache, mapped-window endpoint. Preview median main/head 1766.92/1732.21 ms; Settings 1917.29/2005.43 ms (+88.14 ms), below the +100 ms stop flag. No startup optimization/profiling/CIs/raw samples.
- T+10 s RSS KiB main/head: preview QS 279060/279376, backend 25852/25832; Settings QS 231340/230960, backend 25828/25808. Largest increase 0.113%, below +10%. Thread-aware process discovery includes each owned backend.
- PSS of each separate QS/backend pair, KiB main/head: preview 286818/287112; Settings 239126/238726. These are not combined live-shell + open Settings/worker totals and do not establish the 400–500 MB whole-shell target or physical GPU/device behavior.
- Adapters: AudioCapabilities keeps its five-argument constructor via an optional invalidation callback; public CLI/IPC/import/data/schema facades remain. Explicit providers and wifi_action retain their existing retirement conditions (descriptor ownership/withdrawal parity; zero direct callers + owner approval). Host owns job/result/sequence/completion lifecycle. The sync-golden sequence adapter retires only with an owner-approved replacement of that historical golden.
- Dependency/size checks pass, no new exception/cycle/file moves; backend cap 1809→1806, polling test cap 320→313. Preference ownership remains 66 descriptor/81 legacy. No appearance change, new persistent service or claimed RAM saving.
- Updated PORTED_FEATURES_REVIEW.md marks its first four findings addressed; Launchpad log limits remain a separate follow-up. No further action migration started.
- Laptop checklist (needs real-session check):
  1. Connect/disconnect a paired Bluetooth device; adjust volume/open another panel while waiting; try an unavailable device and retry.
  2. Connect Wi-Fi or a saved profile; conflicting radio/profile operations must reject without stealing the active job. Scan, retry after failure and close/reopen must work.
  3. Export to a new path, then the same path; verify no overwrite. Test a disposable unwritable destination and retry after restoring access; include removable storage if used.
  4. Send a notification and restart the shell; confirm history restores. Preview/demo must make no real device changes; check normal Settings/import still works.

## Ported-feature optimization plan — 2026-10-23

- Branch docs/ported-feature-optimization-plan, base merged main 92c74d6 (PR21 included). Documentation only; no runtime/test/assertion/fixture changes or further migration.
- NEXT_OPTIMIZATION_PLAN.md reviews the 37 registered actions, Clipboard transport, Notifications persistence and Desktop/media seams; records source confidence, proposed owners, tests, risks and a small implementation sequence.
- Bounded scratch reproduction: a real Clipboard worker receives copy + search in one pipe write but publishes only search sequence 2; UI copyPending requires the missing copy outcome. No real clipboard capture/session used.
- Actual fake-device backend/ManualExecutor trace plus the QML reducer demonstrates duplicate rejection clearing UI pending while the original Bluetooth job still exists. Ordinary buttons already guard duplicates; no normal mouse-only reproduction claimed.
- Finite fake producers confirm Launchpad logs retain 5,242,880 bytes and CommandRunner retains 8,388,608 characters without an output bound. No disk exhaustion, RAM leak or performance saving claimed. Notification save-error recovery is source-verified, not native-UI verified.
- References pin inspected DMS, Noctalia, end4-pC, Caelestia and Serpantinum commits; compare adoption costs/limitations with Python subprocess, Qt Quick, notification protocol and Balanced Coupling theory. No third-party runtime code copied.
- Proposed order: Clipboard result delivery + Notification recovery; then approved pending-ownership contract; bounded command capture/conditional detached logs; only afterward consider recordStop migration. No new milestone authorized.
- Public snapshot ownership metadata and detached log retention/process cost require review before implementation. Do not add a broad duplicate-action guard, kill detached jobs, silently truncate successful JSON or infer GPU gains from another shell.
- G0 ONCE in disposable XDG/private Sway/D-Bus: 572 pass / 0 fail / 143 skip (715 total), unchanged from merged main; 105.649 s. qmllint 148 files, 0 errors / 71 existing warnings.
- Skips unchanged: 131 opt-in session/UI, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 detached fake-niri. They are not reported passed; GUI gates/sanity are intentionally not run for this docs-only branch. No raw logs/evidence committed.
- STATE records PR21 as merged and links the next plan; the earlier review links forward. Adapters and their retirement conditions are unchanged; 66 descriptor / 81 legacy schema keys remain.
- Behavior differences: none, documentation only. D1 closed; A6 untouched; no startup profiling, cache/polling/power changes or new dependency exceptions.
- Real-session device/GPU checks and aggregate shell + Settings/worker memory remain unverified. The plan retains <=400 MB steady / <=500 MB ordinary active targets without deriving a combined total from separate PID-pair samples.

## Content result recovery — F1/F2 — 2026-10-23

- Branch fix/content-result-recovery, based on the owner's plan 50194c1 over merged main 92c74d6. First planned review boundary only; F3–F5 and recordStop remain subsequent branches.
- Commits: a14e571 tests / 59da4a2 Clipboard; 6b02acd notification fixture reverted as 652b2a6, corrected as 9c42ea5; 68aa6cd Notification recovery; 9b5d333 worker-restart regression; final documentation separately.
- Baseline: 12 existing Clipboard units passed; new burst tests had 2 passing / 2 failing cases (5 failure records including subtests). Copied-checkout burst UI and restart probes failed on unchanged main. Exploratory baseline G0 was red with those new regressions (5 failure records / 144 skips), not a passing gate.
- Three Notification recovery tests failed before its implementation. The initial post-fix fixture had 2 pass / 1 fail: opening the center also marks history read and could leave an earlier save in flight. Reverted the test commit, waited for center initialization/save before injecting the fault, re-characterized, then reapplied the same runtime patch. Assertion ASTs/timeouts unchanged.
- Clipboard publishes each command result even when requests share a read; idle revision/config checks retain .25/1 s intervals and unchanged-history serialization suppression. JSON fields, sequences, bounds, capture ownership and worker policies stay. No snapshot queue retained.
- Clipboard waits for all outstanding searches before emitting the latest search outcome/Enter activation. Worker exit clears pending counters and old result identity so reused sequence 1 is accepted after restart. Closed/reopened panels and image annotation retain their existing routes.
- Notifications owns only revision counters and a save-error string: one save in flight, latest dirty history coalesced through the existing 500 ms debounce. Success clears only the submitted revision; errors retain dirty state, show Retry in the center, and retry on a new change/backend reconnect. No recursive error notification or periodic retry loop.
- Behavior differences are the intended fixes above. Disk format, schema, Settings lock/merge/backup/fsync/atomic replace, permissions, transient/DND/mute/expiry policy and public IPC/CLI stay. Full shell exit before a successful retry can still lose unsaved in-memory history; user docs explain this limit.
- Affected F1 gates: G0 576/0/144, G1 3/0/0; focused final units 25/0/0. Final targeted native set 8/0/0: five new recovery cases plus existing live history/mute/DND/reload, withdrawal and appearance cases; all disposable copied checkouts/private Sway/D-Bus.
- Full set ONCE on final runtime/test head 9b5d333 (pass/fail/skip): G0 576/0/148; G1 3/0/0; G2 4/0/0; G3 53/0/0; G4 34/0/0; G6 polling 1/0/0. qmllint 148 files, 0 errors / 71 existing warnings. No failing or skipped gate called passed.
- G0 skips: 136 opt-in session/UI, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 detached fake-niri. Versus recorded main, +4 executed units and +5 UI opt-ins (2 Clipboard, 3 Notification); all five new UI cases executed separately above. No existing assertions or frozen fixtures changed.
- One completed sanity comparison: ten fresh-process/fresh-XDG preview and Settings launches per main/head, private software-rendered Sway/D-Bus, warm OS cache, mapped-window endpoint. Preview medians 758.99/754.48 ms; Settings 889.68/844.27 ms (−45.41 ms). No startup optimization/CIs/raw samples committed.
- The first sanity attempt aborted before any valid comparison: descendant-only enumeration found no backend for its memory sample. The completed run identifies owned backends by exact disposable XDG_CONFIG_HOME and samples at T+10 s; it is not an above-threshold product result being retried.
- RSS KiB main/head: preview QS 279324/281356, backend 25892/25900; Settings QS 230848/231128, backend 25856/25860. Largest increase 0.727%; no +100 ms/+10% stop flag. Separate pair PSS KiB: preview 287117/289149, Settings 238655/238939; not a combined live-shell/Settings/worker total or hardware GPU evidence.
- Adapters/retirement conditions unchanged: Clipboard/content import facades, catalog bootstrap, public dispatch and schema facades remain. NotificationSave still uses the same backend/storage path; no new process, executor, dependency exception or file move. Registered actions remain 37/89; schema 66 descriptor/81 legacy.
- STATE/plan and Clipboard/Notification docs updated. No further action migration, A6 polling/cache/power changes or main merge. Hardware/device/rendering and aggregate real-session memory: needs real-session check.
- Laptop checklist:
  1. Super+V: type rapidly, press Enter, reopen, copy text/image and check image-click annotation; verify no stuck Copy/Search state.
  2. Send notifications, use DND/mute, open history and restart the shell; confirm history and settings restore.
  3. If a history storage error occurs, fix storage access and use Retry before quitting; confirm the message clears and history survives restart.

## F3 pending ownership plan — 2026-10-23

- Branch docs/f3-pending-ownership-plan, based on merged main f28be3d (F1/F2, PR22). Documentation only; no runtime/test/assertion/fixture changes.
- F3_PENDING_OWNERSHIP_PLAN.md specifies the proposed clientSerial request tag and actionPending wire metadata; existing lastResult/messages/sequences and direct backend snapshot facades stay. Owner approval of the additive wire contract precedes implementation.
- Ownership comes from existing feature_jobs/charge_job after snapshot completion handling; UI combines it with latest unacknowledged sends. Covers duplicate rejection, late snapshots, synchronous bursts, fileSearch replacement, reentrancy and reconnect without a second scheduler/job table.
- Plan preserves legacy-peer fallback, domain controllers, F1/F2 recovery, public Boolean pendingActions and emit(backend). Malformed metadata after negotiation conservatively retains ownership until a valid frame/reconnect; persistent peer faults can leave busy visible. Adapter retirement requires owner-approved removal of old peers/fixtures.
- G0 ONCE, disposable XDG/private Sway/D-Bus: 576 pass / 0 fail / 148 skip (724 total), 130.781 s; qmllint 148 files, 0 errors / 71 existing warnings. Counts unchanged from F1/F2; skips are 136 opt-in session/UI, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 detached fake-niri.
- Docs-only scope: no GUI gates or launch/RSS sanity, no raw logs committed. Runtime/device/memory claims are unverified; the plan names the later native gates, normal sanity and real-session checklist.
- STATE and NEXT_OPTIMIZATION_PLAN link the review boundary. No behavior change, F4/F5, recordStop migration, D1 work, A6 change, source-ceiling increase or dependency exception.

## F3 action pending ownership — 2026-10-23

- Branch fix/action-pending-ownership, base merged main bc5768c (PR22/24); owner approved clientSerial/actionPending. F3 only plus requested roadmap, no further action migration.
- Commits: d47ec4f initial tests, reverted d1705f9; b24cc60 corrected tests; 94a1d97 legacy Bluetooth fixture data; f516ed4 implementation; final docs separately. No original assertions/frozen fixtures changed; one new batch-test expected was corrected with owner approval (calculate is denied in Settings).
- Unmodified-production characterization: 34 pass / 0 fail / 8 N/A (new wire/reducer cases unavailable). Native baseline: legacy case passes, two tests reproduce three failure records (duplicate, delayed frame, reentrancy), restart wire case N/A. Early pre-commit fake-device/ack fixture setup errors were corrected before the test commit.
- Initial post-change checks exposed two test-fixture defects: Settings calculate expected success, and Qt.quit before the engine connected its quit receiver. Reverted the test commit, corrected expected/fixture scheduling without timeout changes, re-characterized, then restored the implementation draft.
- G0 initially 585/1/152: existing Bluetooth status fixture manually set busy without corresponding ownership. Added only simulated ownership frame data; assertions AST unchanged and the fixture passes on unmodified main and F3. No product behavior was changed to accommodate it; G1 was 3/0/0.
- Backend: optional safe-integer clientSerial advances an acknowledgement watermark even for rejected attempts. emit(backend) appends actionPending from existing feature_jobs/charge_job AFTER snapshot completion. Small stdlib transport helper; no second scheduler/table/executor. lastResult/messages/sequences and direct snapshot/dispatch facades unchanged.
- UI: pendingActions is the Boolean union of existing owners and latest unacknowledged sends. Publish ownership before snapshot/readiness/result callbacks; write a new request before notifying pending consumers. Duplicate errors, stale frames and reentrant sends cannot steal another owner's busy flag; restart clears transport state without mutation replay.
- Legacy peers keep result-based fallback. After negotiation, malformed/missing/regressing ownership preserves the last valid state with a warning until recovery/reconnect. A persistently broken peer may retain busy; no guessed timeout or replay. Weather/capture/detached-job controllers keep their own lifecycle.
- Focused checks: 81/0/0; copied-checkout native F3 + F1/F2 recovery: 9/0/0. Final full set ONCE on runtime/test head f516ed4 (pass/fail/skip): G0 586/0/152; G1 3/0/0; G2 4/0/0; G3 53/0/0; G4 34/0/0; G6 polling 1/0/0. qmllint 148 files, 0 errors / 71 existing warnings.
- G0 versus recorded main: +10 executed units, +4 native opt-ins skipped by default. Skips: 140 session/UI opt-ins, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 detached fake-niri. Four new native cases ran separately above. Temporary execution transport disconnected/recovered during full gates; the same live session completed, no restart or substituted gate result.
- Sanity ONCE: 10 fresh-process/fresh-XDG launches per path/arm, private software-rendered Sway/D-Bus, warm OS cache, mapped-window endpoint. Preview median main/head 847.15/824.29 ms; Settings 907.20/873.49 ms. No +100 ms stop flag; no profiling/CIs/raw samples committed.
- T+10 s RSS KiB main/head: preview QS 279880/280880, backend 25876/25868; Settings QS 231092/231152, backend 25832/25820. Largest increase 0.357%, below +10%. Owned backend identified by exact disposable XDG_CONFIG_HOME.
- Separate pair PSS KiB main/head: preview 287665/288651; Settings 238869/238917. These do not establish combined main shell + Settings/workers memory or hardware GPU/device behavior; needs real-session check. No RAM saving claimed.
- Adapter retirement: old-peer result-based reducer only at zero legacy consumers/fixtures plus owner approval. pendingActions and emit/handle/snapshot stay public facades; prior registry/schema/import adapter conditions remain. Backend remains 1806 nonblank lines, ShellState 246; no new dependency exception/cycle or file moves.
- Intended behavior difference: busy remains accurate until acknowledged/complete or backend exit. Preferences AST, start_feature/finish_features/finish_charge and live/demo routing AST unchanged; settings/history formats, worker ownership, error text, polling/cache/power/visual policy unchanged. Counts remain 37/89 actions and 66 descriptor/81 legacy preference keys.
- ROADMAP.md describes coverage and release criteria: F3 review → proposed F5 output bounds → conditional F4 detached logs → separately authorized lifecycle migrations; core legacy pages and optional M8 stay deferred. README/STATE/architecture/plan updated; no future boundary started.
- Laptop checklist (needs real-session check):
  1. Connect/retry Bluetooth while adjusting volume; close/reopen Devices and confirm busy lasts until completion/error.
  2. Try Wi-Fi failure then retry, including close/reopen; other controls must stay responsive and pending must clear correctly.
  3. Type file searches rapidly; replacing a search must finish with the latest query and no stuck Searching state.
  4. If supported, apply/cancel a charge request; toggle battery saver off again and check restored settings/display mode.
  5. Restart shell/Settings; change a setting and check Clipboard copy/search plus Notification save/Retry recovery.

## Resource bounds and async contracts — 2026-10-24

- Branch fix/resource-bounds-and-async-contracts, main 03e7006; plan committed first as 22047c2. F5/F4 plus the owner's 21-action lifecycle batch; no later boundary, A6 or D1 work.
- Tests/implementation: F5 7f0fa11/8d24297; F4 09b595a/02b2916, signal regressions fe68c97/3e8430e and 0ed8127/9984a4c; async golden 6083964, recordStop 17a3253, preflight 2c6e43b, gowall/saver 7bce3fb, search 4eed0c0, capture 8936169, controllers 1ff90c8, wallpaper 0c75505; final docs separate.
- Baseline new contracts (pass/fail/N/A): F5 combined 28/1/5 (overflow reproduces); F4 combined 32/1/7 (unbounded log reproduces); async 5/0/1, including 84 golden shell/Settings x live/demo subcases. Registry prepare is N/A before its addition; golden JSON unchanged afterward.
- Reverted failed inherited-writer fixture 325eea8 via d441c5e before 09b595a; preflight a7685ac via 297703c, then privacy fixture 4222fef and identical refactor 2c6e43b; wallpaper wiring 97c1387 via 650b4e1 before 0c75505. No failures presented as passes.
- Existing assertion ASTs/timeouts and frozen fixtures unchanged. Owner-approved fe55161 changes only legacy test input wallpaperNext -> mirrorRefresh; fixture-only mocks preserve the original direct-spawn/privacy boundary. New frozen async-domains.json added.
- F5: combined output 8 MiB default, niri/busctl/pw-dump 16 MiB, nmcli 2 MiB; bounded draining, explicit overflow error even at exit 0, no successful truncated JSON. Timeout/cancel/redaction/observer/UTF-8/memfd behavior retained; teardown no longer buffers output.
- F4 intended differences: each log <=8 MiB including marker; excess discarded without SIGPIPE, private 0600/no-symlink handling. One detached event-driven relay per job, none idle; inherited writers keep a job running. Sink error yields 74 only after a successful child, preserving existing nonzero/signal exits.
- Final relay-only cost: one RSS/PSS 7,748/5,186 KiB; eight 62,032/34,447 KiB, 5 FD each. Eight-job limit remains per controller; surviving jobs can add relays after restart. No global directory quota or deletion of old logs; RESOURCE_LIMITS.md explains limits.
- Async: 17 worker specs + 4 sync entry calls into existing Weather/charge controllers; 58/89 registered (32 sync entry calls/26 workers), 31 legacy. PreparedWork captures original preflight/options/Future tags; existing scheduler, completion emitter, charge/search/capture ownership and read-back stay.
- Final full gates on runtime/test HEAD 9984a4c (pass/fail/skip): G0 612/0/152; G1 3/0/0; G2 4/0/0; G3 53/0/0; G4 34/0/0; G6 polling 1/0/0. qmllint: 148 files, 0 errors/71 existing warnings. Command: run-gates.sh --env-file /workspace/.lme-dev/env.sh --pointer-dir /workspace/.lme-dev --gates G0,G1,G2,G3,G4,G6.
- Versus recorded merged-main G0 586/0/152: +26 executed tests (F5 7, F4 13, async 6); skips unchanged: 140 opt-in session/UI, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 detached fake-niri. Native F1/F2/F3 recovery separately executed: 9/0/0 in disposable copied checkouts/private Sway/D-Bus.
- Earlier full green at 3e8430e was superseded after a direct SIGPIPE probe exposed inherited ignored signal state (99 instead of -SIGPIPE). Added failing regression, fixed exec defaults in 9984a4c, then reran the full set above because runtime changed; no stale final-head claim.
- Sanity ONCE: ten fresh-process/fresh-XDG launches per main/head path, warm OS cache, software-rendered private Sway/D-Bus, mapped-window endpoint. Preview medians 815.45/793.08 ms; Settings 832.15/827.86 ms. No +100 ms flag, no profiling/CIs/raw logs committed.
- T+10 s RSS KiB main/head: preview QS 281184/279648, backend 25876/25864; Settings QS 230640/231356, backend 25828/25824. Largest increase 0.31%; no +10% flag. Backend identity uses exact disposable XDG_CONFIG_HOME.
- Simultaneous default-Smoked VM PSS KiB main/head: steady main QS/backend/history worker (3 PIDs) 199479/199425; +Settings/backend (5 PIDs) 365589/365670; +8 relays, excluding payloads 401489/436009; including eight idle Python payloads 424964/458777 (head 21 PIDs). Branch decimal MB: 204.21 / 374.45 / 446.47 / 469.79.
- PSS counts all owned instances/workers/relays; private Sway/D-Bus/OS services excluded. Head summed RSS KiB: 210640/463784/611576 (last includes payloads), with shared pages double-counted. One virtual monitor, software OpenGL, weather auto/capture off; history worker active. No Liquid/laptop/GPU/heavy-command guarantee or RAM-saving claim.
- perform physical lines 216->123, perform_demo 131->93; desktop_backend nonblank ceiling ratchets 1806->1715. No new dependency exception/cycle/file move. Preferences AST and battery_saver/display_control/weather files unchanged; schema remains 66 descriptor/81 legacy.
- Adapters: explicit provider discovery retires only with equivalent descriptor ownership/withdrawal/fallback; PreparedWork/complete/presentation keep existing scheduler/emitter/Future tags. Charge/Weather retain controller lifecycle. Public import/dispatch/snapshot/schema facades retire at zero consumers plus owner approval; F3 legacy-peer pending fallback retains its prior condition.
- Behavior differences: intended F5/F4 resource policies above, including relay PID/lifetime/log-write status; ordinary action errors/results/sequences/snapshots preserved by golden cases. Settings/history formats, persistence/permissions, detached survival, polling/cache/power/visual policy unchanged. Roadmap and six-row RELEASE_CHECKLIST.md updated; release sign-off remains pending.
- Laptop checklist (needs real-session check):
  1. Open/reopen panels and Settings in Smoked/Liquid; verify Clipboard/image annotation and Notification history/Retry.
  2. Exercise Bluetooth and Wi-Fi failure/retry/reconnect while changing volume/brightness; check media/lyrics/widgets.
  3. Export/annotate/OCR and start/stop actual recording; close stale sessions and confirm pending clears/output survives errors.
  4. Launch argv/Bash/terminal jobs, cap a log, check exit/error/eight-job admission and survival after shell restart.
  5. Apply/confirm/revert displays, reconnect outputs, toggle battery saver off and check restored mode/theme/brightness/charge.
  6. Sum PSS for all LME instances/workers/Settings/surviving relays in real ordinary use; record theme/output/job scope and separate heavy-tool peaks before release.

## Capture entry action family — 2026-10-24

- Branch refactor/capture-entry-actions, merged main 3f9ac22 (PR26). Owner authorized the next roadmap family with planning and code on the same branch; plan 7b25dd9 precedes tests 7b718dd and refactor 41cb405. Final docs separately.
- Scope: screenshot/screenshotArea/screenshotWindow/captureClose/captureLanguages, five existing synchronous controller entries. Registry now 63/89 (37 sync entry calls/26 workers), 26 legacy; schema remains 66 descriptor/81 legacy. No async extension or second executor/process.
- Characterization on unchanged production: 6 pass/0 fail/1 registry-specific N/A. Covers 20 action/context/demo combinations, exact errors/sequences, delay/call order, live private-session reopen/close, language filtering, snapshots, demo no spawn/write and unrelated pending owners. No existing tests/assertions/fixtures changed.
- Baseline G0 with new tests: 618/0/153; after extraction 619/0/152. The pure-registration/no-fallback case is the one N/A that now executes; merged-main G0 was 612/0/152. Focused backend/registry/capture/async units: 92/0/2, with two native Capture cases skipped in the unit run and executed in G4 below.
- Runtime changes only capture_actions.py, desktop_backend.py and the lowered architecture ceiling. Four narrow controller callbacks; explicit provider composition unchanged. Both old live/demo branches removed together; no dependency exception/cycle or file move.
- Preferences, handle, start_feature/finish_features/finish_charge, snapshot/feature_snapshot and main ASTs unchanged; screen_capture.py, pending transport, registry and schema modules byte-identical. Surface-teardown delay stays .2 s; Settings rejection precedes demo/live; close retains language state and old worker ownership.
- Final full gates ONCE on runtime/test HEAD 41cb405 (pass/fail/skip): G0 619/0/152; G1 3/0/0; G2 4/0/0; G3 53/0/0; G4 34/0/0; G6 polling 1/0/0. qmllint 148 files, 0 errors/71 existing warnings. Disposable XDG/private Sway/D-Bus only; no real configuration/session touched.
- G0 skips unchanged relative merged main: 140 opt-in session/UI, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 detached fake-niri. G4 actually ran native editor close/reopen, drawing/redaction/export/real OCR, clipboard and annotation cases; hardware niri/GPU behavior still needs real-session check.
- Sanity ONCE: ten fresh-process/fresh-XDG launches per main/head and path, warm OS cache, software-rendered private Sway/D-Bus, mapped-window endpoint polled every 20 ms. Preview median main/head 686.90/688.54 ms; Settings 740.98/740.15 ms. No +100 ms flag; no profiling/CIs/raw evidence committed.
- T+10 s RSS KiB main/head: preview QS 279448/279808, backend 25880/25872; Settings QS 230908/231364, backend 25840/25824. Largest increase 0.197%, no +10% flag. Exact disposable XDG_CONFIG_HOME identifies the owned backend; separate PID samples do not establish a combined shell total.
- Memory context: reuse the preceding simultaneous default-Smoked VM totals (204 MB steady/374 MB Settings/470 MB including eight relays and idle payloads); not re-measured here and not a laptop/Liquid guarantee. This family adds no process or worker; no RAM-saving claim.
- Adapters/retirement: explicit provider bindings retire with equivalent descriptor ownership/withdrawal/fallback. Public perform/perform_demo and controller/snapshot/import/schema facades remain until zero consumers plus owner approval. No new compatibility adapter or wire/data-format change.
- perform physical lines 123->115, perform_demo 93->90; desktop_backend nonblank ceiling 1715->1706. Behavior differences: none on exercised paths. No polling/cache/power/visual changes, D1 work, log-retention change, main merge or later-family implementation.
- Laptop checklist (needs real-session check for this branch):
  1. Capture screen, area and focused window from Control Center/IPC; close/cancel and reopen, including a duplicate attempt while the studio is open.
  2. Check installed OCR languages, extract/copy text, save/copy a redacted PNG and annotate externally; close during OCR and confirm no stale text appears in a new session.
  3. Restart shell/Settings, confirm saved settings and exports remain; Settings must not start its own capture session.

## Display preview action family — 2026-10-24

- Branch refactor/display-preview-actions, merged main 201c452 (PR27). Owner authorized the next roadmap family with planning/code together; plan d81cac2 precedes characterization 1e5f39f and extraction 04ac0d6. Final docs separate.
- Five sync entries: displayRefresh/Apply/Confirm/Revert and platformRefresh. Registry now 68/89 (42 sync entry calls/26 workers), 21 legacy; schema remains 66 descriptor/81 legacy. DisplayPage and mirroring stay legacy by scope; no new executor, worker or registry feature.
- Baseline characterization: 9 pass/0 fail/1 provider-specific N/A; unchanged tests after extraction: 10/0/0. Covers 20 context/demo combinations, exact messages/sequences, snapshot/guard/call order, bad layouts/tokens/deadlines, private real-controller journals/settings, failed-save ordering, demo isolation and legacy mirrorRefresh linkage. No existing assertion/fixture edits.
- G0 before/after: 628/0/153 -> 629/0/152, with the one provider-specific N/A now executing. Merged main was 619/0/152; +10 executed units. Focused backend/display/battery-saver/registry/laptop checks: 120/0/3; skips are detached watchdog and two native idle cases, not counted passed.
- DetachedDisplayCase explicitly enabled separately in disposable XDG/private Sway/D-Bus: before 1/0/0 (20.411 s), after 1/0/0 (20.369 s). Fake niri verifies the independent watchdog restores mode after its initiating process exits; not physical output/GPU evidence.
- Full gates ONCE on final runtime/test HEAD 04ac0d6 (pass/fail/skip): G0 629/0/152; G1 3/0/0; G2 4/0/0; G3 53/0/0; G4 34/0/0; G6 polling 1/0/0. qmllint 148 files, 0 errors/71 existing warnings. No skipped or failing gate called passed.
- G0 skips unchanged from merged main: 140 opt-in session/UI, 5 BlueZ, 5 MPRIS, 1 Matugen, 1 detached fake-niri; the latter actually ran separately above. All checks use disposable config/state/runtime, private compositor/D-Bus and simulated command boundaries; no real session/config touched.
- DisplayControl/watchdog, BatterySaver, schema/pending modules and DisplayPage are byte-identical. Preferences, scheduler/completion, snapshots, main and compositor_features ASTs unchanged. handle changes only by deleting the five migrated legacy admission entries; registry admits shell/Settings before demo/live as before.
- Apply retains saver-pending rejection then guard/start, guard exit then snapshot. Confirm retains decide/journal mutation, Preferences.set then snapshot; a save error still leaves the decision first and old snapshot until refresh. Demo fixtures/deadline/permissive token behavior and live errors stay. No behavior difference on exercised paths or data-format/transaction/polling/cache/power/visual change.
- Sanity ONCE: ten fresh-process/fresh-XDG launches per main/head path, warm OS cache, software-rendered private Sway/D-Bus, mapped-window endpoint polled every 20 ms. Preview median main/head 723.77/709.80 ms; Settings 749.05/764.18 ms (+15.13 ms, below +100 ms). No stop flags or repeat tuning.
- T+10 s RSS KiB main/head: preview QS 281408/279856, backend 25868/25812; Settings QS 231220/231088, backend 25828/25772. No sample increased or crossed +10%; owned backend matched by exact disposable XDG_CONFIG_HOME. Separate PID samples do not establish combined memory or a saving.
- Memory context: prior scoped Smoked VM totals (204 MB steady/374 MB Settings/470 MB including eight relays/test payloads) are not re-measured here or a laptop/Liquid guarantee. This batch adds no processes; no RAM-saving claim or D1 profiling/CIs/raw evidence committed.
- Explicit provider bindings retire with equivalent descriptor ownership/withdrawal/fallback. Public perform/perform_demo, controller/import/snapshot/schema facades stay until zero consumers plus owner approval; legacy demo mirrorRefresh still calls perform_demo(displayRefresh). No new compatibility adapter or dependency exception/cycle/file move.
- perform physical lines 115->98, perform_demo 90->75; coordinator nonblank ceiling ratchets 1706->1681. Roadmap proposes mirroring's three IPC/child-owned actions as the next candidate; no later family, main merge, A6 or schema/UI conversion started.
- Laptop checklist (needs real-session check for this branch):
  1. Open Display settings, refresh, apply an available mode/scale and Keep changes; restart and confirm saved layout/permissions remain normal.
  2. Apply then Revert; apply again and let the timeout restore; repeat while closing Settings so the independent worker must restore.
  3. Turn Battery saver on and confirm Apply stays blocked; turn it off and check prior display mode/brightness/theme restore.
  4. Reconnect an output and refresh Display/Appearance; check supported modes/version and that failure messages leave the UI usable.
