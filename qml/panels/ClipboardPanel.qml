pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

GlassPanel {
    id: root
    implicitWidth: 620
    implicitHeight: 710
    property string selectedId: ""
    property string previewImage: ""
    property bool clearConfirmation: false
    property bool copyAfterSearch: false
    readonly property bool previewOpen: !!previewImage
    readonly property bool searchFocused: search.activeFocus
    focus: true
    function focusSearch() { search.forceActiveFocus(); }
    function copySelected() {
        const item = ClipboardState.entries[history.currentIndex];
        if (item && !ClipboardState.copyPending) ClipboardState.send("copy", {id: item.id});
    }
    function moveSelection(delta) {
        history.currentIndex = Math.max(0, Math.min(ClipboardState.entries.length - 1, history.currentIndex + delta));
        if (history.currentIndex >= 0) selectedId = ClipboardState.entries[history.currentIndex].id;
        history.positionViewAtIndex(history.currentIndex, ListView.Contain);
    }
    Component.onCompleted: { ClipboardState.search("", "all"); Qt.callLater(focusSearch); }
    Connections {
        target: ClipboardState
        function onCopied() { ShellState.closePanels(); }
        function onSearched(success) {
            if (!root.copyAfterSearch) return;
            root.copyAfterSearch = false;
            if (success) Qt.callLater(root.copySelected);
        }
    }
    Keys.onEscapePressed: { if (previewImage) previewImage = ""; else if (clearConfirmation) clearConfirmation = false; else ShellState.closePanels(); }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 22; spacing: 14
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true; spacing: 5
                LabelText { text: "Clipboard"; Layout.fillWidth: true; font.pixelSize: 25; font.weight: Font.Bold }
                LabelText { Layout.fillWidth: true; elide: Text.ElideRight; text: ClipboardState.paused ? "Capture paused" : ClipboardState.capturing ? "Text and images, ready when you need them" : "History is available · capture inactive"; color: Theme.muted; font.pixelSize: 12 }
            }
            LiquidButton { text: ClipboardState.paused ? "Resume" : "Pause"; enabled: ClipboardState.ready; onClicked: ClipboardState.send("pause", {value: !ClipboardState.paused}) }
            IconButton { glyph: "×"; tooltip: "Close clipboard"; onClicked: ShellState.closePanels() }
        }
        ExpressiveField {
            id: search
            Layout.fillWidth: true
            placeholderText: "Search clipboard history"
            Accessible.name: "Search clipboard history"
            onTextChanged: queryDelay.restart()
            onAccepted: {
                if (queryDelay.running || ClipboardState.searching || ClipboardState.query !== text) {
                    queryDelay.stop(); root.copyAfterSearch = true; ClipboardState.search(text, ClipboardState.filter);
                } else root.copySelected();
            }
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) { root.moveSelection(event.key === Qt.Key_Down ? 1 : -1); event.accepted = true; }
            }
            Timer { id: queryDelay; interval: 160; onTriggered: ClipboardState.search(search.text, ClipboardState.filter) }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            Repeater {
                model: ["all", "text", "image"]
                delegate: LiquidButton {
                    required property string modelData
                    text: modelData === "all" ? "All" : modelData === "text" ? "Text" : "Images"
                    selected: ClipboardState.filter === modelData
                    onClicked: ClipboardState.search(search.text, modelData)
                }
            }
            Item { Layout.fillWidth: true }
            LabelText { text: ClipboardState.entries.length + " / " + ClipboardState.total; color: Theme.muted; font.pixelSize: 12 }
            LiquidButton { objectName: "clipboardClear"; text: "Clear…"; enabled: ClipboardState.ready && ClipboardState.total > 0; onClicked: root.clearConfirmation = true }
        }
        LabelText {
            visible: !!text
            text: ClipboardState.message || ClipboardState.state.error || ""
            color: ClipboardState.messageError || ClipboardState.state.error ? Theme.red : Theme.muted
            wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 12
        }
        Item {
            Layout.fillWidth: true; Layout.fillHeight: true
            ListView {
                id: history
                anchors.fill: parent; clip: true; spacing: 8
                model: ClipboardState.entries
                currentIndex: count > 0 ? 0 : -1
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                onModelChanged: {
                    const previous = ClipboardState.entries.findIndex(item => item.id === root.selectedId);
                    currentIndex = previous >= 0 ? previous : ClipboardState.entries.length ? 0 : -1;
                }
                delegate: Rectangle {
                    id: entry
                    required property var modelData
                    required property int index
                    width: history.width - 10; height: modelData.kind === "image" ? 116 : 92; radius: 18
                    color: history.currentIndex === index ? Theme.primaryContainer : Theme.surfaceContainerHigh
                    border.width: history.currentIndex === index ? 1 : 0; border.color: Theme.accent
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 12; spacing: 12
                        Item {
                            visible: entry.modelData.kind === "image"
                            Layout.preferredWidth: 104; Layout.fillHeight: true
                            Image { anchors.fill: parent; source: entry.modelData.image; asynchronous: true; sourceSize.width: 208; sourceSize.height: 208; fillMode: Image.PreserveAspectFit }
                            MouseArea { objectName: "clipboardImage" + entry.index; anchors.fill: parent; onClicked: { root.previewImage = entry.modelData.image; previewClose.forceActiveFocus(); } }
                        }
                        AbstractButton {
                            Layout.fillWidth: true; Layout.fillHeight: true
                            Accessible.name: "Copy " + (entry.modelData.kind === "image" ? "image" : "clipboard text")
                            enabled: ClipboardState.available && !ClipboardState.copyPending
                            onClicked: { root.selectedId = entry.modelData.id; ClipboardState.send("copy", {id: entry.modelData.id}); }
                            contentItem: ColumnLayout {
                                spacing: 5
                                LabelText { text: entry.modelData.preview; Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; font.pixelSize: 14 }
                                LabelText { text: (entry.modelData.pinned ? "Pinned · " : "") + (entry.modelData.kind === "image" ? "Click image to preview" : Math.max(1, Math.round(entry.modelData.bytes / 1024)) + " KB · Text"); color: Theme.muted; font.pixelSize: 11; Layout.fillWidth: true }
                            }
                        }
                        ColumnLayout {
                            spacing: 4
                            IconButton { objectName: "clipboardPin" + entry.index; glyph: entry.modelData.pinned ? "◆" : "◇"; tooltip: entry.modelData.pinned ? "Unpin item" : "Pin item"; implicitWidth: 30; implicitHeight: 30; active: entry.modelData.pinned; onClicked: ClipboardState.send("pin", {id: entry.modelData.id}) }
                            IconButton { objectName: "clipboardDelete" + entry.index; glyph: "×"; tooltip: "Delete item"; implicitWidth: 30; implicitHeight: 30; onClicked: ClipboardState.send("delete", {id: entry.modelData.id}) }
                        }
                    }
                }
            }
            ColumnLayout {
                visible: history.count === 0
                anchors.centerIn: parent; width: parent.width - 64; spacing: 10
                ShellIcon { name: "clipboard"; color: Theme.accent; width: 36; height: 36; Layout.alignment: Qt.AlignHCenter }
                LabelText { text: search.text ? "No matching clipboard items" : "Your next copy starts here"; font.weight: Font.Bold; font.pixelSize: 18; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
                LabelText { text: search.text ? "Try another word or filter." : "Copy text or an image from an application. It will appear in this history."; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter }
            }
        }
        LabelText { text: "↑ ↓ select    Enter copy    Escape close"; color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true }
    }
    Rectangle {
        visible: root.clearConfirmation || !!root.previewImage
        anchors.fill: parent; radius: parent.radius; color: Theme.alpha(Theme.background, 0.96)
        MouseArea { anchors.fill: parent }
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 28; spacing: 18
            LabelText { text: root.previewImage ? "Image preview" : "Clear clipboard history?"; font.pixelSize: 22; font.weight: Font.Bold; Layout.fillWidth: true }
            Image { visible: !!root.previewImage; Layout.fillWidth: true; Layout.fillHeight: true; source: root.previewImage; sourceSize.width: 1000; sourceSize.height: 1000; asynchronous: true; fillMode: Image.PreserveAspectFit }
            LabelText { visible: !root.previewImage; text: "Choose whether to keep your pinned items."; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
            Item { visible: !root.previewImage; Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                LiquidButton { id: previewClose; objectName: "clipboardPreviewBack"; text: root.previewImage ? "Back" : "Cancel"; onClicked: { root.previewImage = ""; root.clearConfirmation = false; root.focusSearch(); } }
                Item { Layout.fillWidth: true }
                LiquidButton { objectName: "clipboardKeepPins"; visible: !root.previewImage; text: "Keep pins"; onClicked: { ClipboardState.send("clear", {includePinned: false}); root.clearConfirmation = false; } }
                LiquidButton { visible: !root.previewImage; text: "Clear all"; palette.button: Theme.red; palette.buttonText: Theme.onPrimary; onClicked: { ClipboardState.send("clear", {includePinned: true}); root.clearConfirmation = false; } }
            }
        }
    }
}
