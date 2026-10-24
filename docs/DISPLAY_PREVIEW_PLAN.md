# Display preview action family

2026-10-24. Branch `refactor/display-preview-actions`, merged main `201c452`.
Owner authorized the next roadmap family, with planning and implementation on
one branch. Apply Ponytail/Modularity without changing display or power policy.

## Scope and existing contracts

Move five synchronous coordinator entries to the existing registry pattern:
displayRefresh, displayApply, displayConfirm, displayRevert, platformRefresh.
DisplayControl, its detached watchdog, journal format/permissions, preview token,
20-second deadline and Settings transactions remain unchanged. Keep DisplayPage
legacy as previously decided. Mirroring retains its separate IPC routes for now.

- Both shell and Settings admit all five before selecting live/demo.
- Refresh installs exactly DisplayControl.snapshot(). Platform refresh installs
  compositor_features(); neither changes controller/sampling ownership.
- Apply rejects an existing batterySaver job before entering the existing saver
  guard. Inside the guard, start(layout); after guard exit, snapshot/install.
  Preserve exception order and the immediate synchronous result, not worker ack.
- Confirm/revert call decide(token, keep). Confirm then persists displayLayout
  through Preferences.set. Only after success, snapshot/install. A settings-save
  error must not reorder the controller journal mutation or install a snapshot.
- Demo refresh retains the same output fixture and deadline expiration. Demo
  apply validates against that fixture; confirm updates only in-memory settings.
  All demo paths retain their common message/sequence and perform no real apply.
- Snapshot slots, host read-back, pending ownership, shutdown, rollback and
  restore behavior stay at the existing owners. Legacy demo mirrorRefresh may
  still call the public perform_demo(displayRefresh) compatibility facade.

## Work and checks

1. Commit this plan, then characterization tests passing on unchanged production:
   shell/Settings x live/demo, exact results/sequences/snapshot state, guard/call
   order, pending/error paths, expired previews, confirmation persistence failure,
   demo isolation and unknown legacy prefixes. Provider-only cases are N/A first.
2. Add a flat display_actions.py provider with narrow callbacks; register through
   the existing composition root. Move live/demo branches together, lower the
   coordinator ceiling and add ownership without dependency exceptions.
3. During work: G0 and backend/display/battery-saver/registry tests. Before review:
   G0-G4 + G6 once on the final runtime/test head, plus the existing opt-in
   DetachedDisplayCase with a private fake niri to verify initiator-exit rollback.
4. One ordinary main/head sanity: ten preview/Settings launches per arm/path,
   medians and T+10 s QS/backend RSS. Ask only for Settings >+100 ms or RSS >+10%.
   No startup profiling/CIs or new aggregate-memory promise.
5. Final migration summary <=30 lines, laptop checklist <=6 lines. Push review
   branch, owner merges. No later family, A6 or D1 work.

Adapters remain public dispatch/controller/import/snapshot facades and explicit
provider bindings; retire only at zero consumers plus owner approval or equivalent
descriptor ownership/withdrawal/fallback. No new protocol, worker or executor.
Physical output switching, reconnect and restoration need real-session checks.

## Execution result

Implemented on runtime/test head `04ac0d6`: all five entries use the existing
sync registry; the detached watchdog and controllers remain byte-identical.
Characterization passed before extraction; final gates, the separate watchdog
check and normal main/head sanity are recorded in MIGRATION_LOG.md. Mirroring,
schema ownership and UI conversion remain outside this branch.
