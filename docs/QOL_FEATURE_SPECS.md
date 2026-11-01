# Specifications: substantive desktop workflows

2026-11-01, revision 2. **Plan only.** This replaces the earlier sixteen small
feature cards; their ideas are a supporting backlog in [QOL_ROADMAP.md](QOL_ROADMAP.md).
No UI, action, schema, archive format or new dependency is implemented/approved.
Sources R1–R16 are in [QOL_REFERENCE_NOTES.md](QOL_REFERENCE_NOTES.md).

Each workflow has a task-level acceptance scenario, a useful first slice and a
hard boundary. “Complete” means the stated supported scenario works end to end,
not merely that a menu appears. Unsupported hardware/auth/window identity stays
explicit. All budgets are design bounds, not measured PSS or savings.

## W1 — Complete audio and headset management

**Task:** use a headset for a call while another app plays elsewhere; deliberately
choose playback/call profile and physical port without losing track of the actual
output. Existing defaults and per-app volume/mute remain the foundation.

**First branch, three cohesive capabilities:**

1. Enumerate current card profiles and physical ports, with availability/reasons.
2. Explicitly select supported profile/port, reconcile recreated nodes/read-back.
3. Route a uniquely identified supported live stream to a selected current sink.

**Before implementation:** a 1–2 d capability check must prove the installed
pactl/JSON/PipeWire Pulse support and unique Pulse stream -> PW serial mapping.
Quickshell's inspected links are read-only. PW node.id is not a Pulse sink-input
index. Ambiguous or native-only unsupported streams show Unavailable/Advanced
audio; do not invent `wpctl set-target` or infer a route from the default sink.

**Flow:** Audio -> device details -> explicit port/profile; active app row ->
Output -> choose live sink. Show requested versus observed state, busy/error,
then actual destination. Profile switch warns about interruption/quality changes.
Hotplug destroys stale references; re-resolve rather than reassigning an old node.

**Owner/change surface:** existing AudioMixer, shared audio service and own pure
parser/provider helpers; current registry/two-worker pool and read-back hooks.
Use narrow run/enumerate/invalidate capabilities, never Bluetooth implementation
imports. Extend/create audio descriptor ownership without bulk bar/page conversion.
A port/profile operation cannot block the coordinator or duplicate a PW subscriber.

**State/contracts:** proposed shell-context device/stream mutation IDs are additive,
validated against fresh inventory immediately before action. Settings may display
state or use an explicitly approved main-owner handoff, not bypass context admission.
No persistent routing preference in v1. At most one mutation per affected card/
stream, compatible with current Bluetooth pairing/connect admission. Completion
clears pending on success/error/cancel and reports unconfirmed read-back honestly.

**Failure/exclusions:** profile recreation, unplug, policy refusal, missing server,
busy microphone/call and multiple streams per app. No automatic profile changes,
codec forcing, reconnect, app routing rules or lowered audio quality by policy.
A Pulse one-shot move is not persistent Follow default. Noctalia's native clear
route removes both target.object and legacy target.node; LME must not promise
that semantic until independently supported (R7/R12).

**Acceptance/tests:** different supported apps demonstrably reach different sinks;
port/profile change reports actual state; disconnect/profile switch cannot route
a new stream by reused ID. Add parser/identity/duplicate/stale/pending/demo tests,
then copied-native UI tests. Physical wired/Bluetooth/HDMI/call checks need the
real session. Existing mute/volume/default behavior and glass/Saver UI remain.

**Bound:** <=128 current stream/device records, <=256 KiB normalized inventory,
one on-demand inventory/action/read-back sequence, no new periodic query/process.
Do not copy full CLI output into every snapshot. Estimate 6–10 d after capability
check; unsupported stream routing is a documented partial outcome, not full completion.

## W2 — Saved network connections and deliberate sharing

**Task:** connect to a saved work VPN, choose the right wired configuration, or
share an available uplink through an explicitly selected saved hotspot profile.
This completes missing connection tasks; Wi-Fi scanning/auth/retry already exists.

**Initial branch:** (1) saved VPN/WireGuard status/activation, (2) wired profiles
per adapter, (3) shared admission, read-back and actionable failure recovery.
A later hotspot slice follows the same owner after AP/topology checks.

**Flow:** Network details separates Wi-Fi, Wired and VPN. Choose a saved UUID,
see Connecting, then observed state or specific auth/plugin/unavailable error.
Disconnect targets that profile AND device, never a generic first Ethernet device.
Hotspot offers an explicit adapter/profile and confirms before dropping current
Wi-Fi on a single radio; AP started does not imply upstream internet connectivity.

**Owner/change surface:** current NM/nmcli domain, worker registry, redacted runner
and Wi-Fi conflict guard through shared narrow capabilities. New network-owned
parser/model and details UI, catalog registration as needed; do not fork the Wi-Fi
controller into a parallel NetworkService. Current refresh cadence is unchanged:
read on open/manual refresh/action completion, reuse existing refresh opportunities.

**Identity/contracts:** fresh UUID, connection type, device membership and current
activation state; labels are not IDs. Reject slave/non-user-facing profiles and
conflicting operations on the affected adapter. Additive action/state contracts
need future approval. No preferences for credentials or new network monitor.

**Auth:** NM/keyring/session agents remain authority. Passwords never enter argv,
logs, preferences, support bundles or snapshots. No invisible `nmcli --ask` wait.
MFA/SSO/plugin/secret-agent needs detected support or explicit external manager
handoff; no claim of universal VPN auth. Cancellation releases current ownership.

**Hotspot boundary:** v1 activates an already-configured secure AP profile. A
configured external network editor may create it. In-shell creation/password/QR
sharing requires a separate proven secret-handoff contract; it is not hidden in
this scope. Check AP/rfkill/multi-adapter/concurrent-radio capability first. Never
rewrite stored policy or unrelated profiles. Activating the chosen saved VPN/AP
legitimately applies its routes/DNS and NM-managed sharing/NAT/DHCP/firewall
effects; disclose them before disruptive activation. No ad-hoc firewall commands
or hidden autoconnect edits. If AP start fails, report
actual Wi-Fi state; do not claim it was restored without observing restoration.

**Acceptance/tests:** activate/disconnect one saved VPN and correct wired profile
without disturbing another adapter; auth failure returns usable UI with no stuck
pending; hotspot clearly warns before disruption. Cover duplicate labels, removed
UUID/device, unsupported type/plugin, redaction, concurrent Wi-Fi mutation,
partial success/read-back failure and demo zero calls. NM/keyring/AP hardware:
needs real-session check. Existing fast Wi-Fi wrong-password behavior must remain.

**Bound:** <=64 saved non-Wi-Fi profiles / <=128 KiB normalized state, existing
pool, zero new resident process/sweeper. Baseline saved Wi-Fi list is not duplicated.
Estimate 7–12 d VPN+wired; saved-hotspot slice +3–5 d (R11/R13).

## W3 — Named display setups and safe presentation recall

**Task:** save Desk/Laptop/Presentation once, then deliberately recall a compatible
resolution/refresh/scale/position/output-enable setup with safe Keep/Revert.
Existing arrangement/mirroring/watchdog is reused, not advertised as new.

**First branch:** capture/name/manage profiles; compare current topology and show
proposed differences; apply only through current DisplayControl preview/decision.
No automatic docking/login/charger/presentation policy or DND/audio bundle.

**Flow:** Displays -> Save current setup -> name. Later select profile -> review
outputs/modes -> Preview -> Keep/Revert. Saving/renaming/deleting profiles never
changes outputs. Mismatched outputs/modes require review or refusal, not silent
partial application. Unsupported/all-disabled layout is rejected before mutation.

**Owner/change surface:** display-owned profile reducer/UI plus existing
DisplayControl.start/decide, display_layout validator and watchdog. No direct
Saver/Mirror feature import, second watchdog, restore algorithm or KDL writer.
Existing Saver/mirroring admission and reversible transaction stay authoritative.

**State/contracts:** proposed private/nonportable displayProfiles key, <=16 profiles,
<=8 outputs/profile, <=64 KiB total, safe IDs/names. Keep flat settings.json and
schema/atomic merge. Initial identity is exact current connectors/topology;
normalization currently omits serial, so do not guess replacement monitors or
silently add/export serials. New profile format is explicit future approval.

**Acceptance/tests:** switching between two known setups is previewed and can
restore original settings when the original topology/session remains valid.
Reject unsafe/all-disabled candidates. Hotplug/session loss requires an explicit
stale/recovery outcome through the existing watchdog; no universal claim that a
vanished screen/session can be restored or every external failure kept visible.
Cover 59.94/60.003 modes, scale, hotplug during confirmation, expired token, Saver
active/restore, mirror conflict, crash/watchdog, two Settings writers. Private
Wayland proves transaction/UI only; actual screens need real-session check.

**Bound:** <=64 KiB persisted metadata; no extra resident process, timer or output
scan. Existing watchdog lifetime unchanged. Estimate 4–6 d; prioritize only when
multiple setups are used. Full manual profile lifecycle is evidenced by R10/R14.

## W4 — Removable media with truthful safe-remove behavior

**Task:** identify an attached USB/SD drive, mount/open its volumes, then safely
remove the intended device without forced unmount, wrong-disk targeting or false
success. This is a new domain, not a file-manager shortcut.

**First branch after capability check:** drive/partition inventory; mount/open;
unmount and supported drive PowerOff/Eject with clear busy/auth/sibling outcomes.
Explicit optional prerequisite is existing UDisks2; no silent service/package
install, LME daemon or new polkit agent. Prefer machine-readable existing system
D-Bus CLI capability; prove parsing/auth first, do not parse localized prose.

**Flow:** group volumes under their physical drive; show label, size, mount state
and available operation. Open only a validated current mountpoint. Before whole
physical-device removal show all affected mounted children/sibling devices. Busy
means close file users and retry explicitly; permission denial/cancel retains UI.

**Identity/safety:** requests reference a current owner-issued identity, not a raw
/dev/sdb supplied by QML. Revalidate device generation, drive/partition membership,
mounts and current capability before each mutation. Exclude system/root/home and
ambiguous/internal targets, including an OS booted from USB. Complete enumeration
is required before whole-drive removal; overflow is an error, not a truncated view.

**Authoritative semantics:** UDisks Unmount, Drive.PowerOff and Eject differ.
DeviceBusy never triggers force/lazy fallback. PowerOff may affect sibling drives
on one reader, so use SiblingId/CanPowerOff checks. State “Unmounted” if that is all
that completed; only claim the requested safe-remove operation after its actual
successful outcome. No format/partition/repair, auto-mount or encrypted unlock in v1.

**Owner/change surface:** new storage descriptor, own provider/pure object parser
and panel/details entry. Reuse runner/pool, shared polkit and validated URI opener;
never broaden fileOpen (latest-search-only) or shell out to arbitrary mount paths.
No watcher/polling: refresh on panel open/manual action/completion. Unplug while
closed is reconciled at next read; before a click always revalidate fresh state.

**Acceptance/tests:** exact target mounted/opened; busy filesystem is not forcibly
unmounted; cancelled auth does not hang. Earlier successful child unmounts can
remain unmounted if a later sibling fails: report each outcome and “device not
removed”, with no guessed automatic remount/rollback. Multi-partition removal matches
confirmation and cannot affect system disks. Pure object fixtures and fake service
errors; copied-native panel lifecycle; actual USB/SD/card-reader/auth tests need
real-session check. R15 is the service contract, not a drop-in QML component.

**Bound:** <=32 drives/128 volumes and <=256 KiB normalized state, no decoded icons
or filesystem crawl. Fail explicitly over cap. Estimate 1–2 d capability check +
6–10 d implementation. New shared OS dependency costs are disclosed, not called free.

## W5 — Manual application/workspace sets

**Task:** start a declared Work/Study set of 3–6 installed apps in one reviewed
operation, reuse current instances when unambiguous, and place windows only with
proven identity. This is not full session/browser/document resurrection.

**Minimum useful slice:** create named sets, review which installed apps will
launch/reuse, start with per-entry outcome and cancellation of unsent entries.
Existing-window destination moves can use explicit selected compositor IDs.
New-window destination placement is a separate capability check, not assumed.

**Example:** Work = browser + terminal + editor + music. Review says two matched
apps will be reused, two will launch. A missing app does not launch a different
binary or fail silently. If matching is ambiguous, ask/select existing window or
leave it running without moving; no guessed app_id/title match or automatic close.

**Owner/change surface:** own work-set reducer/schema/UI; shared application-launch
service and compositor service injected narrowly. Existing window_actions launch
logic is not a public reusable service yet: characterize and extract the smallest
primitive if needed; do not import that feature's private handler or recursively
send public actions through the registry. Preserve terminal/literal argv/history.

**State/contracts:** proposed private workSets key <=12 sets/12 app entries each,
<=64 KiB. Installed desktop IDs and optional user-chosen destination mappings,
not arbitrary captured commands, process memory or window titles. Explicit default
“reuse only a unique known match”; user may choose fresh launch for supporting apps.
App IDs/paths are not exported by default. Catalog withdrawal preserves definitions.

**Placement gate:** niri Spawn gives no returned window identity; single-instance/
DBus apps may produce no new window. Prove launch association or compositor
launch-to-workspace support using the existing event stream, without persistent
window rules, focus-switch races, new watcher/executor or arbitrary sleeps. If not
proven, ship/label app-only sets and explicit existing-window placement, not restore.

**Execution:** one bounded user-triggered plan using existing scheduling; no new
persistent job table/queue. Cancel stops unsent launches only, never kills launched
apps. Restart abandons orchestration and re-reads live state; no hidden replay.
No automatic login/project-directory trigger or rollback that closes user windows.

**Acceptance/tests:** one set opens the declared apps once, preserves explicit
terminal choice, reports partial failure and does not move unrelated windows.
Cover duplicate instances, removed app/workspace, no-new-window launch, restart,
cancel and external window changes; demo zero spawn. Real niri launch identity
needs actual session evidence before placement. R16 supports primitives only.

**Bound:** one <=12-entry active plan, <=64 KiB definitions, zero new resident
process/ticker. Launched applications are user payloads and their RAM is disclosed
separately. Estimate 1–2 d identity check + 4–7 d app-only sets; placement +3–5 d
only if proven. Value is high for daily repeated app sets, confidence is lower.

## W6 — Selective personal-data backup and recovery

**Task:** recover notes/history after reinstall or accidental loss, with a visible
inventory and explicit overwrite choices. Existing full-settings JSON backup and
deployment journal/rollback stay; neither currently backs up notes/clipboard/
notification history. Another settings export button is not the new capability.

**Initial branch:** (1) inspect/select domains and private-data warning, (2) export
validated snapshots, (3) preview and restore selected clean domains with backup and
per-domain outcome. Settings, notes and inactive notification history first;
clipboard is a separate consistency slice after that contract is proven.

**Privacy/format:** proposed versioned local bundle is ADDITIVE, never changes
schema-1 settings JSON or existing import behavior. Plaintext/private content is
opt-in and explicitly described as unencrypted. No homemade encryption, cloud/
scheduled sync, reading OS credential/keyring stores or raw screenshots/log dump.
Selected notes, history and user commands can themselves contain secrets; this
private bundle cannot certify or automatically sanitize them. Preview selected
domains/setting keys and require explicit inclusion; it is not a redacted support
bundle. Preserve
0600 files/0700 staging where supported; do not claim POSIX privacy on FAT/shared
filesystems. User must see destination/privacy implications before export.

**Owner/snapshot contracts:** coordinator composes explicit domain export/restore
APIs via shared capabilities, not imports of Clipboard/Notifications/Notes internals.
Settings uses current validated export/import and lock. Notes owner must be saved/
clean or offer Save/cancel; never read an unsaved buffer as “backed up”. Notification
history exports sanitized inactive snapshots and restores through its owner/revision
path, never revives native actions/toasts. Do not write behind an active QML owner.

**Clipboard slice:** canonical content is in SQLite BLOBs; image files are derived.
Use sqlite3 backup/logical export under its owning worker's consistency rules;
never raw-copy the live DB or assume copying images beside it is coherent. Restore
through worker transaction and regenerate validated derived images. Pause/admit
capture through an explicit owner-scoped lease; release only its temporary hold,
preserving prior pause state and any later explicit user pause choice.
Pinned entries can exceed the ordinary trim target; no new history retention cap
is silently imposed to fit an archive.

**Validation/restore:** manifest/version/known domain set, sizes/checksums/schema
and paths validated BEFORE mutation. No arbitrary zip extraction, symlink/hardlink
or traversal entry; bound decompressed bytes/count, unknown formats rejected.
Initial overall uncompressed cap 256 MiB with streaming <=256 KiB chunks; preflight
and reject oversize data explicitly, never silently omit it. Runtime allocation
includes SQLite/parser overhead; it is not limited merely by the chunk size.

Restore selected domains only with an owner-scoped revision/generation fence or
reservation held from recovery snapshot through commit (including Notes autosave
and pending notification save). Recheck immediately before commit; changed token
means refuse/explicit retry, not overwrite. If an owner cannot guarantee that
fence, offer a recovered copy for manual import rather than in-place restore.
Nonparticipating external file writers are not covered by an LME owner lease;
detected external conflicts require review, not a universal atomic-CAS claim.
Preflight current backups first. Cross-domain atomicity is not promised: commit
per domain with explicit statuses, preserve recovery copies, report partial result
and allow deliberate domain recovery. No generic repair-all/auto retry, global
Undo, force restart or overwrite of unrelated/newer data. Crash/failure injection
is required before a restore UI ships.

**Acceptance/tests:** export known notes/history, change them, preview differences,
restore selected domains without changing unrelated settings or replaying alerts.
Cover dirty NotesState, edits/autosave between snapshot and commit, invalidated
owner reservation, notification save revision, interrupted export/restore,
bundle bomb/traversal, permissions, malformed schema, worker restart and concurrent
writers. Clipboard consistency/image reconstruction has its own tests. Hardware
not required for logical restore; real-session owner coordination still needs check.

**Bound:** manual/streamed operation in current pool; no retained archive bytes,
background backup process or additional writer. <=1 MiB preview metadata, bounded
file staging and explicit disk-space failure. Estimate 8–14 d initial scope;
clipboard +3–5 d, contingent on consistent owner APIs. This is an LME design;
existing backup exclusions/owner code are evidence of the gap, not an upstream
claim. On-demand redacted diagnostics may follow, not replace the recovery contract.

## Common definition of done

- A stated user task succeeds on supported capabilities; partial/unsupported paths
  are visible. Menus or mocked commands alone do not establish device behavior.
- Current public APIs, settings protocol, data and theme quality remain compatible;
  additive contracts above need authorization with the corresponding family.
- Characterization first; no existing assertion edits without approval. Native/
  fault/withdrawal and domain-specific data-loss tests are scoped to the change.
- One state/operation owner, current worker pool/registry, no new polling/cache/
  automatic power policy, daemon or cross-feature dependency exception.
- Disabled entries preserve definitions/data/IDs and withdraw new UI/starts per
  current policy; never delete backups/history, kill user payloads or invent
  new blanket cancellation rules. Demo/preview have zero real side effects.
- Per STATE: affected gates, final full gates once and one runtime launch/RSS
  sanity. Physical checks remain “needs real-session check” until actually run.
