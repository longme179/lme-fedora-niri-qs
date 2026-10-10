pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

GlassPanel {
    id: root
    implicitWidth: 1120
    implicitHeight: 680
    focus: true
    property int draggedWindowId: -1
    onDraggedWindowIdChanged: ShellState.draggingWindow = draggedWindowId >= 0
    Component.onDestruction: ShellState.draggingWindow = false
    readonly property var workspaces: ShellState.workspacesFor(null)
    Keys.onEscapePressed: ShellState.closePanels()
    function moveWindow(id, target) {
        const window = (ShellState.niri.windows || []).find(item => item.id === id);
        if (window && window.workspace_id !== target)
            ShellState.run("moveWindow", {id: id, workspaceId: target});
    }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 18
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 5
                LabelText { text: "Workspace overview"; font.pixelSize: 24; font.weight: Font.Bold }
                LabelText { text: "Drag a window to another workspace, or select it to focus."; color: Theme.muted }
            }
            Item { Layout.fillWidth: true }
            LiquidButton { text: "Live preview"; enabled: !ShellState.demo && ShellState.niri.available; onClicked: ShellState.nativeOverview() }
            IconButton { glyph: "×"; tooltip: "Close overview"; onClicked: ShellState.closePanels() }
        }
        LabelText {
            visible: !ShellState.niri.available
            text: "Connect to a niri session to manage windows."
            color: Theme.muted; Layout.fillWidth: true
        }
        Flickable {
            Layout.fillWidth: true; Layout.fillHeight: true
            contentWidth: width; contentHeight: workspaceGrid.implicitHeight
            clip: true; boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            GridLayout {
                id: workspaceGrid
                width: parent.width
                columns: width >= 900 ? 3 : width >= 600 ? 2 : 1
                columnSpacing: 14; rowSpacing: 14
                Repeater {
                    model: root.workspaces
                    delegate: Rectangle {
                        id: workspaceCard
                        required property var modelData
                        readonly property var windows: (ShellState.niri.windows || []).filter(window => window.workspace_id === modelData.id)
                        Layout.fillWidth: true
                        Layout.preferredWidth: (workspaceGrid.width - (workspaceGrid.columns - 1) * 14) / workspaceGrid.columns
                        Layout.preferredHeight: Math.max(222, windowList.implicitHeight + 64)
                        radius: 18
                        color: drop.containsDrag ? Theme.alpha(Theme.accent, 0.22) : Theme.alpha(Theme.surface, 0.65)
                        border.width: modelData.is_focused || drop.containsDrag ? 2 : 1
                        border.color: modelData.is_focused || drop.containsDrag ? Theme.accent : Theme.border
                        DropArea {
                            id: drop
                            anchors.fill: parent
                            keys: ["lme-window"]
                            onDropped: event => {
                                if (root.draggedWindowId >= 0) {
                                    root.moveWindow(root.draggedWindowId, workspaceCard.modelData.id);
                                    event.acceptProposedAction();
                                }
                            }
                        }
                        ColumnLayout {
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
                            spacing: 10
                            AbstractButton {
                                Layout.fillWidth: true; Layout.preferredHeight: 26
                                padding: 0; hoverEnabled: true
                                Accessible.name: "Focus workspace " + (workspaceCard.modelData.name || workspaceCard.modelData.idx)
                                contentItem: RowLayout {
                                    LabelText { text: (workspaceCard.modelData.name || "Workspace " + workspaceCard.modelData.idx); font.weight: Font.Bold; color: workspaceCard.modelData.is_focused ? Theme.accent : Theme.text }
                                    Item { Layout.fillWidth: true }
                                    LabelText { text: workspaceCard.modelData.output || "Detached"; font.pixelSize: 10; color: Theme.muted }
                                }
                                onClicked: { ShellState.run("workspace", {id: workspaceCard.modelData.id}); ShellState.closePanels(); }
                            }
                            ColumnLayout {
                                id: windowList
                                Layout.fillWidth: true
                                spacing: 8
                                LabelText { visible: workspaceCard.windows.length === 0; text: "Empty workspace"; color: Theme.muted; Layout.preferredHeight: 100; verticalAlignment: Text.AlignVCenter }
                                Repeater {
                                    model: workspaceCard.windows
                                    delegate: Rectangle {
                                        id: windowCard
                                        required property var modelData
                                        Layout.fillWidth: true; Layout.preferredHeight: 64
                                        radius: 12
                                        color: windowPointer.containsMouse ? Theme.alpha(Theme.accent, 0.20) : Theme.panel
                                        border.width: modelData.is_focused ? 1 : 0; border.color: Theme.accent
                                        opacity: root.draggedWindowId === modelData.id ? 0.45 : 1
                                        RowLayout {
                                            anchors.fill: parent; anchors.margins: 10; spacing: 10
                                            Item {
                                                Layout.preferredWidth: 30; Layout.preferredHeight: 30
                                                Image { id: appImage; anchors.fill: parent; source: ShellState.windowIcon(windowCard.modelData); fillMode: Image.PreserveAspectFit }
                                                ShellIcon { anchors.centerIn: parent; name: "applications"; visible: appImage.status !== Image.Ready; color: Theme.accent }
                                            }
                                            ColumnLayout {
                                                Layout.fillWidth: true; spacing: 4
                                                LabelText { Layout.fillWidth: true; text: windowCard.modelData.title || "Untitled window"; elide: Text.ElideRight; font.pixelSize: 12 }
                                                LabelText { Layout.fillWidth: true; text: windowCard.modelData.app_id || "Application"; elide: Text.ElideRight; color: Theme.muted; font.pixelSize: 10 }
                                            }
                                            LiquidComboBox {
                                                implicitWidth: 48; Layout.preferredWidth: 48
                                                model: root.workspaces.map(item => item.idx + " · " + (item.output || "Detached"))
                                                currentIndex: root.workspaces.findIndex(item => item.id === windowCard.modelData.workspace_id)
                                                displayText: currentIndex >= 0 ? String(root.workspaces[currentIndex].idx) : "–"
                                                Accessible.name: "Move " + windowCard.modelData.title + " to workspace"
                                                onActivated: root.moveWindow(windowCard.modelData.id, root.workspaces[currentIndex].id)
                                            }
                                        }
                                        MouseArea {
                                            id: windowPointer
                                            anchors { left: parent.left; top: parent.top; bottom: parent.bottom; right: parent.right; rightMargin: 64 }
                                            hoverEnabled: true
                                            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                                            drag.target: dragProxy
                                            drag.axis: Drag.XAndYAxis
                                            onPressed: mouse => {
                                                const pos = mapToItem(root, mouse.x, mouse.y);
                                                dragProxy.x = pos.x - dragProxy.width / 2;
                                                dragProxy.y = pos.y - dragProxy.height / 2;
                                                dragProxy.title = windowCard.modelData.title || "Window";
                                            }
                                            onReleased: {
                                                if (root.draggedWindowId >= 0) dragProxy.Drag.drop();
                                                root.draggedWindowId = -1;
                                            }
                                            onCanceled: { dragProxy.Drag.cancel(); root.draggedWindowId = -1; }
                                            onClicked: { ShellState.run("focusWindow", {id: windowCard.modelData.id}); ShellState.closePanels(); }
                                            onDoubleClicked: { ShellState.run("focusWindow", {id: windowCard.modelData.id}); ShellState.closePanels(); }
                                            drag.onActiveChanged: if (drag.active) root.draggedWindowId = windowCard.modelData.id
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        LabelText { text: "Left-click the topbar overview button for niri's live window previews. Right-click for this board."; color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
    }
    Rectangle {
        id: dragProxy
        property string title: ""
        width: 220; height: 54; radius: 12; z: 100
        visible: root.draggedWindowId >= 0
        color: Theme.panel; border.width: 2; border.color: Theme.accent
        Drag.active: root.draggedWindowId >= 0
        Drag.keys: ["lme-window"]
        Drag.hotSpot.x: width / 2; Drag.hotSpot.y: height / 2
        LabelText { anchors.fill: parent; anchors.margins: 12; text: dragProxy.title; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
    }
}
