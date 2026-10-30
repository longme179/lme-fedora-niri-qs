"""New diagnostic contracts: mock IPC/proc only, no live desktop mutations."""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[1]
MAIN = dict(id='main-owner', pid=101, config_path=str(ROOT/'shell.qml'))
SETTINGS = dict(id='settings-owner', pid=201, config_path=str(ROOT/'settings.qml'))


def inventory(pss=100000, settings=False, complete=True):
    rows = [dict(pid=101, role='Quickshell'), dict(pid=102, role='backend'), dict(pid=103, role='clipboard worker')]
    if settings: rows += [dict(pid=201, role='Quickshell'), dict(pid=202, role='backend')]
    return dict(complete=complete, pss_kib=pss if complete else None, rss_kib=999999,
                processes=rows, checkouts=[str(ROOT)], issues=[] if complete else ['unreadable'], payload_pss_kib=0)


class WorkloadContractsCase(unittest.TestCase):
    def setUp(self):
        from memory_workload import Session
        self.session = Session(ROOT, '/chosen/quickshell', ())
        self.identity = patch('memory_workload.read_identity', side_effect=lambda p:(1, int(p.name)*10))
        self.identity.start(); self.addCleanup(self.identity.stop)

    def attached(self):
        s = self.session; s.main = MAIN
        s.baseline = {(101,'Quickshell',1010), (102,'backend',1020), (103,'clipboard worker',1030)}
        return s

    def test_admission_rejects_existing_settings_before_any_panel_change(self):
        for instances in ([], [MAIN, MAIN], [MAIN, SETTINGS]):
            with self.subTest(instances=instances), patch.object(self.session, 'instances', return_value=instances), \
                 patch.object(self.session, 'command') as command, self.assertRaises(ValueError):
                self.session.attach()
            command.assert_not_called()
            self.assertIsNone(self.session.main)

    def test_demo_and_incomplete_preflight_never_attach(self):
        s = self.session
        for demo, complete in ((True, True), (False, False)):
            with patch.object(s, 'instances', return_value=[MAIN]), \
                 patch.object(s, 'ipc', return_value=json.dumps(dict(demo=demo))), \
                 patch('memory_workload.collect', return_value=inventory(complete=complete)), \
                 self.assertRaises(ValueError): s.attach()
            self.assertIsNone(s.main)

    def test_valid_preflight_checks_catalog_and_pins_core_identity(self):
        s = self.session
        with patch.object(s, 'instances', return_value=[MAIN]), \
             patch.object(s, 'ipc', return_value='{"demo":false,"player":"not retained"}'), \
             patch('memory_workload.collect', return_value=inventory()): s.attach()
        self.assertEqual(s.main, MAIN)
        self.assertEqual(s.baseline, self.attached().baseline)
        self.assertNotIn('not retained', json.dumps(s.report))
        s.main = None
        with patch.object(s, 'instances', return_value=[MAIN]), \
             patch('memory_workload.load_catalog', return_value={'panel': []}), self.assertRaises(ValueError): s.attach()
        self.assertIsNone(s.main)

    def test_public_void_commands_are_pinned_and_zero_exit_error_text_is_rejected(self):
        s = self.attached()
        with patch.object(s, 'qs', return_value='') as command: s.command('toggle', 'control')
        self.assertEqual(command.call_args.args, ('ipc', '--id', MAIN['id'], 'call', 'shell', 'toggle', 'control'))
        with patch.object(s, 'qs', return_value='IPC target not found'), self.assertRaises(ValueError): s.command('close')

    def test_no_retry_of_a_mutating_ipc_timeout(self):
        s = self.attached()
        with patch.object(s, 'qs', side_effect=subprocess.TimeoutExpired('quickshell', 5)) as command:
            with self.assertRaises(subprocess.TimeoutExpired): s.command('toggle', 'control')
        self.assertEqual(command.call_count, 1)

    def test_zero_exit_with_stderr_is_not_a_successful_void_reply(self):
        with patch('memory_workload.subprocess.run', return_value=subprocess.CompletedProcess([],0,'','Target not found.')):
            with self.assertRaises(ValueError): self.attached().command('close')

    def test_settings_uses_gear_route_and_requires_visible_ack_without_caller_launch(self):
        s = self.attached()
        with patch.object(s, 'instances', side_effect=[[MAIN], [MAIN, SETTINGS]]), \
             patch.object(s, 'ipc', side_effect=['', 'false', 'true']) as ipc, \
             patch('memory_workload.subprocess.Popen') as launch:
            s.open_settings()
        self.assertEqual(ipc.call_args_list, [call(MAIN,'shell','toggle','settings'),
            call(SETTINGS,'settings','startupPending'), call(SETTINGS,'settings','openPage','appearance')])
        launch.assert_not_called(); self.assertEqual(s.settings, SETTINGS)

    def test_inclusive_pss_boundary_and_settings_pair_continuity(self):
        s = self.attached()
        with patch.object(s, 'instances', return_value=[MAIN]), \
             patch('memory_workload.collect', side_effect=[inventory(390625), inventory(390626)]), \
             contextlib.redirect_stdout(io.StringIO()):
            s.measure('steady', 400); s.measure('warm-24', 400)
        self.assertEqual([v['within_budget'] for v in s.report['samples']], [True, False])
        s.settings = SETTINGS
        with patch.object(s, 'instances', return_value=[MAIN, SETTINGS]), \
             patch('memory_workload.collect', return_value=inventory(settings=True)), contextlib.redirect_stdout(io.StringIO()):
            s.measure('Settings-open', 500)
        self.assertEqual({v[0] for v in s.settings_core}, {201,202})

    def test_incomplete_memory_is_saved_as_unknown_not_zero(self):
        s = self.attached()
        with patch.object(s, 'instances', return_value=[MAIN]), \
             patch('memory_workload.collect', return_value=inventory(complete=False)), self.assertRaises(ValueError):
            s.measure('warm-24', 400)
        self.assertIsNone(s.report['samples'][-1]['within_budget'])

    def test_pid_reuse_cannot_masquerade_as_a_stable_worker(self):
        s = self.attached()
        with patch.object(s, 'instances', return_value=[MAIN]), patch('memory_workload.collect', return_value=inventory()), \
             patch('memory_workload.read_identity', return_value=(1,999)), self.assertRaisesRegex(ValueError, 'Persistent'):
            s.measure('warm-48', 400)

    def test_48_timed_cycles_and_checkpoint_order_never_change_settings(self):
        s = self.attached()
        def measured(label, limit): s.report['samples'].append(dict(label=label, memory=inventory()))
        with patch.object(s, 'command') as command, patch.object(s, 'measure', side_effect=measured) as measure, \
             patch.object(s, 'open_settings') as opened, patch('memory_workload.time.sleep'), contextlib.redirect_stdout(io.StringIO()):
            s.exercise(2,5)
        self.assertEqual([v.args for v in command.call_args_list if v.args[0]=='toggle'],
            [('toggle',p) for p in ('clipboard','control','activity','notifications','launcher','power')]*8)
        self.assertEqual([v.args for v in measure.call_args_list],
            [('steady',400),('warm-24',400),('warm-48',400),('Settings-open',500)])
        opened.assert_called_once_with()

    def test_normal_close_checks_both_settings_identities_without_killing(self):
        s = self.attached(); s.settings = SETTINGS
        s.settings_core = {(201,'Quickshell',2010),(202,'backend',2020)}
        with patch.object(s, 'instances', return_value=[MAIN]), \
             patch('memory_workload.same_process', side_effect=[False,True,False,False]), \
             patch('memory_workload.time.sleep'), patch.object(s, 'measure') as measure, \
             patch.object(s, 'qs') as command, contextlib.redirect_stdout(io.StringIO()): s.wait_closed(5)
        measure.assert_called_once_with('Settings-closed',400)
        command.assert_not_called(); self.assertTrue(s.report['settings_exit_confirmed'])

    def test_cli_private_report_survives_error_and_refuses_overwrite(self):
        from memory_workload import main, timing
        for value in ('nan','inf','-1','0'):
            with self.assertRaises(ValueError): timing(value)
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)/'report.json'
            with patch('memory_workload.Session.attach', side_effect=ValueError('diagnostic refusal')), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--theme','liquid','--output',str(output)]),1)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode),0o600)
            self.assertEqual(json.loads(output.read_text())['error'],'diagnostic refusal')
            before = output.read_bytes()
            with patch('memory_workload.Session.attach') as attach, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--theme','liquid','--output',str(output)]),1)
            attach.assert_not_called(); self.assertEqual(output.read_bytes(),before)

    def test_cli_interrupt_preserves_checkpoint_and_only_closes_pinned_panels(self):
        from memory_workload import Session, main
        def interrupted(s, *_):
            s.report['samples'].append(dict(label='steady',within_budget=True,memory=inventory()))
            s.save()
            raise KeyboardInterrupt()
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)/'report.json'
            with patch.object(Session,'attach',lambda s:setattr(s,'main',MAIN)), \
                 patch.object(Session,'exercise',interrupted), patch.object(Session,'command') as close, \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--theme','smoked','--output',str(output)]),1)
            report = json.loads(output.read_text())
            self.assertEqual(report['error'],'Interrupted by user')
            self.assertEqual(report['samples'][0]['label'],'steady')
            close.assert_called_once_with('close')

    def test_same_process_distinguishes_exit_reuse_and_unreadable_identity(self):
        from memory_workload import same_process
        for value, expected in ((FileNotFoundError(),False),(PermissionError(),True)):
            with patch('memory_workload.read_identity',side_effect=value):
                self.assertIs(same_process(201,2010),expected)
        with patch('memory_workload.read_identity',return_value=(1,999)):
            self.assertFalse(same_process(201,2010))

    def test_cli_does_not_follow_a_report_symlink_or_fallback_from_explicit_binary(self):
        from memory_workload import main
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)/'existing'; target.write_text('private existing data')
            link = Path(raw)/'report.json'; link.symlink_to(target)
            with patch('memory_workload.Session.attach') as attach, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--theme','smoked','--output',str(link)]),1)
            attach.assert_not_called(); self.assertEqual(target.read_text(),'private existing data')
            with patch('memory_workload.shutil.which',return_value=None) as which, \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--theme','smoked','--quickshell','/missing','--output',str(Path(raw)/'new.json')]),1)
            which.assert_called_once_with('/missing')


if __name__ == '__main__': unittest.main()
