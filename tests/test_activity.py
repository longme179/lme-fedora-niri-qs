"""Recording detection and optional real MPRIS/QML controls in private Wayland."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from test_backend import Fixture


class RecordingCase(Fixture, unittest.TestCase):
    def recorder(self, name='wf-recorder', state='S'):
        self.put('proc/uptime', '200 100')
        self.put('proc/123/stat', '123 (recorder name) ' + ' '.join([state] + ['0'] * 18 + [str(100 * os.sysconf('SC_CLK_TCK'))]))
        (self.root / 'proc/123/exe').symlink_to('/usr/bin/' + name)
        return self.make_backend()

    def test_supported_recorders_report_elapsed_without_controlling_process(self):
        live = self.recorder('gpu-screen-recorder')
        self.assertEqual(live.recording(), {'active': True, 'name': 'GPU Screen Recorder', 'elapsed': 100})

    def test_missing_exited_and_unrelated_processes_are_inactive(self):
        live = self.recorder('wf-recorder', 'Z')
        self.assertEqual(live.recording(), {'active': False})
        self.assertEqual(self.make_backend().recording(), {'active': False})
        (self.root / 'proc/123/exe').unlink()
        (self.root / 'proc/123/exe').symlink_to('/usr/bin/firefox')
        self.assertEqual(live.recording(), {'active': False})

    def test_other_users_processes_are_ignored(self):
        live = self.recorder()
        with patch('desktop_backend.os.getuid', return_value=os.getuid() + 1):
            self.assertEqual(live.recording(), {'active': False})


@unittest.skipUnless(os.environ.get('LME_TEST_ACTIVITY_UI') == '1', 'Enable only in a private Wayland session')
class ActivityInterfaceCase(unittest.TestCase):
    def test_media_timer_stopwatch_close_reopen_and_motion(self):
        pointer = os.environ.get('LME_TEST_POINTER')
        if not pointer: raise unittest.SkipTest('Set LME_TEST_POINTER to a virtual-pointer click tool')
        python = os.environ.get('LME_TEST_GI_PYTHON', '/usr/bin/python3')
        if subprocess.run([python, '-c', 'import gi'], capture_output=True).returncode: raise unittest.SkipTest('Test fixture needs PyGObject')
        repo = Path(__file__).resolve().parents[1]
        fixture = repo / 'native-features-demo.qml'
        with tempfile.TemporaryFile(mode='w+') as log:
            player = subprocess.Popen([python, str(repo / 'tests/mpris_fixture.py')], stdout=log, stderr=log)
            env = dict(os.environ, LME_SHELL_DEMO='0', LME_SHELL_BACKEND_DEMO='1', LME_TEST_FEATURES='1', LME_TEST_CLIPBOARD_UI='0')
            shell = subprocess.Popen(['quickshell', '-p', str(fixture)], env=env, stdout=log, stderr=log)
            def ipc(method, *args):
                reply = subprocess.run(['quickshell', '-p', str(fixture), 'ipc', 'call', 'featuresFixture', method, *args], env=env, capture_output=True, text=True, timeout=4)
                return reply.stdout.strip()
            def wait(predicate):
                end = time.monotonic() + 10
                while time.monotonic() < end:
                    try: state = json.loads(ipc('activityStatus'))
                    except ValueError: state = {}
                    if predicate(state): return state
                    time.sleep(.1)
                log.seek(0)
                raise AssertionError('Activity UI did not reach expected state: ' + log.read())
            def click(name):
                point = json.loads(ipc('buttonPosition', name))
                subprocess.run([pointer, str(point['x']), str(point['y'])], check=True, timeout=4)
            try:
                wait(lambda s: s.get('players') == 1 and s.get('expansion') == 1)
                click('activityPlay'); wait(lambda s: s.get('playing') is False)
                click('activityNext'); wait(lambda s: s.get('title') == 'Next track')
                click('activityPrevious'); wait(lambda s: s.get('title') == 'Previous track')
                click('activityPlay'); wait(lambda s: s.get('playing') is True)
                click('activityTimer'); wait(lambda s: s.get('timerRunning') and s.get('kind') == 'timer' and s.get('remaining', 1500) < 1500)
                click('activityTimer'); state = wait(lambda s: s.get('timerRunning') is False)
                paused = state['remaining']; time.sleep(.5)
                self.assertEqual(json.loads(ipc('activityStatus'))['remaining'], paused)
                click('activityTimerReset'); wait(lambda s: s.get('remaining') == 1500 and s.get('kind') == 'media')
                click('activityStopwatch'); wait(lambda s: s.get('stopwatchRunning') and s.get('elapsed', 0) > 0 and s.get('kind') == 'stopwatch')
                subprocess.run(['wtype', '-s', '200', '-k', 'Escape'], check=True)
                wait(lambda s: s.get('visible') is False and s.get('expansion') == 0)
                ipc('openActivity'); wait(lambda s: s.get('visible') and s.get('expansion') == 1 and s.get('stopwatchRunning'))
                click('activityStopwatchReset'); wait(lambda s: s.get('elapsed') == 0 and not s.get('stopwatchRunning'))
                ipc('timerNearCompletion'); wait(lambda s: s.get('remaining') == 0 and not s.get('timerRunning'))
                ipc('disableMotion'); click('activityClose')
                wait(lambda s: s.get('visible') is False and not s.get('transitioning'))
            finally:
                shell.terminate(); shell.wait(timeout=6); player.terminate(); player.wait(timeout=5)
            log.seek(0)
            for error in ['ReferenceError', 'TypeError', 'QML error', 'Failed to load configuration', 'Unable to assign']:
                self.assertNotIn(error, log.read()); log.seek(0)
