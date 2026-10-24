# Mirroring action family

2026-10-24. Branch `refactor/mirroring-actions`, merged main `b73a7b0`.
Owner authorized the next roadmap family with planning and code on one branch.
Apply Ponytail/Modularity; preserve live/demo behavior, public APIs and ownership.

## Scope and contracts read at baseline

Move mirrorRefresh, mirrorStart and mirrorStop into one synchronous provider.
Use the existing explicit composition/registry; DisplayMirror and its lifecycle
stay in place. UI, shell IPC methods, settings/schema and polling remain unchanged.

- Context admission permits shell and Settings before choosing demo/live.
- The main shell owns the wl-mirror child. Start checks mirroringEnabled, then
  uses controller.start(source, target, display_control.outputs()); stop invokes
  controller.stop(). Refresh installs controller.state(). Existing result strings,
  privacy invalidation and snapshot slots stay at the coordinator's current seam.
- Settings delegates start/stop through the existing shell IPC. Preserve literal
  argv, string validation, exact true acknowledgement and error ordering; only
  then query mirrorStatus. Refresh queries status without sending a mutation.
- Status fallback contains active=false, tool availability and the current shell
  name. Accept only a JSON object with an exact bool active; malformed/absent
  status retains the existing fallback. Settings never owns a second mirror child.
- Demo refresh reuses displayRefresh and clones a projector only for one output.
  Demo start keeps validation order (outputs then enabled); stop preserves other
  state fields. No demo process or disk writes; common result/sequence unchanged.
- Controller cleanup on child exit, disconnect, disable and shell shutdown stays;
  no new executor, scheduler, retry, process, cache or power-policy behavior.

## Sequence and checks

1. Plan commit, then baseline characterization for context/demo results, call
   order, IPC replies/fallbacks, validation, errors, controller lifecycle and state.
   Provider-specific registration/no-fallback is N/A before extraction.
2. One old legacy-routing fixture currently names mirrorRefresh. Propose replacing
   only that input with controlsRefresh; obtain approval before touching it.
   Assertions, timeouts and frozen fixtures remain unchanged.
3. Add mirror_actions.py with narrow capabilities; remove all three live/demo
   branches and legacy admission entries together, lower coordinator size ceiling.
   Keep the demo displayRefresh facade and existing state/shutdown owners.
4. During work: G0 + mirroring/backend/registry/polling units. Once on final
   runtime/test head: G0-G4 and G6, plus the existing opt-in MirrorUiCase in private
   Wayland. All XDG/Sway/D-Bus disposable; no real config/session touched.
5. One ten-launch main/head preview/Settings sanity, medians and T+10 s QS/backend
   RSS. Ask only for >+100 ms Settings or >+10% RSS. No D1 work/CIs/raw evidence.
6. Final migration entry <=30 lines, laptop checklist <=6; push review branch and
   stop. No next family, UI/schema conversion, log-retention policy or A6 changes.

Adapters: public dispatch/controller/import/snapshot facades retire only at zero
consumers plus owner approval; explicit provider discovery retires with equivalent
descriptor ownership/withdrawal/fallback. Real capture protocols/multiple physical
outputs remain needs real-session check, even when simulated lifecycle tests pass.

## Execution result

Implemented on runtime/test head `c174f14`. The owner approved the old test's
legacy-input replacement (844707c), proved passing against unchanged main before
committing. Three entries now use the existing sync registry; controller, shell
IPC and UI stay byte-identical. Final gates/sanity and laptop checks are summarized
in MIGRATION_LOG.md. No subsequent family is implemented by this branch.
