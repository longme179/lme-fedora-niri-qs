"""Authentication failures and optional real Wayland dialog interaction checks."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from test_backend import FakeRunner, Fixture, backend
from test_features import ManualExecutor


class AuthenticationBackendCase(Fixture, unittest.TestCase):
    def test_rejection_clears_pending_charge_and_keeps_actual_threshold(self):
        self.put('sys/class/power_supply/BAT0/type', 'Battery')
        threshold = self.put('sys/class/power_supply/BAT0/charge_control_end_threshold', '100')
        command = ('pkexec', '--disable-internal-agent', '/usr/bin/python3', '-I', '/usr/local/libexec/lme-shell-charge', '85')
        runner = FakeRunner({command: backend.CommandError('Not authorized; authentication cancelled')}, available={'pkexec'})
        live = self.make_backend(runner)
        live.charge_executor = ManualExecutor()
        with patch.object(backend.os, 'access', return_value=False), patch.object(backend, 'trusted_helper', return_value=True):
            self.assertTrue(live.handle({'action': 'chargeMode', 'value': 85})['pending'])
            live.snapshot()  # Emit acknowledgement before worker completion.
            live.charge_executor.complete()
            state = live.snapshot()
        self.assertFalse(state['lastResult']['ok'])
        self.assertIn('authentication cancelled', state['lastResult']['message'])
        self.assertFalse(state['system']['charging']['busy'])
        self.assertEqual(state['system']['charging']['mode'], 'max')
        self.assertEqual(threshold.read_text(), '100')
        self.assertEqual(runner.calls, [command])


@unittest.skipUnless(os.environ.get('LME_TEST_AUTHENTICATION_UI') == '1',
                     'Set LME_TEST_AUTHENTICATION_UI=1 inside an isolated Wayland session')
class AuthenticationDialogCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qs = shutil.which('quickshell')
        if not cls.qs or not shutil.which('wtype'):
            raise unittest.SkipTest('Quickshell and wtype are required')
        cls.fixture = Path(__file__).resolve().parents[1] / 'authentication-demo.qml'
        cls.log = tempfile.TemporaryFile(mode='w+')
        cls.process = subprocess.Popen([cls.qs, '-p', str(cls.fixture)], stdout=cls.log, stderr=cls.log)
        try:
            cls.wait_for(lambda state: state['visible'] and state['focused'])
        except Exception:
            cls.process.terminate()
            cls.log.seek(0)
            raise AssertionError(cls.log.read()) from None

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.log.seek(0)
        output = cls.log.read()
        cls.log.close()
        assert 'QML error' not in output and 'ReferenceError' not in output and 'TypeError' not in output, output
        assert 'test-only' not in output and 'incorrect' not in output, output

    @classmethod
    def ipc(cls, method):
        return subprocess.run([cls.qs, '-p', str(cls.fixture), 'ipc', 'call', 'authFixture', method],
                              check=True, capture_output=True, text=True, timeout=4).stdout.strip()

    @classmethod
    def wait_for(cls, predicate):
        end = time.monotonic() + 8
        state = None
        while time.monotonic() < end:
            try:
                state = json.loads(cls.ipc('status'))
                if predicate(state): return state
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(0.1)
        raise AssertionError(f'Authentication fixture did not reach expected state: {state}')

    def setUp(self):
        self.ipc('open')
        self.wait_for(lambda state: state['visible'] and state['focused'] and state['inputEmpty'])

    def type(self, text, key=None):
        command = ['wtype', '-s', '200', '-d', '30', text]
        if key: command += ['-s', '100', '-k', key]
        subprocess.run(command, check=True, timeout=5)

    def test_wrong_response_then_enter_success_with_cleared_input(self):
        self.assertTrue(json.loads(self.ipc('status'))['masked'])
        self.type('incorrect', 'Return')
        state = self.wait_for(lambda value: value['failed'] and value['waiting'] and value['focused'])
        self.assertTrue(state['inputEmpty'])
        self.assertEqual(state['submissions'], 1)
        self.type('test-only', 'Return')
        state = self.wait_for(lambda value: value['succeeded'] and not value['visible'])
        self.assertEqual(state['submissions'], 2)
        self.assertTrue(state['inputEmpty'])

    def test_escape_cancels_without_submitting(self):
        self.type('incorrect', 'Escape')
        state = self.wait_for(lambda value: value['cancelled'] and not value['visible'])
        self.assertEqual(state['submissions'], 0)
        self.assertTrue(state['inputEmpty'])

    def test_identity_change_clears_previous_input_and_refocuses(self):
        self.type('incorrect')
        self.wait_for(lambda value: not value['inputEmpty'])
        self.ipc('selectIdentity')
        state = self.wait_for(lambda value: value['inputEmpty'] and value['focused'])
        self.assertEqual(state['submissions'], 0)

    def test_cancel_button_is_keyboard_reachable(self):
        self.type('incorrect')
        subprocess.run(['wtype', '-s', '200', '-k', 'Tab', '-s', '100', '-k', 'space'], check=True, timeout=5)
        state = self.wait_for(lambda value: value['cancelled'] and not value['visible'])
        self.assertEqual(state['submissions'], 0)
        self.assertTrue(state['inputEmpty'])

    def test_new_conversation_discards_previous_input(self):
        self.type('incorrect')
        self.wait_for(lambda value: not value['inputEmpty'])
        self.ipc('open')
        state = self.wait_for(lambda value: value['inputEmpty'] and value['focused'])
        self.assertEqual(state['submissions'], 0)

    def test_visible_challenge_uses_normal_echo(self):
        self.ipc('visibleResponse')
        self.wait_for(lambda value: not value['masked'])
        self.type('test-only', 'Return')
        self.wait_for(lambda value: value['succeeded'])
