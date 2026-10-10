pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Services.Mpris
import "../services"
import "../theme"
import "../components"

Item {
    id: root
    implicitWidth: 386
    implicitHeight: 710
    focus: true
    readonly property var network: ShellState.system.network || {}
    readonly property var bluetooth: ShellState.system.bluetooth || {}
    readonly property var audio: ShellState.system.audio || {}
    readonly property var brightness: ShellState.system.brightness || {}
    readonly property var battery: ShellState.system.battery || {}
    readonly property var players: ShellState.demo ? [] : Mpris.players.values
    property string selectedPlayerName: ""
    readonly property var player: players.find(item => item.dbusName === selectedPlayerName) || players.find(item => item.isPlaying) || players[0] || null
    property date now: new Date()
    property int pendingVolume: -1
    property int pendingBrightness: -1

    function flushVolume() {
        volumeDelay.stop();
        if (pendingVolume >= 0) ShellState.run("volume", { value: pendingVolume });
        pendingVolume = -1;
    }
    function flushBrightness() {
        brightnessDelay.stop();
        if (pendingBrightness >= 0) ShellState.run("brightness", { value: pendingBrightness });
        pendingBrightness = -1;
    }
    function numeric(value, suffix) {
        return value === null || value === undefined ? "—" : Math.round(value) + (suffix || "");
    }

    Timer { interval: 1000; running: root.visible; repeat: true; onTriggered: root.now = new Date() }
    Timer { id: volumeDelay; interval: 100; onTriggered: root.flushVolume() }
    Timer { id: brightnessDelay; interval: 100; onTriggered: root.flushBrightness() }
    Keys.onEscapePressed: ShellState.closePanels()

    component Tile: LiquidButton {
        id: tile
        required property string label
        required property string detail
        property bool active: false
        property color accent: Theme.purple
        Layout.fillWidth: true
        Layout.preferredHeight: 77
        Accessible.name: label + ": " + detail
        background: Rectangle {
            radius: Theme.smallRadius
            color: tile.active ? Theme.alpha(tile.accent, tile.hovered ? 0.28 : 0.18) : Theme.surface
            border.color: tile.activeFocus ? tile.accent : tile.active ? Theme.alpha(tile.accent, 0.48) : Theme.border
            border.width: 1
            opacity: tile.enabled ? 1 : 0.5
        }
        contentItem: ColumnLayout {
            spacing: 6
            Text { text: tile.label; color: tile.active ? tile.accent : Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold }
            Text { Layout.fillWidth: true; text: tile.detail; textFormat: Text.PlainText; elide: Text.ElideRight; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 11 }
        }
    }

    component Caption: Text {
        color: Theme.muted
        font.family: Theme.fontFamily
        font.pixelSize: 11
    }

    GlassPanel { anchors.fill: parent }
    Flickable {
        anchors.fill: parent
        anchors.margins: 22
        contentWidth: width
        contentHeight: content.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        ColumnLayout {
            id: content
            width: parent.width
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 4
                    Text { text: Qt.formatDateTime(root.now, "hh:mm"); color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 32; font.weight: Font.DemiBold }
                    Caption { text: Qt.formatDateTime(root.now, "dddd, MMMM d") }
                }
                Item { Layout.fillWidth: true }
                LiquidButton { text: "×"; Accessible.name: "Close control center"; onClicked: ShellState.closePanels(); palette.button: Theme.surface; palette.buttonText: Theme.text }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 12
                rowSpacing: 10
                Tile {
                    label: "Wi-Fi"
                    detail: !root.network.available ? "Unavailable" : root.network.connected ? root.network.ssid || "Connected" : root.network.enabled ? "Not connected" : "Turned off"
                    active: !!root.network.enabled
                    enabled: !!root.network.available
                    accent: Theme.cyan
                    onClicked: ShellState.run("wifiToggle")
                }
                Tile {
                    label: "Bluetooth"
                    detail: !root.bluetooth.available ? "Unavailable" : root.bluetooth.enabled ? "Powered on" : "Turned off"
                    active: !!root.bluetooth.enabled
                    enabled: !!root.bluetooth.available
                    onClicked: ShellState.run("bluetoothToggle")
                }
                LiquidButton { text: "Network settings"; Layout.fillWidth: true; onClicked: ShellState.run("openSettings", { target: "network" }); palette.button: Theme.surface; palette.buttonText: Theme.cyan }
                LiquidButton { text: "Bluetooth devices"; Layout.fillWidth: true; onClicked: ShellState.run("openSettings", { target: "bluetooth" }); palette.button: Theme.surface; palette.buttonText: Theme.purple }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: sliders.implicitHeight + 26
                radius: Theme.smallRadius
                color: Theme.surface
                ColumnLayout {
                    id: sliders
                    anchors.fill: parent
                    anchors.margins: 13
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        LiquidButton { text: root.audio.muted ? "Unmute" : "Volume"; enabled: !!root.audio.available; onClicked: ShellState.run("mute"); palette.button: Theme.panel; palette.buttonText: root.audio.muted ? Theme.pink : Theme.text; Accessible.name: root.audio.muted ? "Unmute audio" : "Mute audio" }
                        Item { Layout.fillWidth: true }
                        Caption { text: root.audio.available ? (root.audio.muted ? "Muted" : root.numeric(volume.value, "%")) : "Audio unavailable" }
                        LiquidButton { text: "⋯"; Accessible.name: "Audio settings"; onClicked: ShellState.run("openSettings", { target: "audio" }); palette.button: Theme.panel; palette.buttonText: Theme.text; implicitWidth: 32 }
                    }
                    LiquidSlider {
                        id: volume
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        stepSize: 1
                        enabled: !!root.audio.available
                        Accessible.name: "Volume"
                        palette.highlight: Theme.purple
                        onMoved: {
                            root.pendingVolume = Math.round(value);
                            if (!volumeDelay.running) volumeDelay.start();
                        }
                        onPressedChanged: { if (!pressed) root.flushVolume(); }
                    }
                    Binding { target: volume; property: "value"; value: root.audio.volume || 0; when: !volume.pressed; restoreMode: Binding.RestoreNone }
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Brightness"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
                        Item { Layout.fillWidth: true }
                        Caption { text: root.brightness.available ? root.numeric(brightnessSlider.value, "%") : "No backlight device" }
                    }
                    LiquidSlider {
                        id: brightnessSlider
                        Layout.fillWidth: true
                        from: 1
                        to: 100
                        stepSize: 1
                        enabled: !!root.brightness.available
                        Accessible.name: "Screen brightness"
                        palette.highlight: Theme.yellow
                        onMoved: {
                            root.pendingBrightness = Math.round(value);
                            if (!brightnessDelay.running) brightnessDelay.start();
                        }
                        onPressedChanged: { if (!pressed) root.flushBrightness(); }
                    }
                    Binding { target: brightnessSlider; property: "value"; value: root.brightness.percent || 1; when: !brightnessSlider.pressed; restoreMode: Binding.RestoreNone }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Text { text: "Power profile"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
                Item { Layout.fillWidth: true }
                ComboBox {
                    id: profile
                    implicitHeight: 36
                    model: ["Power saver", "Balanced", "Performance"]
                    property var values: ["power-saver", "balanced", "performance"]
                    currentIndex: Math.max(0, values.indexOf(ShellState.system.powerProfile || "balanced"))
                    enabled: !!ShellState.system.powerProfile
                    onActivated: ShellState.run("powerProfile", { value: values[currentIndex] })
                    Accessible.name: "Power profile"
                    palette.button: Theme.surface
                    palette.buttonText: Theme.text
                    palette.text: Theme.text
                    palette.base: Theme.panel
                    palette.highlight: Theme.purple
                    background: Rectangle { radius: Theme.smallRadius; color: Theme.surface; border.width: profile.visualFocus ? 2 : 0; border.color: Theme.accent }
                    contentItem: Text { text: profile.displayText; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; verticalAlignment: Text.AlignVCenter; leftPadding: 10; rightPadding: 24 }
                    indicator: Text { x: profile.width - width - 10; y: (profile.height - height) / 2; text: "⌄"; color: Theme.muted; font.pixelSize: 16 }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: media.implicitHeight + 28
                radius: Theme.smallRadius
                color: Theme.surface
                ColumnLayout {
                    id: media
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        Rectangle {
                            Layout.preferredWidth: 48
                            Layout.preferredHeight: 48
                            radius: 10
                            color: Theme.panel
                            clip: true
                            Image { anchors.fill: parent; source: root.player ? root.player.trackArtUrl : ""; fillMode: Image.PreserveAspectCrop; asynchronous: true }
                            Text { anchors.centerIn: parent; visible: !root.player || !root.player.trackArtUrl; text: "♫"; color: Theme.pink; font.pixelSize: 26 }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            Text { Layout.fillWidth: true; text: root.player ? root.player.trackTitle || root.player.identity : "Nothing playing"; textFormat: Text.PlainText; elide: Text.ElideRight; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold }
                            Caption { Layout.fillWidth: true; text: root.player ? root.player.trackArtist || root.player.identity : "Play media in your favorite app"; textFormat: Text.PlainText; elide: Text.ElideRight }
                        }
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        LiquidButton { text: "Previous"; enabled: !!root.player && root.player.canGoPrevious; onClicked: root.player.previous(); palette.button: Theme.panel; palette.buttonText: Theme.text }
                        LiquidButton { text: root.player && root.player.isPlaying ? "Pause" : "Play"; enabled: !!root.player && root.player.canTogglePlaying; onClicked: root.player.togglePlaying(); palette.button: Theme.purple; palette.buttonText: Theme.background }
                        LiquidButton { text: "Next"; enabled: !!root.player && root.player.canGoNext; onClicked: root.player.next(); palette.button: Theme.panel; palette.buttonText: Theme.text }
                    }
                    ComboBox {
                        id: playerSelector
                        implicitHeight: 36
                        visible: root.players.length > 1
                        Layout.fillWidth: true
                        model: root.players.map(item => item.identity)
                        currentIndex: root.players.indexOf(root.player)
                        Accessible.name: "Media player"
                        onActivated: root.selectedPlayerName = root.players[currentIndex].dbusName
                        palette.button: Theme.panel
                        palette.buttonText: Theme.text
                        palette.text: Theme.text
                        palette.base: Theme.panel
                        palette.highlight: Theme.accent
                        background: Rectangle { radius: Theme.smallRadius; color: Theme.panel; border.width: playerSelector.visualFocus ? 2 : 0; border.color: Theme.accent }
                        contentItem: Text { text: playerSelector.displayText; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; verticalAlignment: Text.AlignVCenter; leftPadding: 10; rightPadding: 24; elide: Text.ElideRight }
                        indicator: Text { x: playerSelector.width - width - 10; y: (playerSelector.height - height) / 2; text: "⌄"; color: Theme.muted; font.pixelSize: 16 }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: (content.width - 20) / 3
                    spacing: 5
                    Caption { text: "CPU" }
                    Text { text: root.numeric(ShellState.system.cpu, "%"); color: Theme.cyan; font.family: Theme.monoFamily; font.pixelSize: 17 }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: (content.width - 20) / 3
                    spacing: 5
                    Caption { text: "RAM" }
                    Text { text: root.numeric(ShellState.system.memoryPercent, "%"); color: Theme.purple; font.family: Theme.monoFamily; font.pixelSize: 17 }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: (content.width - 20) / 3
                    spacing: 5
                    Caption { text: "Battery" }
                    Text { text: root.battery.available ? root.numeric(root.battery.percent, "%") + (root.battery.charging ? " +" : "") : "—"; color: Theme.green; font.family: Theme.monoFamily; font.pixelSize: 17 }
                }
            }
            Caption {
                Layout.fillWidth: true
                font.pixelSize: 10
                wrapMode: Text.WordWrap
                text: {
                    const details = [];
                    if (ShellState.system.tempC !== null && ShellState.system.tempC !== undefined)
                        details.push("Temp " + Math.round(ShellState.system.tempC) + "°C");
                    if (ShellState.system.memoryUsedGiB !== null && ShellState.system.memoryUsedGiB !== undefined
                            && ShellState.system.memoryTotalGiB !== null && ShellState.system.memoryTotalGiB !== undefined)
                        details.push(Number(ShellState.system.memoryUsedGiB).toFixed(1) + " / " + Number(ShellState.system.memoryTotalGiB).toFixed(1) + " GiB");
                    if (root.battery.available) details.push(root.battery.charging ? "Charging" : "On battery");
                    return details.length ? details.join("  ·  ") : "Hardware details unavailable";
                }
            }
            RowLayout {
                Layout.fillWidth: true
                LiquidButton { text: "Screenshot"; Layout.fillWidth: true; onClicked: { ShellState.closePanels(); ShellState.run("screenshot"); } palette.button: Theme.surface; palette.buttonText: Theme.text }
                LiquidButton { text: "Settings"; Layout.fillWidth: true; onClicked: ShellState.togglePanel("settings"); palette.button: Theme.surface; palette.buttonText: Theme.purple }
                LiquidButton { text: "Power"; Layout.fillWidth: true; onClicked: ShellState.togglePanel("power"); palette.button: Theme.surface; palette.buttonText: Theme.pink }
            }
        }
    }
}
