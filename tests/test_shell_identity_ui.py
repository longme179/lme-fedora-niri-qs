"""Real Settings rename, persistence and stable window identity."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from test_backend import backend


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'opt-in private Wayland Settings checks')
class ShellIdentityCase(unittest.TestCase):
    def test_rename_from_settings_survives_restart_and_keeps_focus_routing(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryFile(mode='w+') as log:
            root = Path(temporary)
            shutil.copytree(repo/'scripts', root/'scripts')
            for name in ('qml', 'config', 'assets'): (root/name).symlink_to(repo/name, target_is_directory=True)
            source = (repo/'qml/settings/SettingsApplication.qml').read_text().replace('"../services"', '"qml/services"')
            source = source.replace('"../components"', '"qml/components"')
            source = 'import "qml/settings"\n' + source
            source = source.replace('    id: root\n', '''    id: root
    Component.onCompleted: Quickshell.watchFiles = false
    function find(item, name) { if (!item) return null; if (item.objectName === name) return item; for (const child of item.children || []) { const result=find(child,name); if(result) return result; } return null; }
    IpcHandler {
        target: "identityFixture"
        function state(): string {
            const heading=root.find(view,"shellNameHeading"), about=root.find(view,"aboutShellName");
            return JSON.stringify({ready:ShellState.backendReady,name:ShellState.shellName,title:window.title,
                appId:Quickshell.appId,heading:heading?.text,headingLines:heading?.lineCount,truncated:heading?.truncated,
                fallback:ShellState.focusedTitle,sender:Notifications.history[0]?.appName,about:about?.title,
                input:!!root.find(view,"shellNameInput")});
        }
        function enterName(name: string): void { const input=root.find(view,"shellNameInput"); input.text=name; input.accepted(); }
        function reset(): void { root.find(view,"shellNameReset").clicked(); }
        function notify(): void { Notifications.local("Identity preview", "A notification from your shell"); }
    }
''', 1)
            pragmas = (repo/'settings.qml').read_text().split('import "qml/settings"')[0]
            entry=root/'settings.qml';entry.write_text(pragmas+source)
            config=root/'home'; preferences=config/'lme-shell/settings.json'
            binaries=root/'bin';binaries.mkdir(); marker=root/'focused.json'
            niri=binaries/'niri'
            niri.write_text('''#!/usr/bin/python3
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
if args==['--version']: print('niri 26.04')
elif args==['msg','--json','windows']: print(json.dumps([{'id':27,'app_id':'lme-shell-settings','title':"Nebula & Mây's Desktop Settings"}]))
elif args[:3]==['msg','action','focus-window']: Path(os.environ['LME_FOCUS_MARKER']).write_text(json.dumps(args))
else: print('[]')
''');niri.chmod(0o700)
            env=dict(os.environ, XDG_CONFIG_HOME=str(config), XDG_STATE_HOME=str(root/'state'), XDG_DATA_HOME=str(root/'data'),
                     LME_SHELL_DEMO='0', LME_SHELL_BACKEND_DEMO='0', LME_SETTINGS_PAGE='appearance',
                     LME_FOCUS_MARKER=str(marker), PATH=str(binaries)+os.pathsep+os.environ['PATH'])
            for key in ('LME_SHELL_PREVIEW','LME_SHELL_ENTRY','LME_QS_BINARY'): env.pop(key,None)
            process=None
            def start(): return subprocess.Popen(['quickshell','-p',str(entry)], env=env, stdout=log, stderr=log)
            def ipc(method,*args): return subprocess.check_output(['quickshell','-p',str(entry),'ipc','call','identityFixture',method,*args],env=env,text=True,timeout=5).strip()
            def wait(predicate):
                deadline=time.monotonic()+12; state={}
                while time.monotonic()<deadline:
                    try: state=json.loads(ipc('state'))
                    except (ValueError,subprocess.CalledProcessError): pass
                    if predicate(state): return state
                    time.sleep(.05)
                log.seek(0);self.fail(str(state)+'\n'+log.read())
            try:
                process=start();state=wait(lambda s:s.get('ready') and s.get('input'))
                self.assertEqual(state['appId'],'lme-shell-settings')
                custom="Nebula & Mây's Desktop"
                ipc('enterName','  '+custom+'  ')
                state=wait(lambda s:s.get('name')==custom and s.get('title')==custom+' Settings' and s.get('heading')==custom+' Settings')
                self.assertEqual(state['fallback'],custom)
                self.assertFalse(state['truncated'])
                self.assertEqual(json.loads(preferences.read_text())['shellName'],custom)
                ipc('notify');wait(lambda s:s.get('sender')==custom)
                subprocess.run(['bash',str(root/'scripts/settings.sh'),'--page','about'],env=env,check=True,capture_output=True,timeout=8)
                wait(lambda s:s.get('about')==custom)
                self.assertEqual(json.loads(marker.read_text()),['msg','action','focus-window','--id','27'])
                first_pid=process.pid
                process.terminate();process.wait(timeout=5)
                process=start();state=wait(lambda s:s.get('ready') and s.get('input') and s.get('name')==custom)
                self.assertNotEqual(process.pid,first_pid)
                self.assertEqual(state['title'],custom+' Settings')
                # A second client updates the same file while Settings is open.
                long_name='Orion '+'Desktop'*6
                backend.Preferences(preferences).set('shellName',long_name)
                state=wait(lambda s:s.get('name')==long_name and s.get('heading')==long_name+' Settings')
                self.assertEqual(state['appId'],'lme-shell-settings')
                self.assertGreater(state['headingLines'],1)
                self.assertFalse(state['truncated'])
                ipc('reset');wait(lambda s:s.get('name')=='LME Shell' and s.get('title')=='LME Shell Settings')
                self.assertEqual(json.loads(preferences.read_text())['shellName'],'LME Shell')
                log.seek(0);output=log.read()
                for problem in ('TypeError','ReferenceError','Binding loop','Unable to assign','Failed to load configuration'): self.assertNotIn(problem,output)
            finally:
                if process and process.poll() is None: process.terminate();process.wait(timeout=5)
