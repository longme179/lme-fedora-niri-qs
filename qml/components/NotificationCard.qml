// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

GlassPanel {
    id: root
    required property var entry
    property real maximumHeight: Infinity
    property string timeText: ""
    property bool animateIdle: true
    property bool dismissible: true
    signal dismissRequested()
    signal annotateRequested()
    signal actionRequested(string identifier)
    readonly property real padding: Math.min(Theme.notificationPadding, Math.max(8, (maximumHeight - 60) / 2))
    readonly property bool overflowing: details.contentHeight > details.height + 1
    role: "notificationFill"
    radius: Theme.notificationRadius
    color: Theme.alpha(Theme.notificationFill, Theme.notificationOpacity)
    border.width: Theme.notificationBorderWidth
    border.color: entry.urgency === 2 ? Theme.red : Theme.notificationBorder
    implicitHeight: Math.min(maximumHeight, header.implicitHeight + message.implicitHeight + padding * 2 + 16)

    MouseArea { anchors.fill: parent; enabled: !!root.entry.imagePath; onClicked: root.annotateRequested() }

    RowLayout {
        id: header
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: root.padding }
        spacing: 8
        NotificationEmblem { objectName: "notificationEmblem"; animate: root.animateIdle && Theme.notificationIdleAnimation; accent: root.entry.urgency === 2 ? Theme.red : Theme.notificationAccent }
        LabelText {
            text: root.entry.appName || "Application"
            Layout.fillWidth: true; Layout.minimumWidth: 0
            color: Theme.notificationAccent; font.pixelSize: Theme.notificationBodySize; font.weight: Font.Medium
            elide: Text.ElideRight
        }
        LabelText { visible: !!root.timeText; text: root.timeText; color: Theme.notificationBody; font.pixelSize: 10 }
        IconButton { visible: root.dismissible; glyph: "×"; tooltip: "Dismiss notification"; implicitWidth: 28; implicitHeight: 28; onClicked: root.dismissRequested() }
    }
    Flickable {
        id: details
        objectName: "notificationScroll"
        anchors { left: parent.left; right: parent.right; top: header.bottom; leftMargin: root.padding - 4; rightMargin: root.padding - 4; topMargin: 8 }
        height: Math.max(0, root.height - header.height - root.padding * 2 - 4)
        clip: true; interactive: root.overflowing; boundsBehavior: Flickable.StopAtBounds
        contentWidth: width; contentHeight: message.implicitHeight + 8
        ScrollBar.vertical: ScrollBar {}
        MouseArea { anchors.fill: message; enabled: !!root.entry.imagePath; onClicked: root.annotateRequested() }
        Column {
            id: message
            x: 4; y: 4; width: Math.max(0, details.width - 12); spacing: 8
            LabelText {
                objectName: "notificationSummary"
                width: parent.width; text: root.entry.summary || ""
                color: Theme.notificationTitle; font.pixelSize: Theme.notificationTitleSize; font.weight: Font.Bold
                wrapMode: Text.Wrap
            }
            LabelText {
                objectName: "notificationBody"
                width: parent.width; text: root.entry.body || ""; visible: !!text
                color: Theme.notificationBody; font.pixelSize: Theme.notificationBodySize
                wrapMode: Text.Wrap
            }
            Flow {
                id: actions
                objectName: "notificationActions"
                width: parent.width; spacing: 8
                LiquidButton { objectName: "notificationAnnotate-" + root.entry.id; visible: !!root.entry.imagePath; text: "Annotate"; width: Math.min(implicitWidth, actions.width); onClicked: root.annotateRequested() }
                Repeater {
                    model: root.entry.active === false ? [] : root.entry.actions || []
                    delegate: LiquidButton {
                        id: action
                        required property var modelData
                        text: modelData.text || modelData.identifier
                        width: Math.min(implicitWidth, actions.width)
                        implicitHeight: Math.max(40, contentItem.implicitHeight + topPadding + bottomPadding)
                        contentItem: LabelText { text: action.text; font: action.font; color: action.palette.buttonText; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                        onClicked: root.actionRequested(modelData.identifier)
                    }
                }
            }
        }
    }
}
