pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"
Item {
    id: root
    objectName: "systemMonitor"
    readonly property var state: ShellState.snapshot.monitor || {}
    readonly property var samples: state.history || []
    property string query: ""
    property int order: 0
    readonly property var processes: (state.processes || []).filter(p => (p.name+" "+p.pid+" "+p.user).toLowerCase().includes(query.toLowerCase())).slice().sort((a,b) => order === 0 ? (b.cpu || 0)-(a.cpu || 0) || b.memoryBytes-a.memoryBytes : order === 1 ? b.memoryBytes-a.memoryBytes : a.name.localeCompare(b.name))
    function percent(value) { return value === null || value === undefined ? "—" : Number(value).toFixed(1)+"%"; }
    function bytes(value) { if (value === null || value === undefined) return "—"; return value >= 1048576 ? (value/1048576).toFixed(1)+" MiB" : (value/1024).toFixed(1)+" KiB"; }
    function subscribe() { if (ShellState.backendReady) ShellState.run("monitor", {enabled: true}); }
    Component.onCompleted: subscribe()
    Component.onDestruction: if (ShellState.backendReady) ShellState.run("monitor", {enabled: false})
    Connections { target: ShellState; function onBackendReadyChanged() { if (ShellState.backendReady) root.subscribe(); } }
    Flickable {
        id: scroll; anchors.fill: parent; clip: true
        contentWidth: width; contentHeight: body.implicitHeight + 16; boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        ColumnLayout {
            id: body; width: scroll.width-12; spacing: 16
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    LabelText { text: "System monitor"; font.pixelSize: 22; font.weight: Font.Bold }
                    LabelText { text: "2-second samples · only while open"; color: Theme.muted; font.pixelSize: 12 }
                }
                LabelText { text: ShellState.system.tempC === null || ShellState.system.tempC === undefined ? "CPU temp —" : "CPU "+Number(ShellState.system.tempC).toFixed(0)+" °C"; color: Theme.yellow; font.weight: Font.Bold }
            }
            LabelText { visible: !!root.state.error; text: root.state.error || ""; color: Theme.red; Layout.fillWidth: true; wrapMode: Text.Wrap }
            GridLayout {
                Layout.fillWidth: true; columns: root.width >= 500 ? 2 : 1; columnSpacing: 12; rowSpacing: 12
                Repeater {
                    model: [{title:"CPU",key:"cpu",value:root.percent(ShellState.system.cpu),color:Theme.cyan}, {title:"Memory",key:"memory",value:root.percent(ShellState.system.memoryPercent),color:Theme.purple}]
                    delegate: Rectangle {
                        id: card; required property var modelData
                        Layout.fillWidth: true; implicitHeight: chartBody.implicitHeight+28; radius: 20; color: Theme.surfaceContainer
                        ColumnLayout {
                            id: chartBody; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 8
                            RowLayout {
                                Layout.fillWidth: true
                                LabelText { text: card.modelData.title; font.weight: Font.Bold; Layout.fillWidth: true }
                                LabelText { text: card.modelData.value; color: card.modelData.color; font.pixelSize: 20; font.weight: Font.Bold }
                            }
                            HistoryChart { samples: root.samples; series: card.modelData.key; lineColor: card.modelData.color }
                        }
                    }
                }
            }
            LabelText { text: ShellState.system.memoryUsedGiB === undefined ? "" : ShellState.system.memoryUsedGiB+" / "+ShellState.system.memoryTotalGiB+" GiB used"; color: Theme.muted; font.pixelSize: 12 }
            Flow {
                Layout.fillWidth: true; spacing: 6
                Repeater {
                    model: root.state.cores || []
                    delegate: Rectangle {
                        id: core; required property var modelData
                        width: 80; height: 38; radius: 12; color: Theme.surfaceContainerHigh
                        LabelText { anchors.centerIn: parent; text: core.modelData.name+" "+(core.modelData.percent === null ? "—" : Math.round(core.modelData.percent)+"%"); font.pixelSize: 11 }
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: networkBody.implicitHeight+28; radius: 20; color: Theme.surfaceContainer
                ColumnLayout {
                    id: networkBody; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 8
                    LabelText { text: "Network"; font.weight: Font.Bold }
                    Repeater {
                        model: root.state.interfaces || []
                        delegate: LabelText { required property var modelData; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12; text: modelData.name+"   ↓ "+root.bytes(modelData.download)+"/s   ↑ "+root.bytes(modelData.upload)+"/s"; color: Theme.muted }
                    }
                    HistoryChart { series: "download"; samples: root.samples; lineColor: Theme.green; maximum: Math.max(1024,...root.samples.map(s=>s.download || 0)) }
                    LabelText { text: "Download · peak "+root.bytes(Math.max(0,...root.samples.map(s=>s.download || 0)))+"/s"; color: Theme.green; font.pixelSize: 11 }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                LabelText { text: "Processes"; font.weight: Font.Bold; font.pixelSize: 18; Layout.fillWidth: true }
                LiquidComboBox { objectName: "processSort"; model: ["CPU", "Memory", "Name"]; currentIndex: root.order; onActivated: root.order = currentIndex; implicitWidth: 120 }
            }
            ExpressiveField { objectName: "processSearch"; Layout.fillWidth: true; placeholderText: "Search name, PID or user"; maximumLength: 160; Accessible.name: placeholderText; onTextChanged: root.query = text }
            RowLayout {
                Layout.fillWidth: true
                LabelText { text: "Process / PID / user"; color: Theme.muted; font.pixelSize: 11; Layout.fillWidth: true }
                LabelText { text: "CPU*"; color: Theme.muted; font.pixelSize: 11; Layout.preferredWidth: 60; horizontalAlignment: Text.AlignRight }
                LabelText { text: "Memory"; color: Theme.muted; font.pixelSize: 11; Layout.preferredWidth: 82; horizontalAlignment: Text.AlignRight }
            }
            ListView {
                id: processList; objectName: "processList"; Layout.fillWidth: true; Layout.preferredHeight: 260; clip: true
                model: root.processes; spacing: 4; boundsBehavior: Flickable.StopAtBounds; ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    id: row; required property var modelData
                    width: processList.width-10; height: 54; radius: 12; color: Theme.surfaceContainerHigh
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 10; spacing: 8
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 2
                            LabelText { text: row.modelData.name; textFormat: Text.PlainText; Layout.fillWidth: true; elide: Text.ElideRight; font.weight: Font.Medium }
                            LabelText { text: row.modelData.pid+" · "+row.modelData.user; textFormat: Text.PlainText; color: Theme.muted; font.pixelSize: 10 }
                        }
                        LabelText { text: root.percent(row.modelData.cpu); color: Theme.cyan; font.pixelSize: 12; Layout.preferredWidth: 60; horizontalAlignment: Text.AlignRight }
                        LabelText { text: root.bytes(row.modelData.memoryBytes); font.pixelSize: 12; Layout.preferredWidth: 82; horizontalAlignment: Text.AlignRight }
                    }
                }
                LabelText { anchors.centerIn: parent; visible: processList.count === 0; text: ShellState.backendReady ? "No matching processes" : "Connecting…"; color: Theme.muted }
            }
            LabelText { text: root.processes.length+" / "+(root.state.processCount || 0)+" processes · *100% = one CPU thread"; color: Theme.muted; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap }
        }
    }
}
