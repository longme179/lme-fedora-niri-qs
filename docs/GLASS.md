# Liquid Glass

How the shell's Liquid glass surface style works, how to tune it, and how to
fix common problems. This describes the behavior **shipped on `main`**
(through PRs #87–#91 / issue #77); every claim here matches the code.

## Hybrid model (wallpaper lens + compositor blur)

Glass is a hybrid of two layers that can work together:

1. **Backdrop snapshot (the lens source).** `GlassBackdrop`/`GlassState`
   (`qml/services/GlassState.qml`, `qml/components/GlassBackdrop.qml`) provide a
   per-window wallpaper snapshot/texture (managed with
   `scripts/glass_snapshot.py`) as the refraction source. `GlassMaterial`
   (`qml/components/GlassMaterial.qml`, used by glass surfaces such as
   `GlassPanel`/`GlassOptics`) samples that backdrop and feeds the single-pass
   lens shader `qml/components/shaders/liquid-glass.frag` (SDF rounded box,
   bevel normals, IOR refraction, chromatic dispersion, golden-angle blur LOD,
   cursor specular, grain, fillets, and glass-on-glass nesting via `nest`).
   When no valid snapshot/backdrop is ready, the lens falls back to its
   neutral/color base (the wallpaper-lens path does not live-capture app
   pixels).

2. **Compositor blur (niri ext-background-effect, opt-in).** On niri ≥ 26.04 the
   compositor can blur the region behind shell surfaces. The shell writes an
   owned snippet `~/.config/lme-shell/liquid-blur.kdl` **only** when you click
   **Save niri blur snippet** (`glassBlurApply`, `scripts/liquid_glass.py` /
   `scripts/desktop_backend.py`). Per-surface blur is requested through
   `BackgroundEffect`/blur regions (`SurfaceBlurRegion`, `GlassState`), with
   jelly-deforming popups following strip regions.

**True-backdrop yield.** When the **True backdrop** preset is applied
(`appliedBlur = "true"`, `xray false`), niri ≥ 26.04 is present, and a
surface's blur region is active (`Theme.compositorTrueBlur`/bar/popup gates in
`qml/theme/Theme.qml`), the lens yields to the compositor frost: it renders a
transparent base (bounded tint/alpha, compositor-yield cap), keeping
rim/tint/grain so the app behind the panel appears frosted instead of the
wallpaper snapshot. Otherwise (Frosted preset, no snippet applied, older niri,
or no active blur region) the wallpaper-lens behavior is used.

## Requirements & status

- **niri ≥ 26.04** is required for compositor blur presets
  (`MIN_NIRI=(26,4)`, `probe_niri_version`/version gate in
  `scripts/liquid_glass.py`; `popupBlurSupported`/`niriVersion` in
  `scripts/desktop_backend.py`). `scripts/doctor.sh` checks for 26.04+.
- **Opt-in.** Choosing a backdrop preset only saves the preference; nothing is
  applied until **Save niri blur snippet** writes `liquid-blur.kdl` (it refuses
  to overwrite a user-owned/non-marker file or to write below 26.04). Include it
  after `popup-blur.kdl` in your niri config, then `niri validate`. Applied
  includes reload when applied.
- **Frosted** (`xray true`, default preset) blurs only the wallpaper behind
  panels — cheapest on the iGPU. **True backdrop** (`xray false`) also blurs
  app windows behind panels — **experimental** and can dip during window
  animations. The snippets differ only in the `xray` value.
- **Hairline border.** While a preset is applied, glass panels/bar pills draw a
  1px hairline in the glass border token to mask rounded-corner blur-region
  aliasing; it clears with no applied preset. Smoked mode is untouched.

## Settings (Liquid glass material)

Settings → Appearance → **Liquid glass material** (visible in Liquid glass
mode). Presets are **starting points, not modes**: applying one writes the
existing glass values; sliders remain editable and the selection is not a
persisted "active mode".

### Material presets (factual values)

| Preset | tint | opacity | blur | rim | edgeWidth | grain | passes | offset | summary |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Clear | #f0081420 | 0.65 | 1 | 1 | 1 | 0.004 | 2 | 3 | Default crisp lens. |
| Frosted | #f0182436 | 0.90 | 3 | 0.8 | 0.5 | 0.010 | 1 | 2 | Budget matte: heavier tint/blur, thin edge, fewer passes. |
| Vivid | #f00a1a28 | 0.55 | 1.5 | 1.6 | 1.5 | 0.002 | 3 | 4.5 | Vivid refraction: lighter tint, stronger rim/edge, 3 passes. |

### Controls (real keys, from `config/liquid-glass.json`)

**Lens** (panel tint + `PreferenceSwitch adaptiveContrast`): `blur` (Lens blur,
default 1, 0–4, 0.1), `rim` (Edge highlight, 1, 0–2, 0.05), `edgeWidth` (Edge
width, 1, 0.25–3, 0.05), `grain` (Grain, 0.004, 0–0.08, 0.001), `opacity`
(Panel tint opacity, 0.65, 0–1, 0.01). `tint` (Panel tint, `#RRGGBB`/`#AARRGGBB`,
default `#f0081420`) is set via the tint picker/field. `adaptiveContrast`
darkens glass on bright backdrops and clears it on dark ones (bounded; contrast
floor keeps white text above 3:1 on bright backdrops).

**Compositor** (niri 26.04+, hidden when unsupported): backdrop preset
(Frosted/True) + `passes` (Backdrop blur passes, 2, 1–4, 1, compositor-wide)
and `offset` (Backdrop blur spread, 3, 0.5–8, 0.5, compositor-wide). These
apply only when you save the niri snippet and affect every surface requesting
blur, including Smoked mode; higher values cost GPU time.

**Status line** (`glassBlurStatus`, derived in QML, no backend/file check):
`unsupported (niri < 26.04, detected <version>)` when compositor blur is not
supported; `applied (<preset>)` when `appliedBlur === blurPreset` and set;
otherwise `pending (save snippet)`.

**Other:** `glassSelection` (refractive selection lens), `reducedTransparency`
(Accessibility, swaps to opaque Smoked surfaces live, blur off — same path as
battery saver), **Reset glass** (restores glass values; does not rewrite an
already applied niri snippet).

> Note: `feather`, `smearing`, and `brightness` are **not** shipped glass
> controls/keys; only the keys above exist.

## Frosted vs True backdrop

| | Frosted (`xray true`) | True backdrop (`xray false`) |
|---|---|---|
| What blurs | Wallpaper only | Wallpaper and app windows behind panels |
| Cost/status | Cheapest on iGPU, default | Experimental; can dip during window animations |
| Lens behavior | Wallpaper-lens (snapshot) | Yields to compositor frost when applied + niri ≥ 26.04 + blur region active (bounded tint/alpha); else lens fallback |
| How to use | Select preset, **Save niri blur snippet**, include `liquid-blur.kdl` | Same; gated by version/support |

## Performance (measured facts, PR #91 / issue #77)

**Idle CPU** (3×60 s, same wallpaper, machine untouched,
`/proc/<pid>/stat` utime+stime/`_SC_CLK_TCK`; no `pidstat`). **Zero frames are
rendered at idle by design** (the dirty gate in `GlassMaterial`/`onAfterAnimating`
skips work when unhovered and static; under Wayland nothing renders on no
change), so means are indistinguishable and show **no regression**:

| window | BEFORE main quickshell % | BEFORE main backend % | BEFORE main total % | AFTER (merged) quickshell % | AFTER backend % | AFTER total % |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 11.649 | (n/a w1) | 11.649 | 11.832 | 1.383 | 13.215 |
| 2 | 12.082 | 1.517 | 13.599 | 11.965 | 1.433 | 13.399 |
| 3 | 11.966 | 1.400 | 13.365 | 11.866 | 1.367 | 13.232 |
| **mean** | **11.899** | **~1.46** | **~12.87** | **11.888** | **1.394** | **13.282** |

Per-thread idle (60 s, 0 frames, quickshell process): main 4.13%,
QSGRenderThread 2.53%, WaylandEventThr 2.12%, quickshell:cs0 1.13%,
quickshe:gdrv0 0.83%, quickshell:gl0 0.83% (process 11.57%).

**Telemetry:** `qml/services/FrameLogger.qml` is env-gated
(`LME_GLASS_TELEMETRY=1`), allocation-free when unset, samples per rendered
frame and records per-class `p50`/`p99`/count over a 128-sample ring (flush
logs a line). The **6-scenario p50/p99 table** (glass off / Frosted / True ×
idle / jelly in flight / hover) was **not measured** in the #77 run (pointer
automation unavailable; ydotool absent, wtype cannot move the pointer) — measure
with `LME_GLASS_TELEMETRY=1` across preset cycles + restarts; do not assume
numbers.

## Troubleshooting

- **No compositor blur / panels not frosted by the compositor.** Compositor
  blur needs niri ≥ 26.04 and an applied snippet: pick a preset and click
  **Save niri blur snippet**, include `~/.config/lme-shell/liquid-blur.kdl`
  after `popup-blur.kdl` in your niri config, `niri validate`. Check the status
  line and `scripts/doctor.sh`. “Unsupported” = version gate; “pending (save
  snippet)” = not applied/selection differs. Below 26.04 the lens blur, tint
  and snapshot backdrop still work; compositor blur does not.
- **Panels show wallpaper / stale look over apps.** True-backdrop frosting
  applies only when the True backdrop preset is applied, niri ≥ 26.04, and the
  surface’s blur region is active (gated per bar/popup); otherwise the
  wallpaper-lens is shown. Frosted preset blurs wallpaper only by design.
- **Glass looks dead/flat on a color wallpaper.** Refraction samples the
  wallpaper snapshot/backdrop; a uniform or unavailable image gives little to
  refract. Ensure a wallpaper image is set/available; the lens uses a
  neutral fallback when no valid snapshot/backdrop is ready.
- **Glass off / opaque surfaces (by design).** Battery saver, **Reduced
  transparency** (Accessibility), software rendering, or `surfaceStyle = smoked`
  disable glass/blur paths. Toggle Reduced transparency off or restore Liquid
  glass in Appearance.

## Attribution

The liquid-glass renderer (shader/optics/nesting) and related references adapt
[Serpantinum](https://github.com/ilyamiro/serpantinum) (AGPL-3.0-or-later) by
Illia Miroshnichenko. Selection-lens timing references `GlassLens.qml`. See
[THIRD_PARTY.md](../THIRD_PARTY.md) and
[third_party/Serpantinum-NOTICE](../third_party/Serpantinum-NOTICE) for files,
revisions, modifications, and license terms.
