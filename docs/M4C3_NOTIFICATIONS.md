# Notifications withdrawal contract
Disabling the notifications catalog entry takes effect after shell/Settings restart.
No NotificationServer is started; the shell does not own the notification bus name.
Toasts, notification popup, control tab, Settings page and legacy bar UI are hidden.
The saved bar layout and module IDs remain valid and are never rewritten.
Notification preferences and history bytes remain intact, including muted apps/DND.
Local notifications and mute/DND requests do not write while the feature is withdrawn.
Re-enabling restores access through the same public panel/page/IPC IDs and tab index 4.
Enabled history, annotation click-through, mute/DND and toast suppression remain unchanged.
Bootstrap contexts are explicit; demo/preview retain their existing server guards.
