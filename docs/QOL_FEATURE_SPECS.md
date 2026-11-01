# QoL candidate specifications

2026-11-01. Proposed behavior, not implementation authorization. Priorities,
effort and batching are in [QOL_ROADMAP.md](QOL_ROADMAP.md); references R1–R11
are in [QOL_REFERENCE_NOTES.md](QOL_REFERENCE_NOTES.md). Resource limits below
are design bounds, not measured RAM savings or guarantees. New action/key names
are proposals requiring approval with their future family; existing names stay.

All candidates inherit [delivery constraints](QOL_DELIVERY_PLAN.md): one owner,
existing registry/pool/persistence, English UI, keyboard access, current theme,
bounded metadata, demo isolation, safe withdrawal and explicit error states.
“No new process” means no additional resident process; an explicitly requested
external application/short command still has its own temporary cost.

## Q01 — Settings page quick jump from Launcher

- **Flow:** open Launcher, type `, display`, choose Displays, press Enter. Empty
  `,` shows available pages in sidebar order. Escape returns to the prior query;
  the placeholder/help advertises the mode. No normal app ranking changes.
- **Scope:** page-level search only, using `SettingsRegistry.search()`. No
  per-setting anchors, source scraping, Settings page instantiation or duplicated
  search model. Existing `/`, `:`, `@`, `=` modes retain precedence/behavior.
- **Owner/seams:** `qml/panels/Launcher.qml`, a small launcher-owned result helper,
  shared `qml/settings/SettingsRegistry.qml`, and
  `ShellState.settingsPageAvailable/openSettingsPage`. Validate availability
  explicitly: `SettingsRegistry.page()` silently falls back to the first page.
- **Contract/data:** typed `{kind:"settingsPage", pageId, title, detail}` result;
  no new backend action, IPC or durable preference. Maximum eight results for
  a query, all sixteen pages for the empty mode; derive once per query/catalog
  revision, not every animation frame. No new files containing search history.
- **Integration/failure:** close the invoking panel through the existing opener;
  reuse standalone Settings and preserve openPage/startupPending confirmation.
  Disabled/removed page cannot open; keep the query and give an available-page
  message rather than opening an unrelated page. Demo uses its embedded route.
- **Tests/acceptance:** `SettingsJumpCase`: every enabled page, keyword/token
  parity, disabled entry, invalid ID, prefix conflicts. Native: keyboard search,
  first frame in current theme, existing Settings instance reuse, close/reopen.
  Existing app result order is byte-identical outside the explicit mode.
- **Allocation:** <=64 KiB derived result metadata; release on Launcher teardown.
  Zero new processes/tickers; no page screenshots. Reference R1.

## Q02 — Keyboard window destination menu

- **Flow:** in `@` window mode select a window; Right/Menu key or context button
  opens “Move to workspace…”. Select a current destination and Enter; Esc closes
  only the submenu and restores selection. Left-click/Enter still focus normally.
- **Scope:** expose existing `moveWindow`; Overview already moves windows. No
  new close/kill command, workspace renaming or movement policy. Preserve
  `focus:false`: moving a background window must not unexpectedly switch focus.
- **Owner/seams:** Launcher-owned menu delegates to `scripts/window_actions.py`;
  use window/workspace IDs from current niri state, never array positions or
  workspace names as command text. No additional watcher or refresh cadence.
- **Contract/data:** existing `moveWindow {id,workspaceId}` and result protocol
  unchanged. Current destination marked/disabled. No preference or persisted
  menu state. The backend already revalidates both IDs from fresh compositor data.
- **Integration/failure:** window closes, workspace disappears, hotplug or niri
  restart while open → explicit unavailable result, no substitute destination.
  Do not infer per-click success from unrelated global `lastResult`; the menu can
  close on submission and use existing domain status/read-back, not promise Undo.
- **Tests/acceptance:** `WindowDestinationCase`: all keyboard/pointer paths,
  stale IDs, multiple outputs, current target, focus preservation, demo movement,
  menu dismissal/reopen. Existing native move tests remain unchanged.
- **Allocation:** one lazy menu, current workspaces only, <=64 KiB presentation
  metadata. No new process. This is an LME access-path composition, not a claim
  that another shell's complete window-management stack should be ported.

## Q03 — One-action audio output cycle

- **Flow:** “Next output” in Audio selects the next ready output and names the
  actual device in the existing OSD. Optionally expose a new opt-in bar gesture;
  existing middle/right/scroll defaults and microphone choice do not change.
- **Scope:** output only in v1. Existing output/input selectors and per-app
  volume/mute stay. No automatic Bluetooth profile switch, reconnect or routing
  rule; selecting a default is not a promise to move every existing stream.
- **Owner/seams:** a shared audio service uses existing PipeWire tracked nodes;
  AudioMixer and a narrow BarGestures delegate call it. Avoid a new Python
  poller or per-button `PwObjectTracker`; track only the service's needed nodes.
- **Feedback seam:** current OSDManager.show(label,value) always represents a
  numeric level. Add a small explicit status/text variant to that SAME OSD host
  if the optional gesture ships; preserve volume/brightness rendering. When OSD
  is disabled, use inline Audio/ordinary status feedback, never force it on or
  display a fabricated percentage for device selection.
- **Contract/data:** new opt-in gesture ID, if included, is declared in catalog
  metadata and routed by the host; JSON contains no callbacks. Re-resolve ready
  node identity at activation, use deterministic current list order. No durable
  sink ID or new preference. Zero/one eligible output gives clear no-op feedback.
- **Integration/failure:** `preferredDefaultAudioSink` is a hint. Keep requested
  and actual state distinct; success feedback follows actual-default signals.
  One outstanding request, bounded feature-local deadline, no polling. Hotplug,
  unknown current default, refusal or recreated nodes cannot target a stale object.
  Do not touch `preferredDefaultAudioSource` as a fallback.
- **Tests/acceptance:** `AudioCycleCase`: empty/one/many sinks, readiness, removal,
  wraparound, request refused, actual default lag, no mic mutation, demo no device
  operation. Laptop: wired/Bluetooth/HDMI handoff needs real-session check.
- **Allocation:** <=32 live device labels/identities, no duplicated icons/waveform
  or OSD window. Reuse existing tracker/OSD lifetime. Reference R7.

## Q04 — Installed desktop application actions

- **Flow:** select an app and open its secondary menu: e.g. New Window or the
  browser's declared Private Window. Enter on the ordinary result remains normal
  launch. Do not mix every action into ordinary ranking in v1; no favorites.
- **Owner/seams:** small pure Desktop Action parser beside the existing app
  scanner/`desktop_exec()`, launcher-owned menu, existing window action provider.
  Keep large coordinator size ceilings: extract the relevant parser/setup if
  needed, never add a growing branch to `desktop_backend.py`.
- **Contract/data:** proposed shell-only `launchAction {id,actionId}`. Resolve
  installed entry/action again at execution, not raw QML Exec text. Parse only
  IDs declared by `Actions=`; selected-app lookup is lazy, <=32 actions and
  <=64 KiB returned metadata. Preserve localization, icon/working-directory rules,
  hidden/TryExec filtering and literal argv. No preference or user action database.
- **Launch policy:** reuse configured terminal selection, field-code parsing and
  launch-history rules; record app usage once only after successful submission.
  No shell wrapper unless the installed desktop entry explicitly declares one.
  Quickshell `.execute()` does not guarantee Terminal/field-code parity (R2).
  DBus-only/missing-Exec/unsupported actions explain unavailability; never silently
  launch the main app instead. Normal app launch remains unaffected.
- **Tests/acceptance:** `DesktopActionCase`: localized labels, escaped quotes/%
  and `%i/%c/%k`, file fields without files, Terminal=true, removed/malformed
  action, Flatpak IDs, cwd, no fallback after error, one usage update, demo zero
  spawn. Native menu/focus/close-reopen. Source R2, implementation license review
  only if actual code is copied.
- **Allocation:** no eager global action indexing or watcher; only chosen-app
  metadata lives while the menu is open. Use existing icon provider/cache policy.

## Q05 — Successful capture: Open folder / Copy path

- **Flow:** after Save PNG succeeds, editor shows Open folder and Copy path for
  that export. Copy-only, failed/pending save or absent file offers neither.
  Save-folder entry and annotation image click-through already exist.
- **Owner/seams:** `scripts/screen_capture.py` owns savedPath/token; extend its
  existing action provider and `qml/panels/ScreenshotEditor.qml`. Proposed
  `captureOpenLocation {token}` resolves the controller's successful export,
  not an arbitrary path. Copy path uses the same successful export identity.
- **Contract/data:** session-only path receipt <=4 KiB, replaced on successful
  next save and removed on session close. No durable recent-files index or new
  path preference. Inherit current capture action context admission and demo
  isolation. Keep PNG permissions/exclusive creation and editor close semantics.
- **Safety/failure:** revalidate token/current export and file availability before
  open. Do not broaden `fileOpen`, which permits only latest file-search results.
  Use file URI/literal argv, no shell interpolation. Open parent via existing gio;
  optional exact-file selection only when a verified file-manager API supports
  it, otherwise label Open folder accurately. Missing manager/file, symlink
  retargeting or new save racing with click cannot open an arbitrary replacement.
- **Tests/acceptance:** `CaptureLocationCase`: save twice, close/reopen, save error,
  stale token, missing/moved path, hostile name, simultaneous annotation/OCR,
  clipboard-only export, no file manager, demo no open. Preserve existing image
  click -> annotation test. Recording handoff is a later same-domain increment.
- **Allocation:** no retained pixels or thumbnails; current session metadata only.
  A bounded external file-manager launch is user-requested, not resident shell RAM.
  Reference R6.

## Q06 — Configurable focus durations and presets

- **Flow:** Timer's menu edits focus/short/long durations and selects a named
  preset. Keep Standard at 25/5/15. Editing a preset affects the next session;
  an in-progress session (including paused) keeps its captured duration. Selecting
  another preset explicitly asks before resetting an in-progress session; Cancel
  preserves it. Deleting its preset does not alter the captured session. Standard
  is immutable/duplicable and counts toward the maximum of eight presets.
- **Owner/seams:** existing `FocusTimer.qml` service and `TimerWidget.qml`; small
  focus-owned editor/pure preset reducer. All views observe the same timer.
  Descriptor schema owns proposed `focusPresets` and `focusPresetId`; handwritten
  UI only. No automatic DND/KeepAwake/Battery Saver coupling.
- **Contract/data:** <=8 presets, stable safe IDs, names <=32 characters, finite
  integer minute durations 1–180 for each mode. New keys portable=true,
  appearance=false; explicit named validator, no arbitrary JSON expressions.
  Standard fallback handles removed selected preset; preserve invalid-file
  last-valid behavior and normal Settings merge/write protocol. A whole-list
  edit follows existing last-writer-wins for that key; unrelated keys survive.
  Do not promise per-preset concurrent merging without a separate contract.
- **Time policy:** same existing deadline/pause/reset, 250 ms active-only ticker
  and restart-reset behavior. Suspend currently counts through wall-clock
  deadline; do not change it in this feature. No per-tick persistence, auto-next
  cycle or restart journal. Completion once, including when notifications are
  withdrawn (timer still stops; no forbidden server/bootstrap).
- **Tests/acceptance:** `FocusPresetCase` with injected clock: default parity,
  bounds/bool/NaN, edit/delete while active, pause/resume/reset, stale settings
  writers (unrelated-key preservation and per-key last-writer-wins), paused-session
  selection confirmation/cancel, absent Notifications, one completion, restart
  resets as documented.
  Native keyboard editing and surviving panel close. Reference R9.
- **Allocation:** <=8 KiB preset model, no new process/ticker. Selecting a preset
  must not create another timer singleton or persist current countdown.

## Q07 — Compose selected clipboard text

- **Flow:** opt into Select mode, choose up to twenty text items; numbered chips
  show selection order. Copy combined joins them with newline in that order.
  Escape/filter change/close clears selection; no automatic paste into another app.
- **Scope:** text only. LME already copies plain text; this adds multi-item
  composition, not format stripping. No image stitching, rich HTML, macros,
  placeholders, clipboard manager replacement or new global shortcut by default.
- **Owner/seams:** existing `ClipboardPanel.qml`, `ClipboardState.qml` and
  `clipboard.py` worker. New worker `compose` request carries IDs, not content
  paths from QML. Worker resolves/read-checks selected current records under its
  existing safety/locking policy and performs one wl-copy, not one per selection.
- **Contract/data:** max20 IDs, max64 KiB combined UTF-8 (below existing MAX_TEXT),
  <=128 KiB temporary working budget; reject the whole operation before changing
  clipboard if a selected item is missing/image/over cap. Existing capture pause,
  clipboard ownership lifetime, worker retries and 20–500 history limit stay.
  Successful combined copy may be captured once by the existing watcher; do not
  add another manual history write or blanket dedup policy change.
- **Privacy/failure:** explicit Copy only; no logs/exports of combined text and
  no hidden selection after search changes. Missing files, private-path escape,
  worker restart or failed wl-copy leaves original clipboard untouched where the
  existing tool contract permits; report uncertainty, do not auto-retry writes.
- **Tests/acceptance:** `ClipboardComposeCase`: ordered Unicode joins, duplicate
  IDs, byte boundary, deleted/image item, pause, capture result once, no process
  in Settings/demo, native keyboard select/cancel/copy/close-reopen.
- **Allocation:** IDs in UI, content assembled only in existing worker. No new
  watcher/timer or image decode. This is an LME proposal without an upstream clone.

## Q08 — Collapsible notification groups and group clear

- **Flow:** group header toggles collapse (keyboard Enter/Space, count remains);
  menu adds Clear this app. Search temporarily expands matching groups so
  matches are not hidden. Clearing an app during search explicitly says it clears
  that entire app group, not just matches. Clear all retains its existing scope.
- **Owner/seams:** NotificationCenter presentation plus a notification-owned
  batch reducer/service API. Preserve existing appName identity and ordering;
  don't add a second notification model or sender identity migration.
- **Contract/data:** collapse state session/UI-only, max current groups (history
  <=200). Proposed `dismissGroup(appName)` snapshots the intended IDs at click,
  dismisses live wrappers as today, updates history once and persists once.
  Concurrent arrivals outside that snapshot survive. Permanent mute/DND/actions
  are unchanged. Group clear composes with Q09 when authorized.
- **Tests/acceptance:** `NotificationGroupCase`: hidden matches, empty names,
  two app groups, ID replacement/new arrival during clear, native dismiss once,
  unread consistency, failed-save Retry and restart, withdrawal bytes untouched.
  Native keyboard focus, expanded/collapsed height and glass clipping.
- **Allocation:** <=16 KiB collapsed-ID set/derived headers; no image copies or
  offscreen nested full-list delegates. List remains virtualized. Reference R4.

## Q09 — One-batch history restore after dismissal

- **Flow:** after dismiss/group-clear/clear-all in the center, a strip offers
  “Restore history”. It remains until center closes, next destructive dismissal,
  explicit dismiss or withdrawal. No new countdown/expiry timer in v1.
- **Owner/seams:** notification-owned reducer before live dismiss, existing
  revision/save/retry path after mutation. Never retain native NotificationServer
  objects/wrappers. Restored entries have active=false, popup=false, actions=[],
  no unread increment; “history” wording makes the limited recovery explicit.
- **Contract/data:** one batch, <=200 non-transient immutable rows and <=256 KiB
  serialized metadata. No pixel data. If a batch exceeds this cap, warn BEFORE
  clearing that history cannot be restored; never offer a silently partial Undo.
  New arrivals or reused IDs win; skip collisions instead of replacing newer
  rows. Restore in original timestamp order within the existing history cap.
- **Safety/failure:** image paths remain untrusted and use capture validation on
  click; missing images do not revive actions. Restore saves once via the same
  revision protocol. If disk save fails, existing unsaved/Retry UX remains honest;
  restart loads last committed history, not an undeclared undo journal. No attempt
  to undo external application effects or server close reasons.
- **Tests/acceptance:** `HistoryRestoreCase`: group/all/single, cap preflight,
  transient exclusion, replacement/arrival, reused ID, image deletion, save-error
  recovery, close/reopen discards buffer, no actions/popups/unread restoration,
  disabled Notifications starts no server and retains history/settings bytes.
- **Allocation:** <=256 KiB payload plus bounded runtime representation; target
  <2 MiB retained object allocation, unmeasured. Reference R4 motivates history
  separation; this particular Undo is LME's design, not a cited upstream feature.

## Q10 — Temporary notification mute for one app

- **Flow:** group menu: Mute 15 min / 1 hour / Until turned off; muted-app view
  offers Resume now and absolute “until 16:30”. Global timed/sharing DND remains
  independent; unmuting an app cannot override active global DND.
- **Owner/seams:** existing notification admission predicate and schema fragment.
  Keep permanent `notificationMutedApps`; proposed private/default-deny-export
  `notificationMuteUntil` map (default {}) stores bounded appName -> epoch-ms.
  Timed selection replaces that app's permanent mute through one atomic patch;
  permanent selection clears its timed entry. Never overwrite unrelated apps.
- **Required transaction:** a notification-owned mutation must derive both keys
  from freshly reloaded values INSIDE the existing Preferences lock, then use
  its unchanged merge/fsync/replace path. Proposed `notificationMute` accepts an
  app/mode, not a stale whole map. Existing generic theme-token handling does
  not support this map automatically. Characterize/approve this narrow additive
  contract before Q10; no UI read-then-write or second persistence service.
- **Time/data:** <=64 entries / <=16 KiB; safe finite integer timestamps, app-name
  bounds, v1 choices max1h. Evaluate at arrival/open/user mutation; use existing
  visible-center clock for display if needed, no sweeper/new tick. Expired stored
  entries are inert; cleanup happens only with the next explicit mutation.
  Suspend counts; clock jumps follow wall-clock semantics, no secret monotonic
  persistence promise. Suppressed notifications remain history as current policy,
  never replay later. App-name spoofing limitations are unchanged and documented.
- **Tests/acceptance:** `TimedMuteCase`: expiry boundary with injected clock,
  permanent+timed+global DND combinations, restart, backwards time, malformed map,
  simultaneous different-app mutations (both survive), serialized same-app
  mutations (last accepted choice wins), private export, limit reached, no timer/process or
  replay. New preference contract must be authorized before implementation.
- **Allocation:** bounded metadata only, no notification duplication. Reference R5;
  do not copy upstream's periodic expiry sweep or broaden A6.

## Q11 — Optional XKB layout indicator and selector

- **Flow:** optional bar item shows a short layout label; full accessible name
  and menu list on open. Click cycles, menu chooses a configured layout. Hide
  for a single layout by default; no existing bar layout is rewritten.
- **Owner/seams:** niri-owned bounded event parser/projection, existing shared
  niri stream, own indicator/menu, positioned catalog bar entry. The current
  backend discards event payload; preserve its existing refresh coalescing while
  decoding only KeyboardLayoutsChanged/KeyboardLayoutSwitched. No second stream.
- **Contract/data:** initial authoritative layouts query on demand; proposed
  shell-only layout-select action validates current list/index/fingerprint.
  <=64 layouts and <=64 KiB parser buffer, discard oversize event through newline
  without disabling unrelated events. Reconnect uses current authoritative state.
  IDs stay recognized in saved layouts when the descriptor is disabled.
- **Limits/failure:** verify exact supported niri CLI/IPC before coding; missing
  capability means hidden/Unavailable, not fake success. Handle empty list,
  variants, device removal, invalid index and external layout changes. XKB is
  not Fcitx/IBus engine selection; label it “Keyboard layout”, allow manual hiding
  if another input-method indicator is authoritative. No config editing.
- **Tests/acceptance:** `KeyboardLayoutCase`: fragmented/bad/unknown/oversize
  events, coalescing unchanged, initial query, changed list during click,
  reconnect, demo fixture, native keyboard activation, no additional watcher.
  Actual niri layouts/input-method interaction: needs real-session check.
- **Allocation:** <=0.5 MiB target model/UI allocation, unmeasured; no new resident
  process, periodic query or duplicated event subscription. Reference R3.

## Q12 — Bluetooth Rename and Forget

- **Flow:** a paired device's menu adds Rename and Forget. Rename changes its
  local BlueZ Alias; Forget confirms adapter/device and warns pairing must be
  repeated. Connect/disconnect/pair flows and battery alerts already exist.
- **Owner/seams:** existing BlueZ enumeration + bounded busctl worker operations,
  Bluetooth-owned actions/UI. Reuse current conflict admission with connection
  and pairing; narrow shared capability, never import the peripheral feature.
  Alias capability check precedes UI implementation; permission error is explicit.
- **Contract/data:** proposed shell-only rename/forget actions accept fresh
  adapter+device identity, not a label. Alias <=128 UTF-8 bytes, no controls/NUL;
  provide explicit Reset name only if BlueZ reset semantics are verified. Validate
  adapter and Device1 membership just before Set/RemoveDevice. Demo mutates fixture
  only; read-back invalidates current Bluetooth state through existing hooks.
- **Retention/policy:** BlueZ remains storage authority. No new shell alias DB,
  trust flag mutation or auto reconnect. Forget does not delete battery pins,
  history or notification settings; mark orphaned pins unavailable, with a
  separate user cleanup affordance later. Do not silently migrate address-based
  saved pin IDs to adapter-specific IDs in this feature.
- **Tests/acceptance:** `BluetoothManageCase`: two adapters/same address, stale
  device, confirmation cancel, alias bound/Unicode, busy pair/connect, system-bus
  permission error, failed read-back/pending cleanup and notification dedup.
  Actual Alias/RemoveDevice and re-pair: needs real-session check.
- **Allocation:** current device model only, <=64 KiB added labels/menu metadata;
  existing pool and pairing-agent demand lifecycle remain. Reference R8.

## Q13 — Explicit audio port and profile controls

- **Flow:** device details show supported Port/Profile selectors: speakers vs
  headphones/HDMI, or high-quality playback vs call profile. Unavailable choices
  explain why. Warn that profile switching can interrupt audio/reduce quality.
- **Owner/seams:** audio-owned pure parser + current registry/pool worker;
  AudioMixer consumes its service. Prefer existing optional `pactl -f json`
  capability, already declared/allowlisted. Missing Pulse server/helper/format
  hides unsupported selectors and retains Advanced audio (pavucontrol).
- **Contract/data:** on open and explicit change only, bounded fresh card/port/
  profile inventory <=128 KiB; proposed shell-only selection actions revalidate
  against current enumeration. Never interpret display strings as CLI fragments.
  No new subscriber, periodic refresh, private Pulse library or config write.
- **Lifecycle/failure:** one mutation per card, coexisting with current Bluetooth
  admission. Profile changes recreate nodes; discard stale references, reconcile
  actual devices/read-back, do not force an old node back. Never automatically
  change profile when a call starts/ends. Errors or ambiguous mapping fall back
  to Advanced settings, not a guessed adapter. Current volume/mic mute stay.
- **Tests/acceptance:** `AudioProfileCase`: JSON fixtures/version capability,
  missing/unsupported profile, stale card, unplug/recreated nodes, command success
  but failed read-back, bounded output, demo no commands. Wired/HDMI/Bluetooth
  microphone and active call: needs real-session check.
- **Allocation:** no resident helper; short CLI peaks separately, <=128 KiB
  inventory plus lazy controls; target <=3 MiB active addition, unmeasured. R7.

## Q14 — Move one live app stream to another output (spike-gated)

- **Flow if feasible:** stream row gets Output menu, showing its actual current
  destination and currently eligible sinks. Apply affects this live stream only.
  No persistent app rule or “Follow default” claim in v1.
- **Blocking check:** inspected Quickshell links are read-only; Plasma/Noctalia
  native move APIs do not apply. Prove current PipeWire node/object serial ->
  Pulse sink-input mapping and fresh sink identity via bounded pactl data. PW
  node ID != Pulse index. No unique match means no route action.
- **Spike exit:** fixtures plus one real-session stream move/read-back, stream
  recreation, two streams from the same app and hot-unplug. If identity or server
  capability is unreliable, ship nothing beyond existing Advanced audio; record
  the limitation. One-shot move cannot implement persistent route-clearing policy.
- **Owner/contract if approved:** same audio service as Q13, proposed shell-only
  route action with fresh serial/index verification and one mutation per stream;
  existing worker pool. On completion re-read actual route; failure/uncertainty
  never silently becomes a default-output change. No daemon/watch/persisted routes.
- **Tests/acceptance:** `StreamRouteCase`: duplicate app streams, stale serial,
  sink removed, profile switch, missing pactl/server, partial success/read-back
  error, all demo paths zero real calls. Actual session validation is required,
  not substituted by Sway or fake numeric IDs. Reference R7.
- **Allocation:** <=128 KiB current inventory, no thumbnails or repeated static
  tables in snapshots; target <=3 MiB active UI/model addition, unmeasured.
  Stop after the 1–2 d spike if the stated contract cannot be proven.

## Q15 — Manual named display layouts

- **Flow:** Save current layout as Desk/Presentation; rename/delete; Preview a
  selected profile; existing Keep/Revert countdown decides. No automatic apply
  at login/dock/charger change. Saver and mirroring conflicts remain authoritative.
- **Owner/seams:** existing `DisplayControl.start/decide`, `display_layout`
  validation and watchdog; a display-owned profile reducer/UI. No second watchdog
  or direct KDL writer. Displays page stays handwritten/legacy by decision.
- **Contract/data:** proposed private, nonportable `displayProfiles` default {},
  <=16 profiles, <=8 outputs/profile, <=64 KiB total. Safe stable profile IDs,
  names <=48 characters; existing supported layout fields only. Atomic schema
  writes unchanged. Saving current layout has no compositor side effect.
- **Identity:** initial exact-connector/topology match. Current normalization
  drops serial; do not guess stable physical identity or introduce/export serials
  silently. Missing/extra output or unsupported mode → review/refuse profile,
  not partial silent apply. Reject all-disabled layout before starting preview.
- **Failure/tests:** `DisplayProfileCase`: roundtrip, 59.94/60.003 modes, scale,
  hotplug after preview starts, session/token expiry, Saver active/restore,
  concurrent mirror/preview, Keep/Revert/shutdown/watchdog recovery. Private-session
  transaction checks plus actual multi-monitor laptop check; rollback journal
  format/policy unchanged. Profile deletion never changes current output state.
- **Allocation:** <=64 KiB saved metadata, no additional resident process;
  existing detached watchdog exists only for its current preview lifetime. R10.

## Q16 — Saved VPN/WireGuard quick control

- **Flow:** Network details lists existing saved VPN/WireGuard connections with
  Activate/Disconnect and Manage VPN externally. Tunnel state is separate from
  internet connectivity; “Connected” is not a privacy/security guarantee.
- **Owner/seams:** current NetworkManager/nmcli parsing, redacted runner, worker
  registry and Wi-Fi conflict admission through narrow network capabilities.
  Saved UUID is authoritative; labels are not command IDs. No cross-import of a
  Wi-Fi UI/controller or extra network service.
- **Contract/data:** bounded <=64 profiles / <=64 KiB metadata, refresh on details
  open and explicit actions, reuse existing refresh opportunities. Proposed
  activate/deactivate actions operate saved profiles only; no new settings keys,
  VPN creation/import/plugin installer, route editor, kill-switch or autoconnect.
- **Credentials/failure:** existing NM/keyring remains authority. No secrets in
  argv/preferences/snapshot/log/export. Do not run `--ask` without a real terminal
  or wait for an invisible prompt. Interactive SSO/MFA/secret-agent/polkit needs
  detected support or external manager handoff. Preserve nonblocking coordinator,
  bounded cancellation/pending cleanup and network mutation conflict behavior.
- **Tests/acceptance:** `SavedVpnCase`: type/slave filters, duplicate names/UUIDs,
  removed profile, missing plugin/agent, auth failure, Wi-Fi mutation conflict,
  connect/disconnect/read-back uncertainty, redaction, demo zero calls. Actual
  NM tunnel/keyring/MFA behavior needs real-session check. Reference R11.
- **Allocation:** zero new resident process/poller. One bounded nmcli operation
  through the current pool; external auth/editor cost labeled separately.

## Common completion contract for any authorized family

- The prior behavior is characterized first; unchanged existing assertions and
  frozen fixtures remain. Approved new behavior gets its own focused cases.
- Every displayed success is tied to authoritative domain state or an exact
  operation result; no fake optimistic success, generic retries or destructive
  fallbacks. Registered failures never retry through legacy routing.
- Withdrawal hides new affordances, rejects new invocations, destroys transient
  UI buffers, preserves saved settings/data/IDs. It does not kill detached user
  jobs or change existing backend-retention policy. Follow the owning feature's
  existing bootstrap rule (e.g. Notifications withdrawn starts no server).
- Smoked/Liquid/Material-Saver, keyboard focus, preview/demo, Settings reuse,
  concurrent Settings writes and ordinary close/reopen behavior are covered.
- No additional always-running process, polling cadence change, lower blur/
  image quality or animation downgrade. Measured branch sanity and final gates
  follow STATE; hardware limitations remain explicitly named.
