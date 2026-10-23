# Ported features: stability and QoL review

Reviewed 2026-10-23 against main a963481 and the Wi-Fi feedback branch.
Scope: all current action providers, shared dispatch/completion/runner, settings
transfer, Launchpad jobs, and Clipboard/Notifications/Desktop bootstrap seams.
This is a targeted code review with private-session tests, not a hardware audit.

## Wi-Fi changes in this branch

- The old runner ignored nmcli's repeated secret prompts until its overall
  deadline. A fake process reproduces that wait without accessing a radio.
- The runner now optionally observes cumulative subprocess output. Wi-Fi owns
  phase parsing and authentication decisions; other commands keep their behavior.
  NetworkManager source confirms `--pretty` progress and `--ask` secret prompts:
  [common.c](https://gitlab.freedesktop.org/NetworkManager/NetworkManager/-/blob/main/src/nmcli/common.c),
  [utils.c](https://gitlab.freedesktop.org/NetworkManager/NetworkManager/-/blob/main/src/nmcli/utils.c).
- Repeated password requests fail promptly. Missing passwords and known invalid
  WPA/WPA2 PSKs produce actionable errors. Saved credentials, WEP, SAE and
  enterprise validation remain with NetworkManager/the advanced editor.
- Authentication has a 15-second limit, with a bounded device-state fallback;
  reaching IP configuration retains nmcli's 45-second deadline/50-second runner
  budget. This is not a promise of instantaneous diagnosis on every driver.
- Cleanup only disconnects the same observed ActiveConnection while still in
  an authentication state. A changed connection, DHCP or successful connection
  is left alone; missing/failed state queries skip destructive cleanup.
- The dialog keeps the network on failure, clears the secret immediately after
  submission, supports retry, closes on success and blocks stale-adapter submits.
  Closing it during a pending attempt explicitly leaves the attempt running.
- No new persistent monitor, executor, process pool or background polling cadence.
  Passwords remain stdin-only, in a memfd, with existing error redaction.

## Findings for the next branch

| Priority | Finding and evidence | Smallest proposed correction |
| --- | --- | --- |
| P1 | `audio_actions.py:bluetooth_device` is a sync registry action with a 15 s busctl timeout. `handle()` invokes it on the coordinator; a slow BlueZ call holds subsequent input/completion delivery. Mock invocation confirms sync/15 s. | Move only device connect/disconnect to the existing worker contract, retaining context admission, demo behavior and read-back invalidation on completion/error. Add delayed-BlueZ tests proving volume and pending delivery stay responsive; physical pairing needs a session check. |
| P2 | `local_content_actions.py:notifications` installs history before `write_json`. Injecting a write error leaves the new history in memory despite a failed result and old disk contents. Restart restores the old disk history. | Validate, persist atomically, then install memory. Characterize failure/retry and keep QML's visible history and persistence debounce policy separate. No storage-format change. |
| P2 | `settings_transfer.py:export_document` reserves the destination with O_EXCL but does not remove its own newly created file after write/fsync failure. Injecting fsync failure leaves a destination and a retry raises FileExistsError. | Stage a private 0600 file, fsync, then publish without overwrite (for example with an exclusive hard link) and clean the stage on failure. Test partial write, fsync failure and destination races without touching Preferences transactions. |
| P2 | Wi-Fi ownership is per action ID, not per adapter. `WifiDispatchCase.test_job_errors_duplicate_owners_and_one_completion_per_snapshot` deliberately demonstrates five concurrent action IDs; UI busy guards serialize the usual route, other callers need not. | Design adapter-scoped admission for conflicting connect/saved/disconnect/forget/toggle operations. Preserve read-only scan/summary behavior; obtain approval for the existing concurrency expectation before changing it. No second scheduler. |
| P3 | Launchpad bounds active jobs (8) and tracked jobs (100), but stdout/stderr go directly to an unbounded per-entry log. Re-running truncates it; a noisy long-running entry can still exhaust disk. | Add an explicit bounded-log policy and recovery UX in a separate Launchpad QoL change. User-owned detached jobs must survive shell exit. This is a disk-growth issue, not evidence of a shell RAM leak. |

The first three findings were reproduced with mocked commands/storage in a
scratch script; the last two follow directly from existing tests and file I/O.
They are documented, not silently fixed by the Wi-Fi commit.

## Contracts retained and next plan

- Registry context admission still precedes demo/live routing. Registered errors
  never fall through; the existing scheduler, per-action pending table, sequence
  numbers, ack and one-completion-per-snapshot policy remain authoritative.
- Settings schema/portable membership and lock/reload/merge/fsync/replace remain
  unchanged. Clipboard capture versus history, notification withdrawal and Desktop
  per-output lifecycle stay behind their current shared services/catalog adapters.
- History/widget bounds exist (notifications 200, Clipboard 20–500, Desktop 12).
  These bounds alone do not prove total-process memory use or absence of leaks.
- Recommended order: Bluetooth responsiveness; notification/export failure
  recovery; Wi-Fi group admission; then consider `recordStop` as the next small
  migration. Re-characterize cancellation/ownership before that migration.
  Larger async families still need the seams listed in ASYNC_ACTIONS.md.
- No additional action migration is included here. Avoid a new event bus,
  per-feature backend, queue or timer. Preserve public IDs/data and test each QoL
  change at the domain boundary rather than rewriting the coordinator wholesale.

Real-session checks remain necessary for driver authentication/retries, slow DHCP,
BlueZ, hotplug, compositor/GPU effects and total live-shell plus Settings memory.
