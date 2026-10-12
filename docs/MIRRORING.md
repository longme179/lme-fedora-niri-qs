# Mirror to a monitor or projector

Display mirroring shares one **entire active display** with a second connected
display. It uses the existing `wl-mirror` capture/rendering client and niri's
fullscreen-output support. It does not change your saved monitor arrangement,
resolution or scale, and it does not stream to a remote computer.

## Prepare

Install the optional Fedora package yourself:

```bash
sudo dnf install wl-mirror
```

Fedora 44 packages version 0.18.5. The integration needs the
`--fullscreen-output` option (0.16.4 or newer). LME rechecks missing tools on
demand, so installing the package does not require a shell restart.

Connect the external display and enable both outputs in niri. Open **Settings →
Displays** or **Control Center → Devices → Display mirroring**. If Settings runs
independently, start the main LME shell first: it owns the mirror process, and
Settings sends requests to it over IPC.

## Present

1. Enable mirroring, select **Source** (usually `eDP-1`) and **Destination**
   (for example `HDMI-A-1`). They must be different, active outputs.
2. Click **Start mirror**. A fullscreen window on the destination fits the
   source image with letterboxing when aspect ratios differ; it does not crop.
3. Click **Stop mirror** to close LME's window and return to the destination
   workspace. Other capture or mirror processes are left alone.

The source includes application windows, the pointer and shell UI. Notification
popups follow the existing **Do not disturb while sharing** preference. Keep
private windows off the source display. Niri's capture restrictions still apply.
Keep the destination on its presentation workspace; switching away from that
workspace can hide the fullscreen mirror window.

Disabling the feature, disconnecting/disabling either display or closing LME
stops its child. Capture failures appear in the widget. No NVIDIA probe runs to
start a mirror: `wl-mirror` chooses its Wayland/EGL capture backend, with its
existing DMA-BUF/shared-memory fallback. Recording encoder preferences are
independent of display mirroring.

## Check on your hardware

Start with a terminal on the source and confirm its text and pointer appear on
the destination. Resize/move a source window, check fit on a different aspect
ratio, then Stop and confirm the destination workspace returns. Start again,
unplug the external display and check that the widget stops with a clear message.
Repeat through standalone Settings with the main shell running.

Automated coverage checks validation, owned child cleanup, error reporting,
Settings IPC and real Wayland UI controls using a demo projector. Real output
capture and hybrid Radeon/RTX presentation need this hardware check; they were
not exercised in the cloud environment. See [attribution](../THIRD_PARTY.md).
