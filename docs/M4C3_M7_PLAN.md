# M7 coordinator action inventory and proposed order (not authorized)

Inspected `DesktopBackend.perform`, `perform_demo`, `handle`, `start_feature`,
`finish_features`, the charge executor and the four registered providers.
There are **89 concrete action IDs**: 59 synchronous dispatches (5 already in
providers), 29 asynchronous/worker actions and 1 conditional action (`suspend`).
This expands the open `appearance*` prefix to Save/Apply/Delete and counts the
five registered IDs once; arbitrary prefix matches are not additional actions.

| Domain | Sync | Async | Conditional |
| --- | ---: | ---: | ---: |
| Registered Launchpad/Night Light/Idle/Keybinds | 5 | 0 | 0 |
| Coordinator/preferences/platform | 8 | 0 | 0 |
| Local content/notification storage/desktop edit | 5 | 0 | 0 |
| Launcher/files/windows/overview/workspaces | 7 | 1 | 0 |
| Audio/backlight/Bluetooth | 7 | 0 | 0 |
| Wi-Fi | 2 | 5 | 0 |
| Weather | 1 | 3 | 0 |
| Appearance/profiles/palette | 6 | 1 | 0 |
| Wallpaper/Gowall | 1 | 10 | 0 |
| Capture/annotation | 5 | 4 | 0 |
| Display/mirroring | 7 | 0 | 0 |
| Power/recording/monitor | 5 | 5 | 1 |
| Total | 59 | 29 | 1 |

"Sync" describes the dispatch/ack path, not absence of subprocesses or persistent
controllers. Screenshot start, display preview and mirroring acknowledge directly
but retain managed lifecycle/watchdog state. Weather acknowledges directly while
its controller owns workers: counted async because its state/completion seam needs
more than the current synchronous registry. Charge has its separate executor.
Lock is async; suspend is async only with lock-before-sleep enabled.

Proposed order, with separate authorization and characterization before each:
1. Local content: calculate, copyText, notesInit and notificationSave; narrow
   validator/runner/storage callbacks, unchanged result/query and demo policies.
   These are the cheapest next candidates; desktopEdit remains a host IPC seam.
2. Direct audio controls and scalar profile/palette operations; preserve settings
   context admission, errors, read-back invalidation and demo state projection.
3. Window/launcher operations; retain history, literal argv, terminal selection
   and compositor validation. Keep refresh/platform/preferences orchestration
   at the composition root until their ownership seams are explicit.
4. Authorize an async extension separately, piloting wallpaperScan (stdlib,
   existing feature-job completion). Preserve acknowledgement-before-completion,
   sequence, pending ownership, cancellation and snapshot/result publication.
   Then palettePreview, wallpaper/Gowall, Wi-Fi, weather, capture/recording.
5. Display/mirroring and power last: watchdog/confirm/revert, settings-to-shell
   forwarding, charging executor, saver/recording guards and lock/suspend order
   need dedicated lifecycle tests. No cadence, cache or power-policy redesign.

Both live and demo dispatch trees must move together; unknown IDs/prefixes keep
legacy routing and registered errors never fall back. No async extension or
second-domain provider conversion is part of M4c-3.
