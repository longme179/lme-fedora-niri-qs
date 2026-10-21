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
`id`, relative `descriptor` path and boolean `enabled`. Descriptors contain their
matching `id`, optional `sources`, `preferences`, `bar`, `settingsPage`, `controlTab`.
Presentation entries carry plain metadata and a relative `.qml` `entry` resource.
Preferences are inert schema fragments, not generated UI or a new settings writer.
There are no JSON callbacks, executable expressions or dynamic Python imports.

One stdlib reader, `scripts/feature_catalog.py`, parses strict JSON and validates
version, shapes, identifiers, duplicate keys/IDs, required files and file types.
All referenced paths must be relative, contain no traversal, and resolve to files
beneath the checkout after symlink resolution. Disabled entries are validated too.
Consumers can supply their existing legacy IDs/settings keys for collision checks;
the reader does not create another legacy catalog or scrape source code.

## Process boundaries and compatibility

- Python backend: load/cache metadata once through the reader; validate against
  its existing bar IDs and preference keys. No dispatch/schema/polling changes.
- QML optimization a: one cached async FileView index read, cheap structural
  parsing, no extra Python reader process. Deep validation stays in Python;
  nonempty UI entries wait for the existing backend's validation verdict.
  Descriptor presentation data uses async reads with a bounded startup deadline.
  a measured +69.7 ms for synthetic Settings; b uses optional record.startup for
  bar/page/tab metadata. Heavy descriptor(id) data loads on first use, with a
  per-read deadline. Descriptor-only records remain a compatibility adapter.
  Python still validates every descriptor at boot/CLI/check time. c needs approval.
  Project through the existing registries. Their merge
  boundary checks collisions with their actual legacy arrays, including disabled
  entries. No per-widget process, file watcher, eval or environment index override.
- Settings CLI/check.sh: deep-validate through the same bounded Python reader;
  keep unknown-page messages/exit codes and existing IPC/visible-window handshake.
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
Measure five process/cache-cold launches per path using M0's mapped-window method.
M0's EPYC 7763 is unavailable here (EPYC 9V74); retain historical numbers and measure
an untouched main copy on this same machine as the paired baseline, explicitly
labeling this substitute. Measure empty and synthetic catalogs identically.
Synthetic entries model metadata I/O/validation/projection, not feature execution.
If projected added median exceeds 50 ms on either path, stop for owner review.
