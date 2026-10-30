# Laptop memory workload — 2026-10-31

Branch `chore/laptop-memory-workload`, main `a9108b0`. Deployment is complete.
The next ROADMAP boundary is release evidence, before further migrations.
Apply Ponytail and Modularity: reuse memory_report and public IPC; no new daemon.

## Scope and sequence

1. Characterize current collector and shell/Settings contracts on unchanged main.
   Add new diagnostic contracts before implementation; old assertions stay intact.
2. Add an explicitly invoked stdlib tool. Require one live main instance for the
   selected checkout, enabled workload panels, no existing Settings and a complete
   ownership inventory before sending any UI command. Pin all IPC to instance IDs.
3. Close panels, sample steady, exercise 48 timed open/close requests for Clipboard,
   Controls, Activity, Notifications, Launcher and Power; sample warm-24/warm-48.
   Opening Notifications marks history read; announce this before actions.
4. Open Settings through the existing main-shell Gear route, never a subprocess
   launched by the diagnostic. Preserve the main renderer/environment and executable.
   Require startupPending=false and openPage=true before Settings-open sampling.
   Optionally wait for normal X close and confirm both Settings processes exited.
5. Reuse inclusive PSS, explicit helper --pid roots and the 400/500 decimal MB
   thresholds. Pin persistent PID/start-time identities, distinguish incomplete
   counters from over-budget results, and never silently omit a process.
6. Save a new private JSON report with checkpoints and errors/interruption.
   Never overwrite an existing report, kill a process, alter preferences/theme,
   change rendering quality, or install/start another shell instance.
7. Unit/fake IPC coverage, real copied-checkout private Wayland CLI tests, then
   final G0-G4/G6 once. Product runtime unchanged: no duplicate launch/RSS profiling.
   Update ROADMAP, STATE and release commands; concise migration entry and review PR.

The old unmerged laptop-memory-check prototype is reference material, not a
passing baseline. Its CLI-launch test and unresolved native results are not
imported. New tests pin the Gear route directly; no old assertions change.
Read-only startup queries may retry within a deadline; never replay a timed-out
toggle. Tests use disposable XDG/Sway/D-Bus and only test-owned cleanup.

## Limits and completion

Timed commands cannot establish actual animation completion through current public
IPC. Keep normal laptop defaults (2 seconds open/closed, 5 seconds settling), watch
the UI and stop on an authentication prompt. Record the user-observed theme; no
claim to detect the GPU from the caller environment or to measure VRAM/FPS/peaks.
The warm delta is not a leak verdict. Exit 0 describes the sampled budget only;
helper ownership, visuals and hardware remain needs real-session check.
No resource fix without a demonstrated owner; no D1/A6 changes, schema/action/UI
migrations, retention policy, file moves or release publication in this branch.
