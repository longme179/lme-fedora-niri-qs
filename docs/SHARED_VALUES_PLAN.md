# Shared image paths and peripheral values

2026-10-24. Main d2a58b0 (release-memory PR31 merged), branch
`refactor/shared-domain-values`. Owner requested planning before implementation.
Use Ponytail/Modularity to remove two concrete cross-feature dependencies.

## Read scope and preserved contracts

- Gowall currently imports wallpaper.image_path. Move that exact function and
  EXTENSIONS into the existing shared content_types module. Wallpaper re-exports
  both names; image utilities import the shared validator directly. Preserve
  error text, Unicode/control-character checks, expanded/resolved absolute paths,
  supported extensions, non-existing destination handling and symlink-loop errors.
- Pairing currently imports peripheral_battery.bluetooth_device. Move percentage,
  identity, kind and bluetooth_device unchanged to shared peripheral_values.py.
  Peripheral battery re-exports them for the backend/old consumers; pairing reads
  the shared helper. Preserve strict bool/finite percentage handling, zero,
  address/name/kind fallback, connected gating and property-reader callbacks.
- Kernel reads/merge, BlueZ signals/agent, controller/worker lifecycle, image
  operations, settings/schema, public imports, error/result/snapshot formats,
  UI, polling, cache/power policy and processes stay unchanged.

## Plan before code

1. Commit this plan and the exact legacy-test data proposal. Obtain approval
   before changing the old test inputs; do not edit assertions or timeouts.
2. Add characterization of path/error matrices and both raw/typed BlueZ readers,
   name/identity/battery edge cases, inputs not mutated, module re-exports and
   no import of heavy domain modules by the extracted shared helpers (N/A first).
   Show behavioral tests passing on unmodified main and commit separately.
3. One extraction per helper group. Redirect imports, retain old facades, remove
   each vanished architecture exception in its own extraction commit. Add only
   the shared helper's ownership declaration; no new exceptions or file moves.
4. Affected G0 + content/image/wallpaper/peripheral/pairing/backend units; private
   UI cases where available. Once on final runtime/test head: G0-G4/G6 and normal
   one-branch ten-launch/RSS sanity. Disposable XDG/Sway/D-Bus only; no real config.
5. Final <=30-line migration entry, adapters/retirement, <=6 laptop checks,
   review branch/draft PR, then stop. Leave release hardware/PSS sign-off pending.

Old import facades retire only at zero consumers plus owner approval. Architecture
exceptions are removed only when the static edge is gone; cycles/remaining caps
stay. Source caps 250 nonblank; no new dependency/process or RAM-saving claim.
Provider discovery/schema-format changes, further core-page conversions, log
retention, D1 and A6 remain outside this branch.

## Execution

Plan 3d560c9 precedes characterization 2c1a2e5. Owner approved the test-data diff
on 2026-10-25 (ea26d3c); it passes 20 architecture cases against unchanged main.
Image paths extracted in 1581b09; peripheral values in 7942d92. Both retain public
imports, remove only their vanished exception, and pass their affected gates.
Final gates, one launch/RSS sanity and laptop checks are in MIGRATION_LOG.md.
