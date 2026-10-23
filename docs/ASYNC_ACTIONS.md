# Async actions after M7b

Planning only, checked against main `16de00e` on 2026-10-23. M7b is merged:
`wallpaperScan` delegates to the existing worker scheduler and completion emitter.
There are 30/89 registered IDs (29 sync, one worker). No further conversion is
authorized by this plan. The remaining async inventory has **28 IDs**.

## Existing worker contract fits: 8

| Proposed batch | Actions | What must remain unchanged |
| --- | --- | --- |
| Wallpaper daemon | `wallpaperStatus`, `wallpaperEnsure` | Status/errors, Settings admission, demo state, daemon lifecycle |
| Wi-Fi | `wifiScan`, `wifiConnect`, `wifiSaved`, `wifiDisconnect`, `wifiForget` | Credentials, literal argv, read-back and error/result state |
| Record stop | `recordStop` | Recorder ownership, completion and failure behavior |

Start with the two Wallpaper daemon actions: they share the pilot's domain and
need no new registry phase. Then Wi-Fi; record stop follows after its
existing controller contracts are characterized. These are planning candidates,
not guarantees that extraction will pass its behavior-preservation tests.

Each batch first pins shell/Settings × live/demo behavior on unmodified code:
admission, immediate ack, result/sequence, pending cleanup, snapshot, error and
shutdown behavior. Then move live/demo handlers together, keep narrow capabilities,
and delete their legacy branches. Keep the shared executor/job table, scheduler,
completion emitter and existing read-back calls; registered errors never fall back.
Follow STATE's affected gates, final full gates and single runtime/RSS sanity check.

## Existing worker contract is insufficient: 20

| Extra contract | Actions | Why a mechanical move is unsafe |
| --- | --- | --- |
| Synchronous preflight/options (4) | `palettePreview`, `recordStart`, `lock`, `imageAnnotate` | Keep immediate validation and request-time options, including editor selection before enqueue |
| Group admission/guards (8) | `wallpaper`, `wallpaperNext`, `wallpaperResetOutput`, `gowallThemes`, `gowallGenerate`, `gowallSave`, `gowallApply`, `batterySaver` | Guards must run before job ownership; worker-side guards can reject their own job |
| Replace/cancel (1) | `fileSearch` | Replaces/cancels an older search instead of ordinary duplicate-job rejection |
| Token/lease metadata (3) | `captureExport`, `captureAnnotate`, `captureOcr` | Session validation and future metadata belong to capture lifecycle |
| Separate controllers/executors (4) | `chargeMode`, `weatherSearch`, `weatherDetect`, `weatherRefresh` | Charge and Weather own different pending/completion/shutdown contracts |

Keep these legacy until separately authorized. After the simple batches, inspect
preflight first: consider a small explicit admission/preparation seam, preserving
immediate errors and request-time options. Do not create a generic workflow engine.
Cancellation, capture leases and separate controllers require their own designs;
power/display-sensitive work goes last. Conditional `suspend` and internal
`wallpaperCycle` are outside this 28-ID inventory. Sync `gowallSetup` and
`weatherSelect` are not included.

Correction to the M7b assessment: it listed nine simple candidates, including
`imageAnnotate`. Its current live branch captures `captureEditor` before enqueue;
the registry invokes `live(request)` inside the worker. Reading the editor there
would change behavior when preferences change while the job waits. Hence eight
simple candidates, twenty needing another seam; the total remains twenty-eight.

## Modularity, implementation size and memory

Use [Modularity](../.agents/skills/modularity/SKILL.md) for cohesive ownership and
[Ponytail](../.agents/skills/ponytail/SKILL.md) for the smallest complete extraction.
Stable legacy handlers are acceptable; an action provider is not a new process.
No executor/queue/timer per domain, async framework expansion, file moves, or
polling/cache/power changes are implied by this plan.

Aim for total-shell memory <=400 MB steady / <=500 MB ordinary active use,
including open Settings and owned workers. Prefer aggregate PSS; label summed
RSS limitations and temporary heavy-job peaks. Existing separate-instance RSS
samples do not establish that total; no memory saving is claimed here.
