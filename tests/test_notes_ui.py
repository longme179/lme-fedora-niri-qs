"""Autosave after panel destruction and preservation of conflicting buffers."""
import json,os,subprocess,tempfile,time,unittest
from pathlib import Path

@unittest.skipUnless(os.environ.get('LME_TEST_MOTION_UI')=='1','opt-in private Wayland notes test')
class NotesUiCase(unittest.TestCase):
    def test_closed_editor_saves_and_external_conflict_keeps_buffer(self):
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);note=root/'state/lme-shell/notes.txt';note.parent.mkdir(parents=True);note.write_text('Existing note');note.chmod(0o600)
            (root/'qml').symlink_to(repo/'qml',target_is_directory=True)
            entry=root/'shell.qml';entry.write_text('''//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/panels"
import "qml/services"
ShellRoot {
    Component.onCompleted: Quickshell.watchFiles=false
    FloatingWindow { visible:true; implicitWidth:700;implicitHeight:500
        Loader { id: editor; anchors.fill:parent; sourceComponent:QuickNotes {} }
    }
    function find(item) { if(item.objectName==="quickNotesEditor") return item; for(const child of item.children || []) { const result=find(child); if(result) return result; } if(item.contentItem) return find(item.contentItem); return null; }
    IpcHandler { target:"notesTest"
        function state():string {return JSON.stringify({ready:NotesState.ready,dirty:NotesState.dirty,conflict:NotesState.conflict,content:NotesState.content});}
        function edit(text:string):void { const field=find(editor.item); field.text=text; }
        function close():void {editor.active=false;}
        function reopen():void {editor.active=true;}
    }
}''')
            env={**os.environ,'XDG_STATE_HOME':str(root/'state'),'XDG_CONFIG_HOME':str(root/'config'),'LME_SHELL_DEMO':'0','LME_SHELL_BACKEND_DEMO':'1'}
            with tempfile.TemporaryFile(mode='w+') as log:
                process=subprocess.Popen(['quickshell','-p',str(entry)],env=env,stdout=log,stderr=log)
                def ipc(method,*args): return subprocess.run(['quickshell','-p',str(entry),'ipc','call','notesTest',method,*args],env=env,capture_output=True,text=True,check=True).stdout.strip()
                def wait(predicate):
                    for _ in range(80):
                        try: state=json.loads(ipc('state'))
                        except (ValueError,subprocess.CalledProcessError): time.sleep(.1);continue
                        if predicate(state):return state
                        time.sleep(.1)
                    log.seek(0);raise AssertionError(log.read())
                try:
                    wait(lambda s:s['ready'] and s['content']=='Existing note')
                    ipc('edit','Autosaved after close');ipc('close')
                    wait(lambda s:not s['dirty']);self.assertEqual(note.read_text(),'Autosaved after close')
                    ipc('reopen');time.sleep(.15);ipc('edit','Keep this unsaved buffer');note.write_text('Changed externally')
                    state=wait(lambda s:s['conflict']);self.assertEqual(state['content'],'Keep this unsaved buffer')
                    self.assertEqual(note.read_text(),'Changed externally')
                    self.assertEqual(note.stat().st_mode & 0o777,0o600)
                finally: process.terminate();process.wait(timeout=5)
