"""One-shot inventory contracts; fake proc trees never inspect the user's session."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from test_backend import backend
from launchpad import Launchpad

TOOL = Path(__file__).resolve().parents[1]/'scripts/memory_report.py'
memory = None
if TOOL.exists():
    spec = importlib.util.spec_from_file_location('memory_report', TOOL)
    memory = importlib.util.module_from_spec(spec); spec.loader.exec_module(memory)


class RelayShapeCase(unittest.TestCase):
    def test_existing_detached_relay_is_a_separate_script_with_payload_child(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, XDG_STATE_HOME=folder):
            jobs = Launchpad()
            entry = dict(name='Inventory fixture', kind='command', terminal=False, cwd='',
                command=f'{sys.executable} -c "import time; time.sleep(30)"')
            jobs.run('inventory', {'inventory':entry}, 'unused')
            relay = jobs.jobs['inventory']['process']
            try:
                args = Path(f'/proc/{relay.pid}/cmdline').read_bytes().split(b'\0')
                self.assertEqual(args[1], b'-S')
                self.assertEqual(Path(os.fsdecode(args[2])).name, 'detached_log.py')
                self.assertEqual(args[3], b'--log-fd'); self.assertIn(b'--ready-fd', args)
                children = []
                for proc in Path('/proc').iterdir():
                    if not proc.name.isdecimal(): continue
                    try: parent = int((proc/'stat').read_text().rsplit(')',1)[1].split()[1])
                    except (OSError,ValueError,IndexError): continue
                    if parent==relay.pid: children.append(proc.name)
                self.assertEqual(len(children), 1)
                payload = Path('/proc')/children[0]
                self.assertIn(b'time.sleep(30)', (payload/'cmdline').read_bytes())
            finally:
                relay.terminate(); relay.wait(timeout=3)


@unittest.skipUnless(memory, 'memory tool absent on baseline; new command contracts N/A')
class MemoryReportCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.proc = self.root/'proc'; self.proc.mkdir()
        self.repo = self.checkout('shell A')

    def checkout(self, name):
        root = self.root/name; (root/'scripts').mkdir(parents=True)
        (root/'scripts/desktop_backend.py').write_text('''#!/usr/bin/env python3
"""LME shell's unprivileged JSON-lines backend (Python standard library only)."""
''')
        (root/'shell.qml').write_text('import Quickshell\n')
        (root/'settings.qml').write_text('import Quickshell\n')
        for script in ('clipboard','detached_log','idle_control','audio_visualizer'):
            (root/f'scripts/{script}.py').write_text('# fixture\n')
        return root

    def process(self, pid, parent, argv, pss=100, rss=200, cwd=None):
        path = self.proc/str(pid); path.mkdir()
        fields = ['S',str(parent), *(['0']*22)]; fields[19] = str(pid*10)
        (path/'stat').write_text(f'{pid} (name with ) parentheses) '+' '.join(fields))
        (path/'cmdline').write_bytes(b'\0'.join(os.fsencode(x) for x in argv)+b'\0')
        (path/'cwd').symlink_to(cwd or self.repo, target_is_directory=True)
        (path/'smaps_rollup').write_text(f'Rss: {rss} kB\nPss: {pss} kB\nShared_Clean: 99 kB\n')
        return path

    def collect(self, extra=()):
        return memory.collect(self.proc, os.getuid(), extra)

    def test_two_checkouts_settings_workers_relays_payloads_and_dedup(self):
        other = self.checkout('shell B')
        self.process(101,1,['quickshell','-c','custom-name'])
        self.process(102,101,['python3','-u',self.repo/'scripts/desktop_backend.py'])
        self.process(103,101,['python3',self.repo/'scripts/clipboard.py'])
        self.process(104,103,['wl-paste','--watch','python3'])
        self.process(201,1,['qs','-p',other/'settings.qml'])
        self.process(202,201,['python3',other/'scripts/desktop_backend.py'])
        self.process(301,1,['python3','-S',self.repo/'scripts/detached_log.py','--log-fd','4','--ready-fd','5','--','payload'])
        self.process(302,301,['bash','-c','PRIVATE COMMAND CONTENT'])
        self.process(303,302,['sleep','30'])
        self.process(401,1,['other-shell'])
        report = self.collect((101,102,301))
        self.assertTrue(report['complete'], report)
        self.assertEqual([row['pid'] for row in report['processes']], [101,102,103,104,201,202,301,302,303])
        self.assertEqual(report['pss_kib'],900); self.assertEqual(report['rss_kib'],1800)
        self.assertEqual(report['shell_pss_kib'],700); self.assertEqual(report['payload_pss_kib'],200)
        self.assertEqual([row['pid'] for row in report['processes'] if row['role']=='job payload'],[302,303])
        self.assertEqual(set(report['checkouts']),{str(self.repo),str(other)})
        self.assertNotIn('PRIVATE',json.dumps(report)); self.assertNotIn('PRIVATE',memory.render(report))

    def test_symlink_and_relative_script_paths_keep_identity(self):
        link = self.root/'installed'; link.symlink_to(self.repo, target_is_directory=True)
        self.process(101,1,['python3','-I','-u',link/'scripts/clipboard.py'])
        self.process(102,1,['python3','-X','utf8','scripts/audio_visualizer.py'])
        report = self.collect()
        self.assertTrue(report['complete'],report)
        self.assertEqual(len(report['processes']),2); self.assertEqual(report['checkouts'],[str(self.repo)])

    def test_python_command_or_module_and_argument_only_mentions_are_not_owned(self):
        for pid,argv in enumerate((['python3','-c','pass',self.repo/'scripts/desktop_backend.py'],
                ['python3','-m','unrelated',self.repo/'scripts/clipboard.py'],
                ['bash','-c',str(self.repo/'scripts/detached_log.py')],
                ['cat',self.repo/'scripts/desktop_backend.py']),101):
            self.process(pid,1,argv)
        report = self.collect()
        self.assertFalse(report['complete']); self.assertEqual(report['processes'],[])
        self.assertIsNone(report['pss_kib'])

    def test_same_filename_outside_checkout_is_unresolved_and_never_a_false_pass(self):
        path = self.root/'elsewhere/scripts'; path.mkdir(parents=True)
        self.process(101,1,['python3',path/'desktop_backend.py'])
        report = self.collect()
        self.assertEqual(report['processes'],[]); self.assertFalse(report['complete'])
        self.assertTrue(report['issues'])

    def test_unknown_quickshell_reported_and_explicit_helper_can_be_added(self):
        self.process(101,1,['quickshell','-c','not-identifiable'])
        self.process(201,1,['awww-daemon'])
        report = self.collect()
        self.assertEqual(report['unattributed_quickshell'],[101]); self.assertFalse(report['complete'])
        report = self.collect((101,201,201))
        self.assertTrue(report['complete'], report)
        self.assertEqual([row['pid'] for row in report['processes']],[101,201])

    def test_missing_counter_or_permission_never_becomes_zero_total(self):
        path = self.process(101,1,['python3',self.repo/'scripts/clipboard.py'])
        (path/'smaps_rollup').write_text('Rss: 200 kB\n')
        report = self.collect()
        self.assertFalse(report['complete']); self.assertIsNone(report['pss_kib'])
        self.assertIsNone(report['processes'][0]['pss_kib'])
        with patch.object(memory,'read_memory',side_effect=PermissionError):
            denied = self.collect()
        self.assertFalse(denied['complete']); self.assertIsNone(denied['pss_kib'])
        self.assertIn('incomplete',memory.render(denied).lower())

    def test_pid_reuse_during_sample_discards_counters(self):
        self.process(101,1,['python3',self.repo/'scripts/clipboard.py'])
        original = memory.read_identity; calls = 0
        def changed(path):
            nonlocal calls
            result = original(path); calls += 1
            return (result[0],result[1]+1) if calls>=3 else result
        with patch.object(memory,'read_identity',side_effect=changed): report = self.collect()
        self.assertFalse(report['complete']); self.assertIsNone(report['pss_kib'])
        self.assertIsNone(report['processes'][0]['rss_kib'])

    def test_current_uid_filter_invalid_explicit_pid_and_exited_process(self):
        path = self.process(101,1,['python3',self.repo/'scripts/clipboard.py'])
        report = memory.collect(self.proc, os.getuid()+1, (101,))
        self.assertFalse(report['complete']); self.assertEqual(report['processes'],[])
        self.assertFalse(self.collect((999,))['complete'])
        (path/'stat').unlink()
        report = self.collect()
        self.assertFalse(report['complete']); self.assertTrue(report['issues'])

    def test_cli_is_read_only_secret_free_and_reports_incomplete_exit(self):
        self.process(101,1,['python3',self.repo/'scripts/clipboard.py'])
        report = self.collect()
        with patch.object(memory,'collect',return_value=report) as collect, \
                patch('subprocess.Popen',side_effect=AssertionError('no subprocess')), \
                patch('os.kill',side_effect=AssertionError('no signals')), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(memory.main(['--json','--pid','101','--label','Settings open']),0)
        collect.assert_called_once_with(extra=[101])
        self.assertEqual(json.loads(output.getvalue())['label'],'Settings open')
        with patch.object(memory,'collect',return_value=dict(report,complete=False)), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(memory.main([]),1)


if __name__ == '__main__': unittest.main()
