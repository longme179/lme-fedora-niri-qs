# Network connections

Open the Wi-Fi popup or Control Center → Devices, then **VPN, Ethernet & hotspot**.
This view manages saved NetworkManager connections. It reads on open, Refresh and
action completion; the timestamp is an observation, not a continuous status feed.

## Saved VPN and WireGuard

Choose a profile and its connected base adapter, then Connect. Duplicate names
remain separate profiles; the card shows the UUID suffix. WireGuard uses its
saved virtual interface rather than binding the tunnel to a physical adapter.
Disconnect/Stop targets the displayed activation, not every use of that UUID.

NetworkManager, the system keyring and the session authentication agent retain
credentials. Missing credentials, plugins or authorization produce an actionable
error; use Edit/Advanced network settings to finish setup. The shell does not
import VPN files or store passwords. Panels close before activation so an external
agent can receive keyboard input; reopen the view to inspect the result or cancel.

## Ethernet

Select the saved profile and compatible adapter. An unplugged cable is identified
when NetworkManager reports carrier state. Cards show saved IPv4/IPv6 methods,
saved IPv4 addresses/DNS and observed addresses for active connections. **Edit**
opens `nm-connection-editor` for that exact UUID to configure IP, DNS and routes.
If a profile is already active on another adapter, disconnect it explicitly first.

## Hotspot

Prepare a saved Wi-Fi profile in Advanced network settings: AP mode, shared IPv4
and WPA-PSK or SAE security. Select an adapter, then **Review hotspot…**. The fresh
warning identifies the Wi-Fi connection that will be dropped, other observed
uplinks and NetworkManager-managed sharing effects. Confirm only after reviewing
that warning. Changed profiles, adapters or activations require a new warning.

The adapter must support AP mode and have both hardware/software Wi-Fi enabled.
An active AP confirms NetworkManager activation; it does not prove Internet access.
LME does not promise to restore the previous Wi-Fi after a failed/cancelled attempt.

## Errors, cancellation and limits

Connect, disconnect, hotspot and legacy Wi-Fi writes share admission. Cancellation
interrupts the existing command and checks the actual state; it stops only a new
activation belonging to that attempt, then releases pending ownership. A late
cancellation reports that the operation already finished. Other adapters' existing
activations are retained. Retry retains the selected profile/adapter only while
the NetworkManager server identity remains unchanged.

CLI success alone is insufficient: the shell reads back activation state. If that
cannot be established, it reports observed/unknown state rather than success. Each
command and inventory is bounded; at most 64 supported saved profiles and 128 KiB
of normalized metadata are retained. Unsupported/controller profiles stay in the
system editor. No additional daemon or monitor runs for this view.

The feature uses existing `nmcli`, systemd `busctl` and `nm-connection-editor`
integration. Disabling catalog entry `wifi` hides this additional view while
retaining legacy Wi-Fi, saved NetworkManager profiles and shell preferences.
Standalone Settings cannot start these workers; demo uses in-memory connections.

## Verification scope

Copied-checkout native tests use a private Sway/D-Bus session, the real backend
and workers, and a fake NetworkManager CLI. They cover selection/read-back,
redacted errors/retry, warning/cancel/stale plans, confirmed AP activation,
cancellation after side effects, close/reopen, withdrawal and Settings isolation.
Physical Ethernet, VPN plugins/keyring/agent integration, AP capability and shared
Internet/firewall behavior **need a real-session check**.

For development, run inside a disposable Wayland/D-Bus session:

```sh
LME_TEST_NETWORK_UI=1 PYTHONPATH=scripts:tests python3 -m unittest -v test_network_ui
```

G0 skips these six opt-in cases by default; exercise them explicitly for W2.
