# Release session verification

2026-10-25. Main 83f9cad (content schema PR35 merged), branch
`test/release-session-verification`. Owner requested continued completion after
reporting no observed errors. Release verification takes priority over migrations.

## Scope

Add opt-in private-session integration coverage, not shell runtime changes.
Reuse clipboard_slice_fixture.World's copied real shell/Settings, restoring the
copy's original Clipboard worker before launch. Add read-only observability only
to the copy, preserving the production entries and public IPC.

For Smoked and Liquid with Jelly-v2, one virtual output and no real hardware:

1. Start the live UI with the demo backend; keep real private history/server
   lifecycles, disable capture/weather auto lookup, seed only disposable history.
2. Inventory steady main shell/backend/history worker using memory_report.collect.
3. Open Settings concurrently; traverse existing pages and repeat panel open/close
   cycles, including Activity. Wait for both SlideLoaders to unmount after close;
   check no stuck pending, worker multiplication or JS/configuration errors.
4. Start eight synthetic sleeping jobs through the copied Launchpad controller
   in an owner process that exits. Verify ninth-job admission, relay/payload
   inventory, survival across shell restart and worker replacement. Stop only
   these test-created jobs with PID/start-time ownership checks in cleanup.
5. Record scoped aggregate PSS (including/excluding job payloads), process/worker
   counts, profile and scenario. No hard VM memory-budget assertion, allocation
   optimization or laptop/GPU/compositor-blur claim. Report outside-checkout
   processes/issues explicitly; never turn incomplete samples into successful totals.

Use the existing one-shot collector unchanged; no new CLI, report schema,
sampling service, runtime process, executor, polling/cache/power/visual policy.
Desktop/media/device/encoder-heavy workloads remain real-session checks.

## Work order and checks

- Commit this plan, run existing memory/relay unit contracts and native inventory
  against unchanged main as characterization, then commit new test coverage.
- Run the new opt-in cases separately in disposable XDG/private Sway/D-Bus;
  never inspect/stop the owner's real shell. Inspect only test-owned PIDs in cleanup.
- Final G0-G4/G6 once plus existing detached display/watchdog and targeted
  device/media/recovery checks where available. Explicit skips/reasons reported.
- This branch changes tests/docs only: no duplicate startup/RSS comparison of
  byte-identical product code, no D1 profiling/CIs/raw evidence committed.
- Finish with <=30 migration lines, <=6 laptop checklist lines and a draft PR;
  leave actual radio/GPU/backlight/display/whole-laptop PSS sign-off pending.

Do not convert another schema/action/UI family, extend provider discovery, move
files, delete logs/jobs, publish a release or alter existing test assertions.
The scoped VM totals are release evidence for the fixture workload only.

## Execution

Plan 9c12cd5 precedes coverage f7e290e. Existing memory/relay/native contracts pass
11/0/0 on unchanged production. An uncommitted readiness correction waits for
legitimate notificationSave completion without changing assertions/deadlines;
final combined cases pass, plus a separate bounded 48-cycle Liquid probe.
Extended checks expose two existing Wi-Fi fixture failures, reproduced on main:
the fake backend copied current ownership metadata but never advanced ACK.
17b2064 updates only that fake wire; the whole existing test class AST stays
identical and extended checks pass 22/0/0. Product sources remain byte-identical.
RELEASE_CHECKLIST.md records VM budget misses, stable loader/process/registry
counts, the owner's steady snapshot and remaining laptop checks. Final gate
accounting is in MIGRATION_LOG.md; no runtime/cache/render fix is claimed.
