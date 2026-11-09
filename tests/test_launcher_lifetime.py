"""Desktop apps must not inherit a bounded control command's lifetime.
Contract: test_launcher_lifetime.py covers launcher_lifetime behavior/contracts; check imports for fixtures/helpers under test.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch

from test_backend import Fixture, FakeRunner, backend


class LauncherLifetimeCase(Fixture, unittest.TestCase):
    def live(self, runner):
        live = self.make_backend(runner)
        self.addCleanup(live.feature_executor.shutdown)
        self.addCleanup(live.charge_executor.shutdown)
        self.addCleanup(live.weather.close)
        live.applications.entries = {'browser.desktop': dict(name='Browser', terminal=False,
            path='/known/Browser entry.desktop', argv=['browser', 'literal argument'])}
        return live

    def test_gio_launch_uses_detached_spawn_and_only_the_known_desktop_path(self):
        runner = FakeRunner(available={'gio'})
        live = self.live(runner)
        runner.run = Mock(side_effect=AssertionError('Desktop app used managed output capture'))
        result = live.handle(dict(action='launch', id='browser.desktop', path='/untrusted/entry.desktop'))
        self.assertTrue(result['ok'], result)
        self.assertEqual(runner.spawns, [['/usr/bin/gio', 'launch', '/known/Browser entry.desktop']])
        runner.run.assert_not_called()

    def test_spawn_failure_reports_error_without_recording_usage_or_falling_back(self):
        runner = FakeRunner(available={'gio'})
        live = self.live(runner)
        live.preferences.values['launcherRanking'] = True
        live.launcher_history.record = Mock()
        runner.spawn = Mock(side_effect=backend.CommandError('Unable to launch gio: denied'))
        result = live.handle(dict(action='launch', id='browser.desktop'))
        self.assertFalse(result['ok'])
        self.assertEqual(result['message'], 'Unable to launch gio: denied')
        self.assertEqual(runner.spawn.call_count, 1)
        self.assertFalse(runner.calls)
        live.launcher_history.record.assert_not_called()


@unittest.skipUnless(os.environ.get('LME_TEST_GIO_LAUNCH') == '1', 'opt-in private D-Bus desktop app lifetime')
@unittest.skipUnless(shutil.which('gio'), 'gio is unavailable')
class NativeGioLifetimeCase(Fixture, unittest.TestCase):
    live = LauncherLifetimeCase.live

    def test_real_app_survives_the_control_deadline_and_backend_runner_shutdown(self):
        script, report = self.root/'dummy app.py', self.root/'app.json'
        script.write_text('import json,os,sys,time\nfrom pathlib import Path\n'
            'Path(sys.argv[1]).write_text(json.dumps(dict(pid=os.getpid(),args=sys.argv[2:])) )\n'
            'print("Application owns inherited stdout",flush=True)\ntime.sleep(15)\n')
        desktop = self.root/'Browser entry.desktop'
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Lifetime probe\nExec='
            +sys.executable+' "'+str(script)+'" "'+str(report)+'" "literal argument"\n')
        env = {}
        for key in ('CONFIG', 'STATE', 'CACHE', 'DATA', 'RUNTIME'):
            path = self.root/key.lower(); path.mkdir(mode=0o700)
            env['XDG_'+('RUNTIME_DIR' if key == 'RUNTIME' else key+'_HOME')] = str(path)
        env['DBUS_SYSTEM_BUS_ADDRESS'] = 'unix:path='+str(self.root/'no-system-bus')
        children = []
        original = subprocess.Popen
        def start(*args, **kwargs):
            child = original(*args, **kwargs); children.append(child); return child
        def cleanup():
            if report.exists():
                pid = json.loads(report.read_text())['pid']
                try:
                    if str(script).encode() in Path(f'/proc/{pid}/cmdline').read_bytes():
                        os.kill(pid, signal.SIGTERM)
                except ProcessLookupError: pass
                except FileNotFoundError: pass
            for child in children:
                if child.poll() is None: child.terminate()
                child.wait(timeout=3)
        self.addCleanup(cleanup)
        with patch.dict(os.environ, env):
            runner = backend.CommandRunner(); self.addCleanup(runner.close)
            live = self.live(runner)
            live.applications.entries['browser.desktop'].update(path=str(desktop),
                argv=[sys.executable, str(script), str(report), 'literal argument'])
            with patch('command_runner.subprocess.Popen', side_effect=start):
                result = live.handle(dict(action='launch', id='browser.desktop'))
            self.assertTrue(result['ok'], result)
            deadline = time.monotonic()+3
            while not report.exists() and time.monotonic() < deadline: time.sleep(.02)
            self.assertTrue(report.exists(), 'The desktop application never started')
            runner.close()
            # Exceed the previous three-second control timeout without a timeout override.
            time.sleep(3.2)
            data = json.loads(report.read_text())
            self.assertEqual(data['args'], ['literal argument'])
            state = Path(f"/proc/{data['pid']}/stat").read_text().rsplit(')', 1)[1].split()[0]
            self.assertNotEqual(state, 'Z', 'The shell killed its launched application')
            self.assertFalse(runner.pending)
