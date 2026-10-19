pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import "../services"
import "../services/LauncherSearch.js" as Search
import "../theme"

ColumnLayout {
    id: root
    spacing: 12
    property bool editing: false
    property bool saving: false
    property string editingId: ""
    property string error: ""
    readonly property var entries: ShellState.preferences.launchpadEntries || ({})
    readonly property var matches: Search.apps(filter.text,Object.keys(entries).map(id=>Object.assign({id:id},entries[id])))
    function edit(id) {
        editingId=id; const entry=entries[id] || {name:"",command:"",kind:"command",terminal:false,cwd:""};
        title.text=entry.name; command.text=entry.command; kind.currentIndex=entry.kind==="bash" ? 1 : 0;
        mode.currentIndex=entry.terminal ? 1 : 0; folder.text=entry.cwd; editing=true;
    }
    function save() {
        if(!title.text.trim() || !command.text.trim()) { error="Enter a name and command first.";return; }
        const id=editingId || "task-"+Date.now()+"-"+Math.floor(Math.random()*100000);
        saving=true; ShellState.run("setting",{key:"launchpadEntries",token:id,value:{name:title.text,command:command.text,kind:kind.currentIndex ? "bash" : "command",terminal:mode.currentIndex===1,cwd:folder.text}});
    }
    Connections {
        target: ShellState
        function onLastResultChanged() {
            const result=ShellState.lastResult;
            if(result && result.action==="setting" && !result.pending && root.saving) { root.saving=false; if(result.ok) { root.editing=false;root.error=""; } else root.error=result.message; }
        }
    }
    FileDialog {
        id: binary; title:"Choose a script or executable"
        onAccepted: { const path=decodeURIComponent(selectedFile.toString().replace(/^file:\/\//,""));command.text='"'+path.replace(/\\/g,"\\\\").replace(/"/g,'\\"')+'"';kind.currentIndex=0; }
    }
    RowLayout {
        Layout.fillWidth:true
        ExpressiveField { id:filter; objectName:"launchpadSearch"; Layout.fillWidth:true; placeholderText:"Search commands"; Accessible.name:"Search Launchpad" }
        LiquidButton { objectName:"launchpadAdd"; text:"Add command"; enabled:ShellState.backendReady && Object.keys(root.entries).length<100; onClicked:root.edit("") }
    }
    ListView {
        id:list; Layout.fillWidth:true; Layout.preferredHeight:Math.min(280,Math.max(60,contentHeight)); clip:true
        model:root.matches; spacing:8; boundsBehavior:Flickable.StopAtBounds; ScrollBar.vertical:ScrollBar {}
        delegate: Rectangle {
            id:row; required property var modelData; width:list.width-8; height:100; radius:16; color:Theme.surface
            readonly property var job:(ShellState.snapshot.launchpadJobs || {})[modelData.id] || ({})
            ColumnLayout {
                anchors.fill:parent; anchors.margins:10; spacing:5
                RowLayout {
                    Layout.fillWidth:true
                    LabelText { text:row.modelData.name; font.weight:Font.Bold; Layout.fillWidth:true; elide:Text.ElideRight }
                    LiquidButton { text:"Run"; enabled:ShellState.preferences.launchpadEnabled!==false && !row.job.running; onClicked:ShellState.run("launchpadRun",{id:row.modelData.id}) }
                    IconButton { iconName:"settings"; tooltip:"Edit command"; onClicked:root.edit(row.modelData.id) }
                }
                LabelText { text:row.job.running ? "Running…" : row.job.exitCode!==undefined && row.job.exitCode!==null ? "Exit status: "+row.job.exitCode : (row.modelData.kind==="bash" ? "Bash script" : "Executable")+" · "+(row.modelData.terminal ? "Terminal" : "Background"); color:row.job.exitCode ? Theme.red : Theme.muted; font.pixelSize:12; Layout.fillWidth:true; elide:Text.ElideRight }
                LabelText { text:row.job.log || row.modelData.command.replace(/\n/g," · "); Layout.fillWidth:true; elide:Text.ElideMiddle; color:Theme.muted; font.pixelSize:11 }
            }
        }
    }
    LabelText { visible:!root.matches.length; text:"No commands yet. Add a binary command or paste a Bash script."; color:Theme.muted; wrapMode:Text.Wrap; Layout.fillWidth:true }
    ColumnLayout {
        visible:root.editing; Layout.fillWidth:true; spacing:10
        LabelText { text:root.editingId ? "Edit command" : "New command"; font.weight:Font.Bold }
        ExpressiveField { id:title; objectName:"launchpadName"; Layout.fillWidth:true; placeholderText:"Name"; maximumLength:80; Accessible.name:"Command name" }
        RowLayout {
            Layout.fillWidth:true
            LiquidComboBox { id:kind; objectName:"launchpadKind"; model:["Executable + arguments","Bash script"]; Accessible.name:"Command type" }
            LiquidComboBox { id:mode; objectName:"launchpadMode"; model:["Background","Terminal"]; Accessible.name:"Launch mode" }
            LiquidButton { text:"Browse…"; onClicked:binary.open() }
        }
        Rectangle {
            Layout.fillWidth:true; Layout.preferredHeight:150; radius:14; color:Theme.surface; border.color:Theme.border
            ScrollView { anchors.fill:parent; anchors.margins:10; clip:true
                TextArea { id:command; objectName:"launchpadCommand"; placeholderText:"Executable and arguments, or paste Bash here"; wrapMode:TextEdit.Wrap; color:Theme.text; font.family:Theme.fontFamily; selectByMouse:true; Accessible.name:"Command or Bash script" }
            }
        }
        ExpressiveField { id:folder; Layout.fillWidth:true; placeholderText:"Working directory (empty = home)"; Accessible.name:"Working directory" }
        LabelText { text:root.error || "Executable mode uses quoted arguments. Use Bash for pipes, variables and multiline scripts. Run only commands you trust."; color:root.error ? Theme.red : Theme.muted; wrapMode:Text.Wrap; Layout.fillWidth:true; font.pixelSize:12 }
        RowLayout {
            LiquidButton { objectName:"launchpadSave"; text:"Save"; enabled:!ShellState.pendingActions.setting; onClicked:root.save() }
            LiquidButton { text:"Cancel"; onClicked:root.editing=false }
            Item { Layout.fillWidth:true }
            LiquidButton { text:"Delete"; visible:!!root.editingId; enabled:!ShellState.pendingActions.setting; onClicked:{ root.saving=true;ShellState.run("setting",{key:"launchpadEntries",token:root.editingId,value:null}); } }
        }
    }
}
