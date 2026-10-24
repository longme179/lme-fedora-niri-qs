# Asynchronous action contracts

2026-10-24. Merged resource/lifecycle main 3f9ac22 includes all 21 previously listed
legacy async entry conversions: **58/89 IDs, 32 sync entry calls and 26 workers**.
Merged Capture entry main 201c452 includes its five synchronous start/close/language
entries: **63/89, 37 sync entry calls and 26 workers**. Merged Display preview main
b73a7b0 has **68/89, 42 sync entry calls and 26 workers**. The
Mirroring merge (2390d8d) adds three synchronous mirror routes:
**71/89, 45 sync entry calls and 26 workers**. The subsequent
`refactor/selection-application-actions` review branch adds paletteApply,
glassBlurApply, gowallSetup and weatherSelect: **75/89, 49 sync entry calls and
26 workers**. These are synchronous domain/service calls, not worker conversions.
Existing controllers/watchdogs/transactions stay authoritative; no async contract,
UI composition or schema change. See MIRRORING_PLAN.md and SELECTION_APPLICATION_PLAN.md.

| Family | Actions | Preserved owner/contract |
| --- | --- | --- |
| Existing worker | recordStop | Recorder.stop; original worker queue, privacy invalidation and completion |
| Request-time preflight (4) | palettePreview, recordStart, lock, imageAnnotate | Validate/capture options on the coordinator; execute only the prepared operation in its existing worker |
| Group admission (8) | wallpaper, wallpaperNext, wallpaperResetOutput, gowallThemes, gowallGenerate, gowallSave, gowallApply, batterySaver | Prefix/transition guards before owning a Future; controller mutations and read-back stay at their owners |
| Replace/cancel (1) | fileSearch | Existing Event/Future replacement and latest-state installation; not ordinary duplicate rejection |
| Capture leases (3) | captureExport, captureAnnotate, captureOcr | Existing capture_token attached before ack; stale completion discarded by the host; editor captured at the original stage |
| Separate controllers (4) | chargeMode, weatherSearch, weatherDetect, weatherRefresh | Sync registry entry calls existing asynchronous controllers; no extra executor or new coordinator-worker ack for Weather |

The small optional seam is `ActionSpec.prepare(request) -> PreparedWork(operation,
metadata=None)`. Context admission precedes preparation; demo never prepares.
The registry delegates the operation and trusted Future tags to the existing
start_feature(). `complete(value)` installs domain state, then a static or trusted
callable presentation produces the same message before normal result publication.
No callbacks/expressions in JSON, second job table, queue or universal event bus.

All live/demo branches moved together. Registered errors never fall back to legacy.
The unchanged-context golden covers 21 x shell/Settings x live/demo = 84 scenarios,
with exact ack/completion/result/sequence, calls and selected state. Further cases
cover preflight errors, captured options, group rejection, replacement and stale
capture tokens. Existing import/dispatch/snapshot facades remain available.

Charge still uses charge_executor/charge_job and finish_charge(); WeatherClient
still owns loading, forecast/search/geolocation completion and shutdown. Those are
explicit compatibility/controller seams, not worker specs disguised as synchronous
network operations. Domain algorithms, retries, sampling and power policy stay.

## Remaining boundaries

14 finite coordinator IDs remain legacy on the selection/application branch. Conditional suspend and internal
wallpaperCycle retain their existing paths; neither was in the 21-ID inventory.
Do not infer that every asynchronous operation in the shell is a registry worker.
A later migration needs a named scope, characterization and its actual ownership
contract; remaining stable legacy routes need not move merely to increase a count.

Explicit provider bindings retire only with descriptor discovery and equivalent
ownership/withdrawal/fallback. Public controller/import/dispatch facades retire only
at their documented zero-consumer condition plus owner approval. M8 stays optional.

F5/F4 resource policy and measured relay costs are in RESOURCE_LIMITS.md; release
and laptop checks are in RELEASE_CHECKLIST.md. No RAM saving or physical device/GPU
success follows from dispatch extraction. A6 and D1 remain outside this work.
