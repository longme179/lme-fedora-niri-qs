pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../services"
import "../theme"
import "../components"

Item {
    id: root
    implicitWidth: 660
    implicitHeight: 568
    property string query: ""
    property string selectedAppId: ""
    readonly property var filteredApps: (ShellState.apps || []).filter(app => {
        const terms = query.trim().toLowerCase().split(/\s+/);
        const text = [app.name, app.genericName, app.comment, ...(app.keywords || [])].join(" ").toLowerCase();
        return terms.every(term => text.includes(term));
    })

    function activate(index) {
        if (index < 0 || index >= filteredApps.length) return;
        ShellState.run("launch", { id: filteredApps[index].id });
        ShellState.closePanels();
    }

    function focusSearch() {
        selectedAppId = "";
        query = "";
        search.text = "";
        search.forceActiveFocus();
        applications.currentIndex = 0;
    }

    Component.onCompleted: Qt.callLater(focusSearch)
    Connections {
        target: ShellState
        function onLauncherOpenChanged() {
            if (ShellState.launcherOpen) Qt.callLater(root.focusSearch);
        }
    }
    onFilteredAppsChanged: {
        const previous = filteredApps.findIndex(app => app.id === selectedAppId);
        applications.currentIndex = previous >= 0 ? previous : filteredApps.length ? 0 : -1;
    }

    GlassPanel { anchors.fill: parent }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 3
                Text { text: "Applications"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 24; font.weight: Font.Bold }
                Text { text: "Your next task starts here."; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 13 }
            }
            Item { Layout.fillWidth: true }
            LiquidButton {
                text: "Esc"
                Accessible.name: "Close applications"
                onClicked: ShellState.closePanels()
                palette.button: Theme.surface
                palette.buttonText: Theme.muted
            }
        }

        TextField {
            id: search
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            placeholderText: "Search apps, names, or keywords…"
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 16
            selectByMouse: true
            leftPadding: 18
            rightPadding: 18
            Accessible.name: "Search applications"
            placeholderTextColor: Theme.muted
            background: Rectangle {
                radius: Theme.smallRadius
                color: Theme.surface
                border.color: search.activeFocus ? Theme.purple : Theme.border
                border.width: 1
            }
            onTextChanged: {
                root.selectedAppId = "";
                root.query = text;
            }
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Escape) {
                    ShellState.closePanels();
                    event.accepted = true;
                } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    root.activate(applications.currentIndex);
                    event.accepted = true;
                } else if ([Qt.Key_Down, Qt.Key_Up, Qt.Key_Left, Qt.Key_Right].includes(event.key)) {
                    const columns = Math.max(1, Math.floor(applications.width / applications.cellWidth));
                    const delta = event.key === Qt.Key_Down ? columns : event.key === Qt.Key_Up ? -columns : event.key === Qt.Key_Right ? 1 : -1;
                    applications.currentIndex = Math.max(0, Math.min(root.filteredApps.length - 1, applications.currentIndex + delta));
                    if (applications.currentIndex >= 0 && applications.currentIndex < root.filteredApps.length)
                        root.selectedAppId = root.filteredApps[applications.currentIndex].id;
                    applications.positionViewAtIndex(applications.currentIndex, GridView.Contain);
                    event.accepted = true;
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            GridView {
                id: applications
                anchors.fill: parent
                clip: true
                cellWidth: 122
                cellHeight: 108
                model: root.filteredApps
                currentIndex: 0
            onModelChanged: {
                const previous = root.filteredApps.findIndex(app => app.id === root.selectedAppId);
                currentIndex = previous >= 0 ? previous : root.filteredApps.length ? 0 : -1;
            }
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                delegate: Item {
                    id: tile
                    required property var modelData
                    required property int index
                    width: applications.cellWidth
                    height: applications.cellHeight
                    LiquidButton {
                        id: appButton
                        anchors.fill: parent
                        anchors.margins: 4
                        Accessible.name: tile.modelData.name || tile.modelData.id
                        ToolTip.visible: hovered && (tile.modelData.comment || "").length > 0
                        ToolTip.text: tile.modelData.comment || ""
                        ToolTip.delay: 650
                        onClicked: root.activate(tile.index)
                        background: Rectangle {
                            radius: Theme.smallRadius
                            color: applications.currentIndex === tile.index || appButton.hovered ? Theme.surface : "transparent"
                            border.width: applications.currentIndex === tile.index ? 1 : 0
                            border.color: Theme.purple
                            Behavior on color { ColorAnimation { duration: Theme.animationDuration } }
                        }
                        contentItem: Column {
                            spacing: 8
                            Item {
                                width: parent.width
                                height: 46
                                Image {
                                    id: appImage
                                    anchors.centerIn: parent
                                    width: 40
                                    height: 40
                                    source: ShellState.appIcon(tile.modelData.icon || "application-x-executable")
                                    sourceSize.width: 40
                                    sourceSize.height: 40
                                    fillMode: Image.PreserveAspectFit
                                    asynchronous: true
                                }
                                Text {
                                    anchors.centerIn: parent
                                    visible: appImage.status !== Image.Ready
                                    text: (tile.modelData.name || "A").charAt(0).toUpperCase()
                                    color: Theme.purple
                                    font.pixelSize: 30
                                    font.family: Theme.fontFamily
                                }
                            }
                            Text {
                                width: parent.width
                                text: tile.modelData.name || tile.modelData.id
                                textFormat: Text.PlainText
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                                color: Theme.text
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                            }
                        }
                    }
                }
            }
            Column {
                visible: root.filteredApps.length === 0
                anchors.centerIn: parent
                width: parent.width - 60
                spacing: 10
                Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: root.query ? "No matching applications" : "No applications found"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 18; font.weight: Font.Bold }
                Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; text: root.query ? "Try a shorter name or a different keyword." : "Install an application with a desktop entry, then reopen the launcher."; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 13 }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Text { text: root.filteredApps.length + " applications"; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
            Item { Layout.fillWidth: true }
            Text { text: "↑ ↓ ← → navigate    Enter launch"; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
        }
    }
}
