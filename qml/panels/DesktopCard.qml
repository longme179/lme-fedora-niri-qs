pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import "../components"
import "../services"
import "../theme"

GlassPanel {
    id: root
    required property string widgetId
    required property var record
    property bool editing: DesktopState.editing
    signal moveBy(real dx, real dy)
    signal resizeBy(real dx, real dy)
    signal committed()
    radius: 24
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 14; spacing: 8
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: root.record.type === "notes" ? "Notes" : root.record.type === "media" ? "Media" : "Clock"; font.weight: Font.Bold; Layout.fillWidth: true }
            LabelText { visible: root.editing; text: "Drag header"; color: Theme.muted; font.pixelSize: 11 }
            MouseArea {
                id: grip; objectName: "desktopDrag-" + root.widgetId
                Layout.preferredWidth: 36; Layout.preferredHeight: 30; visible: root.editing
                property point previous: Qt.point(0,0)
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                activeFocusOnTab: true; Accessible.name: "Move desktop widget"; Accessible.role: Accessible.Button
                LabelText { anchors.centerIn: parent; text: "⠿"; color: Theme.accent }
                onPressed: mouse => { forceActiveFocus(); previous = mapToGlobal(mouse.x,mouse.y); }
                onPositionChanged: mouse => { if (!pressed) return; const p=mapToGlobal(mouse.x,mouse.y); root.moveBy(p.x-previous.x,p.y-previous.y); previous=p; }
                onReleased: root.committed()
                Keys.onPressed: event => {
                    const step = event.modifiers & Qt.ShiftModifier ? 1 : 10;
                    if (event.key===Qt.Key_Left) root.moveBy(-step,0);
                    else if (event.key===Qt.Key_Right) root.moveBy(step,0);
                    else if (event.key===Qt.Key_Up) root.moveBy(0,-step);
                    else if (event.key===Qt.Key_Down) root.moveBy(0,step);
                    else return;
                    root.committed(); event.accepted=true;
                }
            }
        }
        ScrollView {
            id: scroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            contentWidth: availableWidth
            Loader { width: scroll.availableWidth; sourceComponent: root.record.type === "clock" ? clockCard : root.record.type === "notes" ? notesCard : mediaCard }
        }
    }
    MouseArea {
        visible: root.editing; objectName: "desktopResize-" + root.widgetId
        anchors.right: parent.right; anchors.bottom: parent.bottom; width: 28; height: 28
        property point previous: Qt.point(0,0)
        cursorShape: Qt.SizeFDiagCursor
        Accessible.name: "Resize desktop widget"
        onPressed: mouse => previous=mapToGlobal(mouse.x,mouse.y)
        onPositionChanged: mouse => { if (!pressed) return; const p=mapToGlobal(mouse.x,mouse.y); root.resizeBy(p.x-previous.x,p.y-previous.y); previous=p; }
        onReleased: root.committed()
        LabelText { anchors.centerIn: parent; text: "◢"; color: Theme.accent }
    }
    Component {
        id: clockCard
        ColumnLayout {
            spacing: 6
            LabelText { text: Qt.formatDateTime(clock.date,"HH:mm"); font.pixelSize: Math.min(54,root.width*.15); font.weight: Font.Bold; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
            LabelText { text: Qt.formatDateTime(clock.date,"dddd, MMMM d"); color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
            SystemClock { id: clock; precision: SystemClock.Minutes; enabled: root.visible }
        }
    }
    Component { id: notesCard; QuickNotes {} }
    Component {
        id: mediaCard
        ColumnLayout {
            spacing: 10
            LabelText { text: ActivityState.track; Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Bold }
            LabelText { text: ActivityState.artist; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
            MediaProgress { player: ActivityState.player; playing: ActivityState.playing; Layout.fillWidth: true }
            MediaActions { player: ActivityState.player; Layout.fillWidth: true }
            LyricsView { player: ActivityState.player; Layout.fillWidth: true }
        }
    }
}
