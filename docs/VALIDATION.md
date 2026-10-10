# Validation and platform limits

Cloud development and the target Fedora desktop are different environments.
The repository includes useful checks that work without controlling the user's
computer, and a separate real-session checklist.

## Development checks

The backend needs Python 3 and no third-party Python packages. The QML runtime
needs Quickshell and matching Qt packages. A useful check sequence is:

```bash
python3 -m compileall -q scripts
bash -n scripts/install.sh scripts/install-fedora.sh scripts/start.sh scripts/doctor.sh
python3 scripts/desktop_backend.py --demo --once
./scripts/install-fedora.sh --optional
./scripts/install.sh --dry-run
```

Run the backend tests with Python's standard library test runner:

```bash
python3 -m unittest discover -s tests -v
```

Installation safeguards can be checked with isolated
temporary `--target` directories; never test replacement against your actual
desktop config unintentionally.

Use a running Wayland compositor for QML runtime checks. Qt's `offscreen`
platform does not load Quickshell's `PanelWindow` backend and is not a substitute
for a compositor. A nested, headless Sway compositor with software rendering
can exercise the shell without controlling the host desktop. On a real Wayland
desktop, `scripts/start.sh --preview` opens a sample-data window safely.

During cloud development, the original five panels were rendered both as previews and
in the normal layer-shell layout at 1920×1080 under headless Sway 1.10.1,
Qt 6.8.2, and Quickshell 0.3.2. The final normal runtime log contained no QML
errors or warnings. The images in [previews](previews) show the actual QML;
their captions distinguish sample desktop state from native-service captures
with test notifications and mock applications.

The expanded control center and workspace board were also rendered at
1920×1080 with the same Qt/Quickshell toolchain, with its PipeWire module enabled.
Native Bluetooth tests use a private BlueZ D-Bus adapter fixture. Native mixer
checks use a private PipeWire 1.4.2 / WirePlumber 0.5.8 session, virtual devices
and a `pw-play` stream; they do not control physical audio hardware. Workspace
drag/drop in QML was exercised with virtual pointer input and simulated niri
state; the backend's stable-ID request was checked on a temporary Unix socket.

The following checks passed:

| Area | Verification |
| --- | --- |
| Backend | All 43 Python tests, including BlueZ failures/confirmation/rfkill, stable workspace ordering/movement, task validation, modern and legacy TuneD/PPD interfaces, and application metadata |
| Installation | Dry run, repeated install, overwrite refusal, backup preservation, broken symlinks, unsafe-target rejection |
| Startup | Demo/preview avoids desktop mutations; argument quoting and saved-wallpaper restoration |
| Shell scripts | Bash syntax and Fedora package preview; non-Fedora installation refused |
| Notifications | Native D-Bus capability negotiation, bodies/actions, replacement IDs, plain-text markup, action-button callbacks |
| Notification lifecycle | Action and clear-all dismiss with reason 2; expiry sends reason 1; app closure sends reason 3 and removes history |
| Do Not Disturb | Actual UI switch suppresses popups and retains session history |
| Media | Actual native MPRIS UI Play/Pause/Next/Previous callbacks and metadata updates against a mock application |
| Top bar geometry | 42 px bar with 8 px top margin; a borderless test app starts at y=50 under Sway, with no bottom reservation |
| System tray | Dropdown renders 18 px icons; native Activate and D-Bus menu action callbacks; outside click and Escape dismiss, including after a native menu |
| Power profile menu | All three labels readable on a dark popup; right edge stays onscreen; pointer and Down/Enter selection work with simulated backend state |
| Launcher keyboard | Typing `kitty` returns one matching demo app; arrow/Enter launches through the simulated backend; Escape closes |
| Demo isolation | Native media/tray actions and notification ownership disabled in demo/preview; normal native mode remains functional |
| Reusable cloud setup | Signed package installation and pinned Quickshell build repeated successfully; startup instructions use a private headless Wayland session |
| Bluetooth power | Real widget turns a private BlueZ adapter fixture on/off, verified with D-Bus property reads; no physical radio writes |
| Workspace board | Pointer drag moves a simulated window from workspace 1 to 3; selectors use stable IDs and show output names |
| Native audio mixer | Device/stream discovery, output preference metadata, and per-stream volume/mute confirmed in the private PipeWire session |
| Agenda | Calendar rendering, keyboard task add, checkbox completion, and focus timer/stopwatch state retained across panel closure |
| Expanded QML | New components pass `qmllint`; rendered panels and native fixture runs load without QML errors or warnings |

Package installation commands for Fedora 44 were not executed on the Debian
cloud machine. Niri configuration snippets were checked against upstream source
and documentation, but were not parsed by a running niri binary.

A nested compositor does not establish real niri positioning, laptop graphics
acceleration, output refresh rates, device control, or power-management behavior.
Use the target laptop for those checks below.

## Target machine checklist

| Check | Expected result |
| --- | --- |
| `scripts/doctor.sh` in niri | Required tools and session connections are available |
| `niri validate` | Existing config plus shell bindings parses successfully |
| Launcher | Search, arrow navigation, Enter launch, Escape close |
| Top bar | Workspace/title updates, aligned pills, compact tray dropdown, and application spacing follow the configured niri gap |
| Control center | Volume/mute, backlight, radios, supported power profiles work |
| Audio mixer | Output/input selection and per-device/app sliders change the intended PipeWire nodes |
| Bluetooth | Correct adapter; power and known-device connection work; failures show service/rfkill details |
| Overview | Native live previews and drag/drop; board focus/movement on each output, including cross-output moves |
| Agenda | Tasks survive shell restart; focus timer/stopwatch persist across panel closure; timer completion respects DND |
| Motion and idle | Panels slide smoothly; disabled motion is immediate; Stay awake inhibits idle and resets on shell restart |
| Notifications | `notify-send` popup, notification center, DND work |
| Media | Compatible MPRIS player metadata and controls update |
| Settings | Preferences survive restart; chosen raster wallpaper restores |
| Displays | Correct placement on internal panel and any external output |
| Laptop graphics | Integrated GPU is suitable; idle shell stays responsive |
| Lock and suspend | Lock authentication, suspend/resume, radios after resume |
| Native screenshot | Capture succeeds and uses configured screenshot location |

Power-off, reboot, logout, suspend, hardware radio toggles, and backlight writes
must not be exercised automatically in a cloud test or during read-only
diagnostics. Perform those checks deliberately on the laptop after saving work.

No cloud result certifies MediaTek MT7921 firmware behavior, NVIDIA driver
integration, exact 120 Hz output modes, battery consumption, thermal limits, or
sleep/resume reliability. Those depend on the real Fedora installation.
