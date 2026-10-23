# F3: action pending ownership

Planning only, 2026-10-23. Baseline: merged main **f28be3d**, including F1/F2
(PR22). This is the next review boundary from NEXT_OPTIMIZATION_PLAN.md.
Runtime implementation requires approval of the additive wire contract below.

## Problem and scope

`DesktopBackend.start_feature()` rejects duplicates correctly. However,
`ShellState.accept()` clears `pendingActions[action]` for every non-pending
result, even a rejection while the original job still owns that action.
The existing fake-device/ManualExecutor reproduction is:

| Event | Backend owner | Current UI busy | Required UI busy |
| --- | --- | --- | --- |
| First bluetoothDevice acknowledged | Original job | true | true |
| Duplicate rejected, sequence 2 | Same original job | false | true |
| Original completion, sequence 3 | None | false | false |

Ordinary Bluetooth/Wi-Fi buttons already guard duplicates; this is a shared
protocol/reducer defect, not evidence of a normal mouse-only device failure.
Do not infer ownership from error strings or suppress repeated run() calls.
Sliders/settings must still submit updates; fileSearch must still replace work.

## Proposed wire contract (approval item)

Keep lastResult, its sequence/messages and ack-before-completion unchanged.
Add an optional request tag and one top-level field on emitted JSON snapshots:

```json
{"action":"bluetoothDevice","path":"...","connected":true,"clientSerial":2}
```
```json
{"actionPending":{"acknowledged":2,"active":["bluetoothDevice"]}}
```

The second example is a fragment of the existing full snapshot, not a new frame.

- ShellState assigns a monotonically increasing clientSerial per backend
  connection, overriding any payload value. Use a JS safe integer, not a QML
  32-bit int. Valid tags are integers 1..9007199254740991; booleans are invalid.
- acknowledged starts at 0 and is the greatest valid tag processed, including
  rejected/context-denied/invalid-action attempts. It advances on requests,
  never on worker completion. Untagged/invalid tags are ignored as optional
  transport metadata; they do not change existing action validation/messages.
- active is a sorted unique list derived only from existing feature_jobs keys,
  plus chargeMode while charge_job exists. A done Future still owns its entry
  until the existing completion path removes it. Sample ownership AFTER snapshot()
  has performed its existing completion handling, never before it.
- This covers coordinator-owned work, not every operation in the shell.
  Weather loading, capture sessions and detached Launchpad jobs retain their
  own state/lifecycle; do not invent entries for them or change their UI.
- Emit the field at the existing wire boundary emit(backend), as catalogValidation
  already is. Keep emit's signature and direct handle()/snapshot()/feature_snapshot()
  facades unchanged; no new field inside lastResult or persisted files.
- Separate shell and Settings processes have separate streams/counters. One
  ordered writer per connection is assumed, as today; no multiplexed RPC.

## UI reducer and compatibility

Retain pendingActions as the current Boolean-map facade. Keep only the latest
unacknowledged serial per action, with no retained requests/payloads/history:

```text
pending(action) = localSerial(action) > acknowledged OR action in active
```

Prune acknowledged local entries on each accepted ownership frame. An old frame
with active=[] cannot clear a request sent after that frame was generated.
A duplicate rejection acknowledges the duplicate but leaves the original active.
Completion/error removes busy only when no owner or newer local request remains.

Update internal bookkeeping, then publish pendingActions, before snapshot/readiness
or lastResult callbacks can submit another request. Do not overwrite a reentrant
run() later in the same accept(). Do not change result/status filtering.

- New UI + old backend (field absent from startup): keep current result-based
  fallback. Old UI + new backend: additive fields are ignored, old results stay.
  The old reducer bug remains for an old peer; no silent request dropping.
- Once ownership metadata is accepted, malformed/missing/regressing metadata
  preserves the last valid ownership and logs through the existing warning path;
  other valid snapshot/result fields still update. The next valid frame recovers.
  A persistently broken peer can leave busy visible until reconnect; never add
  a timeout that falsely declares a still-running job finished.
- Backend exit clears serial, local/active ownership and existing busy flags.
  Restart starts a fresh connection; no replay of mutations or old jobs.
  Keep the existing backend restart limit/delay and shutdown/cancellation policy.

## Implementation boundary and change surface

- desktop_backend.py: record request acknowledgement and decorate wire output
  from existing owners. No changes to start_feature(), registry providers,
  finish_features()/finish_charge() publication, or executor ownership.
- A small stdlib scripts/action_pending.py may hold serial validation/projection
  and the directly related JSON-line transport extraction. Keep emit(backend)
  and malformed-input errors compatible. Respect the backend's 1806-nonblank-line
  ceiling by extracting only this transport responsibility, not unrelated actions.
- ShellState.qml: local bookkeeping, ownership reduction, legacy fallback/reset.
  A small shared ActionPending.js is appropriate if it makes the reducer directly
  testable; no feature implementation imports or new dependency exceptions.
- New tests plus STATE/MIGRATION/plan documentation. Review callers of
  pendingActions and lastResult, including F2 save recovery, before implementation.
  Existing assertions/frozen fixtures remain unchanged; ask if one must change.
- No domain-specific busy rules added to ActionRegistry. No second job table,
  queue, process, timer, executor, per-widget backend or new setting.
  Bookkeeping is proportional to pending action IDs and pruned on acknowledgement.

## Tests and commit sequence

1. **Characterization/regressions first** (`test_action_pending.py`): pin current
   exact ack/error/completion results, sequences, context/demo admission and direct
   facade shapes; these must pass on unmodified main. Record the duplicate-busy
   regression failing before the fix; metadata-specific cases are initially N/A,
   never described as passed. Reuse ManualExecutor/Future and fake runners.
2. **Protocol + reducer fix**, one coherent implementation commit:
   - Duplicate Bluetooth and conflicting Wi-Fi rejection leave the original busy;
     unrelated synchronous success/error cannot steal ownership.
   - Multiple synchronous slider/settings requests, batched input and a snapshot
     generated before a newer send; no dropped writes or premature idle.
   - Already-done jobs still acknowledge first; two completions publish separately;
     failure, cancellation and stale capture-token cleanup use existing policy.
   - fileSearch replacement keeps the current owner; an old completion cannot
     clear a newer local request. Include separate charge_job coverage.
   - Shell/settings and demo paths, unknown actions, invalid/absent tags, safe
     integer boundaries, ownership after snapshot completion and legacy peers.
   - Reentrant result/readiness handlers, malformed ownership recovery, backend
     exit/restart, initial/--once state, no command replay or extra process spawn.
3. **Native copied-checkout tests** (`test_action_pending_ui.py`), written before
   the fix and used during it: controlled blocked worker + duplicate rejection,
   completion/failure/retry, close/reopen, reconnect, and both shell/Settings
   legacy fallback. Inject fake tools/backend only in the copy. Exercise an
   actual pending-driven control and rerun F1/F2 recovery tests to check integration.
4. **Final docs**: report actual results, intended visible fix, additive wire
   fields, compatibility limits and adapter retirement conditions. No raw logs.

Use G0 + G1 + affected units/native cases while working; run G0-G4 and G6 polling
once on the final runtime/test head. Revert a failing implementation commit;
do not stack corrective changes or relax assertions/timeouts to obtain green.
Private disposable XDG/Sway/Wayland/D-Bus only; no real devices/config/session.
One branch sanity per STATE: 10 preview/Settings launches, medians and T+10 s RSS;
stop for Settings >+100 ms or RSS >+10%. No D1 profiling or startup optimization.

## Acceptance, risk and next boundary

- Expected behavior change: busy/enabled state reflects real ownership and
  unacknowledged sends, including after duplicate rejection. No visual redesign,
  action admission, messages, cadence, settings/history format or schema changes.
- Medium risk: ordering/reentrancy and legacy-peer compatibility, rather than
  device algorithms. Charge rollback, Bluetooth and physical radio behavior still
  need real-session checks; private-session success does not verify hardware.
- Adapter: retain legacy result-based pending reduction until old backends and
  legacy fixtures are retired with owner approval. Keep public pendingActions,
  emit/handle/snapshot facades and existing registry adapters.
- Do not start F4/F5, recordStop, further migration, A6 or memory-policy changes.
  No RAM saving claimed; account for the small transport state in normal sanity.
- Laptop checklist: connect/retry Bluetooth while adjusting volume; connect Wi-Fi
  and retry after failure; search rapidly; apply/cancel a charge request if
  supported; close/reopen panels and restart shell/Settings without stuck busy.

**Review decision:** approve F3 only, including clientSerial/actionPending and the
compatibility policy. This document does not start runtime implementation.
