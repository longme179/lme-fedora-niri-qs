# Rendered previews

These images were rendered from this project's QML at 1920×1080 in a headless
Wayland session. The current panel previews use sample desktop state. The native
notification, control-center, and dropdown captures use real Quickshell protocol
services with test notifications, sample hardware state, and mock media/tray
applications. None were captured
from the target Lenovo/Fedora installation. Open `scripts/start.sh --preview`
in a running Wayland session for an interactive preview without desktop mutations.

The workspace board, wider control center, Devices and Agenda images show the
expanded shell. `audio-mixer.png` uses an isolated PipeWire/WirePlumber session
with virtual devices and a real `pw-play` stream. `bluez-adapter.png` uses a
private D-Bus BlueZ adapter fixture, with the actual Python backend and widget.
The older native media/tray and profile-dropdown captures document the first
release's tested protocol interactions; their control-center layout predates
the new tabs. No image represents physical laptop hardware testing.

| Panel | Image |
| --- | --- |
| Application launcher | [launcher.png](launcher.png) |
| Control center | [control.png](control.png) |
| Workspace board with sample windows | [overview.png](overview.png) |
| Devices with sample Bluetooth/Wi-Fi state | [devices.png](devices.png) |
| Agenda calendar with sample desktop state | [agenda.png](agenda.png) |
| Native audio mixer with isolated virtual devices/stream | [audio-mixer.png](audio-mixer.png) |
| Native Bluetooth widget with private BlueZ adapter fixture | [bluez-adapter.png](bluez-adapter.png) |
| Notifications | [notifications.png](notifications.png) |
| Shell settings | [settings.png](settings.png) |
| Power menu | [power.png](power.png) |
| Native notification toast with test content | [notification-toast.png](notification-toast.png) |
| Native media/tray controls with mock applications | [native-control-center.png](native-control-center.png) |
| Power profile dropdown with sample hardware state | [power-profile-dropdown.png](power-profile-dropdown.png) |
| System tray dropdown with a mock application | [tray-dropdown.png](tray-dropdown.png) |
