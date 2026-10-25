# LME Shell: position and next boundaries

2026-10-25. This is a roadmap, not authorization for another implementation.
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
| Infrastructure | Shared runner/storage/content helpers, dependency ratchet, catalog, tab IDs, schema and sync/worker registry; shared image/peripheral values merged, shared display layout implemented for review | Retain stable compatibility facades; remove an adapter only at its stated retirement condition |
| UI composition | 11 catalog records, 10 of 16 Settings pages, Clipboard bar/panel; Notifications tab and context-aware bootstraps | Six core pages and most bar/panel hosts stay legacy by owner decision; no bulk conversion implied |
| Preferences | 66 of 147 keys descriptor-owned; 81 in the single legacy schema fragment | Later small cohesive batches when they reduce real change cost; same flat settings.json and transaction protocol |
| Backend dispatch | Merged: 75 of 89 IDs registered, 49 sync entry calls + 26 workers | 14 legacy IDs; separate charge/weather controllers keep their lifecycle; conditional suspend/internal wallpaperCycle stay outside this batch |
| Cross-feature reliability | Wi-Fi/Bluetooth/persistence, F1-F5, resource/lifecycle, Capture, Display preview, Mirroring and selection/application merged | Laptop integration, scoped combined memory and normal release sign-off |
| Resource confidence | Per-branch native tests, source-size caps and launch/RSS sanity; one-shot memory inventory tool merged | Reviewed real-session shell + Settings/worker inventory and physical device/GPU checks remain necessary |

M0-M3, M4a/b, M5/M6, M4c-1/2/3 and M7a/b/c/d established the reusable contracts.
We have passed the infrastructure/pilot stage and are hardening integration before
expanding migrations. The merged resource branch converted the 21 async entry points
through explicit preflight/admission/lease/controller contracts; see ASYNC_ACTIONS.md.
Capture's five synchronous start/close/language entries are merged; see
CAPTURE_ENTRY_PLAN.md. Display preview/platformRefresh entries are merged; see
DISPLAY_PREVIEW_PLAN.md. Mirroring is merged (2390d8d); see MIRRORING_PLAN.md.
The main shell still owns the mirror child and Settings uses its IPC.
Selection/application is merged (d72e48a), reusing four domain/service registrations; see
SELECTION_APPLICATION_PLAN.md. Demo remains isolated. Controllers/UI/pending/shutdown semantics stay, including
watchdog/guard/confirmation policy; no additional worker/process.
Existing stable legacy ownership is acceptable; full conversion is not the goal.
Shared values merged (53e321a), removing Gowall->Wallpaper and Pairing->Peripheral
battery imports (SHARED_VALUES_PLAN.md). The shared-display-layout branch extracts
the three layout helpers used by BatterySaver and DisplayControl, retaining old
exports (SHARED_DISPLAY_LAYOUT_PLAN.md). Seven exact legacy exceptions remain,
all QML composition edges; no Python cross-feature exception remains. Controllers,
polling and power policy stay unchanged. Physical release/PSS checks remain pending.

## Proposed order after resource/lifecycle review

1. **Close release evidence.** The merged release-memory tool is a one-shot passive
   inventory, not a runtime monitor; see RELEASE_MEMORY_PLAN.md. F5 command bounds, F4 log/relay cost and the
   21 converted async entries are merged. Complete RELEASE_CHECKLIST.md on the laptop and
   assess the combined memory scenario with its profile/worker scope stated.
   Hardware/GPU success cannot be inferred from private software-rendered checks.
2. **Selection/application merged; prefer release evidence.** Four entries
   (paletteApply, glassBlurApply, gowallSetup, weatherSelect) reuse their existing
   domain providers/services. Preview matching, setup admission, preferences and
   demo behavior stay. Fourteen legacy IDs remain: setting, refresh, controlsRefresh,
   wifiWatch, monitor, launcherHistoryClear, wifiToggle, powerProfile, logout,
   suspend, reboot, poweroff, desktopEdit and openSettings. These mostly coordinate
   shared state, transactions or lifecycle; moving them just to reach 89/89 is not
   a goal. No later family is authorized; choose another boundary only if it
   reduces real change cost. Schema remains 81 legacy keys.
3. **Provider discovery/withdrawal policy.** Explicit composition bindings remain
   an adapter. A descriptor backend contract must preserve disabled/broken-catalog
   fallback and ownership before replacing them; no competing registry.
4. **Remaining UI seams only when warranted.** Six core Settings pages and most
   bar/Controls/Launcher/Activity registrations stay legacy by owner decision.
   New migrations need a useful named scope; M8 physical moves are optional/last.
5. **Retention and resource follow-ups, separately scoped.** Per-file Launchpad
   caps do not bound logs from old/deleted IDs. Choose an explicit inactive-log
   policy before deletion; count detached relays surviving restarts and all LME
   instances in ordinary-use memory. Do not kill user jobs or delete active logs.

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
