"""Exercise image utility widgets against a real JSON backend and a local CLI fixture."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import test_local_qml as qml_tests

@unittest.skipUnless(shutil.which('quickshell'),'Quickshell is required')
class UtilitiesQmlCase(unittest.TestCase):
    run_qml=qml_tests.LocalQmlCase.run_qml

    def test_themes_generate_preview_and_saved_awww_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);binary=root/'gowall'
            binary.write_text('''#!/usr/bin/env python3
import sys,shutil
args=sys.argv[1:]
if args==['list']: print('dracula\\nnord')
else: shutil.copyfile(args[1],args[args.index('--output')+1])
''');binary.chmod(0o700)
            image=Path(__file__).resolve().parents[1]/'assets/wallpapers/liquid-dracula.png'
            import json
            result=self.run_qml('import QtTest\nimport "qml/settings"\nimport "qml/services"', '''
    FloatingWindow { implicitWidth:1000;implicitHeight:900
        GowallSettings { id:studio;width:700 }
        AwwwSettings { id:engine;visible:false;width:700 }
        TestCase { id:probe;when:false }
    }
    property int phase:0
    property var checks:({})
    Timer { interval:80;repeat:true;running:true;onTriggered: {
        if(!ShellState.backendReady || Object.keys(ShellState.pendingActions).length) return;
        if(fixture.phase===0) { probe.findChild(studio,"gowallLoadThemes").clicked();fixture.phase++; }
        else if(fixture.phase===1 && studio.themes.length===2) {
            fixture.checks.themes=studio.themes.includes("nord");studio.paths=[INPUT];studio.generate();fixture.phase++;
        } else if(fixture.phase===2 && studio.preview.url) {
            fixture.checks.preview=studio.result.images.length===1 && studio.preview.path.endsWith(".png");
            probe.findChild(engine,"wallpaperTransitionFps").value=120;
            probe.findChild(engine,"wallpaperTransitionFps").moved();fixture.phase++;
        } else if(fixture.phase===3 && ShellState.preferences.wallpaperTransitionFps===120) {
            fixture.checks.saved=true;fixture.checks.registry=SettingsRegistry.page("utilities").key==="utilities";
            fixture.finish(fixture.checks);
        }
    }}
'''.replace('INPUT',json.dumps(str(image))),{'PATH':str(root)+os.pathsep+os.environ['PATH'],'LME_SHELL_DEMO':'0','LME_SHELL_SETTINGS':'1','XDG_CACHE_HOME':str(root/'cache')})
            self.assertEqual(result,dict(themes=True,preview=True,saved=True,registry=True))
