# Delivery and resource plan for substantive workflows

2026-11-01, revision 2. Companion to [the revised roadmap](QOL_ROADMAP.md).
Planning only. This replaces the earlier A–E shortcut-family delivery order.
Ponytail keeps scope small; Modularity keeps rules/state with their domain owner.
Neither skill adds an audit bureaucracy or runtime service.

## Work by vertical workflow

| Workflow | First useful branch scope | Prior proof / existing owner |
| --- | --- | --- |
| W1 Audio | Ports, profiles, supported live-stream destination and observed outcomes | Pulse/PW mapping; existing audio provider/PipeWire model |
| W2 Network | Saved VPN, wired profiles, common conflict/error handling; hotspot separately | NM UUID/device/auth; existing nmcli/Wi-Fi admission |
| W3 Displays | Save/manage, topology review, protected profile recall | Existing DisplayControl/layout/watchdog |
| W4 Removable media | Inventory, mount/open, safe-remove with busy/auth/sibling handling | UDisks/identity/auth capability; new domain owner |
| W5 Work sets | Definitions, reviewed app launch/reuse, per-entry outcome; placement gated | Shared launch primitive + exact window association |
| W6 Personal recovery | Domain selection, snapshots, validated per-domain restore | Existing settings export + Notes/Notifications owner readiness; Clipboard later |

A feature is complete when its task-level acceptance scenario works, not when a
panel loads. Unsupported sub-capabilities remain visible limitations. Small menus,
search shortcuts and keyboard affordances are subordinate to that useful slice.
Do not force unrelated workflows into a branch to hit a feature count.

## Architecture and composition

- Extend the existing domain descriptor when it exists; new domains get own
  sources/provider/entry/schema plus one positioned index entry. No competing
  plugin/command registry or executable JSON. New startup metadata need not
  convert legacy host pages/bar modules. Keep existing files/IDs/order in place.
- Feature implementation imports own files and shared/service APIs only.
  Composition roots inject narrow capabilities, never DesktopBackend. Hosts
  delegate; no new domain algorithm in the coordinator or unrelated SettingsView.
- Existing ActionSpec/PreparedWork/complete/presentation, worker pool (two),
  admission and completion emitter remain. Blocking I/O stays off coordinator.
  No new executor/job table/queue, universal bus or backend per widget. A bounded
  work-set plan is a domain operation, not a second persistent scheduler.
- Shared service extractions are justified only by actual reuse: application
  launch semantics for W5, normalized system-device identity for W1/W4, existing
  display transaction for W3. Characterize first; do not relabel private feature
  rules as shared to bypass the dependency guard. No new exception/cycle.
- No file tree reorganization. New source files <=250 nonblank lines; existing
  large files cannot grow. Parser/state/IO boundaries should be independently
  testable without system devices. Keep public facades and current retirement rules.

## Data and compatibility

Only W3 displayProfiles, W5 workSets and W6's additive bundle need new durable
formats in the first proposed slices. W1/W2/W4 use current system authority/state;
no shell credential store or persistent device-route policy. All names/formats in
specifications are proposals to approve before coding, not changed contracts.

Preferences stay one flat settings.json and one schema assembled from fragments.
Explicit portable/appearance membership defaults deny. Preserve lock -> reload ->
merge/token patch -> fsync -> atomic replace, backups/permissions and last-valid
reload. New domain map edits need an explicit under-lock reducer if they promise
entry-level merging; a stale full map is not made safe by file atomicity alone.

Existing JSON settings imports/deploy rollback do not change for W6. New private
personal-data bundle is independent/additive, previewed and validated; no archive
extraction to arbitrary paths, secret export or blind overwrite behind live owners.
Cross-domain atomic restore is explicitly NOT promised. Each domain owns its
snapshot/commit/recovery, and partially completed restoration remains actionable.
Readiness acknowledgment alone is insufficient: owner revision/reservation must
remain valid through preflight backup and commit, including delayed autosave.
Unsupported reservation/external-writer conflicts get manual-copy recovery rather
than an unsafe overwrite or claimed universal filesystem CAS.

ActionPending/clientSerial/global lastResult do not provide a generic exact-intent
receipt for every UI. Reuse exact domain token/sequence where available; explicitly
specify correlation for new multi-step plans before implementing progress/Retry.
Ack is not completion, requested profile is not actual device state, and failure
after a side effect is not permission for an automatic retry or fallback mutation.

## Resource envelope: bounds, not invented headroom

Accepted ordinary-use aggregate RAM remains <=400 MB steady / <=500 MB active,
including main QS/backend, owned workers and open Settings/backend. The owner's
btop acceptance is not a newly instrumented baseline and reveals no precise spare
headroom. Do not subtract VM RSS from that observation or re-open D1 profiling.

| Workflow | Normalized metadata / retention bound | Heavy operation and release rule |
| --- | --- | --- |
| W1 | <=128 records / <=256 KiB inventory, only current needed state | Bounded pactl query/action/read-back; discard stale node refs and closed detail models |
| W2 | <=64 saved non-Wi-Fi profiles / <=128 KiB, existing Wi-Fi not duplicated | One admitted adapter/profile mutation; no monitor or credential retention |
| W3 | <=16 profiles, 8 outputs/profile, <=64 KiB persisted payload | Reuse current preview/watchdog; no extra process lifetime |
| W4 | <=32 drives/128 volumes / <=256 KiB normalized view | On-demand UDisks calls; no file crawl, new agent or LME daemon |
| W5 | <=12 sets/12 entries each / <=64 KiB definitions; one active plan | Launch user payloads through existing service; no second scheduler or hidden retries |
| W6 | <=1 MiB preview; <=256 MiB uncompressed bundle preflight | Stream <=256 KiB chunks; SQLite/parser overhead separate; remove staging on error |

These caps limit inputs/retention, not physical memory. Python/JS/QML allocations,
Qt layers and SQLite page cache cost more than serialized bytes. Device enumeration
must be complete for a mutation: if capped/truncated, refuse rather than acting on
a partial sibling/profile inventory. Streaming a large archive is not loading it
all into RAM. Disk-space exhaustion and runtime command-output limits are tested.

Zero added LME resident process/periodic timer is the design requirement. Existing
NM/PipeWire/BlueZ/UDisks are shared OS services; UDisks is an explicitly disclosed
optional prerequisite, not a new free helper or silently installed daemon. Count
owned workers/temporary operation overhead honestly. User-launched app sets and
external auth/file managers are payloads, reported separately rather than omitted.

Use existing models/icon providers/backdrops. No new icon/image cache, preview
thumbnails, full-resolution texture retention, duplicate full-screen blur or lower
quality/Jelly animation. New UI respects effective Material/reduced-motion policy
in Battery Saver and never rewrites saved appearance settings to fit a budget.

For a future runtime branch, use STATE's one ordinary sanity check and existing
accepted-use envelope; if additions do not fit, reduce scope/retention or defer.
No new all-features-at-once stress gate, memory profiler or startup-CI campaign.

## Per-branch execution after authorization

1. Approve one named workflow and its additive contracts; confirm actual-use
   relevance for conditional hardware. Run its short capability check first.
   If identity/auth cannot be proven, narrow/report the scope rather than guess.
2. Add characterization on unchanged production code. New behavior cases fail or
   are explicitly N/A before implementation. No existing assertion/fixture edits
   without approval. Separate tests, implementation and docs commits.
3. Implement cohesive slices through existing owners/services. During work use
   G0 + affected units; QML also G1 + relevant native case. Disposable XDG/private
   Sway/D-Bus only. Revert a failing committed step rather than fixing forward.
4. On final runtime head run G0–G4 + G6 polling once; report pass/fail/skip counts
   and reasons. One sanity: ten preview/Settings launches main vs head, medians
   only; QS/backend RSS at T+10 s. Existing stop flags: >+100 ms Settings / >+10% RSS.
5. Review actual resource/lifecycle ownership and scoped laptop behavior. Record
   <=30-line migration entry with adapters/retirement and <=6-line laptop checklist.
   Owner reviews/merges. Next workflow is a new authorization, not automatic scope.

Hardware validation is essential but proportionate: W1 actual headset/routing,
W2 actual NM/keyring/AP, W3 actual output/hotplug, W4 actual USB/SD/auth, W5 actual
niri window association, W6 actual owner coordination. Mark each “needs real-session
check” until run; a mocked success or skipped native test does not prove it.

## Recommended first authorization: W1

Capability check: identify real server/streams/sinks/cards, prove stable mappings
and profile read-back. Then ports/profile controls and supported live-stream routes
in one bounded audio branch. Keep current defaults, volume/mute, Bluetooth pending
and theme behavior unchanged. Do not implement persistent app policy or Follow
default unless its distinct metadata-clearing contract is separately proven.

Laptop checklist for that future branch (max six lines):
1. Use wired/Bluetooth headphones and speakers; inspect actual ports/profiles.
2. Change a supported port/profile; verify real audio and visible read-back.
3. Route two supported active apps to different sinks; verify by listening/state.
4. Disconnect/reconnect during a selection; no wrong target or stuck pending.
5. Use a microphone/call; no automatic profile switch or hidden mute change.
6. Close/reopen with Liquid/Saver/Settings; normal RAM and lifecycle remain intact.

The current branch changes Markdown only: G0 once, no native gates or launch/RSS
sanity. This verification cannot establish any of the proposed runtime capabilities.
