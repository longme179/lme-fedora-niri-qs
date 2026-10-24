# Resource/lifecycle release checks

2026-10-24. Private test results are in MIGRATION_LOG.md. A release still needs
owner sign-off on the real laptop; simulated device/GPU success is insufficient.
Test the review branch through the normal installation, with the previous shell
instance stopped. Preserve the normal saved preferences for the restore checks.

| Check | Pass criterion | Laptop status |
| --- | --- | --- |
| Startup and integration | Open/close/reopen shell panels and standalone Settings; try Smoked and Liquid, app launch, clipboard copy/search/image annotation, notifications and save Retry | Needs real-session check |
| Radio and media | Bluetooth connect/disconnect/unplug and Wi-Fi bad-password/retry/reconnect; volume/brightness stay responsive; media/lyrics/desktop widgets still behave normally | Needs real-session check |
| Capture and recorder | Image export/annotation/OCR and stale-session close; start/stop recording with audio/region and actual encoders; no stuck pending, retained output on failures | Needs real-session check |
| Detached jobs | Run literal argv, explicit Bash and terminal entries; verify cap marker, exit/error, eight-job admission and survival across shell restart; inspect surviving relays | Needs real-session check |
| Display and power restore | Display apply/confirm/revert and reconnect; battery saver on/off restores prior mode/brightness/theme; charge apply/cancel if supported | Needs real-session check |
| Total memory | Inventory all LME instances, both Quickshells/backends, persistent workers and surviving relays; sum /proc/PID/smaps_rollup Pss for steady, Settings-open and ordinary active use; separate heavy user-job peaks | Needs real-session check |

Use KiB/PSS consistently; summed RSS double-counts shared Qt/Python pages. Verify
the process inventory before accepting a total. A single PID or separate-instance
sample does not establish the <=400 MB steady / <=500 MB ordinary-active target.
Include the actual theme, monitors, media/widgets and active-job count in the result.
The private simultaneous scenario uses default Smoked and no physical GPU/radios;
its scoped outcome cannot close the laptop column above.

Do not publish a fully validated release while a relevant laptop check is pending.
