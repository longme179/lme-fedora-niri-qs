# The kitty palette sink (B3-1)

The wallpaper palette feature can also write the live shell palette to
**kitty**, so new kitty windows pick up the same colors as your other
applications. This is the "External app colors" card in Settings →
Wallpaper.

## What it does

- Writes `~/.config/kitty/lme-palette.conf` with the 21 color keys kitty
  understands (`background`, `foreground`, `cursor`, `selection_*`,
  `color0`–`color15`).
- Adds one marked include line to `~/.config/kitty/kitty.conf` (the
  `# BEGIN/END lme-shell palette (managed)` block); new kitty windows read
  the colors through that include.
- When the file changes, running kitty windows are told to reload their
  configuration with `SIGUSR1`. Identical renders are detected and skipped —
  no signal is sent.
- `lme-palette.conf` is removed again by **Undo**; the `kitty.conf` include
  block is removed too.

## Preferences

Set both in Settings → Wallpaper → External app colors (they live in the
shared palette group):

| Preference | Meaning |
| --- | --- |
| `paletteSinkKitty` | Master switch; when on, every palette writer re-renders the sink. |
| `paletteSinkKittyInclude` | Consent to edit `kitty.conf` (one marked include line). |

## When the sink re-renders

- Wallpaper applied while wallpaper-follow is on (the same writers as the
  Material palette itself).
- Palette sync and palette apply from Settings ("Apply now").
- Palette preset apply and **lme Dracula** reset (LME's built-in Dracula
  preset is exported; the default shell theme is not, since its colors live
  only in the shell's QML theme).

## kitty.conf handling

- Exactly one include line per managed block; if it is already there the
  file is left alone (no signal).
- On the first edit the shell backs up your `kitty.conf` once to
  `~/.local/state/lme-shell/kitty.conf.backup`.
- Deleting the include line or other changes elsewhere in the file is
  respected; the block is re-created as needed.
- If the markers drift (the block is edited by hand or removed by other
  means) the status shows **kitty.conf markers drifted — resolve manually**
  and the shell stops editing the file until you fix it.
- Backups are never auto-restored.
- If `kitty.conf` did not exist, the shell creates it for the include and
  **Undo** deletes it again.

## Validation

The sink renders text that passes three gates:

1. The fixed 21-key set with hex-line checking (unknown directives and other
   noise cannot pass).
2. On include insertion or "Apply now": `kitty +runpy` running
   `load_config(..., accumulate_bad_lines)`; any bad line or warning text
   (unknown keys, missing includes) fails validation, and no signal is sent.

Contrast is enforced after rendering: foreground/cursor/`color7`/`color15`/
selection pairs must reach 4.5:1 against the background; the bright and base
variants of `color1`–`color6`/`color8`/`color9`–`color14` must reach 3.0;
adjusted colors are reported in the status row.

## Status

While the master switch is on, the card shows the include state ("include
line active", "include line missing from kitty.conf", "include not allowed
yet", "kitty.conf markers drifted - resolve manually", "include line added to
kitty.conf"), the palette file state, the last apply digest and the PIDs of
the kitty windows it signalled, and any error text. With the switch off, or
if the projection is missing, it shows "status unavailable".

## Limitations

- `SIGUSR1` reload re-reads the whole config, so font zoom resets once per
  palette change. The include line is required for **new** windows.
- Runtime socket control (`allow_remote_control`/`listen_on`) is
  deliberately not used.

## Attribution

The design follows the end-4/dots-hyprland kitty palette sink and
pctrade/end4-pC (both GPL-3.0); see [THIRD_PARTY.md](THIRD_PARTY.md). The
implementation here is original, written from the written design
specification above.
