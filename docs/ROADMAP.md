# LME Shell: position and next boundaries

2026-11-01. This is a roadmap, not authorization for another implementation.
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

The owner requests percentage progress. Use the fixed acceptance score below;
migration counts remain coverage, not product stability or remaining effort.

## Acceptance progress: 100% (10/10 checkpoints)

Each checkpoint is worth 10% as a reporting convention, not an estimate of time
or engineering effort. A checkpoint closes only on its stated evidence. Default
skips are not passes; real-device evidence cannot be substituted with VM results.

| # | Checkpoint and evidence | State |
| --- | --- | --- |
| 1 | Shared runner, atomic storage, content and layout contracts extracted/tested | Verified |
| 2 | One assembled preference schema, compatibility and persistence/export parity | Verified |
| 3 | Sync/worker dispatch, context, pending/completion and demo contracts | Verified |
| 4 | Catalog UI/schema/bootstrap/withdrawal patterns proven in copied checkouts | Verified |
| 5 | Dependency/size guardrails, isolated gates and public compatibility facades | Verified |
| 6 | Ported integration/failure recovery contracts (F1-F5, capture/display/radios) | Verified in automated scope |
| 7 | Safe deployment/update tooling; owner confirms deployment completed | Verified |
| 8 | Preview/Settings/native release automation and launch/RSS sanity | Verified in automated scope |
| 9 | Owner's practical laptop functionality/integration sign-off | Owner accepted, 2026-11-01 |
| 10 | Aggregate shell RAM <=400 MB steady / <=500 MB ordinary active; acceptance method recorded below | Owner accepted aggregate btop observation, 2026-11-01 |

Owner decision (2026-11-01): tested functionality behaves as expected; observed
memory does not exceed 400 MB and was explicitly confirmed to mean the aggregate,
not individual PIDs. The owner closes the RAM checkpoint and the current roadmap
at 100% on that practical basis. An all-features-at-once stress workload is not
required for this acceptance. This replaces the earlier requirement for further
warm/Settings/GPU PSS evidence; no new quantitative PSS/GPU result is claimed.
Historical VM overruns stay recorded. Diagnostic tools remain available for a
future regression; this closure does not authorize another migration or release upload.

Report overall acceptance and current-branch delivery separately. More descriptors
do not increase a completed checkpoint. Keep this denominator fixed; record why a
checkpoint reopens after a regression, and label any owner-authorized goal changes.
The real-session rows in RELEASE_CHECKLIST.md still govern release approval.

## Where we are

| Area | Current coverage | What remains |
| --- | --- | --- |
| Infrastructure | Shared runner/storage/content/layout helpers, dependency ratchet, catalog, tab IDs, schema fragments and sync/worker registry; six descriptor-selected backend providers | Retain stable compatibility facades; remove an adapter only at its stated retirement condition |
| UI composition | 17 catalog records (seven with empty startup UI metadata), 10 of 16 Settings pages, Clipboard bar/panel; Notifications tab and context-aware bootstraps | Six core pages and most bar/panel hosts stay legacy by owner decision; no bulk conversion implied |
| Preferences | 79 of 147 keys descriptor-owned; 68 in the single legacy schema fragment | Later small cohesive batches when they reduce real change cost; same flat settings.json and transaction protocol |
| Backend dispatch | Merged: 75 of 89 IDs registered, 49 sync entry calls + 26 workers | 14 legacy IDs; separate charge/weather controllers keep their lifecycle; conditional suspend/internal wallpaperCycle stay outside this batch |
| Cross-feature reliability | Automated contracts plus owner-accepted practical laptop functionality (2026-11-01) | Address concrete regressions/new scopes when reported |
| Resource confidence | Inventory/lifecycle tools retained; earlier PSS snapshots preserved; owner accepts aggregate btop observations at or below 400 MB in ordinary use | Quantitative PSS/GPU tools are optional future diagnostics, not an open acceptance gate |

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
battery imports (SHARED_VALUES_PLAN.md). Shared display layout merged (8d1764e), extracting
the three layout helpers used by BatterySaver and DisplayControl, retaining old
exports (SHARED_DISPLAY_LAYOUT_PLAN.md). Seven exact legacy exceptions remain,
all QML composition edges; no Python cross-feature exception remains. Controllers,
polling and power policy stay unchanged. The dated owner acceptance above closes the practical laptop milestone.
Device schema merged (8aea87f), moving four scalar keys to preference-only
peripherals, batterySaver and mirroring descriptors, following OSD. Their existing
UI/controllers and action registrations stay legacy; empty startup metadata adds
no navigation entry. This is schema ownership, not full UI/feature conversion.
Content schema merged (83f9cad), following the same pattern for Lyrics (five),
File search (two) and Bluetooth (two). Home-dependent search defaults and private
root/adapter exclusions stay; direct roots validation and existing named mode/
adapter callbacks reuse domain policy. Lookup/scanning/pairing and UI stay legacy.
Merged release-session/render-lifetime verification adds copied-checkout Smoked/Liquid
panel/Settings/restart/job checks, without runtime changes. See the combined PSS
table in RELEASE_CHECKLIST.md: process/loader/registry lifecycles pass, warmed
software-rendered memory is over budget; a bounded probe is not a leak verdict.

## Proposed order after resource/lifecycle review

1. **Practical acceptance closed.** Owner confirmation above closes functionality
   and RAM for the current normal-use scope. RELEASE_CHECKLIST.md records the
   decision and method; earlier PSS/VM data stay historical. The passive inventory
   and [laptop workload](LAPTOP_MEMORY_WORKLOAD.md) remain optional tools for a
   concrete future regression. No more profiling or broad audit is needed merely
   to repeat this accepted milestone; future runtime changes keep their affected checks.
2. **Selection/application merged; prefer release evidence.** Four entries
   (paletteApply, glassBlurApply, gowallSetup, weatherSelect) reuse their existing
   domain providers/services. Preview matching, setup admission, preferences and
   demo behavior stay. Fourteen legacy IDs remain: setting, refresh, controlsRefresh,
   wifiWatch, monitor, launcherHistoryClear, wifiToggle, powerProfile, logout,
   suspend, reboot, poweroff, desktopEdit and openSettings. These mostly coordinate
   shared state, transactions or lifecycle; moving them just to reach 89/89 is not
   a goal. No further action family is authorized; choose another boundary only if it
   reduces real change cost. Schema remains 68 legacy keys.
3. **Provider ownership: six domains.** Night Light, Idle, Keybinds, Weather,
   Battery Saver and Mirroring declare their single provider via backend.entry/
   factory in their existing descriptors. The root retains narrow capabilities and original
   fallback factories; it resolves references atomically before accepting a valid
   catalog. Disabled entries hide UI and retain backend/controller access, as
   before; broken references retain legacy-only UI plus the existing diagnostic.
   Missing metadata keeps the compatibility factory. See PROVIDER_OWNERSHIP_PLAN.md
   and CONTROLLER_PROVIDERS_PLAN.md. Saver/Mirror keep legacy UI because their
   startup metadata stays empty; source ownership moves without file moves.
   Review frozen schema-only descriptor-shape tests before a future family;
   owner approval is required for any existing assertion change. There is no new
   action registry, async contract, process, polling or controller change; the
   registered ID and preference counts above stay the same. Original fallbacks
   and import facades retire only with equivalent fault coverage and owner approval.
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
- A release has passing applicable gates, explicitly listed skips and owner
  acceptance with the practical workload/memory method stated. Quantitative PSS
  evidence must be labeled separately; the 2026-11-01 decision closes this roadmap.
- D1 is closed. A6 polling/cache/power changes, aggregate metadata generation,
  new executors/event buses and unapproved feature work remain outside this roadmap.

Next authorization should name one boundary above, not reopen the entire project.
