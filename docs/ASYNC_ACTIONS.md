# Async actions after Wi-Fi extraction

M7b/M7c/M7d and Wi-Fi feedback are merged (main ace2744). The device-action
reliability follow-up on runtime head 3e167ad moves the already registered
bluetoothDevice to the same worker pool: 37/89 registered IDs, 28 sync and nine
workers. There is no new registry phase or executor. The **21 remaining legacy
async IDs** below are unchanged; further conversion still needs authorization.

## Remaining action the existing worker contract fits: 1

| Proposed batch | Actions | What must remain unchanged |
| --- | --- | --- |
| Record stop | `recordStop` | Recorder ownership, completion and failure behavior |

The daemon pair and Wi-Fi needed no new registry phase. Next propose recordStop
after its existing controller contracts are characterized. This is a planning
candidate, not a guarantee that extraction will pass behavior-preservation tests.

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
`wallpaperCycle` are outside this inventory. Sync `gowallSetup` and
`weatherSelect` are not included.

Correction to the M7b assessment: it listed nine simple candidates, including
`imageAnnotate`. Its current live branch captures `captureEditor` before enqueue;
the registry invokes `live(request)` inside the worker. Reading the editor there
would change behavior when preferences change while the job waits. Hence eight
original simple candidates, twenty needing another seam; after M7d, one plus twenty.

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
