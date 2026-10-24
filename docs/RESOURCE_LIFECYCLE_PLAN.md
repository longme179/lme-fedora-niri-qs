# Resource bounds and asynchronous lifecycle contracts

2026-10-24. Owner-authorized plan and execution on one branch:
`fix/resource-bounds-and-async-contracts`, baseline main **03e7006** (F3 merged).
Use Ponytail and Modularity proportionately. Preserve CLI/IPC, settings transactions,
existing job/controller ownership and all ordinary error/result/sequence behavior.

## 1. F5: bounded command capture

- Inventory inspected: command_runner.py, managed_command.py, Wi-Fi observer,
  backend/domain call sites and runner/managed/infrastructure tests. Captured data
  is CLI text/JSON; wl-copy deliberately discards pipes. Detached spawns are separate.
- Retain at most 8 MiB combined stdout/stderr by default; allow 16 MiB for the
  larger JSON producers niri/busctl/pw-dump, 2 MiB for nmcli. These are defensive
  ceilings, not measured maximum legitimate responses. A named optional per-call
  bound can accommodate an explicitly tested larger domain contract.
- Drain both pipes in bounded chunks without communicate()'s unbounded buffers.
  Overflow is an explicit error even for exit 0, never successful truncated JSON;
  continue draining/discarding until completion, existing cancellation or deadline.
- Preserve cumulative byte observer input, its exception cleanup, UTF-8 replacement,
  universal newline translation, error redaction/truncation, memfd input, process
  groups and wl-copy DEVNULL. Cleanup must not reintroduce unbounded capture.
- Tests first: normal exact messages, both streams, limit boundaries, invalid
  limits, multibyte/newlines, observer, noisy timeout/cancel, inherited pipes and
  reaping. Reuse existing managed/Wi-Fi tests; no asserted expectations relaxed.

## 2. F4: detached Launchpad logs and resource decision

- Proposed cap: 8 MiB TOTAL per log, including one explicit truncation marker.
  Drain/discard excess so commands receive no SIGPIPE and can finish normally.
  Keep 0600/no-symlink log handling, literal argv, explicit Bash/terminal selection,
  cwd, eight-job admission, ordinary exit codes and shell-exit survival.
- Prototype then measure the actual stdlib relay before integration: one and eight
  idle relays, aggregate RSS/PSS, descriptors and EOF/exit cleanup. One relay per
  running job, none at idle; no daemon/thread/process per widget. Decide with the
  measured overhead and final combined-shell scenario, never claim free memory.
- Relay owns launch/readiness/error handshake and output lifetime. No parent-death
  signal: user commands stay detached. Explicitly terminating its process group
  must still clean up test/user jobs. Disk-write errors must not hang producers;
  retain a useful diagnostic when possible. Never rotate/delete an active writer.
- Per-log bounds do not bound old entry IDs/directories. Completed-log retention
  cleanup is separate; do not silently delete user logs in this branch.
- Chosen relay uses stdlib posix_spawnp and -S, with no parent-death signal.
  Actual idle relay-only sample: one RSS/PSS 7,768/5,188 KiB; eight aggregate
  RSS/PSS 62,152/34,455 KiB, 5 FD each. User command memory is separate; these
  samples do not prove the combined-shell target. None persist at idle.
  Truncation preserves the command exit status. A log sink failure drains output
  and reports exit 74 only if the command itself succeeded; nonzero/signal command
  exits keep precedence. The job remains running until inherited writers close.
  Eight is the existing per-controller limit, not a global limit: detached jobs
  surviving a shell restart can add relays. Count those in whole-shell samples.
- Tests: prefix/marker, stdout+stderr, ENOSPC, missing exec/cwd, exit/signals,
  inherited writers, repeated jobs, shell-exit survival, terminal mode and symlinks.
  Ask before adapting existing mocked launch assertions to the relay boundary.

## 3. Async migration, in small domain commits

Characterize shell/Settings x live/demo before moving each domain. Move live and
demo routes together; keep narrow capabilities and the existing composition list.

| Order | IDs | Required contract |
| --- | --- | --- |
| First | recordStop | Existing worker spec; recorder owns stop/shutdown and host retains privacy invalidation |
| Preflight/options | palettePreview, recordStart, lock, imageAnnotate | Coordinator prepares immutable options/validation before queueing; worker executes the returned operation |
| Group admission | wallpaper/Next/ResetOutput; gowallThemes/Generate/Save/Apply; batterySaver | Prefix/guard checks occur before owning a job, with the same request-time state and error order |
| Replace/cancel | fileSearch | Retain Event/old Future replacement and latest-result installation; no ordinary duplicate rejection |
| Capture leases | captureExport/Annotate/Ocr | Validate at the same stage; attach the existing capture_token before acknowledgement, discard stale completion as today |
| Separate controllers | chargeMode; weatherSearch/Detect/Refresh | Registry entry invokes the existing coordinator/controller operation; existing charge executor and Weather loading/results stay at their owners |

Small extension: optional ActionSpec.prepare(request) returns PreparedWork(operation,
metadata). Worker dispatch delegates to the SAME start_feature(); metadata contains
existing trusted Future tags, not JSON callbacks or another job table. Optional
callable presentation formats domain completion messages (OCR) after complete().
Old ActionSpec constructors/defaults remain valid. Controller entry calls are sync
registry dispatch even where their controller continues async; do not turn Weather
requests into coordinator-worker acknowledgements. Keep charge_mode's separate
pending/completion facade and all host read-back invalidation calls unchanged.

If an extraction cannot preserve admission/cancellation/completion with these seams,
leave that action legacy and record exact evidence and the next required contract.
Do not create a workflow engine, new executor/queue/timer, or change A6 policy.

## 4. Verification and release boundary

- Plan first, characterization tests, implementation per domain, final docs as
  separate commits on this branch. Revert a failing commit; no assertion edits
  without approval. New source <=250 nonblank lines; ratchet existing ceilings.
- During work: G0 plus affected Python tests; G1/native only for actual QML changes.
  Full G0-G4 and G6 once on final runtime/test head. Explicit skips stay visible.
- One normal branch sanity: 10 preview/Settings launches main/head medians and
  T+10 s QS/backend RSS; stop for Settings >+100 ms or RSS >+10%. D1 stays closed.
- Add one simultaneous shell + Settings + owned-worker PSS scenario, including
  relays, with sampled process inventory and temporary-job scope. Compare with
  <=400 MB steady / <=500 MB ordinary-active targets; a VM sample is not a laptop
  guarantee. No raw evidence committed and no new continuous monitoring service.
- Laptop checklist/release notes must say needs real-session check for Bluetooth,
  GPU/recording, display confirm/revert and battery-saver restore. This environment
  cannot close those checks; do not label the release fully validated without them.
