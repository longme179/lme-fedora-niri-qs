# W2 — Network connections implementation

Authorized: saved VPN/WireGuard, Ethernet profiles and deliberate saved-hotspot
activation. W1 and the previous practical roadmap stay accepted; W3+ is outside
this branch. Follow STATE.md, Ponytail and the local Modularity adapter.

## Boundaries

- NetworkManager owns profiles, routes, DNS, credentials, authorization and AP
  sharing. No shell credential database, new preference keys or secret agent.
- Reuse wifi_actions, its admission guard, the existing worker pool and completion
  emitter. Catalog feature wifi composes the existing five Wi-Fi specs with W2.
  Keep old imports/actions and the working authentication/retry path unchanged.
- New parser/model and command helpers stay network-owned, stdlib and flat.
  Pass narrow callbacks; never pass DesktopBackend. No new dependency exception.
- Add a lazy Network connections popup to WifiWidget, accessible from Devices
  and the existing Wi-Fi popup. Existing bar/page/tab order and layouts stay.
- Read on open, Refresh and completion only. No additional monitor or polling.

## Contracts

- Inventory: fresh system-bus ID/NM unique owner, device D-Bus path, profile UUID,
  type, binding and active-connection path. Labels never identify an operation.
- Parse only explicitly selected secret-free nmcli fields. Exclude controller/
  slave and unsupported profiles; preserve duplicate names as separate UUIDs.
  Bound discovery, command output and normalized state (64 profiles/128 KiB).
- VPN uses an explicit connected uplink; WireGuard honors its saved virtual
  interface. Ethernet selects one compatible managed adapter/profile. Editing
  delegates to nm-connection-editor for that UUID; no in-shell IP/DNS writer.
- Disconnect addresses a freshly validated active-connection path and device,
  not a generic first device or all activations of a UUID.
- Saved AP must use AP mode, shared IPv4 and WPA-PSK/SAE; selected Wi-Fi adapter
  must report AP capability and enabled hardware/software radio.
- Plan/confirm/start: show current selected-adapter Wi-Fi disruption, other
  observed uplinks and NM-managed sharing effects. Revalidate the plan token,
  UUID, adapter and epoch before activation. AP active does not prove Internet.
- Never ask nmcli invisibly for passwords. Existing agents/keyring handle saved
  credentials; missing secrets/plugins/auth return sanitized actionable errors.
- One admitted network mutation, shared with Wi-Fi writes. Bounded activation
  and observed read-back. Closing UI does not abandon ownership. Cancellation
  sets an Event, interrupts the existing runner and targets only the attempted
  connection during cleanup; publish observed outcome before releasing ownership.
- Failed AP activation/cancellation does not promise previous Wi-Fi restoration.
- New snapshot appears only after first use. Demo uses an in-memory inventory,
  no processes/writes. Settings rejects mutation before demo/live dispatch.
- Disabled catalog entry hides only W2 UI; legacy Wi-Fi/actions/data remain.

## Execution and verification

1. Freeze existing Wi-Fi specs, registration/no startup work and compatibility;
   show new characterization passing before production changes.
2. Add bounded inventory/planning/command contracts and fake NM fixtures before
   implementation: stale IDs, duplicate labels, active-path scope, errors,
   redaction, Wi-Fi conflicts, cancellation, AP confirmations and demo isolation.
3. Implement provider/helpers, then lazy UI. Keep each new source <=250 nonblank
   lines and existing file ceilings; retain import facades.
4. Native copied-checkout UI: open/refresh/select, connect/read-back/error retry,
   hotspot warning/cancel/stale plan, close/reopen, withdrawal and worker isolation.
5. Affected G0/G1 and focused cases during work; final G0-G4/G6 once, plus native
   cases. One ten-launch/RSS sanity check per STATE; no D1 profiling or raw logs.
6. Record one migration entry <=30 lines, guide and laptop checklist <=6 lines;
   push review branch, owner merges. NM/keyring/AP/wired hardware needs real-session
   check; a fake nmcli success is not hardware acceptance.
