# Delivering QoL without growing another shell inside LME

2026-11-01. Planning companion to [QOL_ROADMAP.md](QOL_ROADMAP.md).
No runtime changes, milestone authorization or new standing gate is introduced.
Ponytail keeps the implementation small; Balanced Coupling keeps domain rules
with their owner and stable infrastructure shared.

## Ownership and change surface

| Candidate | Domain owner / existing seam | Allowed composition touch |
| --- | --- | --- |
| Q01–Q02 | Launcher result/menu helpers; SettingsRegistry/shared page opener; existing window provider | Launcher delegates typed activation; no domain code in SettingsView |
| Q03 | Shared audio service, current PipeWire model/OSD | AudioMixer/optional BarGestures delegate; additive text/status OSD variant |
| Q04 | Desktop-entry parsing + existing application/window launch owner | Launcher menu, narrow provider binding |
| Q05 | Capture controller/export state and capture action provider | ScreenshotEditor delegates validated token operation |
| Q06 | FocusTimer + preset schema/editor | Existing TimerWidget loads own editor |
| Q07 | Clipboard worker/state + composition reducer | ClipboardPanel selection UI only |
| Q08–Q10 | Notifications admission/history/reducer + existing schema | Center/group menu; no separate notification daemon |
| Q11 | Compositor state/parser + layout action, own bar entry | Existing niri stream delegates keyboard events |
| Q12 | BlueZ device action owner | Existing Devices menu; shared battery values only |
| Q13–Q14 | Audio identity/parser/action owner | Mixer consumes service; no Bluetooth implementation import |
| Q15 | Display profiles + existing transaction/layout service | Existing Displays page, no direct Saver/Mirror imports |
| Q16 | NetworkManager profile/action owner | Network details and existing network mutation admission |

Keep existing files in place; own new helpers may live in feature folders or
beside their domain. Prefer extending an existing owner over inventing a second
provider for the same rules. Extend the owning descriptor when available. A
genuinely new owner gets one descriptor/index entry; `startup:{}` can declare
source/schema/backend ownership without converting legacy pages/bar modules.
Use validated `after` anchors for new visible entries; do not reorder saved
layouts or duplicate a legacy registration. Runtime/source/schema withdrawal
semantics follow the current catalog contract, not a new global kill switch.

Existing catalog kinds do not express executable command menus. Do not insert
callbacks into JSON or create a competing command registry. Q01 uses typed
result activation and existing services; Q03 may need one small explicit gesture
host delegate. A general command palette is deferred until a separate contract
is justified. New helpers cannot become an excuse to convert core legacy UI.

For backend actions, reuse ActionSpec/providers, narrow capabilities, existing
two-worker pool, PreparedWork/complete/presentation and result emitter. Use a
worker for blocking system I/O, never hide a blocking busctl/nmcli/pactl call in
the coordinator. Discovery remains the existing composition mechanism. If an
existing owner lacks a descriptor backend binding, keep a narrow explicit root
binding rather than inventing automatic imports. No new registry extension is
assumed. `desktop_backend.py` cannot grow beyond its current size ceiling.

The dependency guard must show no new feature-to-feature edge/cycle/exception.
Allowed: Launcher -> shared SettingsRegistry/ShellState; Audio -> shared runner;
Bluetooth -> shared peripheral values; Display -> shared layout. Disallowed:
Audio -> BluetoothState implementation; Utilities -> new copy of every domain;
Display profiles -> BatterySaver private internals. Use existing host-owned
admission/services instead. Do not relabel feature internals “shared” merely
to make the guard green.

## Data, result and failure contracts

- Settings remain one flat settings.json. New keys live in descriptor schema
  fragments, with named validators/resolvers and explicit portable/appearance
  membership; default deny export. Preserve lock -> reload -> merge/token patch
  -> fsync -> atomic replace, permissions, backups and last-valid reload.
- Proposed durable data is limited to Q06 presets, Q10 expiry rules and Q15
  profiles. The others are session-derived or stored by the existing OS authority.
  No per-frame/tick writes, second settings writer or hidden durable search log.
- Q10 requires an explicit notification-owned under-lock mutation of its two
  mute keys; the current generic theme-token path is not such an API. This is
  an additive contract prerequisite, not permission to replace Preferences.
  Q06 whole-list edits retain current per-key last-writer-wins semantics.
- History/selection/undo buffers are bounded metadata, never live native handles
  or decoded images. Disabled features retain settings/history/saved layout IDs.
  Removing a menu cannot silently clear BlueZ pairing or user files.
- `clientSerial`, ack sequence and actionPending are ownership/watermark signals;
  global lastResult is not a reliable per-intent receipt for arbitrary Undo.
  Q01/Q02 use existing navigation/actions without promising transactional Undo;
  Q09 owns its synchronous in-memory history mutation. Q05 uses current capture
  token/savedPath. Later complex result UI must specify exact domain correlation
  before coding; no generic receipt framework is pre-authorized.
- Error after side effect/read-back failure means unconfirmed state, not a safe
  invitation to retry. Destructive operations require explicit confirmation;
  no automatic retries for Forget, profile apply, clipboard write or VPN auth.
  Busy/cancel/error clears pending through the existing owner and completion path.
- Existing public IPC/CLI/env/import/result shapes remain compatible. Proposed
  new actions/keys/gesture IDs are additive contracts to approve with each family.
  No default hotkey/config rewrite; optional binding examples use safe deployment
  workflow and explicit user invocation, never silently patch real niri files.

## Resource envelope and arithmetic

Owner practical acceptance (aggregate ordinary use <=400 MB) is not a new PSS
sample and does not quantify spare headroom. Do not subtract it from a VM RSS
number. These **raw metadata caps** guide implementation; JS/Python/QML object
overhead, allocator retention, Qt rendering and temporary commands cost more.

| Family | Additional retained raw metadata design cap | Bounded transient payloads | Resident process / periodic timer increase |
| --- | --- | --- | --- |
| A | ~16 KiB audio identities; registry data already shared | <=144 KiB result/menu/device metadata | 0 / 0 |
| B | <=12 KiB presets + current saved-path receipt | <=204 KiB selected action/capture/compose data | 0 / 0 |
| C | <=16 KiB timed rules; collapse/undo released on close | <=288 KiB group/restore/rule data | 0 / 0 |
| D | <=80 KiB layout model + bounded event buffer | <=272 KiB layout/device/profile metadata | 0 / 0 |
| E | <=64 KiB saved display profiles | <=256 KiB route/profile/VPN metadata | 0 / 0 |

The conservative payload sum is **<=188 KiB retained** and **<=1,164 KiB
transient** across all candidate families, before runtime object overhead.
This deliberately overcounts several mutually exclusive menus but **does not**
bound total PSS: menu textures, loaded code, shared models and command buffers
still matter. Q09 targets <2 MiB object allocation; Q13/Q14 each target <=3 MiB
active addition, all unmeasured. Use caps to reject oversize input before work,
not to truncate silently or claim exact physical memory usage.

For new native/command inventories, request only needed fields, enforce runner
output limits, and treat truncated/invalid output as unavailable. No large CLI
JSON copied into each periodic snapshot; publish only the normalized domain
state needed by the visible UI. Static metadata stays in the catalog, not in
every snapshot. No separate icon/screenshot cache or thumbnail preloading.

Before committing to a family, inspect the affected model/layer lifetime. While
closed, release submenu delegates, undo snapshots, tracker consumers and receipts
at their stated scope. Keep shared service objects that truly have other users;
do not tear down the backend or user jobs to reduce one menu's number.
One-shot operation deadlines are permitted for bounded user actions; no additional
periodic sampler, expiry sweeper or timer per view. Existing clock/cadence stays.

The acceptance inequalities remain:

`steady baseline + retained additions <= 400 MB`

`ordinary active baseline + concurrent additions <= 500 MB`

Count main QS/backend, owned workers and open standalone Settings/backend.
Do not sum individual RSS as if it were unique memory; PSS is optional diagnostic
evidence when needed, not a reopened baseline sign-off. User-launched file manager,
audio editor and heavy temporary capture/record/upscale payloads must be labeled
separately and never hidden. No all-features-at-once stress gate is introduced.
If actual headroom is insufficient, reduce scope/retention or defer a candidate;
do not reduce blur quality, texture resolution or animation to make room.

## Integration checklist for each family

| Shared concern | Required behavior |
| --- | --- |
| Liquid / Smoked / Material | Existing controls/tokens, no new contrast/inverted-black selected-text rule |
| Battery Saver | Effective no-blur/no-animation/material policy honored; new UI does not rewrite saved appearance/brightness |
| Open/close | Reuse popup host, backdrop/Jelly lifetime and input grabs; no duplicate offscreen FBO for a menu |
| Settings startup | Existing first-frame readiness, openPage confirmation, startupPending and instance reuse |
| Concurrent UI | Main + standalone Settings share lock/merge; stale writers cannot drop unrelated keys |
| Disabled catalog entry | Hide affordance, preserve saved IDs/data; no dead Gear link or new work; retain current action/controller policy |
| Screen sharing / auth | Existing DND/suppression and input-grab release; no secret/notification leakage |
| External changes | Revalidate live IDs; no optimistic policy success, stale object reference or blind restore |
| Demo / preview | No real device mutation/process/user-file write; use existing demo bootstrap rules |
| Accessibility | Tab/arrow/Menu/Escape paths, focus restoration, accessible names/state; no color-only status or hover-only action |

## Implementation sequence after explicit authorization

1. Confirm selected family's scope/defaults and list additive contracts from its
   cards. Characterize current routes/data/error messages first on unchanged
   production code. New behavior cases should fail or be explicitly N/A before
   implementation; do not edit an existing assertion without asking.
2. Commit characterization; then small domain-owned implementation commits, one
   feature at a time. Tests and public docs travel with each feature. Reuse the
   registry/service rather than extending the root switch. Revert a failing
   committed step instead of stacking corrective implementation commits.
3. While working, Python: G0 + relevant units; QML: G0 + G1 + relevant native
   case. Use disposable XDG/private Sway/D-Bus/copied checkouts. No real config,
   running shell or physical-device mutation in the test harness.
4. On final runtime head, run G0–G4 and G6 polling once. Report actual pass/fail/
   skip counts and reasons. One branch sanity: ten preview/Settings launches,
   main vs head medians only, QS/backend RSS at T+10 s. Stop for the existing
   >+100 ms Settings or >+10% RSS flags; no D1 statistics or raw evidence trees.
5. Record <=30-line migration entry, adapter retirement conditions and <=6-line
   laptop checklist. Hardware checks say “needs real-session check” until the
   owner runs them. Owner reviews/merges; next family needs a new authorization.

Suggested family-A unit/native cases are named in the cards. Notification work
also reuses history persistence/retry and capture annotation cases; audio uses
hotplug/read-back fixtures; Q15 retains display watchdog/Saver regression; Q16
retains network mutation/redaction cases. Never report a skipped native test as
proof of real Bluetooth/Pulse/NM/monitor behavior.

## First-family acceptance and review packet

- Q01 finds exactly available Settings pages and opens the right one in the
  current theme without another Settings instance; app ranking stays unchanged.
- Q02 moves only the selected live window to the chosen live workspace, with
  existing focus:false behavior and usable keyboard/focus recovery.
- Q03 cycles only ready outputs, confirms actual default and never changes mic,
  default gestures or audio profile. Status OSD preserves numeric OSD behavior;
  disabled OSD has inline/status fallback. Unsupported state gives useful feedback.
- No new resident process/periodic timer/dependency exception. Gate counts,
  branch sanity and ordinary-use memory are honestly scoped; no savings claimed
  without measurement. Existing glass/animations remain visually equivalent.
- Proposed laptop checklist: (1) Launcher `,` query → existing Settings; (2)
  disabled page absent; (3) `@` move + Esc/focus; (4) output cycle/unplug;
  (5) Liquid/Saver/restore; (6) restart + ordinary main/Settings use.

The planning branch itself runs **G0 only**, once, per STATE. No launch/RSS,
native-device test or benchmark is needed for Markdown. Its final migration
entry records that limited verification; no runtime behavior changed.
