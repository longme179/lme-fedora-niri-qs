// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockClockView.qml (lock layer, fan-in 1 — LockSurface's clock view).
// Ported from the clock half of iNiR's LockSurface.qml @ edca6cc (GPL-3.0):
// the status row (network · bluetooth · volume · battery), the large clock,
// the bottom-left weather readout and the unlock hint that fades after 4s.
// The clock→login view machine and all input handling stay in LockSurface.
// REL: services (NetworkState/BluetoothState/AudioState/PowerState/WeatherState),
// components (ShellIcon/ShellText), theme. No context dependency on purpose —
// this view only reads services, so engine fixtures can load it standalone.
pragma ComponentBehavior: Bound
import QtQuick
import "../../services"
import "../../theme"
import "../../components"

Item {
    id: root

    property date now: new Date()
    // The clock sits above centre so the media widget can sit below it (iNiR layout).
    readonly property real clockOffset: -Math.min(width, height) * 0.10
    readonly property bool batteryLow: PowerState.battery.available && !PowerState.battery.charging
        && PowerState.battery.percent !== null && PowerState.battery.percent <= 15
    readonly property bool weatherReady: typeof WeatherState.data.temperature === "number"
    readonly property bool bluetoothOn: BluetoothState.nativeAdapters.some(adapter => adapter.enabled)
    // Read-only surface state (engine cases pin the service gates through these).
    readonly property alias weatherVisible: weatherRow.visible
    readonly property alias batteryVisible: batteryRow.visible
    readonly property string clockLabel: clockText.text

    // ---- status row: compact indicators along the top edge ---------------------
    Row {
        spacing: 18
        anchors { top: parent.top; topMargin: 24; horizontalCenter: parent.horizontalCenter }

        Row {
            spacing: 5
            visible: NetworkState.state.connected
            ShellIcon { name: "wifi"; color: Theme.text; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16 }
            ShellText {
                anchors.verticalCenter: parent.verticalCenter
                visible: text.length > 0 && text.length < 16
                text: NetworkState.state.ssid
                color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12
            }
        }

        ShellIcon {
            visible: root.bluetoothOn
            name: "bluetooth"; color: Theme.text
            anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16
        }

        Row {
            spacing: 5
            visible: AudioState.state.available
            ShellIcon {
                name: "audio"; color: AudioState.state.muted ? Theme.muted : Theme.text
                anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16
            }
            ShellText {
                anchors.verticalCenter: parent.verticalCenter
                text: AudioState.state.muted ? "Muted" : AudioState.state.volume + "%"
                color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12
            }
        }

        Row {
            id: batteryRow
            spacing: 5
            visible: PowerState.battery.available
            ShellIcon {
                name: "battery"; color: root.batteryLow ? Theme.red : Theme.text
                anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16
            }
            ShellText {
                anchors.verticalCenter: parent.verticalCenter
                text: (PowerState.battery.charging ? "⚡ " : "") + PowerState.battery.percent + "%"
                color: root.batteryLow ? Theme.red : Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12
            }
        }
    }

    // ---- the clock --------------------------------------------------------------
    Column {
        spacing: 6
        anchors { horizontalCenter: parent.horizontalCenter; verticalCenter: parent.verticalCenter; verticalCenterOffset: root.clockOffset }

        ShellText {
            id: clockText
            text: Qt.formatDateTime(root.now, "HH:mm")
            color: Theme.text; font.family: Theme.fontFamily
            font.pixelSize: Math.min(root.width, root.height) * 0.16
            font.weight: Font.Light
        }
        ShellText {
            id: dateText
            text: Qt.formatDateTime(root.now, "dddd, MMMM d")
            color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 18
        }
    }

    // ---- weather readout (bottom-left) -------------------------------------------
    Row {
        id: weatherRow
        spacing: 12
        visible: root.weatherReady
        anchors { left: parent.left; leftMargin: 40; bottom: parent.bottom; bottomMargin: 40 }

        ShellIcon {
            name: WeatherState.data.icon || "weather-cloud"
            color: Theme.yellow
            anchors.verticalCenter: parent.verticalCenter; width: 44; height: 44
        }
        Column {
            spacing: 2
            anchors.verticalCenter: parent.verticalCenter
            ShellText {
                text: Math.round(WeatherState.data.temperature) + (WeatherState.data.unit || "")
                color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 26; font.weight: Font.Light
            }
            ShellText {
                text: WeatherState.data.condition || ""
                visible: text.length > 0
                color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 13
            }
            ShellText {
                text: (WeatherState.built.location || {}).name || ""
                visible: text.length > 0
                color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12; opacity: 0.8
            }
        }
    }

    // ---- the unlock hint: fades out after 4s, resets on re-show (iNiR) ----------
    ShellText {
        id: hintText
        anchors { bottom: parent.bottom; bottomMargin: 40; horizontalCenter: parent.horizontalCenter }
        text: "Press any key or click to unlock"
        color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12
        property real hintOpacity: 0.7
        opacity: hintOpacity
        Behavior on hintOpacity { NumberAnimation { duration: Theme.animationDuration * 2; easing.type: Easing.OutCubic } }
        Timer {
            id: hintFadeTimer
            interval: 4000
            running: root.visible
            onTriggered: hintText.hintOpacity = 0
        }
    }

    onVisibleChanged: {
        if (visible) {
            hintText.hintOpacity = 0.7;
            hintFadeTimer.restart();
        }
    }

    // A live clock for the view (re-evaluates every 5s; cheap and battery-kind).
    Timer {
        interval: 5000
        running: root.visible
        repeat: true
        triggeredOnStart: true
        onTriggered: root.now = new Date()
    }
}
