"""Gowall supervision survives abrupt backend destruction by Quickshell."""
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
import unittest

from test_backend import Fixture, backend


class ManagedSupervisionCase(Fixture, unittest.TestCase):
    def wait_for(self, predicate, timeout=3):
        deadline = time.monotonic()+timeout
        while time.monotonic()<deadline:
            if predicate(): return
            time.sleep(.01)
        self.fail('Timed out waiting for managed command')

    @staticmethod
    def running(pid):
        try: return (Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()[0] != 'Z'
        except FileNotFoundError: return False

    def tool(self):
        binary=self.root/'bin/gowall';binary.parent.mkdir()
        binary.write_text('#!'+sys.executable+'\n'+'''
import os, signal, subprocess, sys, time
from pathlib import Path
level = int(sys.argv[1]) if sys.argv[1].isdigit() else 0
signal.signal(signal.SIGTERM, signal.SIG_IGN)
with open(os.environ['LME_TEST_GOWALL_PIDS'], 'a') as stream:
    stream.write(str(os.getpid())+'\\n'); stream.flush()
if level < 2: subprocess.Popen([sys.executable, __file__, str(level+1)])
else: Path(os.environ['LME_TEST_GOWALL_READY']).touch()
while True: time.sleep(.05)
''');binary.chmod(0o700)
        env={**os.environ,'PATH':str(binary.parent)+os.pathsep+os.environ.get('PATH',''),
             'XDG_CONFIG_HOME':str(self.root/'config'),'XDG_CACHE_HOME':str(self.root/'cache'),
             'XDG_STATE_HOME':str(self.root/'state'),'XDG_RUNTIME_DIR':str(self.root/'runtime'),
             'LME_TEST_GOWALL_PIDS':str(self.root/'pids'),'LME_TEST_GOWALL_READY':str(self.root/'ready')}
        source=self.put('source.png','fixture')
        return env,dict(action='gowallGenerate',operation='upscale',paths=[str(source)],options={})

    def test_sigkill_backend_stops_stubborn_gowall_and_upscaler_group(self):
        env,request=self.tool()
        process=subprocess.Popen([sys.executable,str(Path(backend.__file__)),'--settings'],
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        def cleanup():
            if process.poll() is None:process.kill();process.wait(timeout=3)
            for stream in (process.stdin,process.stdout,process.stderr):stream.close()
        self.addCleanup(cleanup)
        self.assertIn('preferences',json.loads(process.stdout.readline()))
        process.stdin.write(json.dumps(request)+'\n');process.stdin.flush()
        self.assertTrue(json.loads(process.stdout.readline())['lastResult']['pending'])
        self.wait_for((self.root/'ready').exists)
        pids=[int(pid) for pid in (self.root/'pids').read_text().splitlines()]
        self.assertEqual(len(pids),3)
        supervisor=os.getpgid(pids[0]);self.assertNotIn(supervisor,pids)
        process.kill();process.wait(timeout=2)
        self.wait_for(lambda:not any(self.running(pid) for pid in [supervisor,*pids]))
        self.assertEqual(process.returncode,-signal.SIGKILL)

    def test_normal_output_input_exit_status_and_stale_parent_race(self):
        runner=backend.CommandRunner();runner.commands['gowall']=sys.executable
        self.addCleanup(runner.close)
        self.assertEqual(runner.run('gowall','-c','import sys; print(sys.stdin.read())',input='image path'), 'image path')
        with self.assertRaisesRegex(backend.CommandError,'failed \\(7\\): Failed: \\[redacted\\]'):
            runner.run('gowall','-c','import sys; sys.stderr.write("Failed: "+sys.stdin.read()); sys.exit(7)',input='private')
        marker=self.root/'must-not-start'
        helper=Path(backend.__file__).with_name('managed_command.py')
        result=subprocess.run([sys.executable,str(helper),'--parent',str(os.getpid()+100000000),'--',sys.executable,
                               '-c','from pathlib import Path; Path('+repr(str(marker))+').touch()'],
                              start_new_session=True,capture_output=True,text=True,timeout=3)
        self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(marker.exists())

    @unittest.skipUnless(shutil.which('quickshell'),'Quickshell is required for process destruction checks')
    def test_quickshell_quit_stops_owned_gowall_tree(self):
        env,request=self.tool();env.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
        Path(env['XDG_RUNTIME_DIR']).mkdir(mode=0o700)
        qs=shutil.which('quickshell');entry=self.root/'shell.qml'
        command=json.dumps([sys.executable,str(Path(backend.__file__)),'--settings'])
        entry.write_text('''import QtQuick
import Quickshell
import Quickshell.Io
ShellRoot {
    property bool sent: false
    Process {
        id: backend
        running: true; stdinEnabled: true
        command: '''+command+'''
        stdout: SplitParser {
            onRead: function(line) {
                if (!sent) { sent = true; backend.write('''+json.dumps(json.dumps(request)+'\n')+'''); }
            }
        }
    }
}
''')
        with (self.root/'qs.log').open('w+') as log:
            shell=subprocess.Popen([qs,'-p',str(entry)],env=env,stdout=log,stderr=log)
            try:
                self.wait_for((self.root/'ready').exists,timeout=6)
                pids=[int(pid) for pid in (self.root/'pids').read_text().splitlines()]
                self.assertEqual(len(pids),3)
                supervisor=os.getpgid(pids[0])
                result=subprocess.run([qs,'-p',str(entry),'kill'],env=env,capture_output=True,text=True,timeout=4)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                shell.wait(timeout=4)
                self.wait_for(lambda:not any(self.running(pid) for pid in [supervisor,*pids]))
            finally:
                if shell.poll() is None:shell.terminate();shell.wait(timeout=4)


if __name__=='__main__':unittest.main()
