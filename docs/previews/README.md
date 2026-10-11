# Rendered previews

These images were rendered from this project's QML at 1920×1080 in a headless
Wayland session. The current panel previews use sample desktop state. The native
notification, control-center, and dropdown captures use real Quickshell protocol
services with test notifications, sample hardware state, and mock media/tray
applications. None were captured
from the target Lenovo/Fedora installation. Open `scripts/start.sh --preview`
in a running Wayland session for an interactive preview without desktop mutations.

The current Control Center image includes sample weather and numerical charge
controls. Weather settings also uses sample data; it does not reveal the cloud
IP location or establish the laptop’s firmware capability.

`authentication.png` shows the actual authentication popup with a simulated
conversation and account. No real password or Polkit/PAM session was used for
the screenshot.

The workspace board, wider control center, Devices and Agenda images show the
expanded shell. `audio-mixer.png` now shows the Material layout with sample data.
`native-audio-mixer.png` preserves the earlier isolated PipeWire/WirePlumber session
with virtual devices and a real `pw-play` stream. `bluez-adapter.png` uses a
private D-Bus BlueZ adapter fixture, with the actual Python backend and widget.
The older native media/tray and profile-dropdown captures document the first
release's tested protocol interactions; their control-center layout predates
the new tabs. No image represents physical laptop hardware testing.

| Panel | Image |
| --- | --- |
| Clipboard history with sample text/images | [clipboard.png](clipboard.png) |
| Expanding Activity with sample media and timers | [activity.png](activity.png) |
| Clipboard Settings with sample preferences | [clipboard-settings.png](clipboard-settings.png) |
| Application launcher | [launcher.png](launcher.png) |
| Control center | [control.png](control.png) |
| Workspace board with sample windows | [overview.png](overview.png) |
| Devices with sample Bluetooth/Wi-Fi state | [devices.png](devices.png) |
| Agenda calendar with sample desktop state | [agenda.png](agenda.png) |
| Material audio mixer with sample state | [audio-mixer.png](audio-mixer.png) |
| Native audio mixer with isolated virtual devices/stream | [native-audio-mixer.png](native-audio-mixer.png) |
| Native Bluetooth widget with private BlueZ adapter fixture | [bluez-adapter.png](bluez-adapter.png) |
| Notifications | [notifications.png](notifications.png) |
| Standalone Settings app with sample state | [settings.png](settings.png) |
| Live class color editing with sample theme | [element-colors.png](element-colors.png) |
| Font roles and body sizing | [element-fonts.png](element-fonts.png) |
| Bottom bar and associated panel placement, sample desktop | [bottom-bar.png](bottom-bar.png) |
| Weather settings with sample location/forecast | [weather-settings.png](weather-settings.png) |
| Modular topbar editor with sample state | [topbar-editor.png](topbar-editor.png) |
| Power menu | [power.png](power.png) |
| Authentication popup with a simulated conversation | [authentication.png](authentication.png) |
| Native notification toast with test content | [notification-toast.png](notification-toast.png) |
| Native media/tray controls with mock applications | [native-control-center.png](native-control-center.png) |
| Power profile dropdown with sample hardware state | [power-profile-dropdown.png](power-profile-dropdown.png) |
| System tray dropdown with a mock application | [tray-dropdown.png](tray-dropdown.png) |
