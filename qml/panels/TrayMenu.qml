pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Services.SystemTray
import "../components"
import "../services"
import "../theme"

GlassPanel {
    id: root
    property var windowInfo: null
    readonly property var items: ShellState.demo ? [] : SystemTray.items.values
    implicitWidth: 268
    implicitHeight: Math.min(content.implicitHeight + 24, 360)
    radius: Theme.smallRadius
    focus: true
    Keys.onEscapePressed: ShellState.closePanels()

    function displayMenu(trayItem, button) {
        if (!windowInfo || !trayItem.hasMenu) return;
        const position = windowInfo.itemPosition(button);
        trayItem.display(windowInfo, Math.round(position.x + button.width), Math.round(position.y));
    }

    Flickable {
        anchors.fill: parent
        anchors.margins: 12
        contentWidth: width
        contentHeight: content.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        ColumnLayout {
            id: content
            width: parent.width
            spacing: 6
            LabelText {
                text: "System tray"
                color: Theme.muted
                font.pixelSize: 12
                Layout.fillWidth: true
                Layout.bottomMargin: 4
            }
            LabelText {
                visible: root.items.length === 0
                text: "No tray applications"
                color: Theme.muted
                Layout.fillWidth: true
                Layout.preferredHeight: 34
                verticalAlignment: Text.AlignVCenter
            }
            Repeater {
                model: root.items
                delegate: AbstractButton {
                    id: trayButton
                    required property var modelData
                    readonly property string title: modelData.tooltipTitle || modelData.title || modelData.id || "Tray application"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    padding: 0
                    hoverEnabled: true
                    Accessible.name: title
                    Accessible.role: Accessible.Button
                    background: Rectangle {
                        radius: 8
                        color: trayButton.hovered || trayButton.visualFocus ? Theme.alpha(Theme.accent, 0.18) : "transparent"
                        border.width: trayButton.visualFocus ? 1 : 0
                        border.color: Theme.accent
                    }
                    contentItem: Item {
                        Image {
                            id: trayIcon
                            anchors.left: parent.left; anchors.leftMargin: 9
                            anchors.verticalCenter: parent.verticalCenter
                            width: 18; height: 18
                            source: trayButton.modelData.icon
                            sourceSize.width: 18; sourceSize.height: 18
                            fillMode: Image.PreserveAspectFit
                        }
                        LabelText {
                            anchors.left: trayIcon.right; anchors.leftMargin: 10
                            anchors.right: parent.right; anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            text: trayButton.title
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                    }
                    onClicked: {
                        if (modelData.onlyMenu) root.displayMenu(modelData, trayButton);
                        else { modelData.activate(); ShellState.closePanels(); }
                    }
                    TapHandler {
                        acceptedButtons: Qt.RightButton
                        onTapped: root.displayMenu(trayButton.modelData, trayButton)
                    }
                    WheelHandler { onWheel: event => trayButton.modelData.scroll(event.angleDelta.y, false) }
                    ToolTip.visible: hovered
                    ToolTip.text: trayButton.title
                    ToolTip.delay: 500
                }
            }
        }
    }
}
