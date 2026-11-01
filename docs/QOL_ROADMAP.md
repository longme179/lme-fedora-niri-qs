# Proposed QoL expansion roadmap

2026-11-01. **Planning only; implementation is not authorized.**
The existing [roadmap](ROADMAP.md) remains owner-accepted **100% (10/10)**.
This is a separate menu of possible improvements, not new unfinished work added
to that denominator. Start with one small family, review its value, then choose
whether to continue. None of the sixteen proposals is a release requirement.

Evidence baseline: runtime `74d6c5e`, acceptance documentation `c09c8a4`;
`main` was `5e4a4d8` and PR #42 remained open when researched. This planning
branch is stacked on #42. No runtime, tests, schemas or real user files change.

Read [feature specifications](QOL_FEATURE_SPECS.md) for behavior and edge cases,
[delivery constraints](QOL_DELIVERY_PLAN.md) for ownership/resources/testing, and
[source notes](QOL_REFERENCE_NOTES.md) for nine inspected upstream shells.

## Selection criteria

Prioritize repeated actions saved, discoverability, recoverable mistakes and
reliable device handoff. Prefer an existing service with a small new affordance
over a new subsystem. A feature that needs an unproven identity, transaction or
hardware contract follows a small feasibility check; it is not disguised as a
simple menu. Preserve Liquid/Smoked appearance and Material/Battery Saver behavior.

The owner's ordinary-use aggregate RAM acceptance stands. New work must retain
the <=400 MB steady / <=500 MB ordinary-active target, including open Settings,
backends and workers. No new resident daemon, executor, universal event bus,
widget sampler or background indexer is proposed. Do not revive D1 profiling.
A6 polling/cache/power-policy changes remain outside this plan.

## What is already present

| Area | Existing behavior | Actual missing increment proposed here |
| --- | --- | --- |
| Launcher | Usage ranking, Launchpad, app/window/file/emoji/calculator modes | Settings page results; selected-app actions; keyboard window destinations |
| Settings | Search, page IDs, standalone reuse/startup barrier | Search those same pages from Launcher; no second search index |
| Audio | Default input/output selectors; per-app volume/mute | One-action output cycle; ports/profiles; conditional stream routing |
| Notifications | Grouping, search, persistent history, actions, permanent app mute, global timed/sharing DND | Group collapse/clear, history recovery, per-app expiry |
| Capture | Folder field, PNG export, annotation/OCR/undo, image click-through | Open successful export's location; copy its path |
| Clipboard | Plain text/images, history/search/pins, capture pause | Deliberate multi-item text composition; not another plain-text mode |
| Focus | 25/5/15-minute timer, pause/reset, stopwatch | Configurable durations and a small preset list |
| Windows | Overview move/drag/drop and compositor validation | Keyboard-accessible destination menu in Launcher |
| Devices | Bluetooth pairing/connect/disconnect and battery alerts | Rename/Forget with clear ownership and confirmation |
| Display | Preview/Keep/Revert watchdog, mirroring, Saver restoration | Manual named layouts through the same transaction |
| Other | Media-player selector, lyrics, per-output wallpaper/playlists/transitions, configurable OSD | No duplicate implementation proposed |

## Candidate portfolio

Effort means focused engineering days including tests and documentation, assuming
one developer familiar with LME. It is a sizing range, not a delivery promise.
Risk is correctness/integration risk, not visual complexity. Confidence concerns
the estimate. Hardware validation and owner review availability are additional.

| ID | Missing QoL | Priority / repeated value | Effort | Risk / confidence | Primary reference |
| --- | --- | --- | --- | --- | --- |
| Q01 | Settings page quick jump from Launcher | First / frequent | 1–2 d | Low / high | end4-pC |
| Q02 | Window destination menu from Launcher | First / frequent keyboard workflow | 1–2 d | Low / high | LME move contract; desktop workspace UX |
| Q03 | Cycle audio output with actual-device feedback | First / frequent device handoff | 1–2 d | Low–medium / medium | Caelestia |
| Q04 | Installed app secondary actions | Next / frequent for supported apps | 3–5 d | Medium / medium | Noctalia, DMS |
| Q05 | Open capture folder / copy saved path | Next / frequent sharing workflow | 1–2 d | Low / high | GNOME, Noctalia |
| Q06 | Custom focus durations/presets | Next / regular focus workflow | 2–3 d | Low–medium / medium | end4-pC + LME composition |
| Q07 | Compose selected clipboard text | Next / repeated copying | 2–3 d | Medium / medium | LME proposal, not an upstream claim |
| Q08 | Collapse and clear a notification group | Next / high-volume apps | 1–2 d | Low–medium / high | COSMIC |
| Q09 | Restore one dismissed history batch | Next / mistake recovery | 2–4 d | Medium / medium | Noctalia history boundary + LME design |
| Q10 | Timed per-app notification mute | Next / recurring interruptions | 1–2 d | Medium / high | DMS expiry predicate |
| Q11 | Optional XKB layout indicator/select | Conditional / high for multi-layout users | 2–4 d | Medium / medium | Serpantinum, Noctalia, Cinnamon |
| Q12 | Bluetooth Rename / Forget | Conditional / occasional but useful | 2–4 d | Medium / medium | Noctalia; BlueZ capability check |
| Q13 | Audio ports / profiles | Conditional / headset and HDMI users | 3–5 d | Medium–high / medium | DMS |
| Q14 | Route one live app stream to an output | Spike first / valuable when supported | 1–2 d spike + 3–5 d | High / low | Plasma, Noctalia |
| Q15 | Manual named display layouts | Later / desk/presentation workflow | 3–5 d | High / medium | DMS |
| Q16 | Saved VPN/WireGuard quick connect | Later / depends on actual usage | 3–5 d | High / medium | GNOME |

Q02 is a new access path to existing behavior, not a new window-moving engine.
Q07/Q09 are original LME compositions; the references do not prove identical
upstream features. Source presence does not prove upstream efficiency or quality.

## Recommended implementation families

Each family is a separate future branch, 3–6 related features, one review stop.
The proposed names do not authorize branch creation or implementation now.

1. **A — Navigation/handoff: Q01, Q02, Q03.** Best first branch
   (`feature/qol-quick-actions`): three useful deltas, no new durable settings
   required. Do Q01, Q02, then Q03. Preserve app ranking, window focus semantics,
   gesture defaults and default-microphone selection. Estimate **3–6 d**.
2. **B — Everyday tools: Q04, Q05, Q06, Q07.** App actions, saved capture handoff,
   timer customization and clipboard composition. Reuse existing domain owners;
   these do not become a generic Utilities service. Estimate **8–13 d**.
3. **C — Notification recovery: Q08, Q09, Q10.** One notification-owned reducer,
   one persistence path, consistent group menu. Q08 precedes Q09; Q10 is
   independent but shares admission tests. Estimate **4–8 d**.
4. **D — Input/device controls: Q11, Q12, Q13.** Approve only if these devices are
   used. Protocol/profile/BlueZ checks precede each implementation; unsupported
   capabilities stay hidden or explain the limitation. Estimate **7–13 d**.
5. **E — Conditional system integration: Q14, Q15, Q16.** Reserve this family;
   Q14 is not promised before its mapping spike. These are independent domains,
   so smaller scoped work may be preferable if one proves costly. Estimate
   **10–17 d**, including Q14's spike, with low aggregate confidence.

Families A+B total **11–19 focused days**; allow roughly 20% integration/review
contingency when scheduling (**13–23 d**, rounded). All five total **32–57 d**
before contingency (**39–69 d** with 20%). This is portfolio sizing, not an
obligation to implement everything or an estimate of calendar time. Re-estimate
after A using actual change surface and review cost; drop low-use items freely.

## Dependencies and stop points

| Dependency | Consequence |
| --- | --- |
| Existing Settings registry/page opener | Q01 uses it directly; no schema/source scraping |
| Existing validated window action provider | Q02 adds UI only |
| Actual PipeWire default/readiness | Q03 cannot declare success from a preference hint |
| Desktop Action parsing/terminal semantics | Q04 must pass fixtures before launch UI ships |
| Capture-owned successful export identity | Q05 cannot broaden generic `fileOpen` |
| Notification group reducer | Q08 → Q09; only history snapshots are recoverable |
| Existing niri stream + supported keyboard protocol | Q11; no second watcher |
| Current BlueZ/Pulse topology identity | Q12/Q13/Q14 reject stale/ambiguous targets |
| Existing DisplayControl transaction/watchdog | Q15; no parallel restore implementation |
| Existing NM keyring/agent capability | Q16; unsupported auth opens external management |

Do not build generic operation receipts, an Undo framework or a command bus for
family A. Where a later result UI needs exact operation identity, specify that
domain's receipt before coding; global `lastResult` is insufficient. If the
capability cannot be implemented with the current contract, defer that candidate
rather than expanding the infrastructure silently.

## Deliberately deferred

- **Universal command palette / per-setting deep links:** after Q01 demonstrates
  demand. Requires typed declarative command/anchor metadata the current catalog
  does not have. No central parallel list, JSON callbacks or arbitrary scripts.
- **Per-setting Reset + generic Undo:** authoritative context defaults plus
  compare-and-restore inside the existing Preferences lock and per-intent result
  receipts. A UI read-then-write would overwrite concurrent Settings edits.
- **Timer restart recovery:** separate runtime journal, suspend/wall-clock and
  duplicate-completion contract. Q06 keeps today's restart-reset behavior.
- **Timed clipboard resume:** worker/main expiry agreement and suspend/restart
  semantics need their own scope; capture pause already exists. No poller added.
- **Safe eject / external mounts:** UDisks2, polkit, busy files and device identity
  need a dedicated design. Opening a folder is not proof it can be unmounted.
- **Automatic dock/audio/VPN/scenes/power policies:** A6 remains out of scope.
  No auto profile switch during calls, no auto GPU launch/probing, no new reconnect
  daemon, no background indexer, online assistant or dependency stack.
- **Visual overhaul:** new controls inherit the existing glass/material/theme and
  motion policy. No extra full-screen blur, black selected text or lower quality.

## Defaults recommended for future authorization

| Choice | Recommendation and trade-off |
| --- | --- |
| Q01 search discovery | Explicit `,` Settings mode + visible hint; preserves existing app ranking, costs an extra character |
| Q03 activation | Add button/menu action first; optional bar gesture, no changed default binding; less surprise than hijacking middle click |
| Q04 action ranking | Secondary menu only, no action results in ordinary app search; less search clutter, one extra step |
| Q06 running timer edit | Current session keeps its captured duration; edits affect the next session; predictable rather than live reset |
| Q07 composition order | Numbered selection order, newline separator, explicit Copy combined; no auto-paste or rich formats |
| Q09 lifetime | One bounded batch until center close or next dismissal; avoids a new expiry timer, shorter recovery window |
| Q10 mute clock | Absolute wall-clock expiry, no replay; suspend counts, clock changes are visible policy limitations |
| Q11 language authority | XKB only, opt-in module; avoids competing with Fcitx/IBus |
| Q12 Forget | Explicit confirmation; keep pin/history data, offer separate cleanup later |
| Q13/Q14 capability | Existing pactl when verified, otherwise Advanced audio; fewer supported systems rather than guessed IDs |
| Q15 profile match | Exact connectors/topology in v1; refuse mismatch rather than guessing monitor identity |
| Q16 credentials | Existing NM/keyring, external manager for interactive auth; no shell secret store |

These choices are planning recommendations, not approved behavior/API changes.
The next owner prompt can authorize **family A only** and accept or adjust its
three defaults. Subsequent families remain optional. Planning completion and
future feature delivery must be reported separately from the closed 100% roadmap.
