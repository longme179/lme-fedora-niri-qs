"""Authentication feedback uses fake processes, never NetworkManager."""
import importlib.util
import inspect
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock

from command_runner import CommandRunner, CommandError

AUTH = importlib.util.find_spec('wifi_auth') is not None
OBSERVE = 'observe' in inspect.signature(CommandRunner.run).parameters
PROMPT = 'Password (802-11-wireless-security.psk): '
PATH = '/org/freedesktop/NetworkManager/ActiveConnection/12'


class RunnerOutputCase(unittest.TestCase):
    def runner(self):
        runner = CommandRunner(); self.addCleanup(runner.close)
        runner.commands['nmcli'] = sys.executable
        return runner

    def test_baseline_without_observer_waits_for_timeout_even_after_repeated_prompts(self):
        runner = self.runner()
        script = 'import time; print('+repr(PROMPT+'\n'+PROMPT)+', flush=True); time.sleep(45)'
        with self.assertRaisesRegex(CommandError, 'nmcli timed out'):
            runner.run('nmcli', '-c', script, timeout=.25, input='fake secret\n')
        self.assertFalse(runner.pending)

    @unittest.skipUnless(OBSERVE, 'output observation is not implemented on baseline')
    def test_observer_exception_reaps_process_and_releases_pending_without_waiting_for_timeout(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary)/'pid'
            script = 'import os,time; from pathlib import Path; Path('+repr(str(marker))+').write_text(str(os.getpid())); print("ready",flush=True); time.sleep(45)'
            def observe(out, err):
                if out and b'ready' in out: raise CommandError('observer stopped')
            started = time.monotonic()
            with self.assertRaisesRegex(CommandError, '^observer stopped$'):
                runner.run('nmcli', '-c', script, timeout=45, observe=observe)
            self.assertLess(time.monotonic()-started, 3)
            self.assertFalse(runner.pending)
            with self.assertRaises(ProcessLookupError): os.kill(int(marker.read_text()), 0)


@unittest.skipUnless(AUTH, 'Wi-Fi authentication guard absent on baseline')
class WifiAuthenticationCase(unittest.TestCase):
    def watch(self, password='valid password', state=60):
        from wifi_auth import Attempt
        run = Mock(return_value=str(state)+' (state)\n'+PATH)
        clock = Mock(return_value=100.0)
        return Attempt(run, 'wlan0', password, clock=clock), run, clock

    def test_prompt_detection_is_cumulative_chunk_safe_and_does_not_treat_ssid_text_as_prompt(self):
        from wifi_auth import AuthenticationError
        watch, run, clock = self.watch()
        watch(("Passwords needed for '"+PROMPT+PROMPT+"'\n").encode(), b'')
        watch(PROMPT[:20].encode(), None)
        for _ in range(3): watch(PROMPT.encode(), None)
        with self.assertRaisesRegex(AuthenticationError, 'password.*again'):
            watch((PROMPT+'\n\x1b[2K\r'+PROMPT).encode(), None)
        self.assertEqual(run.call_count, 1)

    def test_blank_password_prompts_immediately_but_saved_credentials_can_connect_without_prompt(self):
        from wifi_auth import AuthenticationError
        watch, run, clock = self.watch(password='')
        with self.assertRaisesRegex(AuthenticationError, 'Enter.*password'):
            watch(PROMPT.encode(), b'')
        other, run, clock = self.watch(password='')
        other(b'\r| connecting (getting IP configuration)', None)
        clock.return_value = 140
        other(b'\r| connecting (getting IP configuration)', None)

    def test_authentication_deadline_does_not_shorten_dhcp_or_confuse_spinner_with_ssid(self):
        from wifi_auth import AuthenticationError
        watch, run, clock = self.watch()
        watch(b'\r\x1b[2K/ connecting (getting IP configuration)', None)
        clock.return_value = 140; watch(b'', b'')
        other, run, clock = self.watch()
        clock.return_value = 116
        with self.assertRaisesRegex(AuthenticationError, 'authentication'):
            other(b"Network name: connecting (getting IP configuration)", None)

    def test_cleanup_only_disconnects_same_owned_activation_still_authenticating(self):
        for path, state, cancel in ((PATH, 60, True), (PATH, 100, False), (PATH, 70, False), (PATH+'1', 60, False)):
            watch, run, clock = self.watch()
            watch(PROMPT.encode(), None)
            run.return_value = str(state)+' (state)\n'+path
            watch.cancel()
            disconnects = [call for call in run.call_args_list if 'disconnect' in call.args]
            self.assertEqual(bool(disconnects), cancel)
            if cancel: self.assertEqual(disconnects[0].args, ('nmcli', '--wait', '0', 'device', 'disconnect', 'wlan0'))
        watch, run, clock = self.watch(); run.side_effect = CommandError('adapter removed')
        watch(PROMPT.encode(), None); watch.cancel()

    def test_real_fake_nmcli_reprompt_aborts_early_and_allows_a_fresh_attempt(self):
        from wifi_auth import connect, AuthenticationError
        runner = CommandRunner(); runner.commands['nmcli'] = sys.executable; self.addCleanup(runner.close)
        script = 'import time; print('+repr(PROMPT)+' ,flush=True); time.sleep(.05); print('+repr(PROMPT)+',flush=True); time.sleep(45)'
        queries = []
        def run(name, *args, **kwargs):
            if '--ask' in args: return runner.run(name, '-c', script, **kwargs)
            queries.append(args)
            return '60 (connecting)\n'+PATH
        started = time.monotonic()
        with self.assertRaisesRegex(AuthenticationError, 'password.*again'):
            connect(run, ('device','wifi','connect','AA:BB','ifname','wlan0'), 'wlan0', 'valid password')
        self.assertLess(time.monotonic()-started, 3); self.assertFalse(runner.pending)
        self.assertTrue(any('disconnect' in args for args in queries))
        self.assertEqual(runner.run('nmcli', '-c', 'print("retry successful")'), 'retry successful')

    def test_abort_recovers_a_late_activation_path_without_polling_between_prompts(self):
        from wifi_auth import AuthenticationError
        watch, run, clock = self.watch()
        run.return_value = '30 (disconnected)\n--'
        watch(PROMPT.encode(), None)
        for _ in range(3): watch(PROMPT.encode(), None)
        self.assertEqual(run.call_count, 1)
        run.return_value = '60 (connecting)\n'+PATH
        with self.assertRaises(AuthenticationError): watch((PROMPT+'\n'+PROMPT).encode(), None)
        watch.cancel()
        self.assertTrue(any('disconnect' in call.args for call in run.call_args_list))
        other, run, clock = self.watch()
        clock.return_value = 116
        with self.assertRaises(AuthenticationError): other(b'', None)
        other.cancel()
        self.assertTrue(any('disconnect' in call.args for call in run.call_args_list))

    def test_deadline_checks_device_state_if_pretty_progress_is_missing(self):
        watch, run, clock = self.watch(state=70)
        clock.return_value = 116
        watch(b'', None)
        self.assertTrue(watch.authenticated)


class WifiPasswordValidationCase(unittest.TestCase):
    @unittest.skipUnless(AUTH, 'Wi-Fi authentication guard absent on baseline')
    def test_psk_validation_allows_hex_and_does_not_apply_wpa2_minimum_to_wpa3(self):
        from wifi_actions import WifiCapabilities, perform
        state = dict(available=True, device='wlan0', networks=[dict(bssid='AA:BB', security='WPA2')])
        run = Mock(); capabilities = WifiCapabilities(lambda **kwargs: state, run, Mock())
        for password in ('short', 'x'*64, 'é'*32):
            with self.assertRaisesRegex(ValueError, 'WPA/WPA2 passwords'):
                perform(capabilities, 'wifiConnect', dict(bssid='AA:BB', password=password))
        run.assert_not_called()
        for password in ('12345678', 'a'*64):
            self.assertEqual(perform(capabilities, 'wifiConnect', dict(bssid='AA:BB', password=password)), 'Wi-Fi connected')
        state['networks'][0]['security'] = 'WPA3'
        self.assertEqual(perform(capabilities, 'wifiConnect', dict(bssid='AA:BB', password='short')), 'Wi-Fi connected')
