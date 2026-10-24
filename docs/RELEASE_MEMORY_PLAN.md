# Release memory inventory

2026-10-24. Main d72e48a (selection/application merged), branch
`chore/release-memory-check`. Owner requested the next roadmap step, planning
before implementation. Release evidence is next; stable coordinator IDs stay put.

## Scope

Add a one-shot, stdlib `scripts/memory_report.py` for the laptop checklist.
It reads only the current user's /proc metadata and memory counters; no daemon,
watch loop, runtime integration, settings writes, signals or subprocess commands.
Never collect environment variables or print user command arguments.

- Identify LME Python entry scripts by interpreter/script position and checkout
  identity, not substring matching. Discover their Quickshell ancestors and
  direct Quickshell entry paths; include multiple checkouts/Settings and detached
  log relays after their original backend exits. Never assume one PID tree.
- Include descendants once. Report Launchpad relay payloads separately, plus an
  inclusive total. Other descendants are conservative/reviewable helper counts;
  launched applications may be included and must be reviewed before sign-off.
- Recheck PID/start-time identity around smaps_rollup reads. Missing permissions,
  missing counters, exits/reuse and unattributed Quickshell candidates make the
  report incomplete; do not substitute zero or call a partial total a pass.
- Report per-PID PSS/RSS KiB, grouped PSS and decimal MB; summed RSS explicitly
  double-counts shared pages. No automated release approval or budget guarantee.
- Allow explicit --pid additions for independent/shared helpers or unresolved
  processes. No blanket environment inheritance as proof of ownership. Shared
  daemons and independently reparented payloads need manual inventory review.
- CLI offers human-readable output, --json and a scenario --label. These are a
  new diagnostic command only; existing shell/doctor/API/data formats stay.

## Sequence and checks

1. Commit this plan, then characterize the existing detached relay/payload shape
   on main and commit the new tool contracts (N/A before the tool exists).
2. Implement the small collector/CLI; fixture tests cover multiple checkouts,
   symlinks, detached relays/payloads, duplicate roots, unrelated processes,
   unknown Quickshell, denied/missing counters, PID reuse and secret-free output.
   Add an opt-in private Wayland check with preview, Settings and a detached job.
3. Run affected G0/units; once on final tool/test head run G0-G4/G6, native
   inventory and the normal single launch/RSS sanity. All sessions/XDG disposable.
   Keep old assertions/fixtures untouched and obey 250-nonblank source caps.
4. Document three laptop commands/scenarios: steady, Settings-open, ordinary
   active. List theme/output/media/job context and the process inventory before
   accepting the <=400/500 MB target. Record <=30 migration lines and stop at a
   draft review PR. Physical GPU/radio/restore and laptop totals remain unverified.

No D1 profiling, A6 policy changes, log deletion/retention, provider discovery,
schema/UI conversions, process lifetime changes or claim of a memory reduction.
