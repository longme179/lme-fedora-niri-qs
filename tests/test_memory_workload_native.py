"""Private Wayland CLI wiring with static Qt software UI; not a GPU stress result."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest

from release_session_fixture import ReleaseWorld


@unittest.skipUnless(os.environ.get('LME_TEST_MEMORY_WORKLOAD') == '1',
                     'private Wayland laptop workload CLI')
class NativeMemoryWorkloadCase(unittest.TestCase):
    def world(self, directory):
        world = ReleaseWorld(Path(directory), 'liquid')
        preferences = json.loads(world.settings.read_text())
        preferences.update(animations=False, springMotion=False, peripheralBatteryAlerts=False)
        world.settings.write_text(json.dumps(preferences))
        world.env['QT_QUICK_BACKEND'] = 'software'
        return world

    def arguments(self, world):
        return [sys.executable, str(world.root/'scripts/memory_workload.py'),
            '--checkout', str(world.root), '--theme', 'liquid', '--dwell', '2', '--settle', '5',
            '--output', str(world.home/'workload.json')]

    def invoke(self, world):
        report = world.home/'workload.json'
        reply = subprocess.run(self.arguments(world), env=world.env, capture_output=True, text=True, timeout=300)
        return reply, report, json.loads(report.read_text())

    def test_existing_settings_refuses_workload_and_keeps_the_panel_open(self):
        with tempfile.TemporaryDirectory(prefix='laptop-workload-busy-') as directory:
            world = self.world(directory)
            with world.launch() as main, world.launch('settings', page='appearance'):
                main.call('toggle', 'control', target='shell')
                main.wait(lambda s: s['panelOpen'])
                reply, _, report = self.invoke(world)
                self.assertEqual(reply.returncode, 1)
                self.assertIn('close Settings', report['error'])
                self.assertEqual(report['samples'], [])
                self.assertTrue(main.wait(lambda s: s['ready'])['panelOpen'])

    def test_wait_close_checks_real_settings_close_signal_and_backend_exit(self):
        with tempfile.TemporaryDirectory(prefix='laptop-workload-close-') as directory:
            world = self.world(directory)
            path = world.root/'qml/settings/SettingsApplication.qml'; text = path.read_text()
            text = text.replace('function startupPending()', '''function closeForMemoryCheck(): void {
                if (view.item) (view.item as SettingsView).closeRequested();
            }
            function startupPending()''', 1)
            path.write_text(text)
            with world.launch() as main, tempfile.TemporaryFile(mode='w+') as log:
                main.wait(lambda s: s['workerReady'] and s['count'] == 2)
                before = world.settings.read_bytes()
                process = subprocess.Popen(self.arguments(world)+['--wait-close'], env=world.env, stdout=log, stderr=log)
                try:
                    deadline = time.monotonic()+300; output = ''
                    marker = 'Close Settings with its X now'
                    while time.monotonic() < deadline and process.poll() is None:
                        log.seek(0); output = log.read()
                        if marker in output: break
                        time.sleep(.05)
                    self.assertIn(marker, output)
                    subprocess.run(['quickshell', '-p', str(world.root/'settings.qml'), 'ipc', 'call',
                        'settings', 'closeForMemoryCheck'], env=world.env, check=True, capture_output=True, timeout=5)
                    process.wait(timeout=15)
                    report = json.loads((world.home/'workload.json').read_text())
                    self.assertIsNone(report['error'])
                    self.assertEqual([s['label'] for s in report['samples']],
                        ['steady', 'warm-24', 'warm-48', 'Settings-open', 'Settings-closed'])
                    self.assertTrue(all(s['memory']['complete'] for s in report['samples']))
                    self.assertEqual(stat.S_IMODE((world.home/'workload.json').stat().st_mode), 0o600)
                    self.assertEqual(world.settings.read_bytes(), before)
                    self.assertTrue(report['settings_exit_confirmed'])
                    self.assertEqual(report['samples'][-1]['label'], 'Settings-closed')
                    self.assertEqual(process.returncode, int(not all(s['within_budget'] for s in report['samples'])))
                    self.assertTrue(main.wait(lambda s: s['ready'])['ready'])
                finally:
                    if process.poll() is None: process.terminate(); process.wait(timeout=8)
                    subprocess.run(['quickshell', '-p', str(world.root/'settings.qml'), 'kill'],
                                   env=world.env, capture_output=True, timeout=5)
