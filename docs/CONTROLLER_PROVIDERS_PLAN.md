# Controller-provider catalog batch

2026-10-31. Base main 5e4a4d8 includes the accepted three-provider pilot (PR #41).
Owner requests continued roadmap implementation and percentage progress reporting.
Use the fixed acceptance checkpoints in ROADMAP.md; this batch has five equal
delivery stages: plan, characterization, conversion, gates, sanity/docs/review PR.

## Scope

Convert provider selection for Weather, Battery Saver and Mirroring only, one
implementation commit each. Reuse backend.entry/factory, provider_factories(),
the current fallback map, narrow capabilities and the three-second startup guard.
No provider/controller algorithm, ActionSpec, executor, queue, async contract,
polling, power policy, UI, preference definition or index position changes.

- Weather: four existing sync entries call WeatherClient; the controller keeps
  async search/detect/forecast ownership. Existing Settings/network guards stay.
- Battery Saver: its worker prepare/complete/admission and journal/restore owner
  remain unchanged. Declare its two sources and remove their duplicate legacy
  ownership record in the same commit.
- Mirroring: three existing sync entries retain main-owned child/Settings IPC.
  Declare mirror_actions.py/display_mirror.py in the mirroring descriptor and
  remove those two files from legacy display ownership, without moving them.

Disabled or missing entries retain backend actions/controllers; Weather UI still
withdraws through its existing guards. Saver/Mirroring have schema-only records:
their legacy UI remains, as before. Broken references fail closed to legacy UI
plus diagnostic/original factories. Factory/action errors never retry via fallback.
Keep all original imports and public IPC/CLI/result/snapshot/data contracts.

## Characterization and change surface

First run current controller/worker golden tests and add provider/spec purity,
demo protocol/state and disabled/broken-catalog characterization on unchanged main.
New descriptor-selection/fault cases are N/A until the complete family converts.
Prove each copied descriptor selects its own factory without composition edits;
verify complete current bindings and missing/disabled/invalid reference behavior.

Two existing test setup inputs must track the expanded catalog; assertions,
timeouts and frozen fixtures stay unchanged:
- The old three-provider test explicitly filters input metadata to its original
  PILOTS tuple; a new full-catalog case guards all six capability bindings.
- The native unbound-provider fixture changes weather/weather_actions to
  fileSearch/file_search_actions, because Weather becomes bound in this batch.
  The same unbound/fallback/navigation assertions still execute.

## Delivery and verification

Commit this plan/progress rubric, tests, each provider conversion, then final docs.
Run affected controller/backend/catalog units and architecture checks per change.
On final runtime head run G0-G4/G6 once; explicitly run the relevant copied native
fault/navigation/withdrawal cases with disposable XDG/private Wayland/D-Bus.
Run one ten-launch main/head preview/Settings sanity with QS/backend RSS at ten
seconds. Stop at STATE's +100 ms Settings / +10% RSS flags. Revert a failed
committed implementation; never edit existing assertions to make it pass.
Record one <=30-line migration summary and <=6-line laptop checklist; open a
review PR, no merge. Hardware/GPU/PSS acceptance remains pending, not inferred
from software-rendered regression or per-process RSS. D1/A6/M8 stay closed/deferred.
