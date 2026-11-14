// Role: LockPage.qml (lock layer settings, fan-in 1 — Settings' lock page).
// Phase 3 PR2 of the native lock port: the owner decisions D2 (blur, off in
// battery saver) and D3 (keyring auto-unlock, opt-out) plus the widget toggles.
// The preferences themselves live in config/lock.json (catalog schema).
// REL: components (SettingsCard/PreferenceSwitch), services (ShellState), theme.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    spacing: 20

    SettingsCard {
        title: "Lock screen"
        description: "The shell's own ext-session-lock screen (Super+L). Wallpaper comes from the desktop; blur and widgets follow these choices."
        PreferenceSwitch {
            title: "Blur the lock wallpaper"
            detail: "Soft MultiEffect blur behind the lock screen. Turns off automatically while battery saver is on."
            preference: "lockBlur"
        }
        PreferenceSwitch {
            title: "Show weather on the lock screen"
            detail: "The bottom-left readout. Set a location in Settings → Weather first."
            preference: "lockWeather"
        }
        PreferenceSwitch {
            title: "Show the media card"
            detail: "Cover art and playback controls while something is playing."
            preference: "lockMediaWidget"
        }
        LabelText {
            text: "Keep an escape hatch ready: loginctl unlock-sessions, or quickshell -c lme-shell ipc call lock deactivate."
            Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
        }
    }

    SettingsCard {
        title: "Keyring"
        PreferenceSwitch {
            title: "Unlock the keyring with the password"
            detail: "Feed the accepted lock password to the login keyring, so secrets are ready right after unlock."
            preference: "lockKeyringUnlock"
        }
        LabelText {
            text: "Uses the session's gnome-keyring; the password never leaves the unlock attempt."
            Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
        }
    }
}
