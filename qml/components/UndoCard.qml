// Role: UndoCard.qml (shared layer, fan-in 2 — the shell toast window and the Settings
// app overlay). The visible face of UndoState: one line, one way back, one countdown.
// REL: qml/services/UndoState.qml (registry); qml/panels/UndoToast.qml and
//      qml/settings/SettingsApplication.qml (the two hosts).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../services"
import "../theme"

GlassPanel {
    id: root
    implicitWidth: 380
    implicitHeight: content.implicitHeight + 24

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            LabelText {
                Layout.fillWidth: true
                text: UndoState.label
                wrapMode: Text.Wrap
                font.pixelSize: 13
            }
            LiquidButton {
                objectName: "undoToastAction"
                text: "Undo"
                Accessible.name: "Undo " + UndoState.label
                onClicked: UndoState.undo()
            }
        }
    }

    // The offer outlives the card by design (the registry holds it); the card only
    // decides when an unanswered offer settles. Hovering holds the door open, like
    // the OSD (OSDWindow.qml keeps the same stop/restart contract).
    Timer {
        id: expiry
        interval: 7000
        onTriggered: if (UndoState.pending) UndoState.settle()
    }
    Connections {
        target: UndoState
        function onOffered(text) { expiry.restart() }
    }
    HoverHandler {
        onHoveredChanged: {
            if (hovered) expiry.stop();
            else if (UndoState.pending) expiry.restart();
        }
    }
}
