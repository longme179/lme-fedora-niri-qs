# Desktop upgrades

These seven additions retain the connected glass top bar, Roboto, flat Dracula
surfaces and the existing native Polkit agent. Settings and code remain English.

| Proposal | Where to use it | Behavior |
| --- | --- | --- |
| 13 · Appearance profiles | Settings → Appearance; Control Center profile menu | Save and apply accent, opacity, comfortable/compact density and motion together. Dracula stays available as the built-in default. Up to 20 profiles; saving an existing custom name updates it. |
| 9 · Display Settings | Settings → Displays | Native niri modes, including fractional refresh rates, scale and draggable monitor arrangement with exact X/Y fields. Apply, then keep within 20 seconds or revert. The confirmation remains above the scrolling page. |
| 6 · Notification Center | Notification button / Super+N | Group by application, search text, mute app popups, restore expired history after restart, and DND for 15 minutes, 1 hour, 8 hours or until turned off. Muted apps can be allowed again after their history is cleared. |
| 5 · Wallpaper library | Settings → Wallpaper | Browse a folder recursively, search image names, preview, star favorites and apply through awww. PNG, JPEG, WebP, GIF and BMP; thumbnails decode asynchronously with a bounded requested size. |
| 4 · Modular Control Center | Control Center → Edit layout | Drag module grips, use keyboard-accessible arrows, hide/show each tile or card, select full/half width and save automatically. Width is adjustable from 480 to 900 px. Half-width cards stack in a narrow panel. |
| 2 · Smart launcher | Applications button / Super+Space | Name/keyword ranking, subsequences and small spelling mistakes, persistent favorites, arithmetic, emoji/symbol search and currently open windows. |
| 3 · Wi-Fi connections | Wi-Fi bar button, Control Center tile or Devices tab | Scan, enter a password in the shell, connect/disconnect, reconnect saved profiles and confirm before forgetting one. Busy and error states stay visible. |

## Displays

An independent Python watcher applies the preview and restores **mode, scale and
position** on timeout, a partial command failure or a revert request. Closing
Settings or exiting its backend does not cancel that watcher. Only modes reported
by the active output are accepted; this interface does not disable your last
screen or rewrite your niri configuration.

Confirmed layouts are saved in `settings.json`. The supplied `scripts/start.sh`
restores supported saved modes on currently attached screens at the next start,
skipping disconnected screens and modes no longer advertised. If you start with
`qs -c gpt` directly, either use your installed `scripts/start.sh --config gpt`
instead or run `python3 scripts/desktop_backend.py --restore-displays` at startup.
A niri configuration reload can override these runtime settings.

The watcher protects against ordinary application exits. It cannot restore after
an OS/compositor crash, or after the watcher itself is killed with SIGKILL. Test
60/120 Hz and external displays on your actual laptop before relying on a saved
layout. Orientation, HDR and VRR are outside this iteration.

## Launcher

- Type app names normally; star an app or use **Favorites** to filter.
- `= (2 + 3) * 4` calculates; Enter copies the result with `wl-copy`.
- `: smile` searches the bundled Unicode emoji/symbol names; Enter copies.
- `@ terminal` searches open window titles/app IDs and focuses the selection.
- Up/Down chooses a result; Enter activates; Escape closes.

Arithmetic supports `+ - * / // % **`, parentheses, decimals, and `× ÷ ^` aliases.
It uses an AST whitelist rather than evaluating code. Expressions and exponents
are bounded; unsupported syntax and division by zero show an inline error.
File search remains a separate future feature.

## Wi-Fi

NetworkManager owns scanning, credentials and saved connections. The shell sends
passwords to `nmcli --ask` through stdin, never command arguments, snapshots or
logs. Password inputs are masked and cleared when their popup closes. Network
operations run in background workers so the JSON backend can acknowledge other
actions. Scans happen on request; periodic status sampling uses the cached scan.

Saved profiles can reuse their existing secret or accept a replacement password.
NetworkManager may request authorization through the existing Polkit popup.
Enterprise networks with certificates/account configuration use **Advanced
network settings** (`nm-connection-editor`). Hidden-network creation is outside
this iteration. Never install two competing session authentication agents.

## Local data and requirements

Preferences share the existing atomic, locked `~/.config/lme-shell/settings.json`.
Notification history is stored privately beside it in `notification-history.json`
(up to 200 entries; summary 512 characters and body 4096 characters). Transient
notifications are excluded, and restored records have no live actions or popups.
History is debounced by 500 ms; an abrupt shell crash can lose the newest records.
Clear all removes saved history after the next successful write. DND deadlines
survive restart; expired deadlines automatically stop silencing popups.

Wallpaper scans stop after 500 images or 10,000 paths and report truncation. They
skip image links outside the selected folder. Favorites do not modify source
files. Slideshow and per-monitor wallpaper selection remain for a separate step.

No new Python dependencies are required. In addition to the existing runtime,
install `qt6-qtimageformats` for the advertised image formats; it is now included
in the required Fedora package list and installer. Roboto, Noto Color Emoji,
NetworkManager/nmcli, wl-clipboard and awww remain the existing dependencies.
See [requirements](../requirements-fedora.txt) and [installation](INSTALL.md).

## Validation

Run `scripts/check.sh` for backend contracts and shell syntax. In an isolated
Wayland session with the development virtual-pointer tools:

```bash
LME_TEST_AUTHENTICATION_UI=1 LME_TEST_CLIPBOARD_NATIVE=1 \
LME_TEST_CLIPBOARD_UI=1 LME_TEST_ACTIVITY_UI=1 LME_TEST_UPGRADE_UI=1 \
LME_TEST_DISPLAY_WATCHDOG=1 LME_TEST_POINTER=/path/to/pointer-click \
LME_TEST_DRAG=/path/to/pointer-drag scripts/check.sh
```

`upgrades-demo.qml` is gated by `LME_TEST_UPGRADES=1` and uses sample state. The
watchdog integration test supplies a fake niri command on a private PATH and
waits for real timeout after the initiating process exits. No test changes a
physical output, radio, saved network, charge mode or host authentication policy.
