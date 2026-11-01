# Proposed roadmap: complete useful desktop workflows

2026-11-01, revision 2. **Planning only; no runtime implementation authorized.**
This revision replaces the earlier shortcut-first order at the owner's request.
The existing [roadmap](ROADMAP.md) remains accepted **100% (10/10)**. This is a
new optional portfolio, not work added to the completed acceptance denominator.

The earlier plan over-weighted low implementation cost and saved clicks. This
plan prioritizes missing capabilities: completing an audio, network, display,
storage, work-session or recovery task without piecing together external tools.
Small affordances can accompany those workflows, but do not lead the roadmap.

Baseline: runtime `74d6c5e`, acceptance docs `c09c8a4`; main was `5e4a4d8` when
researched. Branch `docs/qol-expansion-plan` is stacked on PR #42. Only documents
change. See [specifications](QOL_FEATURE_SPECS.md), [delivery/resource plan](QOL_DELIVERY_PLAN.md)
and [inspected sources](QOL_REFERENCE_NOTES.md).

## What qualifies for priority

A candidate should complete a missing task, remove a recurring failure/manual
workaround, or protect user data. Assess the value of the whole workflow before
its menus. A new shortcut to an already-complete task is a supporting improvement.
A speculative capability is not ready merely because another shell shows its UI.

Prioritization uses four questions, without a pseudo-precise weighted score:

1. What task becomes possible or reliably recoverable that LME cannot do today?
2. Is that task relevant to this laptop/user, and how often does it recur?
3. Can the result be verified and failures handled without guessing device/window
   identity, losing data or silently changing another setting?
4. What are the implementation, dependency and retained-resource costs?

Known usage includes Bluetooth headphones, media, Wi-Fi and niri. VPN, multiple
monitors, USB frequency and desired app sets are not confirmed. Hardware-dependent
items are valuable conditionally; do not implement all six merely to fill a list.

## The substantive portfolio

Effort is focused engineering days including tests/docs, not elapsed calendar
commitments. Estimates are provisional and include no new RAM/performance result.

| Order | Workflow / meaningful outcome | Existing foundation versus new capability | Effort / confidence |
| --- | --- | --- | --- |
| **W1** | **Complete audio/headset management:** physical port, playback/call profile, supported live-app destination | Defaults and app volume/mute exist; ports/profiles/stream routes do not | 1–2 d capability check + 6–10 d / medium |
| **W2** | **Network connections:** saved work VPN, explicit wired profile, deliberate sharing | Wi-Fi exists and Ethernet connectivity is detected; saved VPN/wired/AP control is missing | 7–12 d VPN+wired; +3–5 d saved-hotspot slice / medium |
| **W3** | **Named display setups:** recall Desk/Presentation through safe preview and rollback | Arrangement/mirroring/Keep-Revert exist; named recall and topology review do not | 4–6 d / medium-high |
| **W4** | **Removable media:** identify, mount/open, safely unmount/power off USB/SD | No UDisks/storage UI or action owner exists | 1–2 d capability check + 6–10 d / medium |
| **W5** | **Manual work sets:** start a declared group of apps; place only provably identified windows | Single app/Launchpad launch and existing-window moves exist; grouped execution/reconciliation do not | 1–2 d identity check + 4–7 d app sets; placement +3–5 d only if proven / low–medium |
| **W6** | **Selective personal-data backup/recovery:** include notes/history with preview and safe domain restore | Full-settings backup/deploy rollback exist; personal data is explicitly excluded | 8–14 d for initial settings+notes+notification scope; clipboard +3–5 d / medium-low |

These are capability families, not six large all-or-nothing releases. Each has a
minimum useful slice and explicit exclusions in its specification. Estimate the
next authorized family after its feasibility check; do not turn the total into a
deadline or implementation authorization.

## Recommended order and branch scopes

1. **Start with W1** because headphone/media usage is established. Prove current
   Pulse/PipeWire identity first. A cohesive future branch contains ports, card
   profiles and supported per-stream destinations, with read-back/error handling.
   If routing is unsupported, report the limitation; do not label the full workflow
   complete or silently substitute a default-output switch. No automatic call policy.
2. **Then W2**, if saved VPN/wired/sharing are used. First branch: saved VPN,
   wired-profile activation and shared conflict/error recovery. Existing Wi-Fi
   behavior stays. Hotspot is a later slice after topology/secret handling checks;
   an external profile editor may configure the first profile, not an invisible prompt.
3. **Promote W3 immediately when multiple output setups are actually used.** Its
   benefit is substantial for docking/presentations and low for a single fixed
   panel. One branch can cover capture/name, topology review and safe recall.
4. **W4 when removable devices are part of normal work.** One branch covers drive
   inventory, mount/open and safe-remove outcomes. New optional UDisks capability
   is explicit; no automatic mount or filesystem maintenance.
5. **W5 gets an early bounded design check if opening 3–6 apps is a daily task.**
   It may outrank W3/W4 by real usage. App-only work sets are useful by themselves;
   true destination placement cannot ship until new-window correlation is proven.
6. **W6 prioritizes avoiding data loss.** Start with clean-owner backup/restore of
   settings, notes and inactive notification history. Clipboard is a separate
   consistency slice; no raw live database copy or generic restore-everything button.

Runtime branches still use 3–6 cohesive capabilities where practical, one review
stop per branch. Do not bundle unrelated workflows to meet a count. Each future
prompt must authorize its scope and additive contracts; this plan authorizes none.

## Dependencies and release boundaries

| Boundary | Required evidence before promising the capability |
| --- | --- |
| W1 stream routes | Unique fresh Pulse/PW mapping; native-only streams explicitly supported or unavailable; actual destination read-back |
| W2 profile controls | UUID plus device identity, NM/keyring/agent support, cancellation and conflict admission |
| W3 display recall | Exact topology/mode validation and existing DisplayControl watchdog/Keep-Revert |
| W4 safe removal | UDisks identity, partition/sibling effects, busy/auth behavior and successful intended drive operation |
| W5 app placement | Exact window IDs or proven launch association; app name/app_id alone is insufficient |
| W6 recovery | Owner-coordinated snapshots/restores, validated private bundle, crash/partial-commit recovery |

No universal event bus, generic multi-domain transaction or additional executor
is needed. Reuse existing owners, shared capabilities, registry/pool and completion
path. A failed identity check means explicit limitation, not best-effort mutation.

## Supporting backlog, no longer the first milestone

The earlier Q01–Q16 IDs remain historical planning references, not a second order.
Promoted: Q13/Q14 -> W1; Q16 -> W2; Q15 -> W3. The other proposed increments are
optional finishing work when they help an authorized workflow:

- Launcher Settings jump, keyboard window menu and app secondary actions.
- Audio output cycle, Bluetooth Rename/Forget, keyboard-layout indicator.
- Capture Open folder/Copy path, configurable focus presets, clipboard composition.
- Notification group collapse/clear, history-only restore and timed per-app mute.

Do not fund these ahead of a missing high-value capability solely because they
are easier. Keep existing app ranking/no-favorites behavior and theme rules.
Named timer recovery, safe per-setting Undo and a universal command palette also
remain deferred; their receipt/locking/clock contracts are separate work.

## Resource, policy and scope limits

- Keep <=400 MB steady / <=500 MB ordinary-active total shell, including Settings,
  backend/workers. Owner's accepted ordinary-use baseline stays closed. There is
  no new measurement, known spare headroom or promise that all proposals fit.
- Zero additional LME resident service, periodic watcher/sampler, executor or
  per-widget timer. Reuse current event stream/pool and demand-driven read-back.
  UDisks is an explicit optional OS dependency, not an LME-owned daemon to install
  or launch silently. External payload costs are reported, not hidden.
- D1 remains closed. A6 still excludes automatic docking, audio/VPN/reconnect
  policies, background backups, polling/cache/power-policy changes. Manual profile
  selection does not authorize changing NM autoconnect or WirePlumber policy.
- Keep stdlib/unprivileged runtime, catalog/schema ownership, no cross-feature
  imports, handwritten Settings and Preferences lock/merge/fsync/atomic replace.
- Preserve glass/animation quality; use effective Material/no-motion policy in
  Saver. No new visual overhaul or resource sacrifice is proposed.

## Decisions recommended before coding

Authorize W1's capability check plus the proven audio slices first. Use transient
live-stream routing, not persisted per-app rules; missing support remains explicit.
For W2, start with already-saved profiles and external interactive-auth handoff.
For W3, manual exact-topology recall; for W4, never force-unmount; for W5, reviewed
app-only start before any ambiguous placement; for W6, opt-in unencrypted private
local backup with explicit warning, never cloud/scheduled sync or invented crypto.

These are planning recommendations. Old roadmap acceptance remains **100%**;
this revised planning task can complete while all new runtime work remains unstarted.
