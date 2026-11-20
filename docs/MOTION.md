# Motion tokens and the animation factory

How the shell standardizes movement: one token singleton, four curve roles,
and factory components every new animation is born from. User-facing preset
behavior (Smooth/Expressive/Jelly, speed, bounce) lives in
[CAPTURE_NIGHT_MOTION.md](CAPTURE_NIGHT_MOTION.md#motion-presets).

## The token singleton

`qml/theme/Motion.qml` owns:

- **Pill duration tokens** — `fast` 140 ms, `glide` 260 ms, `standard` 300 ms,
  `morph` 420 ms, `pulse` 420 ms, `shapeshift` 820 ms, `heat` 1100 ms
  (iNiR PillMotion lineage; see THIRD_PARTY.md).
- **Factory duration tokens** — `fade` 180 ms, `fadeExit` 150 ms, `pop` 220 ms.
- **The curve set** — `curveSpatial` and `curveSpatialFast` (may overshoot;
  Material expressive curves ported from DMS Anims.qml, MIT), `curveEffects`
  and `curveExit` (monotonic; for colors, opacity and progress).

Every duration goes through `Motion.scaled(ms)`: it scales with the user's
motion speed and collapses to 0 when animations are off (battery saver or
Settings). Curves never change with the speed slider — the motion preset
decides which curve family applies and how much overshoot `Theme` bakes into
the spatial ones.

## Factory components

| Component | Use for | Knobs |
| --- | --- | --- |
| `MotionAnimation` | numbers that move things (x, y, size) | `role`, `large`, `ms` |
| `ColorMotion` | color changes | Theme duration token |
| `OpacityMotion` | fades (opacity, dim amounts) | `exit`, `ms` |
| `MotionPopup` | animated popups (spring + curve machine) | see the component |
| `MotionValue` | spring-driven values | stiffness/damping from Theme |

`MotionAnimation.role` picks the curve family and the token duration:
`"spatial"` (default family), `"spatialFast"`, `"effects"` (monotonic) or
`"exit"`. Leave `role` empty and set `large` for the legacy slide pairing.
`ms` overrides the token with an explicit value that still scales and gates.

## The rule for new code

New animations are born from the factory components — not from hand-rolled
`Easing.BezierSpline` blocks with local durations. Raw `NumberAnimation`/
`ColorAnimation` stays acceptable only where the factory cannot express the
case. If you need a new duration, add it as a Motion token instead of a local
constant so the animations gate and the speed slider keep working.

## Where the tokens come from

The pill tokens rewrite iNiR's PillMotion set on LME's own gate; the spatial
and effects curves are ported from DankMaterialShell's Anims.qml (MIT); both
carry notices in THIRD_PARTY.md. `Theme.qml` keeps the spring functions
(`springStiffness`, `springDamping`) because MotionPopup and the pill family
consume them through Theme today.
