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
    readonly property bool wifiConnected: network.wifiConnected === undefined ? !!network.connected : !!network.wifiConnected
    readonly property var bluetooth: ShellState.system.bluetooth || {}
    readonly property var audio: ShellState.system.audio || {}
    readonly property var microphone: ShellState.system.microphone || {}
    readonly property var brightness: ShellState.system.brightness || {}
    readonly property var battery: ShellState.system.battery || {}
    readonly property var players: ShellState.demo ? [] : Mpris.players.values
    property string selectedPlayerName: ""
    readonly property var player: players.find(item => item.dbusName === selectedPlayerName) || players.find(item => item.isPlaying) || players[0] || null
    property date now: new Date()
    property int pendingVolume: -1
    property int pendingBrightness: -1
    property int pendingMic: -1

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
    function flushMic() {
        micDelay.stop();
        if (pendingMic >= 0) ShellState.run("micVolume", {value: pendingMic});
        pendingMic = -1;
    }
    function numeric(value, suffix) {
        return value === null || value === undefined ? "—" : Math.round(value) + (suffix || "");
    }

    Timer { interval: 1000; running: root.visible; repeat: true; onTriggered: root.now = new Date() }
    Timer { id: volumeDelay; interval: 100; onTriggered: root.flushVolume() }
    Timer { id: brightnessDelay; interval: 100; onTriggered: root.flushBrightness() }
    Timer { id: micDelay; interval: 100; onTriggered: root.flushMic() }
    Keys.onEscapePressed: ShellState.closePanels()

    component Tile: LiquidButton {
        id: tile
        required property string label
        required property string detail
        property bool active: false
        property color accent: Theme.purple
        Layout.fillWidth: true
        implicitHeight: Theme.compact ? 66 : 77
        Accessible.name: label + ": " + detail
        background: Rectangle {
            radius: tile.active ? 24 : 16
            color: tile.active ? Theme.mix(Theme.panel, tile.accent, tile.hovered ? 0.38 : 0.28) : Theme.surfaceContainerHigh
            border.color: tile.activeFocus ? tile.accent : tile.active ? Theme.alpha(tile.accent, 0.48) : Theme.border
            border.width: 1
            opacity: tile.enabled ? 1 : 0.5
            Behavior on radius { MotionAnimation {} }
        }
        contentItem: ColumnLayout {
            spacing: 6
            Text { Layout.fillWidth: true; elide: Text.ElideRight; text: tile.label; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.weight: Font.Bold }
            Text { Layout.fillWidth: true; text: tile.detail; textFormat: Text.PlainText; elide: Text.ElideRight; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
        }
    }

    component Caption: Text {
        color: Theme.muted
        font.family: Theme.fontFamily
        font.pixelSize: 12
    }

    Flickable {
        id: scroll
        anchors.fill: parent; anchors.margins: 8
        contentWidth: width; contentHeight: body.implicitHeight
        clip: true; boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        ColumnLayout {
            id: body; width: scroll.width - 8; spacing: Theme.cardSpacing
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 4
                    Text { text: Qt.formatDateTime(root.now, "hh:mm"); color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 32; font.weight: Font.Bold }
                    Caption { text: Qt.locale("en_US").toString(root.now, "dddd, MMMM d") }
                }
                Item { Layout.fillWidth: true }
                LiquidButton { text: "Lock"; onClicked: { ShellState.closePanels(); ShellState.run("lock"); } }
            }
            GridLayout {
                id: content; Layout.fillWidth: true
                columns: width >= 500 ? 2 : 1
                columnSpacing: 12; rowSpacing: Theme.cardSpacing
                Repeater {
                    model: ShellState.preferences.controlLayout || []
                    delegate: Loader {
                        id: card
                        required property var modelData
                        active: modelData.enabled
                        visible: active
                        Layout.fillWidth: true; Layout.preferredWidth: 1
                        Layout.columnSpan: content.columns === 1 || modelData.size === "full" ? content.columns : 1
                        Layout.preferredHeight: item ? (item as Item).implicitHeight : 0
                        sourceComponent: root.moduleComponent(modelData.id)
                    }
                }
            }
            LabelText { visible: !(ShellState.preferences.controlLayout || []).some(m => m.enabled); text: "All widgets are hidden. Use Edit layout to restore them."; wrapMode: Text.Wrap; Layout.fillWidth: true; color: Theme.muted }
        }
    }
    function moduleComponent(id) {
        return ({weather: weatherModule, charging: chargingModule, wifi: wifiModule, bluetooth: bluetoothModule, microphone: microphoneModule, dnd: dndModule, stayAwake: stayAwakeModule, motion: motionModule, nightLight: nightLightModule, sliders: slidersModule, powerProfile: powerProfileModule, media: mediaModule, resources: resourcesModule, capture: captureModule, overview: overviewModule})[id] || null;
    }
    Component {
        id: weatherModule
        WeatherWidget {}
    }
    Component {
        id: chargingModule
        ChargingWidget {}
    }
    Component {
        id: wifiModule
        Tile {
            label: "Wi-Fi"
            detail: !root.network.available ? "Unavailable" : root.wifiConnected ? root.network.ssid || "Connected" : root.network.enabled ? "Not connected" : "Turned off"
            active: !!root.network.enabled
            enabled: !!root.network.available
            accent: Theme.cyan
            onClicked: ShellState.togglePanel("wifi")
        }
    }
    Component {
        id: bluetoothModule
        Tile {
            label: "Bluetooth"
            detail: ShellState.pendingActions.bluetoothToggle ? "Changing power…" : root.bluetooth.hardBlocked ? "Hardware blocked" : root.bluetooth.softBlocked ? "Software blocked" : !root.bluetooth.available ? "No adapter" : root.bluetooth.enabled ? "Powered on" : "Turned off"
            active: !!root.bluetooth.enabled
            enabled: !!root.bluetooth.available && !root.bluetooth.hardBlocked && !ShellState.pendingActions.bluetoothToggle
            onClicked: ShellState.run("bluetoothToggle")
        }
    }
    Component {
        id: microphoneModule
        Tile {
            label: "Microphone"; detail: !root.microphone.available ? "Unavailable" : root.microphone.muted ? "Muted" : "Ready to record"
            active: !!root.microphone.available && !root.microphone.muted; enabled: !!root.microphone.available
            accent: Theme.pink; onClicked: ShellState.run("micMute")
        }
    }
    Component {
        id: dndModule
        Tile { label: "Do not disturb"; detail: Notifications.dnd ? "Popups silenced" : "Notifications enabled"; active: Notifications.dnd; accent: Theme.yellow; onClicked: Notifications.setDnd(Notifications.dnd ? 0 : -1) }
    }
    Component {
        id: stayAwakeModule
        Tile { label: "Stay awake"; detail: ShellState.stayAwake ? "Idle sleep inhibited" : "Normal idle behavior"; active: ShellState.stayAwake; accent: Theme.green; onClicked: ShellState.stayAwake = !ShellState.stayAwake }
    }
    Component {
        id: motionModule
        Tile { label: "Motion"; detail: Theme.animations ? Theme.motionPreset[0].toUpperCase() + Theme.motionPreset.slice(1) + " · " + Theme.motionSpeed.toFixed(1) + "×" : "Reduced motion"; active: Theme.animations; onClicked: ShellState.run("setting", {key: "animations", value: !Theme.animations}) }
    }
    Component {
        id: nightLightModule
        Tile {
            label: "Night Light"; accent: Theme.yellow
            readonly property var night: ShellState.snapshot.nightLight || {}
            active: !!night.active
            detail: night.error ? "Needs attention · Settings" : night.active ? (night.temperature || 4500) + " K" : ShellState.preferences.nightLightEnabled ? "Scheduled" : "Turned off"
            onClicked: if (night.error || night.available === false) ShellState.openSettingsPage("nightLight"); else ShellState.run("setting", {key: "nightLightEnabled", value: !ShellState.preferences.nightLightEnabled})
        }
    }
    Component {
        id: slidersModule
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: sliders.implicitHeight + 26
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
                    IconButton { glyph: "⋯"; tooltip: "Audio settings"; onClicked: ShellState.run("openSettings", { target: "audio" }); implicitWidth: 32 }
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
                    LiquidButton { text: root.microphone.muted ? "Unmute mic" : "Microphone"; enabled: !!root.microphone.available; onClicked: ShellState.run("micMute"); palette.button: Theme.panel; palette.buttonText: root.microphone.muted ? Theme.pink : Theme.text }
                    Item { Layout.fillWidth: true }
                    Caption { text: root.microphone.available ? root.microphone.muted ? "Muted" : root.numeric(micVolume.value, "%") : "No microphone" }
                }
                LiquidSlider {
                    id: micVolume
                    Layout.fillWidth: true; from: 0; to: 100; stepSize: 1
                    enabled: !!root.microphone.available; Accessible.name: "Microphone level"
                    palette.highlight: Theme.pink
                    onMoved: { root.pendingMic = Math.round(value); if (!micDelay.running) micDelay.start(); }
                    onPressedChanged: if (!pressed) root.flushMic()
                }
                Binding { target: micVolume; property: "value"; value: root.microphone.volume || 0; when: !micVolume.pressed; restoreMode: Binding.RestoreNone }
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
    }
    Component {
        id: powerProfileModule
        RowLayout {
            Layout.fillWidth: true
            Text { text: "Power profile"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
            Item { Layout.fillWidth: true }
            LiquidComboBox {
                id: profile
                model: ["Power saver", "Balanced", "Performance"]
                property var values: ["power-saver", "balanced", "performance"]
                currentIndex: Math.max(0, values.indexOf(ShellState.system.powerProfile || "balanced"))
                enabled: !!ShellState.system.powerProfile
                onActivated: ShellState.run("powerProfile", { value: values[currentIndex] })
                Accessible.name: "Power profile"
            }
        }
    }
    Component {
        id: mediaModule
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: media.implicitHeight + 28
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
                        Text { Layout.fillWidth: true; text: root.player ? root.player.trackTitle || root.player.identity : "Nothing playing"; textFormat: Text.PlainText; elide: Text.ElideRight; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.weight: Font.Bold }
                        Caption { Layout.fillWidth: true; text: root.player ? root.player.trackArtist || root.player.identity : "Play media in your favorite app"; textFormat: Text.PlainText; elide: Text.ElideRight }
                    }
                }
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    LiquidButton { text: "Previous"; leftPadding: 8; rightPadding: 8; enabled: !!root.player && root.player.canGoPrevious; onClicked: root.player.previous(); palette.button: Theme.panel; palette.buttonText: Theme.text }
                    LiquidButton { text: root.player && root.player.isPlaying ? "Pause" : "Play"; leftPadding: 8; rightPadding: 8; enabled: !!root.player && root.player.canTogglePlaying; onClicked: root.player.togglePlaying(); palette.button: Theme.purple; palette.buttonText: Theme.background }
                    LiquidButton { text: "Next"; leftPadding: 8; rightPadding: 8; enabled: !!root.player && root.player.canGoNext; onClicked: root.player.next(); palette.button: Theme.panel; palette.buttonText: Theme.text }
                }
                LiquidComboBox {
                    id: playerSelector
                    visible: root.players.length > 1
                    Layout.fillWidth: true
                    model: root.players.map(item => item.identity)
                    currentIndex: root.players.indexOf(root.player)
                    Accessible.name: "Media player"
                    onActivated: root.selectedPlayerName = root.players[currentIndex].dbusName
                    palette.button: Theme.panel
                }
            }
        }
    }
    Component {
        id: resourcesModule
        Rectangle {
            implicitHeight: resources.implicitHeight + 28
            radius: Theme.smallRadius; color: Theme.surface
            ColumnLayout {
                id: resources
                anchors.fill: parent; anchors.margins: 14
                RowLayout {
                    Layout.fillWidth: true
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: Math.max(60, (resources.width - 12) / 3)
                        spacing: 5
                        Caption { text: "CPU" }
                        Text { text: root.numeric(ShellState.system.cpu, "%"); color: Theme.cyan; font.family: Theme.monoFamily; font.pixelSize: 17 }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: Math.max(60, (resources.width - 12) / 3)
                        spacing: 5
                        Caption { text: "RAM" }
                        Text { text: root.numeric(ShellState.system.memoryPercent, "%"); color: Theme.purple; font.family: Theme.monoFamily; font.pixelSize: 17 }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: Math.max(60, (resources.width - 12) / 3)
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
                LiquidButton { text: "System monitor"; Layout.fillWidth: true; onClicked: ShellState.controlTab = 5 }
            }
        }
    }
    Component {
        id: captureModule
        GridLayout {
            columns: width < 420 ? 2 : 4
            columnSpacing: 8; rowSpacing: 8
            Layout.fillWidth: true
            LiquidButton { text: "Screen capture"; Layout.fillWidth: true; onClicked: ShellState.takeScreenshot("screen"); palette.button: Theme.surface; palette.buttonText: Theme.text }
            LiquidButton { text: "Select area"; Layout.fillWidth: true; onClicked: ShellState.takeScreenshot("area"); palette.button: Theme.surface; palette.buttonText: Theme.text }
            LiquidButton { text: "Focused window"; Layout.fillWidth: true; onClicked: ShellState.takeScreenshot("window"); palette.button: Theme.surface; palette.buttonText: Theme.text }
            LabelText { visible: (ShellState.snapshot.capture || {}).status === "pending"; text: "A capture is pending. Escape cancels niri's selector; use Cancel capture to start again."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
            LiquidButton { text: "Cancel capture"; visible: (ShellState.snapshot.capture || {}).status === "pending"; onClicked: ShellState.run("captureClose") }
            LiquidButton { text: "Settings"; Layout.fillWidth: true; onClicked: ShellState.togglePanel("settings"); palette.button: Theme.surface; palette.buttonText: Theme.purple }
            LiquidButton { text: "Power"; Layout.fillWidth: true; onClicked: ShellState.togglePanel("power"); palette.button: Theme.surface; palette.buttonText: Theme.pink }
        }
    }
    Component {
        id: overviewModule
        LiquidButton { text: "Workspace overview"; Layout.fillWidth: true; onClicked: ShellState.togglePanel("overview") }
    }
}
