"""Real bridge framing/lifecycle and immediate QML spectrum response."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from test_backend import Fixture


class VisualizerBridgeCase(Fixture, unittest.TestCase):
    def test_reactive_config_streams_attack_silence_and_stops_only_its_child(self):
        child_pid=self.root/'child.pid'
        binary=self.put('bin/cava', '''#!/usr/bin/python3
import configparser,os,sys,time
from pathlib import Path
c=configparser.ConfigParser();c.read(sys.argv[sys.argv.index('-p')+1])
assert c.getint('general','framerate')==60
assert c.getint('general','bars')==16
assert c.getint('general','autosens')==1
assert c.getint('smoothing','noise_reduction')==20
assert c.getint('smoothing','monstercat')==0
assert c.getint('smoothing','waves')==0
Path(os.environ['LME_CAVA_CHILD_PID']).write_text(str(os.getpid()))
for level in (0,95,0):print(';'.join([str(level)]*16)+';',flush=True)
time.sleep(30)
''');binary.chmod(0o755)
        entry=Path(__file__).resolve().parents[1]/'scripts/audio_visualizer.py'
        env={**os.environ,'PATH':str(binary.parent)+os.pathsep+os.environ.get('PATH',''),'LME_CAVA_CHILD_PID':str(child_pid)}
        with tempfile.TemporaryFile(mode='w+') as output:
            process=subprocess.Popen([sys.executable,str(entry)],env=env,stdout=output,stderr=output)
            try:
                end=time.monotonic()+4
                while time.monotonic()<end:
                    output.seek(0);lines=output.read().splitlines()
                    if len(lines)>=3:break
                    time.sleep(.02)
                self.assertEqual([json.loads(line)['bars'][0] for line in lines],[0,.95,0])
                pid=int(child_pid.read_text())
            finally:process.terminate();process.wait(timeout=5)
            with self.assertRaises(ProcessLookupError):os.kill(pid,0)


@unittest.skipUnless(os.environ.get('LME_TEST_MOTION_UI')=='1','opt-in private Wayland spectrum check')
class VisualizerMotionCase(unittest.TestCase):
    def test_attack_and_release_follow_frame_without_a_second_easing_tail(self):
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryFile(mode='w+') as log:
            root=Path(temporary)
            for name in ('qml','scripts','config'):(root/name).symlink_to(repo/name,target_is_directory=True)
            entry=root/'shell.qml';entry.write_text('''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env LME_SHELL_DEMO=1
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/components"
import "qml/services"
import "qml/theme"
ShellRoot {
    FloatingWindow {
        implicitWidth: 500; implicitHeight: 160; color: Theme.background
        AudioVisualizer { id: spectrum; anchors.centerIn: parent; width: 450; height: 40; visible: true }
    }
    IpcHandler {
        target: "spectrumFixture"
        function sample(value: real): string {
            VisualizerState.bars=Array(16).fill(value);
            const bar=spectrum.children[0].children.find(item => item.index === 0);
            return JSON.stringify({height:bar ? bar.height : -1,animations:Theme.animations});
        }
    }
}
''')
            env={**os.environ,'XDG_CONFIG_HOME':str(root/'settings'),'LME_SHELL_DEMO':'1'}
            process=subprocess.Popen(['quickshell','-p',str(entry)],env=env,stdout=log,stderr=log)
            def sample(level):
                result=subprocess.run(['quickshell','-p',str(entry),'ipc','call','spectrumFixture','sample',str(level)],env=env,capture_output=True,text=True,timeout=4)
                return json.loads(result.stdout)
            try:
                end=time.monotonic()+6
                while time.monotonic()<end:
                    try:
                        if sample(0)['height']==2:break
                    except ValueError:pass
                    time.sleep(.05)
                for level,height in ((.9,36),(.2,8),(0,2)):
                    state=sample(level);self.assertTrue(state['animations']);self.assertAlmostEqual(state['height'],height,places=4)
                log.seek(0);output=log.read()
                for error in ('ReferenceError','TypeError','binding loop','Failed to load configuration'):self.assertNotIn(error,output)
            finally:process.terminate();process.wait(timeout=5)
