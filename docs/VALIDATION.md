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
| Backend | All 75 Python backend tests, including authentication cancellation, BlueZ failures/confirmation/rfkill, stable workspace ordering/movement, task validation, modern and legacy TuneD/PPD interfaces, and application metadata |
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

The Material/settings update passed eight additional tests covering layout
validation, nested-default isolation, stale-writer merging, external reload,
settings-only backend restrictions, demo isolation, desktop-entry installation and symlink-target protection.
All 51 tests passed. The six main panel previews, five standalone settings pages
and three alternate control-center tabs rendered without QML warnings/errors.
Roboto was resolved through fontconfig rather than replaced by a fallback.

The actual Settings window was exercised under the private Wayland compositor:
row reorder and cross-zone drag wrote the expected module arrays; changing the
shape was reflected by the separate running shell; repeated launch selected the
requested page through IPC. Its 800×600 minimum size remained usable with page
scrolling. Notification ownership stayed with the original shell while Settings
was open. These are cloud UI checks, not physical-device tests.

Package installation commands for Fedora 44 were not executed on the Debian
cloud machine. Niri configuration snippets were checked against upstream source
and documentation, but were not parsed by a running niri binary.

A nested compositor does not establish real niri positioning, laptop graphics
acceleration, output refresh rates, device control, or power-management behavior.
Use the target laptop for those checks below.

## Authentication popup validation

The native Polkit agent registered successfully when the real shell was started
without a controlling terminal on a private D-Bus authority fixture. The test
used a process-local login-session lookup fixture because the headless cloud
process is not in a real logind desktop session. It did not use the host Polkit
service, run PAM, submit a real password or grant privileges.

Six additional dialog tests exercise the actual QML window under headless
Wayland using virtual keyboard input: masked entry, failure/retry and Enter
success, Escape cancellation, Tab/Space on Cancel, account changes, a new
conversation clearing old input, and visible (non-password) challenges.
These use a simulated conversation in `authentication-demo.qml` and verify
that response text does not appear in its logs. The backend cancellation test
confirms that pending charging clears and the actual threshold remains unchanged.

To repeat all checks inside a **private Wayland test session** with `wtype` and
Quickshell installed:

```bash
LME_TEST_AUTHENTICATION_UI=1 ./scripts/check.sh
```

Without that environment variable, the six GUI tests are skipped; ordinary
backend checks remain usable without a compositor. For a manual isolated dialog
preview, run `quickshell -p authentication-demo.qml`. It accepts only the dummy
response `test-only`; do not enter a real password into a demo. It never starts
an authentication agent or performs a privileged operation.

The target laptop still needs verification of actual Polkit/PAM authentication,
successful helper execution, and its firmware's charging read-back. Check
[AUTHENTICATION.md](AUTHENTICATION.md) for the real-session setup.

## Wallpaper, weather and charging update

On 2026-10-11 (Asia/Saigon), `scripts/check.sh` passed **74 tests**. The new
contracts cover awww daemon startup/readiness, missing/failed commands, safe
path arguments, restoration without preference changes, numerical charge
thresholds, fixed IdeaPad conservation, modern `charge_types` enums, rollback,
readback rejection, asynchronous charge acknowledgements, weather geolocation,
forecast/search parsing, units, refresh/backoff/stale state, atomic manual
location selection and demo isolation.

Native `awww` **0.12.1**, pinned to
`f66e12a76dbc4c669b2f1375f78bce49f5b19d66`, was built with Rust 1.89.0 and
Cargo.lock. Its real daemon started automatically on the private Sway output.
The restoration CLI applied the bundled PNG; `awww query` confirmed the image
path and 1920×1080 output. The Settings backend action applied a fade and saved
its temporary preference file only after success. The upstream build emitted
three unnecessary-unsafe warnings; it completed successfully.

Live HTTPS requests successfully detected approximate IP location, parsed
current weather and a three-day forecast, and returned city-search results.
The native Settings UI searched for Da Nang and selecting a result saved its
normalized coordinates with automatic mode disabled. All preference writes
for that check used an isolated temporary config directory. No cloud location
is included in published preview images.

Control Center and Weather settings rendered under Qt 6.8.2 / Quickshell 0.3.2.
Weather remained usable at the Settings window's 800×600 minimum size with
scrolling. Clicking the demo charging button changed the displayed limit from
85% to 100%. Topbar labels were readable at 13 and 16 px, and Overview and
Applications opened after a one-second hover with no tooltip. New weather and
charging QML and the updated bar passed `qmllint`. ShellState retains two known
Quickshell metadata warnings about `QProcess::ExitStatus`; native/preview
runtime logs contain no QML errors or warnings.

Charge writes were tested against synthetic sysfs files only. The privileged
helper was previewed, never installed on the cloud host. Fedora package
availability, Polkit authentication and the Lenovo's physical charging cutoff
still need target-machine validation. The niri startup fragment was updated to
use the wallpaper wrapper but was not parsed by a niri binary in this cloud.
Reusable cloud install/start instructions now include pinned awww activation
and the Codeberg/Open-Meteo/IPwho.is network destinations. Saving that draft
does not prove publication or restoration into a fresh task.

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
| Charging | Supported thresholds or firmware conservation mode are detected; both choices are read back after authentication; verify physical cutoff on AC |
| Weather | Automatic IP location resolves, forecasts load, manual city and units update, offline errors preserve stale data |
| Settings | Independent window opens from launcher/bar/Super+Comma; changes reach the shell without restart; search, keyboard navigation and selected states work; wallpaper applies |
| Modular bar | Add/remove modules, reorder arrows, position menus and cross-zone drag/drop persist; connected pill is the default; crowded groups remain usable |
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

## Clipboard and Activity update

On 2026-10-11, all **98 checks** passed under the private Sway 1.10.1 session
with Quickshell 0.3.2, Qt 6.8.2 and wl-clipboard 2.2.1. This includes 89 backend
checks and nine optional native/dialog checks. The new tests cover Unicode and
multiline round trips, deduplication, full-text search, filters, image MIME/cache,
persistence, permissions, pause, pin limits, oldest-first/content-budget cleanup,
stale IDs, sensitive hints and validated settings. Supported recorder detection
uses synthetic proc fixtures, including other-user and zombie rejection.

A real `wl-paste --watch` / `wl-copy` integration test captured and restored
both text and PNG bytes, then exercised pause/resume and clear with/without pins.
The actual Clipboard QML was driven with virtual keyboard and pointer input:
search/Enter copied the intended bytes, including Enter before search debounce;
image preview, pin, confirmed clearing with retained pins and delete worked.
History for these tests lives in temporary directories. Updating the shared
Settings preferences also stopped/restarted capture while retaining history.

A private-bus MPRIS player exercised actual Play/Pause, Next and Previous button
callbacks and metadata updates. The Activity QML test started/paused/reset the
shared timer, verified stopwatch persistence across panel closure, reached timer
completion, closed with Escape/Close and disabled motion. A normal layer-shell
smoke check opened both new panels; expanding Activity left the application's
compositor geometry unchanged. All GUI checks run sequentially to avoid focus
conflicts between test windows.

Clipboard and Activity demo previews and the new Settings page rendered without
QML errors. Clipboard Settings was also inspected at its 800×600 window minimum;
navigation and page content scroll. New feature QML passed `qmllint` with the
Quickshell import path; ClipboardState retains the toolchain's existing
`QProcess::ExitStatus` metadata warning. Public previews use sample content.

Repeat the complete checks **only in a private Wayland session**:

```bash
LME_TEST_AUTHENTICATION_UI=1 LME_TEST_CLIPBOARD_NATIVE=1 \
LME_TEST_CLIPBOARD_UI=1 LME_TEST_ACTIVITY_UI=1 \
LME_TEST_POINTER=/path/to/virtual-pointer-click ./scripts/check.sh
```

The click driver accepts absolute X/Y coordinates and must match the test
output size. The MPRIS fixture uses PyGObject, configurable with
`LME_TEST_GI_PYTHON`; it is a test dependency only. Without native flags, the
nine integration cases skip. Do not overlap fixture instances, normal shell
panels or automatic screenshots during GUI checks.

Target Fedora/niri still needs validation with the user's actual clipboard
sources, MPRIS players, multiple outputs and supported recording application.
See [CLIPBOARD_ACTIVITY.md](CLIPBOARD_ACTIVITY.md) for the update checklist.


## Seven desktop upgrades (October 11, 2026)

The complete existing/new suite passed **114 tests without skips**, including
11 private-session integrations. Subsequent clock-adjustment and wired-versus-Wi-Fi regression checks
also passed, bringing the validated total to **116 tests**. The native upgrade
flow was rerun successfully with actual display-mode selection and monitor drag
before Apply and Keep. Backend contracts
cover appearance save/apply/delete, modular layout validation, private persistent
notification snapshots, bounded wallpaper scanning, arithmetic restrictions,
Wi-Fi identity/password handling and asynchronous acknowledgements.

Native QML pointer/keyboard checks cover profile saving, display confirmation,
wallpaper loading, module dragging, 480 px controls, fuzzy/typo app matching,
calculator errors/results, emoji/window search, Wi-Fi password popup cancellation,
notification groups/rules and DND expiry. The independent display integration
used a fake niri executable and verified a real 20-second rollback after the
initiating process exited. The safety timeout also uses a monotonic clock so
wall-clock changes cannot postpone recovery.

All changed feature components passed qmllint without warnings. Seven refreshed
QML previews rendered without runtime warnings. Settings was inspected in its
actual native window at the 800 × 600 minimum size, and every Control Center
card was inspected at half width. Icon-only controls use IconButton to avoid
padding clipping. Required Fedora package command generation and Bash syntax
checks passed. Preview/sample data never changed host settings or hardware.

Physical Lenovo MT7921 connectivity, actual panel/external-monitor commits and
Fedora package installation remain local verification steps. The runtime
watchdog and UI protocol tests cannot prove driver/display compatibility.
See [Desktop upgrades](DESKTOP_UPGRADES.md) for feature use and limits.


## Monitor, laptop idle, keybindings and popup blur — 2026-10-11

The full private Wayland suite passed 128 tests without skips. After the final lifecycle fix, all 13 laptop regressions passed (including the additional real Quickshell shutdown test), bringing the verified coverage to **129 distinct tests** across the full run and final targeted reruns. All seven authentication checks also passed after adding blur requests to that overlay.

```bash
source /workspace/.lme-dev/wayland-env.sh
LME_TEST_AUTHENTICATION_UI=1 LME_TEST_CLIPBOARD_NATIVE=1 \
LME_TEST_CLIPBOARD_UI=1 LME_TEST_ACTIVITY_UI=1 LME_TEST_UPGRADE_UI=1 \
LME_TEST_DISPLAY_WATCHDOG=1 LME_TEST_IDLE_NATIVE=1 \
LME_TEST_POINTER=/workspace/.lme-dev/pointer-click \
LME_TEST_DRAG=/workspace/.lme-dev/pointer-drag ./scripts/check.sh
```

Final coverage:

- CPU/network delta sampling, counter resets, CPU thread loads, process RSS, tricky process names, reused PIDs, bounded history and on-demand sampling. A real read-only `/proc` sample also succeeded.
- AC adapter online detection despite a full battery, validation and persistence of both idle profiles, profile switching, Stay awake and owned process cleanup.
- swaylock ready-fd success/failure and reuse with a controlled fake locker. Lock failure prevents both the backend's suspend and the idle CLI's sleep request.
- Actual swayidle on private Wayland: timeout, pointer-triggered resume and display-resume command on termination. Temporary niri commands log actions; no host display/lock/suspend is performed.
- Actual Quickshell Process shutdown: its backend can be killed without normal cleanup, so the Linux parent-death signal prevents an orphan idle daemon. Direct backend SIGTERM cleanup also passes.
- KDL includes/cycles, disabled binds/properties, nested comments, raw strings, Unicode escapes, strings containing braces, source line numbers and partial errors.
- Actual QML clicks/keyboard entry in System, process search, idle timeout selection, keybinding search and automatic refetch after Use path, alongside the existing launcher/Wi-Fi/notification/display/layout checks.
- New feature views, settings pages and chart components passed qmllint. shell.qml has Quickshell attached-type metadata warnings, and ShellState.qml has pre-existing QProcess::ExitStatus metadata warnings in this toolchain; both were validated at runtime. The unsupported-compositor fallback loaded correctly. 480 px Control Center and an 800 px Settings window were inspected; lists and longer content scroll rather than overflowing their cards.
- Demo actions report success without host commands or saved preference changes. Scripts passed Bash syntax checks and the diff passed whitespace validation.

The cloud compositor is Sway/software rendering, not niri on Radeon. **Native full-screen blur remains unverified on the target Lenovo**; its niri 26.04+ protocol/config requirements are documented in LAPTOP_FEATURES.md. Fedora PAM/logind suspend, physical AC switching and the actual AMD temperature sensors still need target-machine checks. No GPU telemetry, privileged charging write, real suspend/lock, or Fedora DNF transaction was performed in cloud validation.

Setup now retains signed swayidle 1.8.0 and swaylock 1.8.2 packages in the private toolchain and saves their installation/start instructions in the cloud configuration draft. The native tests run sequentially and clean up only their own processes.

## Night Light, Screenshot studio and motion — 2026-10-11

The final full suite passed **141 tests without skips** in 90.928 seconds,
including the private Wayland integrations. Bash syntax checks and the demo
backend contract also passed.

```bash
source /workspace/.lme-dev/wayland-env.sh
LME_TEST_AUTHENTICATION_UI=1 LME_TEST_CLIPBOARD_NATIVE=1 \
LME_TEST_CLIPBOARD_UI=1 LME_TEST_ACTIVITY_UI=1 LME_TEST_UPGRADE_UI=1 \
LME_TEST_DISPLAY_WATCHDOG=1 LME_TEST_IDLE_NATIVE=1 LME_TEST_CAPTURE_UI=1 \
LME_TEST_POINTER=/workspace/.lme-dev/pointer-click \
LME_TEST_DRAG=/workspace/.lme-dev/pointer-drag ./scripts/check.sh
```

- Night Light checks cover local-time boundaries, midnight schedules, disabled
  and manual modes, approximate sunrise/sunset, polar/location failures,
  temperature validation, owned worker cleanup and gamma failures. Standalone
  Settings never starts a second controller and clears stale active status
  when the desktop shell stops.
- Private native QML checks select the motion preset, edit Night Light times,
  reject invalid input, and measure Jelly overshoot followed by settling.
  Disabling animations removes both the transition and deformation. Old
  appearance profiles and Control Center layouts preserve saved values and
  receive the new defaults/module.
- Screenshot checks cover the three niri command forms, private paths,
  cancellation timeout, PNG limits, stale sessions, language validation,
  exclusive saves, rapid repeated saves and removal of partial failed writes.
  Late OCR completions cannot leak into the next screenshot.
- Actual pointer/keyboard input exercises Pen, Highlight, Rectangle, Arrow,
  Redact, Undo/Redo, Save PNG, Copy image and local OCR. The exported PNG keeps
  its 960 × 540 dimensions; covered pixels are opaque black, other pixels retain
  the source image, and copied/saved bytes match the flattened export.
  Text-field shortcuts still copy text. The native editor also works at its
  850 × 700 minimum size.
- The real shell opens its independent editor and can close/reopen it twice.
  This integration uses a controlled fake niri executable, not a real desktop
  capture. Real Tesseract recognizes the sample image; English and Vietnamese
  models were also exercised together for the published sample preview.
- Production feature views and motion components pass qmllint without warnings.
  The reused upgrades fixture has two existing dynamic-QObject metadata warnings;
  shell.qml and ShellState.qml retain the earlier attached-type/ExitStatus
  metadata warnings. Real runtime entry points show no corresponding errors.
  Three new preview images contain only project-generated sample content.

The owner confirmed that native popup blur works as expected on **niri 26.04**
after including `config/niri/popup-blur.kdl`: applications and the bar remain
visible behind the blur and the popup stays sharp. This supersedes the target
blur limitation in the earlier laptop validation section.

The private cloud session uses Sway and software rendering. Real `wlsunset`
0.3.0 reports gamma rejection on its virtual output; this is correctly surfaced
as a failure, not an active filter. **Gamma on the Lenovo panel and actual niri
screen/area/window capture still need target-machine verification.** The niri
`--path` API was checked against official IPC source, including v25.11. Fedora
DNF installation and 120 Hz hardware motion smoothness were not measured here.
Niri also copies the original screenshot; redaction does not erase that earlier
clipboard/history item. See [setup and usage](CAPTURE_NIGHT_MOTION.md).

The saved cloud configuration draft retains signed `wlsunset` and Tesseract
language packages, selects the live Sway socket instead of stale sockets, and
documents the complete private validation command. Saving the draft does not
publish the environment configuration.

## Settings, element theming and liquid feedback — 2026-10-11

The full private Wayland command completed **147 tests with no skips or
failures**, plus Bash syntax checks and the demo backend snapshot. Enable the
earlier native flags and `LME_TEST_PERSONALIZATION_UI=1`; see the saved cloud
start instructions. After the bar height boundary and semantic hover adjustments,
all six focused personalization checks were rerun, including both native cases.

- The actual root shell starts as `quickshell -c gpt` through an installed
  symlink. It opens Settings, reuses its instance, accepts Elements navigation,
  closes it through the window manager and opens it again. This uses private
  config/runtime paths and a fake niri executable without hardware mutations.
  A separate check covers a PATH with only the `qs` binary name.
- Real pointer/keyboard input exercises hover scale, press/hold/release ripple,
  Motion off/on, valid/invalid hex edits, body/bar font inheritance, bottom-edge
  geometry and the 36/64 px bar height boundaries. Panels retain their position
  during exit, can reopen mid-exit, unload after exit and close immediately with
  Motion disabled. These checks also inspect runtime logs for QML errors.
  A danger confirmation retains its red palette during hover after ordinary
  button colors are customized; the fixture does not activate that action.
- Backend checks reject malformed/unknown tokens, preserve different edits from
  stale clients under the existing file lock, reset individual overrides,
  migrate older profiles and preserve demo isolation.
- All shared controls, Settings pages/application, bar components, Theme and
  changed Activity/DesktopPreview components pass qmllint without warnings.
  Actual Settings was also inspected at 800 × 600 with 20 px body text; sidebar
  labels wrap without cutting words. The three new previews render project sample
  state and contain no user application pixels, credentials or location data.
- Caelestia/iNiR motion patterns and the ported DMS curves are attributed in
  `THIRD_PARTY.md`; the DMS MIT notice is retained. The private pointer tools can
  now be recreated by the saved cloud setup script. The setup update is a draft
  for review and is not automatically published.

These checks use Qt 6.8.2 / Quickshell 0.3.2 on private Sway with software
rendering. **Real Fedora/niri bar reservation, Lenovo gamma/capture and Radeon
120 Hz animation performance remain untested here.** Existing owner-confirmed
niri 26.04 blur behavior is preserved. The supplied main-shell log alone does
not establish the exact original Settings failure on the owner's installation;
the binary alias and native close/reopen paths are now covered directly.
