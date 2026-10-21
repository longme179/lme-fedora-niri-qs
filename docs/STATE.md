# Agent state (2026-10-21)

Read this file at task start; consult ARCHITECTURE.md for contracts.
Do not read archive/ unless answering a specific historical question.

## Merged and authorized

- M0 baseline/harness; M1 runner/storage; M2 content types; G3 baseline repair;
  M3 stable control-tab IDs; M4a catalog infrastructure; M4b Clipboard slice: merged.
- D1: JSON index + descriptors accepted by the owner. Startup optimization CLOSED.
- M5: implemented on refactor/m5-settings-schema, awaiting owner review/merge.
  Ten descriptor-owned preference keys; 137 legacy. Only Clipboard UI is converted.
- M6/batch conversions need the next owner prompt. M8 moves deferred.
- A6 remains out of scope: no polling, cache or power-policy changes.

## Compatibility adapters and retirement

- Runner/errors/TOOLS, storage and Clipboard content-type re-exports: keep public
  import facades until an explicit owner-approved compatibility change.
- Integer controlTab and named LME_SHELL_CONTROL_TAB mapping: public compatibility;
  internal adapters retire only after all callers/fixtures use stable IDs.
- Hybrid registry projections, legacy lists, legacy_ids() source bridge and panel
  allowlist: retire per namespace after its final legacy registration/fixture.
- ClipboardFeature -> ClipboardState.start(): retain until equivalent bootstrap
  preserves main-only once semantics and Settings/demo/preview guards.
- ClipboardButton -> ActionBarButton: retain until an equivalent entry preserves
  geometry, gestures and screen context. No Clipboard implementation files moved.
- DEFAULT_PREFERENCES/validate_preference and PORTABLE/APPEARANCE_KEYS are schema
  facades; retain public names until explicit owner-approved compatibility changes.
- Legacy validator/default bindings (137 keys), original key-order inventory,
  BarRegistry default resolver and bundled-fragment fallback retire only after
  their last consumer/fallback contract is migrated. Worker fault policy is separate.
- Architecture exceptions/size ceilings: remove vanished edges, lower shrunken
  large-file ceilings; no new cross-feature edges or cycles.

## Gates and working rules

- `./scripts/check.sh`: architecture/catalog + unit discovery + Bash/demo checks.
- `./scripts/run-gates.sh --gates G0` isolates XDG, Sway/Wayland and D-Bus;
  optional `--env-file FILE --pointer-dir DIR`. Gate cases: tests/migration_checks.py.
- During work: Python = G0 + relevant units; QML = G0 + G1 + relevant native case.
  Full G0-G4 + G6 polling ONCE before merge review; explicit task scope overrides
  by task. Report actual pass/fail/skip counts and reasons.
- Tests first, then refactor, then docs commits. No assertion edits without asking;
  revert a failed commit, never fix forward. Keep behavior and public contracts.
- Disposable sessions only; never real config/session. Hardware: needs real-session check.
- Future branch sanity once before merge: 10 preview/Settings launches each,
  main vs head medians; QS/backend RSS at 10 s. Ask if Settings >+100 ms or RSS >+10%.
- No more D1 profiling, CIs, A/A, seeds, aggregate c or validation scheduling.
- Priorities: modularity, scalability, functionality, stability, memory footprint.
- Future family batches: 3-6 features per branch; one review stop per branch.
- Ask only for behavior/API/data-format changes, unclassifiable baseline failure,
  or sanity flags. Never start an unauthorized milestone or merge/push main.
- Replies <=40 lines; one MIGRATION entry <=30 lines, laptop checklist <=6 lines.
  Commit only final gate summaries; no raw evidence directories.
- Preserve stdlib/unprivileged backend, English text, Preferences lock/merge/atomic
  writes, preview/standalone Settings and non-destructive installers.

Historical records: archive/migration/ (moved unchanged; not required task reading).
