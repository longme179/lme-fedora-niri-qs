# M4a: empty feature catalog infrastructure

Scope: infrastructure and measurement only; no existing feature registration moves.
Baseline: main `186354a` (M3 merged). M4b needs separate authorization.

## Hybrid ordering and ownership

- Existing registry arrays remain authoritative for their legacy entries.
- Keep their exact relative order and metadata; append enabled descriptor entries
  in index order. Within each descriptor there is at most one bar/page/tab entry.
- Alternative: insertion anchors would preserve a converted page's old position,
  but require missing-anchor/cycle rules. Append is the simpler M4a choice.
  A later conversion must explicitly review ordering before replacing a legacy ID;
  M4a is not permission to change the order of an existing feature.
- Reject duplicate IDs within each namespace (feature, bar, settings page, control
  tab), including disabled entries and collisions with legacy registrations.
- Conversion removes the old registration in the same commit. Never shadow it.
- Disabled descriptors retain valid IDs and preference metadata; omit their UI
  projections, without rewriting saved settings/layouts. No schema is consumed yet.

## Data and validation

`config/features.json`: `{"version":1,"features":[]}`. Index records contain
`id`, relative `descriptor`, boolean `enabled`, optional `startup` with all UI entries.
Descriptors: `id`, optional `sources`, `preferences`, `bar`, `settingsPage`, `controlTab`.
Presentation entries carry metadata and a `.qml` resource; duplicated fields must match.
Preferences are inert schema fragments, not generated UI or a new settings writer.
There are no JSON callbacks, executable expressions or dynamic Python imports.

One stdlib reader, `scripts/feature_catalog.py`, parses strict JSON and validates
version, shapes, identifiers, duplicate keys/IDs, required files and file types.
All referenced paths must be relative, contain no traversal, and resolve to files
beneath the checkout after symlink resolution. Disabled entries are validated too.
Consumers can supply their existing legacy IDs/settings keys for collision checks;
the reader does not create another legacy catalog or scrape source code.

## Process boundaries and compatibility

- Backend: bounded validation/cache at its startup concurrent with QML, before
  preferences. No catalog reads on import; verdict uses the snapshot, no new worker.
- QML: cached async index read, cheap validation, no process. Nonempty entries wait
  for the backend verdict before QML resource loading; this trust gate remains.
  Heavy descriptor(id) is lazy/cached with read deadlines. Descriptor-only reader/QML
  startup remains an adapter; CLI new-page discovery needs its key in index startup.
  Publish data/settlement together; cache projections used by BarRegistry.info.
- settings.sh: legacy/canonical catalog HITs use Bash builtins (format: round-4 log).
  MISS uses --page: index read/match only, no descriptor/resource/deep checks.
  Keep exit codes/messages, IPC handshake/focus/recovery. Admission is not validation.
  Explicit feature_catalog.py --check and check.sh retain bounded deep validation.
- While legacy lists exist, a broken/timed-out catalog settles to legacy-only plus
  console diagnostics and the existing ShellState error banner. Never block legacy
  pages or treat catalog failure as missing saved appearance. Settings still waits
  for Theme/backend readiness; openPage()/startupPending() retain their contracts.
- Keep `BarRegistry.info/clone`, `SettingsRegistry.pages/page/search` and
  `ControlRegistry` APIs. Generic URL-entry fallbacks accept descriptor entries;
  all legacy component factories and specialized bindings remain unchanged.
- Integer tab indices are still boundary adapters. Assign appended tabs unused
  nonnegative indices after the legacy maximum; retain existing fallback behavior.

## Tests and cost decision

First pin legacy bar/page/tab metadata and CLI failures on unmodified production.
New reader contracts execute after extraction; native injection uses a fully copied
checkout, with no production hook. Cover disabled IDs, duplicate legacy ownership,
malformed/missing/escaping resources, schema key collisions and Settings readiness.
Do not edit existing assertions. Existing fixture setup may copy the new helper.

Run G0–G3 and polling-only G6 before/after in private XDG/Wayland/D-Bus sessions.
Keep M0's mapped-window endpoint/user scripts and short owned runtime paths.
This does not prove full feature readiness or GPU behavior. Round 3 interleaves
main/A-A, optimization commits, empty/add/replace; round 4 follows its committed
M4A_ROUND4_PREREG.md (60 Settings/30 Preview rounds), one warm-up, fresh non-cache
XDG dirs. Report median/IQR/min/max, 20,000 joint round-block bootstrap resamples
of difference of medians (95% percentile CI), exploratory two-sided Mann–Whitney p.
A/A single-run spread is not a median CI; never compare separate runs.
Empty: CI includes zero or upper <=10 ms on both paths; synthetic replace: upper
<=50 ms on both paths. Add doubles legacy counts; replace removes legacy registrations
and CLI admission in a copied fixture, retaining first-frame factories. Neither models
converted loading/workers, realistic schema payloads or GPU rendering. If the rule
misses, report options and wait. Aggregate c and M4b need separate approval.
