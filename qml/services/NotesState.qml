pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
Singleton {
    id: root
    property string content: ""
    property string baseline: ""
    property bool ready: ShellState.demo
    property bool dirty: false
    property bool conflict: false
    property bool initializing: false
    property bool pendingSave: false
    property string error: ""
    readonly property string filePath: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME")+"/.local/state") + "/lme-shell/notes.txt"
    function edit(text) { if(content===text) return; content=text; dirty=content!==baseline; if(dirty) delay.restart(); }
    function save() {
        if(ShellState.demo || !ready || !dirty || conflict) return;
        if(content.length>100000) { error="Notes exceed 100,000 characters; shorten or copy the buffer"; return; }
        pendingSave=true; file.reload();
    }
    function reload() { dirty=false; conflict=false; error=""; pendingSave=false; file.reload(); }
    Timer { id: delay; interval: 600; onTriggered: root.save() }
    FileView {
        id: file; path: ShellState.demo ? "" : root.filePath
        atomicWrites: true; blockWrites: true; watchChanges: true; printErrors: false
        onFileChanged: reload()
        onLoaded: {
            const latest=text(); root.ready=true; root.initializing=false;
            if(latest.length>100000) { root.error="Existing note is too large; file was left untouched"; root.conflict=true; return; }
            if(root.dirty && latest!==root.baseline && latest!==root.content) { root.conflict=true; root.pendingSave=false; root.error="Notes changed outside the shell. Copy your unsaved text before reloading."; return; }
            if(!root.dirty) root.content=latest;
            root.baseline=latest;
            if(root.pendingSave) { root.pendingSave=false; setText(root.content); }
        }
        onSaved: { root.baseline=root.content; root.dirty=false; root.error=""; }
        onSaveFailed: error => { root.error="Notes could not be saved: "+FileViewError.toString(error); root.dirty=true; }
        onLoadFailed: error => {
            if(ShellState.demo) return;
            if(error===FileViewError.FileNotFound && ShellState.backendReady && !root.initializing) { root.initializing=true; ShellState.run("notesInit"); }
            else if(error!==FileViewError.FileNotFound) root.error="Notes could not be read: "+FileViewError.toString(error);
        }
    }
    Connections {
        target: ShellState
        function onBackendReadyChanged() { if(ShellState.backendReady && !root.ready && !ShellState.demo) file.reload(); }
        function onLastResultChanged() { if(ShellState.lastResult.action==="notesInit") { if(ShellState.lastResult.ok) file.reload(); else { root.error=ShellState.lastResult.message; root.initializing=false; } } }
    }
    // Blocking final write flushes a small local buffer before QML children are destroyed.
    Component.onDestruction: if(!ShellState.demo && ready && dirty && !conflict && content.length<=100000) file.setText(content)
}
