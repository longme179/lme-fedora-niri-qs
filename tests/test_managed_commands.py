"""Owned tool invocations stop on shutdown without canceling detached user jobs."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

from test_backend import Fixture, backend
from launchpad import Launchpad


class ManagedCommandsCase(Fixture, unittest.TestCase):
    def wait_for(self, predicate, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.01)
        self.fail('Timed out waiting for the command fixture')

    def test_close_cancels_running_tool_and_rejects_a_following_command(self):
        runner = backend.CommandRunner()
        runner.commands['gowall'] = sys.executable
        marker = self.root/'started'
        errors = []
        def run():
            try:
                runner.run('gowall', '-c', 'from pathlib import Path; import time; Path('+repr(str(marker))+').touch(); time.sleep(30)', timeout=600)
            except backend.CommandError as error: errors.append(str(error))
        worker = threading.Thread(target=run)
        worker.start()
        self.addCleanup(lambda: (runner.close(), worker.join(timeout=3)))
        self.wait_for(marker.exists)
        started = time.monotonic()
        runner.close(); worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertLess(time.monotonic()-started, 2)
        self.assertEqual(len(errors), 1)
        self.assertIn('canceled', errors[0])
        with patch.object(backend.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(backend.CommandError, 'closing'): runner.run('gowall', '-c', 'pass')
            launch.assert_not_called()
        runner.close()

    def test_timeout_kills_stubborn_command_and_wl_copy_does_not_capture_pipes(self):
        runner = backend.CommandRunner()
        runner.commands['gowall'] = sys.executable
        marker = self.root/'group.json'
        script = 'import json,os,signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); open('+repr(str(marker))+',"w").write(json.dumps([os.getpid()])); time.sleep(30)'
        with self.assertRaisesRegex(backend.CommandError, 'timed out'):
            runner.run('gowall', '-c', script, timeout=.3)
        pids = json.loads(marker.read_text())
        for pid in pids:
            stat = Path('/proc')/str(pid)/'stat'
            self.assertTrue(not stat.exists() or stat.read_text().rsplit(')', 1)[1].split()[0] == 'Z', f'Process {pid} is still running')
        runner.commands['wl-copy'] = sys.executable
        with patch.object(backend.subprocess, 'Popen', wraps=subprocess.Popen) as launch:
            self.assertEqual(runner.run('wl-copy', '-c', 'print("clipboard owner")', input='private'), '')
            self.assertEqual(launch.call_args.kwargs['stdout'], subprocess.DEVNULL)
            self.assertEqual(launch.call_args.kwargs['stderr'], subprocess.DEVNULL)

    def test_large_stdin_survives_slow_reader_and_output_retries(self):
        runner = backend.CommandRunner()
        runner.commands['nmcli'] = sys.executable
        self.addCleanup(runner.close)
        payload = 'sample-input 🌙 ' * 30000
        script = 'import sys,time; time.sleep(.25); data=sys.stdin.read(); time.sleep(.25); print(len(data))'
        self.assertEqual(runner.run('nmcli', '-c', script, input=payload, timeout=3), str(len(payload)))
        self.assertEqual(runner.run('nmcli', '-c', 'import sys; print(len(sys.stdin.read()))', input=''), '0')

    def test_close_does_not_terminate_detached_launchpad_job(self):
        runner = backend.CommandRunner()
        launchpad = Launchpad()
        entry = dict(name='User job', kind='command', terminal=False, cwd='',
                     command=shlex.join([sys.executable, '-c', 'import time; time.sleep(30)']))
        with patch.dict(os.environ, XDG_STATE_HOME=str(self.root/'state')):
            launchpad.run('user-job', {'user-job':entry}, 'kitty')
        child = launchpad.jobs['user-job']['process']
        self.addCleanup(lambda: (child.terminate(), child.wait(timeout=3)))
        runner.close()
        self.assertIsNone(child.poll())

    def test_settings_sigterm_stops_gowall_and_its_child_tree_without_publishing_late_results(self):
        binary = self.root/'bin/gowall'
        binary.parent.mkdir()
        pids = self.root/'pids'
        ready = self.root/'ready'
        binary.write_text('#!'+sys.executable+'\n'+'''
import os, signal, subprocess, sys, time
from pathlib import Path
level = int(sys.argv[1]) if sys.argv[1].isdigit() else 0
child = None
def stop(*_):
    if child is not None: child.wait(timeout=1)
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
with open(os.environ['LME_TEST_GOWALL_PIDS'], 'a') as stream:
    stream.write(str(os.getpid())+'\\n'); stream.flush()
if level < 2: child = subprocess.Popen([sys.executable, __file__, str(level+1)])
else: Path(os.environ['LME_TEST_GOWALL_READY']).touch()
while True: time.sleep(.05)
''')
        binary.chmod(0o700)
        source = self.put('source.png', 'source fixture')
        env = dict(os.environ, PATH=str(binary.parent)+os.pathsep+os.environ.get('PATH',''),
                   XDG_CONFIG_HOME=str(self.root/'config'), XDG_CACHE_HOME=str(self.root/'cache'),
                   XDG_STATE_HOME=str(self.root/'state'), XDG_RUNTIME_DIR=str(self.root/'runtime'),
                   LME_TEST_GOWALL_PIDS=str(pids), LME_TEST_GOWALL_READY=str(ready))
        process = subprocess.Popen([sys.executable, str(Path(backend.__file__)), '--settings'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        def cleanup():
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)
            for stream in (process.stdin, process.stdout, process.stderr): stream.close()
        self.addCleanup(cleanup)
        self.assertIn('preferences', json.loads(process.stdout.readline()))
        process.stdin.write(json.dumps(dict(action='gowallGenerate', operation='upscale', paths=[str(source)], options={}))+'\n')
        process.stdin.flush()
        pending = json.loads(process.stdout.readline())
        self.assertTrue(pending['lastResult']['pending'])
        self.wait_for(ready.exists)
        owned = [int(pid) for pid in pids.read_text().splitlines()]
        self.assertEqual(len(owned), 3)
        started = time.monotonic(); process.terminate()
        stdout, stderr = process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertLess(time.monotonic()-started, 3)
        self.assertFalse(any((Path('/proc')/str(pid)).exists() for pid in owned), 'Gowall descendants were not reaped')
        for line in stdout.splitlines(): self.assertTrue(json.loads(line)['lastResult'].get('pending', False))
        self.assertFalse(list((self.root/'cache/lme-shell/gowall').glob('job-*')))


if __name__ == '__main__': unittest.main()
