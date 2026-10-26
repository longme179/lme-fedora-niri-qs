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

## One-shot memory inventory

From the checkout directory, run each command after the described state settles:

```bash
python3 scripts/memory_report.py --label steady
# Open Settings and leave it visible, alongside the normal shell.
python3 scripts/memory_report.py --label Settings-open
# Exercise the usual panels/media/widgets and any ordinary Launchpad jobs.
python3 scripts/memory_report.py --label ordinary-active --json
```

The tool is read-only and runs once; it does not launch/stop applications, read
environment variables, print user command arguments or save a report itself.
For an explicitly invoked timed workload and automatic PSS/budget/Settings-exit
checks, see [Laptop memory workload](LAPTOP_MEMORY_CHECK.md). That separate optional
tool opens panels and Settings; its private native baseline is currently unresolved.
It includes recognized current-user LME scripts across checkouts, their Quickshell
ancestors, workers and descendants, including surviving detached log relays.
PSS/RSS are KiB; the displayed MB are decimal. The inclusive PSS includes job
payloads; the separate shell/helpers subtotal excludes identified relay payloads.
Other descendants are conservatively included: review launched applications rather
than silently charging them to the shell or omitting them from the inventory.

Review the PID list and checkout roots first. Independent/reparented daemons
(for example an awww-daemon surviving its original backend), shared services and
payloads that daemonize away from their relay may need explicit `--pid PID`
additions; the option is repeatable and never overrides read/identity diagnostics.
Unattributed Quickshell PIDs can belong to other shells: verify ownership before
adding them and document any confirmed exclusions. The collector excludes itself.

Exit 0 means the selected snapshot had counters and no detected ambiguity; it
does not certify complete ownership, a memory budget or release readiness.
Exit 1 means incomplete/no selected processes: inspect issues and repeat after
transient processes settle. Missing PSS, permission failures and PID reuse never
become zero or a successful total. Summed RSS double-counts shared pages.

Record theme, outputs, media/widgets, instance/worker/relay counts and temporary
heavy jobs with the result. Only an inventory reviewed on the laptop can close
the table's memory row; the other hardware/integration rows remain manual checks.

## Combined private-session result (2026-10-26)

Main 83f9cad, verification head 17b2064; production runtime is byte-identical.
The copied real shell/Settings have read-only probes; the original Clipboard
worker is restored before launch. One virtual output, software OpenGL/pixman,
Jelly-v2, demo backend, real private two-entry history, capture/weather lookup/
Bluetooth pairing/desktop shapes off. No media, encoder or real device workload.
Sway does not reproduce niri compositor blur or a physical GPU allocation path.

All samples below use complete collector counters, no outside-scope LME PIDs,
and aggregate PSS for the fixture checkout. MB are decimal, including payloads.
The three/five-process states are main QS/backend/history, then Settings/backend;
21 adds eight relays and eight synthetic idle Python payloads.

| Scenario | PIDs | Smoked PSS MB | Liquid PSS MB |
| --- | ---: | ---: | ---: |
| Fresh steady shell | 3 | 246.58 | 268.76 |
| Settings open alongside shell | 5 | 461.54 | 517.78 |
| After 18 panel open/close cycles | 5 | 672.57 | 814.08 |
| Settings closed after those cycles | 3 | 421.37 | 533.01 |
| Settings reopened + eight detached jobs | 21 | 699.41 | 829.77 |
| Shell restarted, Settings/jobs retained | 21 | 480.97 | 490.45 |

These are functional-test passes, **not memory-budget passes**: warmed VM states
exceed the <=400/500 MB targets even before heavy tools. Most growth is in the
main Quickshell; backends/history remain small and process counts do not grow.
After close, both loaders unmount, pending clears, and glass registry counts stay
Smoked 0/0/0 and Liquid 1/1/0 (backdrops/consumers/popup regions; Liquid retains bar).
An additional 48-cycle Liquid probe reaches roughly 790k KiB PSS by round three,
then ranges 778299-792544 KiB over rounds three-eight; there is no continued
monotonic rise in that bounded run. This does not prove absence of leaks or name
the allocation owner inside Qt/driver/allocator. No cache/render/power change was
made to force the VM under budget; laptop GPU/ordinary-active samples remain needed.

The owner supplied one laptop steady snapshot: **169.64 MB inclusive PSS, 8 PIDs**,
complete counters and no unattributed Quickshell. This is below the steady target
for the detected inventory. Theme/revision and helper ownership are not recorded;
Settings-open/ordinary-active and independent-helper review remain pending.
Keep the laptop memory row open until those contexts and inventories are reviewed.

To repeat only the private integration cases, inside the disposable session set
`LME_TEST_RELEASE_SESSION=1` and run `python3 -m unittest -v test_release_session`.
Do not run this opt-in against the real desktop/session.
