# Agent state (2026-10-31)

Read this file at task start; consult ARCHITECTURE.md for contracts.
Do not read archive/ unless answering a specific historical question.

## Merged and authorized

- M0-M3, M4a/M4b, M5/M6, M4c-1/2/3, M7a/b/c/d, F1-F5, resource/lifecycle, Capture, Display preview, Mirroring and selection/application merged: 75/89 IDs (49 sync entry calls + 26 workers).
  Ten catalog pages; 79 descriptor keys/68 legacy; Clipboard bar converted; tab/bootstrap adapters implemented (17 catalog records, seven schema-only).
- D1 startup optimization CLOSED; further async conversions need authorization; M8 deferred.
- Release verification merged (e91ca29). Render-lifetime verification adds normal Settings shutdown and 48-cycle object/layer guards; runtime unchanged. Owner confirms main + Settings, closed 186.12 MB PSS; warmed laptop/theme/helper review pending. Software VM still exceeds budget; no proven retention fix. Opt-in laptop workload adds pinned PSS checkpoints/Gear-owned Settings; GPU/warm samples remain pending. See LAPTOP_MEMORY_WORKLOAD.md and RELEASE_CHECKLIST.md; no later migration family authorized.
- A6 remains out of scope: no polling, cache or power-policy changes.
- Development skills: Ponytail full + .agents/skills/modularity/SKILL.md; use proportionately, without extra ceremony.
- Total-shell memory target: <=400 MB steady / <=500 MB ordinary active use, including workers and open Settings.
  Prefer aggregate PSS, label summed RSS limitations and temporary-job peaks; individual PID samples are not the total.

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
- Night Light/Idle/Keybinds descriptor-provider pilot: explicit fallback factories and narrow capability bindings remain; disabled/missing entries keep actions, broken references retain legacy UI + diagnostic. Other providers stay explicit. Retire fallbacks/import facades only with equivalent fault/withdrawal coverage + owner approval. PreparedWork/complete/presentation retain the host scheduler/emitter/Future tags; Charge/Weather keep lifecycle. Public perform/perform_demo/wifi_action facades retain their zero-consumer retirement rule and cadence.
- PageNavigation forwards navigateRequested(pageId); retain old page signals until owner-approved retirement.
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
