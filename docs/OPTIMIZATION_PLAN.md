# The shell optimization audit and roadmap — measured against end4-pC and serpantinum — 2026-11-13

Owner ask (2026-11-13): audit the whole codebase, not just the clipboard — "tham khảo sao cho
các Shell của ta được tối ưu như họ, có thể cải thiện animations như họ luôn cũng nên". Method:
two subagents (one researching the reference shells, one probing this machine live) plus a
codebase sweep. The AGPL-3.0 relicense (same day) covers pattern and verbatim adoption from
both references (end4-pC GPL-3.0, serpantinum AGPL-3.0; GPLv3 §13 permits the combination).

## What was measured on the live machine (2026-11-13)

- One-shot helper cost: `clipboard.py --state` = 79-81 ms per run; bare `python3 -c pass` =
  11 ms; the 134-module import chain = 30-60 ms (`_colorize` 12.9, `argparse` 8.5,
  `settings_schema` 6.5 ms…); the actual DB work = 0.1-0.9 ms. **~99% of every one-shot is
  interpreter+import overhead.**
- DB speed is NOT the problem: `entries("", "all")` = 0.1 ms, `count(*)` = 0.0 ms, History
  open = 0.3 ms — even on a 42 MB file (which was 99.9% freelist: 13 entries, 8.7 KB live;
  now self-healing VACUUM reclaims it, see the clipboard fix).
- Capture latency: `wl-copy` → DB commit + revision bump = 70-105 ms end-to-end.
- The clipboard refresh bug (fixed in the live-refresh PR): a QML `Timer` without
  `repeat: true` fired ONCE per panel open — captures could never refresh the visible list.

## What the references do (verified in their sources)

| Pattern | Source | License | We have it? |
|---|---|---|---|
| Clipboard: signal → debounce → one-shot list → reactive property; dirty-flag while hidden | end4-pC `services/Cliphist.qml`; serpantinum `src/quickshell/clipboard/Clipboard.qml` | GPL-3.0 / AGPL-3.0 | **Yes now** — revision.txt + FileView watch (the clipboard fix) |
| Debounced niri event-stream + full-state re-fetch (80 ms debounce, 1 s stream revive) | end4-pC `services/NiriBackend.qml` | GPL-3.0 | Partial — 4 services already ride `niri msg -j event-stream`; audit each for the debounce+revive pattern |
| Change-gated property writes + subscriber refcounting | serpantinum `CompositorStateBase.qml`/`NiriState.qml` | AGPL-3.0 | Partial — snapshot Identity merge exists; refcounting of streams not audited yet |
| Central M3 curve/preset library (`emphasizedDecel/Accel`, elementMove family, `Component { NumberAnimation }` presets) | end4-pC `modules/common/Appearance.qml` | GPL-3.0 | **No** — 40 inline `Easing.*` usages across 8 curve types, `BezierSpline` hand-rolled 8 times, no `qml/theme/` curve home |
| Single-progress-value animation driver (one `animProgress` + one Behavior drives size/opacity/origin; asymmetric open/close) | serpantinum `popouts/Osd.qml` | AGPL-3.0 | Not systematically — per-widget ad-hoc |
| Lazy visibility-gated Loader (`active: opacity > 0`) | end4-pC `FadeLoader.qml` | GPL-3.0 | Not audited per-panel; panels instantiate eagerly today |
| Incremental ListModel sync (set/append/remove, never rebuild) + pagination | serpantinum `Clipboard.qml` (`syncClipBoxModel`, page 60) | AGPL-3.0 | No — `state.entries` array reassignment (fine at 50-100 rows; the panel caps display) |
| Region-limited backdrop blur (sub-rect `ShaderEffectSource` + oversample) | end4-pC `FastBlurred.qml` | GPL-3.0 | Different mechanism — we use compositor blur (`BackgroundEffect.blurRegion`), already region-limited; no action |
| Consolidated persistent helper for high-frequency feeds | serpantinum-core (Rust daemon, lease-based) | AGPL-3.0 | No — 89 one-shot Python helpers; each event pays ~80 ms spawn |

## Ranked legs (each is one branch + PR + remote engine verification)

1. **Animation curve library** (`qml/theme/Motion.qml`, new — no pinned strings touched):
   port the M3 curve set (elementMove 500 / elementMoveSmall 350 / enter 400 emphasizedDecel
   / exit 200 emphasizedAccel / resize 300 / menuDecel 350 OutExpo) with reusable
   `Component { NumberAnimation }` presets. Then migrate widgets in batches (EqualizerPanel
   12 animations, StretchIndicator 6, LiquidButton/Feedback). Impact: consistent, tunable
   motion shell-wide; the "animations like them" ask.
2. **Single-progress popup driver**: port the OSD/pop-in pattern (one `animProgress`,
   asymmetric durations, `visible: ... || progress > 0.001`) to the OSD + panel pop-ins.
   Impact: one animation instead of four per surface; clean close-out lifecycle.
3. **Event-stream hygiene sweep**: for each of the 4 niri-stream consumers, verify the
   end4-pC shape (per-line debounce ~80 ms, full-state re-fetch, 1 s dead-stream revive,
   per-line try/catch). Impact: bounded refresh rate during event storms; zero idle cost.
4. **Change-gated writes + refcounting**: adopt serpantinum's `assign()` (skip unchanged
   values before property sets) and `subscribers > 0` gating on the chatty streams.
   Impact: removes spurious QML binding invalidation — the dominant hidden cost.
5. **Lazy panel loading**: FadeLoader pattern for heavy panels (Settings views, media).
   Impact: startup time + steady-state memory (ties into the RSS budget).
6. **Spawn consolidation pilot**: the highest-frequency one-shot paths (the 2 s snapshot
   poll's family) behind one persistent helper speaking newline JSON (SplitParser), with
   1 s auto-restart — the serpantinum-core shape, but Python. Impact: removes ~80 ms per
   event; this is also the natural Q6-era retirement vehicle for the backend poll.
7. **ListModel incremental sync**: if the clipboard panel ever pages beyond ~100 rows.
   Low priority today (display-capped, queries are 0.1 ms).

## Delivered in this session (the ask's first leg)

- **PR: clipboard live refresh** — the `repeat: true` bug, the revision.txt event channel
  (FileView/inotify; a copy refreshes the open list in ~150 ms; zero cost while hidden;
  instant refresh on reopen), and the self-healing VACUUM. Measured before/after on the
  live machine; engine case green remotely.
- **PR: AGPL-3.0 relicense** — LICENSE + 71 SPDX headers + README/THIRD_PARTY statements.
- This audit.

Verification for every leg stays the standing discipline: test-first (local set), sandbox
G0, the owner's machine full G0 with engine cases live, then the live drift day.
