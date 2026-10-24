# Agent state (2026-10-24)

Read this file at task start; consult ARCHITECTURE.md for contracts.
Do not read archive/ unless answering a specific historical question.

## Merged and authorized

- M0-M3, M4a/M4b, M5/M6, M4c-1/2/3, M7a/b/c/d and F1-F3 merged. Resource branch review: 58/89 IDs (32 sync entry calls + 26 workers), including the 21 listed async conversions.
  Ten catalog pages; 66 descriptor keys/81 legacy; Clipboard bar converted; tab/bootstrap adapters implemented.
- D1 startup optimization CLOSED; further async conversions need authorization; M8 deferred.
- fix/resource-bounds-and-async-contracts implements the owner's F5/F4 + async plan; see RESOURCE_LIFECYCLE_PLAN.md, RESOURCE_LIMITS.md and ROADMAP.md. Real laptop checks remain pending in RELEASE_CHECKLIST.md; no further boundary is authorized.
- A6 remains out of scope: no polling, cache or power-policy changes.
- Development skills: Ponytail full + .agents/skills/modularity/SKILL.md; use proportionately, without extra ceremony.
- Total-shell memory target: <=400 MB steady / <=500 MB ordinary active use, including workers and open Settings.
  Prefer aggregate PSS, label summed RSS limitations and temporary-job peaks; individual PID samples are not the total.

## Compatibility adapters and retirement

- Runner/errors/TOOLS, storage/content-type re-exports: keep public facades until owner-approved retirement.
- F3 legacy pending reducer retains old-peer/fixture fallback; retire only at zero legacy consumers plus owner approval. pendingActions and emit/handle/snapshot stay public facades.
- Integer controlTab/named env mapping: public compatibility; internal adapters retire after all callers/fixtures use stable IDs.
- Hybrid registry projections, legacy lists, legacy_ids() source bridge and panel
  allowlist: retire per namespace after its final legacy registration/fixture.
- ClipboardFeature -> ClipboardState.start(): retain until equivalent bootstrap
  preserves main-only once semantics and Settings/demo/preview guards.
- ClipboardButton -> ActionBarButton: retain until an equivalent entry preserves
  geometry, gestures and screen context. No Clipboard implementation files moved.
- Explicit providers retire with descriptor discovery/ownership/fallback parity; PreparedWork/complete/presentation retain the host scheduler/emitter and Future tags. Charge/Weather controllers keep their lifecycle. Public perform/perform_demo/wifi_action facades retire at zero callers + owner approval; state facades retain cadence.
- PageNavigation forwards navigateRequested(pageId); retain old page signals until owner-approved retirement.
- Notifications.start/demo readiness and legacy bar availability guards retire only with equivalent catalog composition/worker isolation; public flags/IDs stay.
- DEFAULT_PREFERENCES/validate_preference and PORTABLE/APPEARANCE_KEYS are schema
  facades; retain public names until explicit owner-approved compatibility changes.
- Legacy fragment (81 keys), validator/default bindings, inventory, bar-layout resolver
  and bundled-fragment fallback retire at their last consumer/fault contract. Worker policy is separate.
- Architecture exceptions/size ceilings: remove vanished edges, lower shrunken
  large-file ceilings; no new cross-feature edges or cycles.

## Gates and working rules

- `./scripts/check.sh`: architecture/catalog + unit discovery + Bash/demo checks.
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
- Replies <=40 lines; one MIGRATION entry <=30 lines, laptop checklist <=6 lines.
  Commit only final gate summaries; no raw evidence directories.
- Preserve stdlib/unprivileged backend, English text, Preferences lock/merge/atomic
  writes, preview/standalone Settings and non-destructive installers.
