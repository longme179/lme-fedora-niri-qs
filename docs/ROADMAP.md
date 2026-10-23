# LME Shell: position and next boundaries

2026-10-23. This is a roadmap, not authorization for another implementation.
Read STATE.md for current ownership/process rules; archive documents are history.

## Destination

A stable, extensible shell where a feature uses existing catalog/schema/service
contracts, without edits inside unrelated features. Keep handwritten Settings,
stdlib/unprivileged backend, public facades and safe persistence. Share processes,
workers and rendering resources. Prefer useful boundaries over moving every file.

Target total memory: <=400 MB steady / <=500 MB ordinary active use, counting
main Quickshell, backend, persistent workers and open Settings/backends. Prefer
aggregate PSS; label heavy temporary tools separately. Separate-instance samples
do not establish this total. Hardware/GPU/session behavior needs laptop checks.

There is no meaningful single completion percentage: a capture lease or display
rollback has greater risk than several scalar settings. Counts below measure
migration coverage, not product stability or remaining engineering effort.

## Where we are

| Area | Current coverage | What remains |
| --- | --- | --- |
| Infrastructure | Shared runner/storage/content helpers, dependency ratchet, catalog, tab IDs, schema and sync/worker registry implemented | Retain stable compatibility facades; remove an adapter only at its stated retirement condition |
| UI composition | 11 catalog records, 10 of 16 Settings pages, Clipboard bar/panel; Notifications tab and context-aware bootstraps | Six core pages and most bar/panel hosts stay legacy by owner decision; no bulk conversion implied |
| Preferences | 66 of 147 keys descriptor-owned; 81 in the single legacy schema fragment | Later small cohesive batches when they reduce real change cost; same flat settings.json and transaction protocol |
| Backend dispatch | 37 of 89 IDs registered: 28 sync + 9 workers | 52 legacy IDs; 21 have async-specific contracts, including one simple candidate and twenty needing additional seams |
| Cross-feature reliability | Wi-Fi feedback/admission, Bluetooth nonblocking dispatch, notification/export persistence and F1/F2 merged | F3 on the current review branch fixes pending ownership; F4/F5 are still proposals |
| Resource confidence | Per-branch native tests, source-size caps and launch/RSS sanity | Combined real-session shell + Settings/worker memory and physical device/GPU checks remain necessary |

M0-M3, M4a/b, M5/M6, M4c-1/2/3 and M7a/b/c/d established the reusable contracts.
We have passed the infrastructure/pilot stage and are hardening integration before
expanding migrations. F3 adds a transport contract, not another ported action.
Existing stable legacy ownership is acceptable; full conversion is not the goal.

## Proposed order after F3 review

1. **Finish this correctness boundary.** Review F3's duplicate rejection, delayed
   snapshots, reentrant callbacks and restart behavior on the laptop. Merge only
   after checks and review. F1/F2 recovery must remain covered.
2. **F5: bounded shared command capture.** Inventory valid output sizes and text/
   JSON/observer contracts first. Bound retention while draining both pipes;
   overflow must be an explicit redacted failure, never successful truncated JSON.
   Preserve timeout/cancellation/process-group and secret handling. No RAM saving
   is promised before evidence; this is an unimplemented hardening proposal.
3. **F4: detached Launchpad logging, conditional.** Approve retention/error policy
   and process cost first. An active writer cap may require a detached relay per
   job; completed-log cleanup alone is insufficient. Preserve shell-exit survival,
   terminal/argv semantics and eight-job limit. Skip if it needs a general job
   framework or an unacceptable memory/process trade-off.
4. **Resume small backend migrations only when authorized.** recordStop is the
   next candidate for the existing worker contract. Then consider request-time
   preflight/options; see ASYNC_ACTIONS.md. Group admission, replace/cancel,
   capture token/lease and separate controllers each need an explicit design.
   Battery/display-sensitive contracts go last; never port all twenty mechanically.
5. **Close modularity gaps where change cost warrants it.** Small schema families,
   descriptor provider discovery/withdrawal policy, remaining host registration
   seams and removal of obsolete dependency exceptions. Core legacy pages/bar/
   Controls/Launcher/Activity stay put until a separately approved useful scope.
   M8 physical moves are optional and last; they are not a prerequisite for release.
6. **Release confidence.** Repeat the laptop integration checklist and exercise
   notification/clipboard recovery, radio hotplug/reconnect, capture, display
   confirm/revert and battery-saver restore. Measure combined memory in ordinary
   use, including Settings/workers, and record scope/temporary peaks honestly.
   Address demonstrated regressions at their owner before another conversion.

## Completion criteria and scope limits

- A comparable converted feature requires its own implementation/descriptor,
  one positioned index entry, tests and docs; no imports of another feature.
- Each job/controller has one owner for admission, completion and shutdown;
  busy/error/retry UI matches that lifecycle, without extra per-widget services.
- Failure paths preserve saved data, allow recovery and remain tested in preview
  and standalone Settings. Current CLI/IPC/env/import contracts stay compatible.
- A release has passing applicable gates, explicitly listed skips, laptop checks
  and a scoped aggregate memory result. Unit coverage alone is insufficient.
- D1 is closed. A6 polling/cache/power changes, aggregate metadata generation,
  new executors/event buses and unapproved feature work remain outside this roadmap.

Next authorization should name one boundary above, not reopen the entire project.
