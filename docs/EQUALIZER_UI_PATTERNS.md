# Equalizer UI Patterns for LME Shell

This note captures the implementation targets for getting Serpantinum close parity while retaining LME's feature boundaries.

## Runtime model

- `serial_io` is not a polling UI; use serpantinum's sync calls only on user actions and in-page refresh.
- The shell surface is the catalog panel `EqualizerPanel.qml` (centered, scrim 0.4),
  opened through `ShellState.togglePanel("equalizer")` from the top-bar module,
  Control Center tile and Audio mixer, plus the Settings → Equalizer page.
  The earlier standalone `EqualizerPopup`/`EqualizerFeature` bootstrap was removed
  (2026-11-06): a popup instantiated under `ShellRoot` has no window to render into,
  and a bootstrap-alive surface probed `eqGet` at every backend start.
- The typed property state for hydra/restore is inside `EqualizerPanel` roots:
  - `gains: [10 floats]`
  - `balance`, `mono`, `swap`, `dynamics`, `bypass`, `dyneq`.
- In-memory state stays only as UI pending detail. The daemon remains authoritative, so reopening the EQ surface calls `eqGet`.
- Prefer full apply commands over telemetry loops: LME does not yet use Serpantinum's JSON state file.
- Every apply path (Panel `apply()`, page Apply button, page presets) auto-starts the
  daemon when the equalizer preference is disabled, then sends `eqApply`.

## Current incremental status

- `eqGet` works from both settings and panel surfaces; both are instantiated on
  demand, so nothing probes while no surface is open.
- Presets are present as two rows on the Settings page.
- Control Center exposes a quick tile; the Audio mixer links to the panel.
