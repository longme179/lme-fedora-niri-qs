"""Launchpad persistence and real subprocess dispatch without a desktop session."""
import os
import sys
import time
import unittest
from unittest.mock import patch
from test_backend import Fixture, backend
from launchpad import Launchpad, entries
from settings_transfer import document

class LaunchpadCase(Fixture,unittest.TestCase):
    def entry(self,command='printf hello',**changes):
        return dict(name='A task',command=command,kind='command',terminal=False,cwd='',**changes)

    def test_token_updates_rename_delete_and_portability(self):
        self.preferences.set('launchpadEntries',self.entry(),token='one')
        other=backend.Preferences(self.preferences.path)
        other.set('launchpadEntries',self.entry('true'),token='two')
        self.preferences.set('launchpadEntries',{**self.entry(),'name':'Renamed'},token='one')
        self.assertEqual(set(self.preferences.values['launchpadEntries']),{'one','two'})
        self.assertEqual(self.preferences.values['launchpadEntries']['one']['name'],'Renamed')
        self.assertNotIn('launchpadEntries',document(self.preferences.values,'preset')['settings'])
        self.assertIn('launchpadEntries',document(self.preferences.values,'backup')['settings'])
        self.preferences.set('launchpadEntries',None,token='one')
        self.assertEqual(set(backend.Preferences(self.preferences.path).values['launchpadEntries']),{'two'})
        with self.assertRaises(ValueError): entries({str(i):self.entry('a'*16000) for i in range(20)})

    def test_invalid_entries_do_not_replace_saved_commands(self):
        for value in ([],{'bad/id':self.entry()}, {'a':self.entry('"bad')},{'a':{**self.entry(),'kind':'python'}},{'a':{**self.entry(),'cwd':'relative'}},{'a':{**self.entry(),'terminal':1}}):
            with self.subTest(value=value),self.assertRaises(ValueError): entries(value)

    def test_background_arguments_are_literal_and_bash_is_explicit(self):
        tool=Launchpad()
        work=self.root/'work space';work.mkdir()
        output=work/'argument.txt'
        import shlex
        command=shlex.join([sys.executable,'-c','import pathlib,sys;pathlib.Path("argument.txt").write_text(sys.argv[1])','$(touch PWNED); hello'])
        with patch.dict(os.environ,XDG_STATE_HOME=str(self.root/'state')):
            tool.run('one',{'one':{**self.entry(command),'cwd':str(work)}},'missing')
            deadline=time.monotonic()+3
            while tool.snapshot()['one']['running'] and time.monotonic()<deadline: time.sleep(.02)
            self.assertEqual(tool.snapshot()['one']['exitCode'],0)
            self.assertEqual(output.read_text(),'$(touch PWNED); hello')
            self.assertFalse((work/'PWNED').exists())
            tool.run('two',{'two':{**self.entry('printf from-bash; exit 7'),'kind':'bash'}},'missing')
            while tool.snapshot()['two']['running'] and time.monotonic()<deadline: time.sleep(.02)
            job=tool.snapshot()['two'];self.assertEqual(job['exitCode'],7)
            from pathlib import Path
            self.assertEqual(Path(job['log']).read_text(),'from-bash')
            script=work/'relative-script';script.write_text('#!/bin/sh\nprintf relative');script.chmod(0o700)
            tool.run('relative',{'relative':{**self.entry('./relative-script'),'cwd':str(work)}},'missing')
            while tool.snapshot()['relative']['running'] and time.monotonic()<deadline: time.sleep(.02)
            self.assertEqual(Path(tool.snapshot()['relative']['log']).read_text(),'relative')

    def test_terminal_wrapper_cwd_missing_tools_and_duplicate_run(self):
        from unittest.mock import Mock
        tool=Launchpad();process=Mock();process.poll.return_value=None
        item={**self.entry('/bin/echo "a b"'),'terminal':True,'cwd':str(self.root)}
        with patch.dict(os.environ,XDG_STATE_HOME=str(self.root/'state')),patch('launchpad.shutil.which',side_effect=lambda name:'/usr/bin/kitty' if name=='kitty' else name),patch('launchpad.subprocess.Popen',return_value=process) as launch:
            tool.run('a',{'a':item},'kitty')
            args,kwargs=launch.call_args
            self.assertEqual(args[0][-2:],['/bin/echo','a b'])
            self.assertEqual(kwargs['cwd'],self.root)
            self.assertEqual(args[0][:2],['/usr/bin/kitty','-e'])
            with self.assertRaisesRegex(ValueError,'already running'): tool.run('a',{'a':item},'kitty')
        with self.assertRaisesRegex(ValueError,'unavailable'): tool.run('missing',{'missing':self.entry('lme-no-such-program')},'kitty')

    def test_backend_disabled_and_demo_never_execute(self):
        live=self.make_backend();self.preferences.set('launchpadEnabled',False)
        self.assertFalse(live.handle(dict(action='launchpadRun',id='a'))['ok'])
        demo=backend.DesktopBackend(demo=True,preferences=self.preferences)
        with patch('launchpad.subprocess.Popen') as launch:
            self.assertTrue(demo.handle(dict(action='launchpadRun',id='a'))['ok'])
            launch.assert_not_called()

import shutil
import test_local_qml as qml_tests

@unittest.skipUnless(shutil.which('quickshell'),'Quickshell is required')
class LaunchpadQmlCase(unittest.TestCase):
    run_qml=qml_tests.LocalQmlCase.run_qml

    def test_editor_launcher_search_and_popup_lifecycle(self):
        result=self.run_qml('import QtTest\nimport "qml/panels"\nimport "qml/services"', '''
    FloatingWindow { implicitWidth:900;implicitHeight:900
        LaunchpadEditor { id:editor;width:700 }
        Launcher { id:launcher;visible:false;width:700;height:650 }
        TestCase { id:probe;when:false }
    }
    property int phase:0
    property var checks:({})
    Timer { interval:80;repeat:true;running:true;onTriggered: {
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) {
            editor.edit("");probe.findChild(editor,"launchpadName").text="Nightly report";
            probe.findChild(editor,"launchpadCommand").text="printf 'hello world'";
            editor.save();fixture.phase++;
        } else if(fixture.phase===1 && Object.keys(editor.entries).length===1) {
            launcher.query="night report";
            fixture.checks.search=launcher.results.some(item=>item.kind==="launchpad" && item.name==="Nightly report");
            const id=Object.keys(editor.entries)[0];editor.edit(id);probe.findChild(editor,"launchpadName").text="Renamed report";
            editor.save();fixture.phase++;
        } else if(fixture.phase===2 && !editor.saving) {
            const id=Object.keys(editor.entries)[0];fixture.checks.rename=editor.entries[id].name==="Renamed report";
            ShellState.togglePanel("launchpad");fixture.checks.open=ShellState.launchpadOpen && ShellState.panelOpen;
            ShellState.togglePanel("launcher");fixture.checks.exclusive=!ShellState.launchpadOpen && ShellState.launcherOpen;
            ShellState.closePanels();fixture.checks.closed=!ShellState.panelOpen;
            ShellState.run("setting",{key:"launchpadEntries",token:id,value:null});fixture.phase++;
        } else if(fixture.phase===3 && !Object.keys(editor.entries).length) { fixture.checks.deleted=true;fixture.finish(fixture.checks); }
    }}
''')
        self.assertEqual(result,dict(search=True,rename=True,open=True,exclusive=True,closed=True,deleted=True))
