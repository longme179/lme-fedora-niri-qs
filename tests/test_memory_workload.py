"""New opt-in diagnostic contracts; no real session is contacted by unit tests."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MAIN = dict(id='mainfixture', pid=101, config_path=str(ROOT/'shell.qml'))
SETTINGS = dict(id='settingsfixture', pid=201, config_path=str(ROOT/'settings.qml'))


def inventory(pss=100000, settings=False, complete=True):
    rows = [dict(pid=101, role='Quickshell'), dict(pid=102, role='backend'),
            dict(pid=103, role='clipboard worker')]
    if settings: rows += [dict(pid=201, role='Quickshell'), dict(pid=202, role='backend')]
    return dict(complete=complete, pss_kib=pss if complete else None, processes=rows,
                checkouts=[str(ROOT)], issues=[] if complete else ['memory unreadable'],
                rss_kib=999999, payload_pss_kib=0)


class MemoryWorkloadCase(unittest.TestCase):
    def session(self):
        from memory_workload import Session
        s = Session(ROOT, 'quickshell', ())
        s.main = MAIN
        return s

    def test_attach_rejects_demo_missing_or_duplicate_main_and_existing_settings(self):
        from memory_workload import Session
        for instances in ([], [MAIN, MAIN], [MAIN, SETTINGS]):
            s = Session(ROOT, 'quickshell', ())
            with patch.object(s, 'instances', return_value=instances), self.assertRaises(ValueError):
                s.attach()
        s = Session(ROOT, 'quickshell', ())
        with patch.object(s, 'instances', return_value=[MAIN]), \
             patch.object(s, 'ipc', return_value='{"demo":true}'), self.assertRaisesRegex(ValueError, 'demo'):
            s.attach()

    def test_pins_ipc_to_instance_and_rejects_zero_exit_error_text_for_void(self):
        s = self.session()
        with patch.object(s, 'qs', return_value='') as call:
            s.command('toggle', 'activity')
        self.assertEqual(call.call_args.args, ('ipc', '--id', 'mainfixture', 'call', 'shell', 'toggle', 'activity'))
        with patch.object(s, 'qs', return_value='IPC target was not found'), self.assertRaises(ValueError):
            s.command('close')

    def test_nonzero_cli_result_and_malformed_instance_json_are_errors(self):
        s = self.session()
        result = subprocess.CompletedProcess([], 1, '', 'failure')
        with patch('memory_workload.subprocess.run', return_value=result), self.assertRaises(ValueError):
            s.qs('list', '--all', '--json')
        with patch.object(s, 'qs', return_value='not JSON'), self.assertRaises(ValueError):
            s.instances()

    def test_pss_budget_boundary_uses_inclusive_pss_not_summed_rss(self):
        s = self.session()
        with patch.object(s, 'instances', return_value=[MAIN]), \
             patch('memory_workload.collect', side_effect=[inventory(390625), inventory(390626)]), \
             contextlib.redirect_stdout(io.StringIO()):
            s.measure('steady', 400)
            s.measure('warm-24', 400)
        self.assertEqual([v['within_budget'] for v in s.report['samples']], [True, False])

    def test_incomplete_inventory_is_retained_and_never_passes(self):
        s = self.session()
        with patch.object(s, 'instances', return_value=[MAIN]), \
             patch('memory_workload.collect', return_value=inventory(complete=False)), \
             self.assertRaisesRegex(ValueError, 'Incomplete'):
            s.measure('steady', 400)
        self.assertIsNone(s.report['samples'][0]['within_budget'])

    def test_persistent_restart_is_not_mistaken_for_a_stable_workload(self):
        s = self.session(); changed = inventory(); changed['processes'][1]['pid'] = 999
        with patch.object(s, 'instances', return_value=[MAIN]), \
             patch('memory_workload.collect', side_effect=[inventory(), changed]), \
             contextlib.redirect_stdout(io.StringIO()):
            s.measure('steady', 400)
            with self.assertRaisesRegex(ValueError, 'Persistent'):
                s.measure('warm-24', 400)

    def test_workload_orders_48_cycles_and_checkpoints_without_setting_commands(self):
        s = self.session()
        with patch.object(s, 'command') as call, patch.object(s, 'measure') as measure, \
             patch.object(s, 'open_settings') as settings, patch('memory_workload.time.sleep'):
            s.exercise(.1, .1)
        toggles = [c.args for c in call.call_args_list if c.args[0] == 'toggle']
        self.assertEqual(toggles, [('toggle', p) for p in ('clipboard', 'control', 'activity', 'notifications', 'launcher', 'power')]*8)
        self.assertEqual([c.args for c in measure.call_args_list], [('steady', 400), ('warm-24', 400), ('warm-48', 400), ('Settings-open', 500)])
        self.assertEqual(sum(c.args == ('close',) for c in call.call_args_list), 49)
        settings.assert_called_once_with()

    def test_settings_ready_requires_visible_reply_and_does_not_kill_a_process(self):
        s = self.session()
        with patch.object(s, 'instances', side_effect=[[MAIN], [MAIN, SETTINGS]]), \
             patch.object(s, 'ipc', side_effect=['false', 'true']), \
             patch('memory_workload.subprocess.Popen') as launch:
            s.open_settings()
        self.assertEqual(s.settings, SETTINGS)
        self.assertEqual(launch.call_args.args[0], [str(ROOT/'scripts/settings.sh'), '--page', 'appearance'])
        launch.return_value.terminate.assert_not_called()
        launch.return_value.kill.assert_not_called()

    def test_output_is_exclusive_and_bad_timing_is_rejected_before_actions(self):
        from memory_workload import main, timing
        for value in ('nan', 'inf', '-1', '0'):
            with self.assertRaises(ValueError): timing(value)
        with tempfile.TemporaryDirectory() as directory, patch('memory_workload.Session.attach') as attach:
            path = Path(directory)/'existing.json'; path.write_text('keep')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--checkout', str(ROOT), '--theme', 'liquid', '--output', str(path)]), 1)
            self.assertEqual(path.read_text(), 'keep')
            attach.assert_not_called()
