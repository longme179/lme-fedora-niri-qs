# Equalizer UI Patterns for LME Shell

This note captures the implementation targets for getting Serpantinum close parity while retaining LME's feature boundaries.

## Runtime model

- `serial_io` is not a polling UI; use serpantinum's sync calls only on user actions and in-page refresh.
- `EqualizerPopup` uses `MotionPopup` from `../components/MotionPopup.qml`; this gives the normal spring/enter animation.
- The typed property state for hydra/restore is inside `EqualizerPopup` roots:
  - `gains: [10 floats]`
  - `balance`, `mono`, `swap`, `dynamics`, `bypass`, `dyneq`.
- In-memory state stays only as UI pending detail. The daemon remains authoritative, so reopening the EQ surface calls `eqGet`.
- Prefer full apply commands over telemetry loops: LME does not yet use Serpantinum's JSON state file.
- Presets should eventually call `set` classically through the `eqApply` pathway.

## Current incremental status

- `eqGet` works from both settings and panel surfaces.
- MotionPopup version uses per-control change commits rather than polling.
- Presets are present as two rows.
- Dynamic EQ disables manual controls through `dyneq`.
- Control Center expose a quick tile.