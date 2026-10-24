# Capture entry actions: plan and execution boundary

2026-10-24. Branch `refactor/capture-entry-actions`, merged main `3f9ac22`.
The owner authorized the next roadmap family, planning and code on one branch.
Use Ponytail/Modularity; keep release hardware checks pending, D1 closed and A6
unchanged. Do not alter the six core Settings pages or move implementation files.

## Selected family

Finish the Capture provider boundary with five existing synchronous entries:
`screenshot`, `screenshotArea`, `screenshotWindow`, `captureClose`,
`captureLanguages`. The first three initiate the existing niri session; they are
not new registry workers. Export/annotation/OCR already use the provider and
the existing capture controller. This removes split ownership of the same
lifecycle, without a second abstraction or scheduler.

Defer display rollback/mirroring, settings transactions and the remaining schema
groups: each has a distinct contract and does not belong in this capture batch.
Log retention and provider discovery also remain separate decisions.

## Contracts read at the merged baseline

- `handle()` admits shell only before selecting demo/live. Settings rejects all
  five with `This action is unavailable in the settings app`.
- Live starts retain the 0.2 s surface-teardown delay, then call the existing
  ScreenCapture.start with screen/area/window respectively. Controller errors,
  private paths, repeated-session rejection and cancellation remain authoritative.
- Close calls the existing controller and returns `Screenshot closed`; languages
  calls the existing detector and returns `OCR languages refreshed`.
- Demo starts do nothing; demo close still calls close, demo languages installs
  exactly eng/vie. The common demo message and sequence stay unchanged.
- State remains in the controller; feature_snapshot exposes the same capture
  object/fields. Existing pending work and stale-token handling remain untouched.
- Unknown capture/screenshot prefixes retain their original legacy errors.

## Commit and verification sequence

1. Commit this plan before production code. Add characterization tests and show
   them passing on unchanged main: five actions x shell/Settings x live/demo,
   result sequence/error truncation, delay/call order, live session reopen/close,
   languages, unchanged ownership and unknown prefixes. No assertion edits.
2. Extend `scripts/capture_actions.py` with narrow controller capabilities; reuse
   explicit composition and ActionRegistry. Delete both old live/demo routes in
   the same extraction commit; ratchet the coordinator size ceiling downward.
3. During work run G0 plus capture/registry/backend units. Before review run
   G0-G4 and G6 polling once on the final runtime/test head, including existing
   native editor/reopen/annotation tests. Report all skips explicitly.
4. One normal sanity: ten preview/Settings launches each on main and branch,
   medians and T+10 s QS/backend RSS. Stop for >+100 ms Settings or >+10% RSS.
   Reuse the previous simultaneous whole-shell sample as context, not as a new
   laptop guarantee. No profiling/CIs/raw evidence committed.
5. Final docs: migration entry <=30 lines, current coverage/adapters, <=6 laptop
   checks. Push a review branch; owner merges. No release/hardware claims.

Adapters remain: public perform/perform_demo, existing controller and snapshot
facades, explicit provider discovery. Retire only at zero consumers with owner
approval or equivalent descriptor ownership/withdrawal/fallback as applicable.

## Execution result

Implemented on runtime/test head `41cb405`; five sync entries now use the existing
Capture provider. No controller/UI/scheduler/worker-policy changes. Characterization
passed on unchanged production code; final gates and the normal launch/RSS sanity
are summarized in MIGRATION_LOG.md. Real niri/GPU checks remain laptop work.
