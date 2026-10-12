"""Display validation, owned child lifetime and Settings-to-shell IPC."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from test_backend import backend, Fixture, FakeRunner
from display_mirror import DisplayMirror

OUTPUTS = [{'name': 'eDP-1', 'enabled': True}, {'name': 'HDMI-A-1', 'enabled': True},
           {'name': 'DP-1', 'enabled': False}]


class MirroringCase(Fixture, unittest.TestCase):
    def test_rejects_invalid_displays_missing_tool_and_keeps_other_instances(self):
        mirror = DisplayMirror(FakeRunner(available={'wl-mirror'}))
        for source, target in [('eDP-1', 'eDP-1'), ('eDP-1', 'DP-1'), ('unknown', 'HDMI-A-1'),
                               (None, 'HDMI-A-1'), ('--help', 'HDMI-A-1')]:
            with patch('display_mirror.subprocess.Popen') as spawn:
                with self.assertRaises(ValueError): mirror.start(source, target, OUTPUTS)
                spawn.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'Install wl-mirror'):
            DisplayMirror(FakeRunner()).start('eDP-1', 'HDMI-A-1', OUTPUTS)
        mirror.stop()
        self.assertFalse(mirror.state()['active'])

    def test_real_owned_child_stops_on_hotplug_disable_and_close(self):
        executable = self.put('wl-mirror', '#!/usr/bin/python3\nimport time\ntime.sleep(60)\n')
        executable.chmod(0o755)
        runner = FakeRunner(available={'wl-mirror'})
        mirror = DisplayMirror(runner)
        self.addCleanup(mirror.close)
        outsider = subprocess.Popen([str(executable)])
        self.addCleanup(lambda: (outsider.terminate(), outsider.wait(timeout=3)))
        with patch.object(runner, 'executable', return_value=str(executable)):
            for stop in ('disconnect', 'disable', 'close'):
                mirror.start('eDP-1', 'HDMI-A-1', OUTPUTS)
                child = mirror.child
                self.assertEqual(child.args[1:], ['--fullscreen-output', 'HDMI-A-1', '--scaling', 'fit',
                                                '--title', 'LME Display Mirror', 'eDP-1'])
                with self.assertRaisesRegex(ValueError, 'Stop the current'): mirror.start('eDP-1', 'HDMI-A-1', OUTPUTS)
                self.assertEqual(mirror.child.pid, child.pid)
                if stop == 'disconnect':
                    state = mirror.state(outputs=OUTPUTS[:1])
                    self.assertIn('disconnected', state['error'])
                elif stop == 'disable': mirror.state(enabled=False)
                else: mirror.close()
                self.assertFalse(mirror.state()['active'])
                self.assertIsNotNone(child.poll())
                self.assertIsNone(outsider.poll())

    def test_exit_error_is_reported_and_restart_clears_it(self):
        executable = self.put('wl-mirror', '#!/usr/bin/python3\nimport sys\nprint("capture protocol unavailable",file=sys.stderr)\nsys.exit(1)\n')
        executable.chmod(0o755)
        runner = FakeRunner(available={'wl-mirror'}); mirror = DisplayMirror(runner)
        self.addCleanup(mirror.close)
        with patch.object(runner, 'executable', return_value=str(executable)):
            mirror.start('eDP-1', 'HDMI-A-1', OUTPUTS)
            mirror.child.wait(timeout=3)
            state = mirror.state()
            self.assertFalse(state['active']); self.assertIn('capture protocol unavailable', state['error'])
            self.assertIsNone(mirror.log)
            mirror.start('eDP-1', 'HDMI-A-1', OUTPUTS)
            self.assertEqual(mirror.info['error'], '')

    def test_settings_proxies_owned_service_and_reports_missing_shell(self):
        live = self.make_backend(FakeRunner(available={'quickshell', 'wl-mirror'})); live.settings_only = True
        self.addCleanup(live.mirror.close)
        state = {'active': True, 'source': 'eDP-1', 'target': 'HDMI-A-1', 'available': True, 'error': ''}
        runner = live.runner
        prefix = ('quickshell', '-p', live.shell_entry, 'ipc', 'call', 'shell')
        runner.responses[prefix + ('mirrorStart', 'eDP-1', 'HDMI-A-1')] = 'true\n'
        runner.responses[prefix + ('mirrorStatus',)] = json.dumps(state)
        with patch('display_mirror.subprocess.Popen') as spawn:
            self.assertTrue(live.handle({'action': 'mirrorStart', 'source': 'eDP-1', 'target': 'HDMI-A-1'})['ok'])
            self.assertEqual(live.snapshot()['mirror'], state)
            spawn.assert_not_called()
        runner.responses[prefix + ('mirrorStatus',)] = 'Target not found.'
        live.handle({'action': 'mirrorRefresh'})
        self.assertFalse(live.snapshot()['mirror']['active'])
        self.assertIn('Start LME', live.snapshot()['mirror']['error'])
        self.assertFalse(live.handle({'action': 'mirrorStop'})['ok'])

    def test_demo_and_disabled_mirroring_never_spawn_or_touch_display_layout(self):
        demo = self.make_backend(demo=True)
        demo.handle({'action': 'mirrorRefresh'})
        with patch('display_mirror.subprocess.Popen') as spawn:
            self.assertTrue(demo.handle({'action': 'mirrorStart', 'source': 'eDP-1', 'target': 'HDMI-A-1'})['ok'])
            self.assertTrue(demo.snapshot()['mirror']['active'])
            self.assertTrue(demo.handle({'action': 'mirrorStop'})['ok'])
            self.assertFalse(demo.snapshot()['mirror']['active'])
            spawn.assert_not_called()
        live = self.make_backend(); live.preferences.set('mirroringEnabled', False)
        self.assertFalse(live.handle({'action': 'mirrorStart', 'source': 'eDP-1', 'target': 'HDMI-A-1'})['ok'])
        self.assertEqual(live.preferences.values['displayLayout'], [])
        self.assertEqual(live.runner.calls, [])


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'opt-in private Wayland UI')
class MirrorUiCase(unittest.TestCase):
    def test_output_pickers_start_stop_and_live_state(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('qml', 'scripts', 'config'):
                (root/name).symlink_to(repo/name, target_is_directory=True)
            entry = root/'shell.qml'
            entry.write_text('''//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/components"
import "qml/services"
ShellRoot {
    Component.onCompleted: Quickshell.watchFiles = false
    FloatingWindow { fullscreen: true
        MirrorControls { id: controls; width: 600; anchors.centerIn: parent }
    }
    IpcHandler {
        target: "mirrorTest"
        function state(): string {
            const name = controls.state.active ? "mirrorStop" : "mirrorStart";
            const button = controls.children.find(c => c.children && c.children.some(b => b.objectName === name)).children.find(b => b.objectName === name);
            const point = button.mapToGlobal(button.width / 2, button.height / 2);
            return JSON.stringify({ready: ShellState.backendReady, active: !!controls.state.active,
                outputs: controls.outputs.length, source: controls.sourceName, target: controls.targetName,
                enabled: button.enabled, x: Math.round(point.x), y: Math.round(point.y)});
        }
    }
}''')
            env = dict(os.environ, LME_SHELL_DEMO='1', XDG_CONFIG_HOME=str(root/'home'),
                       XDG_STATE_HOME=str(root/'state'), XDG_DATA_HOME=str(root/'data'))
            with (root/'gui.log').open('w+') as log:
                process = subprocess.Popen(['quickshell', '-p', str(entry)], env=env, stdout=log, stderr=log)
                def wait(active):
                    deadline = time.monotonic()+7
                    while time.monotonic() < deadline:
                        reply = subprocess.run(['quickshell', '-p', str(entry), 'ipc', 'call', 'mirrorTest', 'state'], env=env, capture_output=True, text=True, timeout=3)
                        try: state = json.loads(reply.stdout)
                        except ValueError: state = {}
                        if state.get('ready') and state.get('outputs') == 2 and state.get('active') == active and state.get('enabled'): return state
                        time.sleep(.05)
                    log.seek(0); self.fail(log.read() + '\n' + str(state))
                try:
                    state = wait(False)
                    self.assertEqual((state['source'], state['target']), ('eDP-1', 'HDMI-A-1'))
                    for active in (True, False):
                        subprocess.run([os.environ['LME_TEST_POINTER'], str(state['x']), str(state['y'])], env=env, check=True, timeout=5)
                        state = wait(active)
                    log.seek(0); output = log.read()
                    for problem in ('TypeError', 'ReferenceError', 'Binding loop', 'Unable to assign', 'Failed to load configuration'):
                        self.assertNotIn(problem, output)
                finally:
                    process.terminate(); process.wait(timeout=5)
