# Audio and headset controls

Open **Control Center → Audio**. Existing default output/input selectors and
per-app volume/mute remain. The new controls add hardware profiles, physical
ports and a destination for each reported live playback stream.

## Use

1. Open Audio or press **Refresh** to read devices/options/current routes.
2. Under **Profiles, ports & app outputs**, choose a card profile or physical
   input/output port. Unavailable options are disabled. A profile change can
   interrupt sound and recreate devices; a call profile can reduce playback quality.
3. For a reported application stream, select its **Output**. Multiple streams
   belonging to the same application are separate; only the chosen stream moves.
4. The selection displays observed state after read-back, not an optimistic choice.
   If it cannot be confirmed, the error stays visible with the observed/unknown
   state. Refresh before deciding whether to retry.

**Checked at** is the last completed inventory read. Refresh after starting a
new app, unplugging devices or changing audio externally. There is no additional
background audio poller. Changing default output does not promise to move every
existing app stream. This feature does not persist per-app rules, auto reconnect
devices, automatically switch call profiles or change system audio policy.
Existing WirePlumber/session-manager policy may remember a destination independently
of LME; this feature does not replace or disable that policy.

## Supported capabilities

- Fedora's existing PipeWire/WirePlumber session and `pulseaudio-utils` (`pactl`)
  with JSON output. The packages are already in requirements-fedora.txt.
- Verified local stream routing uses existing `pipewire-utils`: `pw-dump` and
  `pw-metadata`. The native core cookie must match Pulse and source/sink serials
  must resolve uniquely before metadata can be written. A remote/mismatched core
  is refused; no command targets an unrelated local stream by numeric guess.
- If native tools are absent, a Pulse move is attempted with observed read-back;
  an unconfirmed result is an error. Explicit-client routes can require the
  native tools. No new package/service is installed automatically by the shell.
- Ports/profiles depend on what the driver/server reports. Virtual devices may
  expose neither. Unknown current values display **Not reported**, not the first
  option. Native-only streams without a Pulse playback record are not routed by
  this version; **Advanced audio settings** remains available.
- Port availability accepts pactl's native `availability` strings (`available`,
  `not available`, `availability unknown`), separately from profile `available`
  booleans. An unplugged port is disabled and rejected before mutation; an unknown
  availability remains selectable because the server has not ruled it out.
- Real headset/HDMI ports, call modes and hardware unplug behavior still need a
  real-session check. Virtual audio tests do not establish every device's support.

Fedora dependencies if missing: `sudo dnf install pulseaudio-utils pipewire-utils`.
Run `./scripts/doctor.sh` for missing-tool diagnostics; it does not change routing.

## Ownership and safety

`config/audio.json` owns sources and the selected provider; its index startup
metadata is empty, so no legacy bar/tab/page is registered twice. Disabling this
entry withdraws the addon UI/queries and retains ordinary volume/mute/defaults,
saved layouts/settings and compatibility actions, following current catalog policy.
No preference/default/export format or persistent route database is added.

- `audio_inventory.py`: pure bounded JSON normalization, server-scoped identities,
  availability and selection validation. Pulse indexes and PW node IDs are distinct.
- `audio_devices.py`: on-demand commands and observed confirmation, one operation
  in the existing two-worker pool. No executor/watcher/timer per control.
- `audio_pipewire.py`: validates the matching native core and stream/sink serials;
  sets ephemeral target.object and clears deprecated target.node for that stream.
- `audio_device_actions.py`: composes existing AudioCapabilities controls with four
  worker IDs: audioDevicesRefresh, audioPort, audioProfile, audioRoute. Context
  admission precedes demo/live; standalone Settings cannot mutate these controls.
- `AudioHardware`, `AudioRoute`, `AudioChoice`: handwritten controls using existing
  glass/material/theme resources. Port/profile/route delegates withdraw lazily.

Refresh has a six-second total deadline; changes have eight seconds including
queries, bounded affected-list confirmation and final read-back. Each command
has its own remaining-time/output bound and follows existing runner cancellation.
No busy loop or retry that repeats the mutation. Errors after a side effect can
leave a changed device: the UI reports actual state or explicitly unknown state.

The model is limited to 128 objects, 64 options per list and 256 KiB normalized
metadata; raw commands are also bounded. Oversized/malformed/ambiguous inventories
fail visibly rather than silently dropping targets. No images/textures are stored.
Audio device operations reject another audio operation or an already pending
Bluetooth connection. External changes can still race a request; final read-back
detects an unconfirmed result. Existing Bluetooth, volume and mute contracts stay.

## Compatibility and tests

Old AudioCapabilities/provide_audio exports remain import facades. Retire them
only at zero consumers with owner approval. Descriptor fallback remains for broken/
missing catalog metadata. The demo projection retains the legacy launchpadJobs
absence contract while showing new domain projections; remove that exclusion only
after an explicitly approved demo API/fixture change.

Characterization/goldens pin existing commands/context/preferences and real mixer
open/close. New units cover JSON variants/bounds, IDs, stale servers/streams,
unavailable options, pending/errors, no demo spawn/write, native core validation
and exact metadata targets. Native G1 covers controls/demo/error/withdrawal and
stable open menus. Additional opt-in virtual audio tests use private PipeWire,
WirePlumber, two null sinks and two clients; hardware monitors are disabled.
Merge-audit cases cover timeout recovery, mid-read server restart, reused sink
indexes, partial metadata side effects and native port availability. The copied
UI probe retains audio completions across unrelated notification acknowledgements;
this observation aid adds no cache or hook to the installed shell.

In an already private D-Bus/Wayland test environment with the tools installed:

```bash
LME_TEST_AUDIO_UI=1 LME_TEST_AUDIO_SESSION=1 PYTHONPATH=scripts:tests \
  python3 -m unittest -v test_audio_session test_audio_headset_ui
```

Use disposable XDG/runtime directories and private compositor/session; never the
running user shell/config. Default G0 explicitly skips native cases; skips are not
passes. `scripts/run-gates.sh --gates G1` runs the device-independent native UI set.
