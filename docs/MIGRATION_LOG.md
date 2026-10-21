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
