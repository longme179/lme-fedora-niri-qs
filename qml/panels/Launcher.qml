pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import "../services"
import "../services/LauncherSearch.js" as Search
import "../theme"
import "../components"
Item {
    id: root
    implicitWidth: 700; implicitHeight: 650
    property string query: ""
    property string selectedId: ""
    property var emoji: []
    property string calculation: ""
    property string calculationError: ""
    property bool calculating: false
    readonly property string mode: query.startsWith("/") && ShellState.preferences.fileSearchEnabled !== false ? "files" : query.startsWith(":") ? "emoji" : query.startsWith("@") ? "windows" : query.startsWith("=") || /^[\d\s().+*/%^-]+$/.test(query.trim()) && /[+*/%^-]/.test(query) ? "calculator" : "apps"
    readonly property string fileQuery: query.slice(1).trim()
    readonly property var files: ShellState.snapshot.fileSearch || {query:"",entries:[]}
    readonly property string expression: query.replace(/^=/, "").trim()
    readonly property var results: {
        const text = query.replace(/^[:@]/, "").trim().toLowerCase();
        if (mode === "files") return files.query===fileQuery ? (files.entries || []).map(e => Object.assign({},e,{detail:(e.directory ? "Folder · " : "File · ")+e.path})) : [];
        if (mode === "calculator") return calculation && !calculating ? [{kind: "copy", id: "calculation", name: calculation, detail: "Enter to copy result", value: calculation}] : [];
        if (mode === "emoji") return emoji.filter(e => (e.name + " " + e.keywords).includes(text)).slice(0, 100).map(e => ({kind: "copy", id: e.emoji, name: e.emoji + "  " + e.name, detail: "Copy emoji", value: e.emoji}));
        const windows = (ShellState.niri.windows || []).filter(w => [w.title || "", w.app_id || ""].join(" ").toLowerCase().includes(text)).map(w => ({kind: "window", id: "window-" + w.id, windowId: w.id, name: w.title || w.app_id || "Window", detail: "Open window · workspace " + (((ShellState.niri.workspaces || []).find(ws => ws.id === w.workspace_id) || {}).idx || "—"), icon: ShellState.windowIcon(w)}));
        if (mode === "windows") return windows;
        const apps = Search.apps(text, ShellState.apps).map(a => ({kind: "app", id: a.id, name: a.name, detail: a.genericName || a.comment || "Launch application", icon: ShellState.appIcon(a.icon)}));
        return [...apps, ...(text ? windows : [])];
    }
    function activate(index) {
        const item = results[index];
        if (!item) return;
        if (item.kind === "app") ShellState.run("launch", {id: item.id});
        else if (item.kind === "window") ShellState.run("focusWindow", {id: item.windowId});
        else if (item.kind === "file") ShellState.run("fileOpen", {path: item.path});
        else ShellState.run("copyText", {text: item.value});
        ShellState.closePanels();
    }
    function focusSearch() { selectedId = ""; query = ""; search.text = ""; search.forceActiveFocus(); resultsList.currentIndex = 0; }
    onResultsChanged: { const previous = results.findIndex(r => r.id === selectedId); resultsList.currentIndex = previous >= 0 ? previous : results.length ? 0 : -1; }
    onQueryChanged: {
        calculation = ""; calculationError = "";
        calculating = mode === "calculator" && expression.length > 0;
        fileDelay.stop(); if(mode === "files" && fileQuery.length>=2) fileDelay.restart();
        calculateDelay.stop(); if (calculating) calculateDelay.restart();
    }
    Timer { id: fileDelay; interval: 180; onTriggered: ShellState.run("fileSearch",{query:root.fileQuery}) }
    Timer { id: calculateDelay; interval: 140; onTriggered: ShellState.run("calculate", {query: root.expression}) }
    FileView {
        id: emojiFile; path: Quickshell.shellPath("assets/emoji.json"); printErrors: true
        onLoaded: { try { root.emoji = JSON.parse(text()); } catch (error) { root.calculationError = "Emoji index could not be read"; } }
    }
    Component.onCompleted: Qt.callLater(focusSearch)
    Connections {
        target: ShellState
        function onLauncherOpenChanged() { if (ShellState.launcherOpen) Qt.callLater(root.focusSearch); }
        function onLastResultChanged() {
            const result = ShellState.lastResult;
            if (!result || result.action !== "calculate" || result.query !== root.expression || root.mode !== "calculator") return;
            root.calculating = false; root.calculation = result.ok ? result.message : ""; root.calculationError = result.ok ? "" : result.message;
        }
    }
    GlassPanel { role: "launcherFill"; anchors.fill: parent }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 16
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Launcher"; font.pixelSize: 24; font.weight: Font.Bold; Layout.fillWidth: true }
            LiquidButton { text: "Esc"; onClicked: ShellState.closePanels(); Accessible.name: "Close launcher" }
        }
        LabelText { visible: root.mode === "files"; text: root.fileQuery.length<2 ? "Enter at least two characters after /" : ShellState.pendingActions.fileSearch ? "Searching local folders…" : root.files.query===root.fileQuery && root.files.truncated ? "Results limited; narrow the name or search folders" : "Local filename search"; Layout.fillWidth: true; color: Theme.muted; font.pixelSize: 12 }
        ExpressiveField {
            id: search; objectName: "launcherSearch"; Layout.fillWidth: true; Layout.preferredHeight: 52
            placeholderText: "Apps · / files · = calculate · : emoji · @ windows"; maximumLength: 160; Accessible.name: "Search launcher"
            onTextChanged: { root.selectedId = ""; root.query = text; }
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Escape) { ShellState.closePanels(); event.accepted = true; }
                else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { root.activate(resultsList.currentIndex); event.accepted = true; }
                else if ([Qt.Key_Down, Qt.Key_Up].includes(event.key)) {
                    resultsList.currentIndex = Math.max(0, Math.min(root.results.length - 1, resultsList.currentIndex + (event.key === Qt.Key_Down ? 1 : -1)));
                    root.selectedId = root.results[resultsList.currentIndex] ? root.results[resultsList.currentIndex].id : "";
                    resultsList.positionViewAtIndex(resultsList.currentIndex, ListView.Contain); event.accepted = true;
                }
            }
        }
        LabelText { text: root.calculationError || (root.calculating ? "Calculating…" : ""); visible: text.length > 0; color: root.calculationError ? Theme.red : Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
        Item {
            Layout.fillWidth: true; Layout.fillHeight: true
            ListView {
                id: resultsList; anchors.fill: parent; clip: true; spacing: 6; model: root.results
                boundsBehavior: Flickable.StopAtBounds; ScrollBar.vertical: ScrollBar {}
                header: Item { height: 4 }
                footer: Item { height: 4 }
                delegate: Item {
                    id: resultRow; required property var modelData; required property int index
                    width: resultsList.width; height: Theme.compact ? 62 : 72
                    Rectangle {
                        anchors.top: parent.top; anchors.bottom: parent.bottom
                        x: 4; width: parent.width - 16; radius: 16
                        color: resultsList.currentIndex === resultRow.index ? Theme.primaryContainer : Theme.alpha(Theme.surfaceContainer, .6)
                        LiquidButton { objectName: "launcherResult-" + resultRow.index; anchors.fill: parent; flat: true; cornerRadius: parent.radius; background: Item {}  contentItem: Item {}  Accessible.name: resultRow.modelData.name; onClicked: root.activate(resultRow.index) }
                        RowLayout {
                            anchors.fill: parent; anchors.margins: 12; spacing: 14
                            Item {
                                Layout.preferredWidth: 36; Layout.preferredHeight: 36
                                Image { id: appIcon; anchors.fill: parent; source: resultRow.modelData.icon || ""; sourceSize.width: 36; sourceSize.height: 36; asynchronous: true; fillMode: Image.PreserveAspectFit }
                                LabelText { anchors.centerIn: parent; visible: appIcon.status !== Image.Ready; text: resultRow.modelData.id === "calculation" ? "=" : resultRow.modelData.kind === "copy" ? resultRow.modelData.value.substring(0, 2) : resultRow.modelData.name.charAt(0); font.pixelSize: 26; color: Theme.accent }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 4
                                LabelText { text: resultRow.modelData.name; font.weight: Font.Bold; Layout.fillWidth: true; elide: Text.ElideRight }
                                LabelText { text: resultRow.modelData.detail; color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
                            }
                        }
                    }
                }
            }
            LabelText { anchors.centerIn: parent; width: parent.width - 24; visible: !root.results.length && !root.calculating && !root.calculationError; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; color: Theme.muted; text: root.mode === "calculator" ? "Enter an arithmetic expression" : "No matching results" }
        }
        LabelText { text: root.results.length + " results · ↑ ↓ navigate · Enter open or copy"; color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
    }
}
