"""The first visible Settings frame uses one complete saved appearance snapshot."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from test_backend import backend


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is required')
class SettingsStartupCase(unittest.TestCase):
    def run_settings(self, style, saver=False, restart=False, fail=False, reopen=False, native=False):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('qml', 'assets'):
                (root/name).symlink_to(repo/name, target_is_directory=True)
            shutil.copytree(repo/'config', root/'config')
            scripts = root/'scripts'; scripts.mkdir()
            shutil.copy2(repo/'scripts/settings.sh', scripts/'settings.sh')
            if (repo/'scripts/feature_catalog.py').exists():
                shutil.copy2(repo/'scripts/feature_catalog.py', scripts/'feature_catalog.py')
            preferences = copy.deepcopy(backend.DEFAULT_PREFERENCES)
            preferences.update(surfaceStyle=style, fontOverrides={'body': 'DejaVu Sans'}, opacity=.81)
            preferences['liquidGlass']['opacity'] = .63
            state = dict(apps=[], system={}, niri={'available': False, 'windows': [], 'workspaces': []},
                         preferences=preferences, platform={'niriVersion': 'niri 26.04', 'popupBlurSupported': True},
                         batterySaver={'active': saver}, catalogValidation={'error': ''}, lastResult={'action': 'ready', 'ok': True, 'sequence': 0})
            (root/'snapshot.json').write_text(json.dumps(state))
            (scripts/'desktop_backend.py').write_text('''import json, sys, time
from pathlib import Path
time.sleep(''' + ('30' if fail else '1' if reopen else '.5') + ''')
state=json.loads((Path(__file__).parent.parent/'snapshot.json').read_text())
print(json.dumps(state), flush=True)
for line in sys.stdin:
    state['lastResult']={'action':json.loads(line)['action'], 'ok':True, 'sequence':state['lastResult']['sequence']+1}
    print(json.dumps(state), flush=True)
''')
            source = (repo/'qml/settings/SettingsApplication.qml').read_text()
            source = source.replace('pragma ComponentBehavior: Bound\n', '')
            for name in ('services', 'components', 'theme'):
                source = source.replace('"../'+name+'"', '"qml/'+name+'"')
            instrumentation = '''
    property var frames: []
    property bool disconnected: false
    property bool stopped: false
    property bool remainedVisible: true
    function sample() {
        return {ready: ShellState.backendReady, liquid: Theme.liquidGlass,
            opacity: Theme.panelOpacity, animations: Theme.animations, font: Theme.fontFamily,
            saver: ShellState.batterySaverActive, blur: ShellState.liquidBlurEnabled,
            page: view.item ? view.item.page : view.page};
    }
    FrameAnimation {
        running: true
        onTriggered: if (window.visible && root.frames.length < 50) root.frames.push(root.sample());
    }
    Timer {
        interval: 20; running: true; repeat: true
        onTriggered: {
            if (window.visible && root.frames.length === 0) root.frames.push(root.sample());
            if (RESTART && root.frames.length > 3 && ShellState.backendReady && !root.stopped) {
                root.stopped = true;
                ShellState.backend.running = false;
            }
            if (root.stopped && !ShellState.backendReady) {
                root.disconnected = true;
                root.remainedVisible = root.remainedVisible && window.visible && Theme.liquidGlass;
            }
        }
    }
    Timer {
        interval: FINISH; running: true
        onTriggered: {
            console.log("SETTINGS_STARTUP " + JSON.stringify({frames: root.frames,
                disconnected: root.disconnected, remainedVisible: root.remainedVisible, visible: window.visible}));
            Qt.quit();
        }
    }
'''.replace('RESTART', 'true' if restart else 'false').replace('FINISH', '2200' if reopen else '1400')
            if fail:
                instrumentation += '    Component.onCompleted: startupDeadline.interval = 100\n'
            source = source.replace('    id: root\n', '    id: root\n'+instrumentation, 1)
            entry = root/'settings.qml'
            entry.write_text('''//@ pragma AppId lme-shell-settings
//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
pragma ComponentBehavior: Bound
import "qml/settings"
import "qml/theme"
''' + source)
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                       LME_SHELL_DEMO='0', LME_SHELL_SETTINGS='1',
                       XDG_CONFIG_HOME=str(root/'user-config'), XDG_STATE_HOME=str(root/'state'),
                       XDG_DATA_HOME=str(root/'data'), DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(root/'no-system-bus'))
            for key in ('LME_SHELL_PREVIEW', 'LME_SHELL_BACKEND_DEMO'): env.pop(key, None)
            if native:
                env.update(QT_QPA_PLATFORM='wayland', QT_QUICK_BACKEND=os.environ.get('QT_QUICK_BACKEND', 'software'))
            if reopen:
                with tempfile.TemporaryFile(mode='w+') as output:
                    process = subprocess.Popen(['quickshell', '-p', str(entry)], env=env, stdout=output, stderr=output)
                    try:
                        deadline = time.monotonic()+5
                        while time.monotonic() < deadline and process.poll() is None:
                            output.seek(0)
                            if 'Configuration Loaded' in output.read(): break
                            time.sleep(.02)
                        pending = subprocess.check_output(['quickshell', '-p', str(entry), 'ipc', 'call',
                            'settings', 'startupPending'], env=env, text=True, timeout=3).strip()
                        self.assertEqual(pending, 'true')
                        for page in ('elements', 'behavior'):
                            reply = subprocess.run(['bash', str(scripts/'settings.sh'), '--page', page], env=env,
                                                   capture_output=True, text=True, timeout=4)
                            self.assertEqual(reply.returncode, 0, reply.stderr)
                            self.assertNotIn('restarting', reply.stderr)
                            self.assertIsNone(process.poll(), 'Opening a queued page restarted Settings')
                        process.wait(timeout=6)
                        output.seek(0); log = output.read(); returncode = process.returncode
                    finally:
                        if process.poll() is None: process.terminate(); process.wait(timeout=3)
            else:
                result = subprocess.run(['quickshell', '-p', str(entry)], env=env, capture_output=True, text=True, timeout=8)
                log = result.stdout+result.stderr; returncode = result.returncode
            self.assertEqual(returncode, 0, log)
            for error in ('TypeError', 'ReferenceError', 'Unable to assign', 'Binding loop', 'Failed to load configuration'):
                self.assertNotIn(error, log)
            lines = [line.split('SETTINGS_STARTUP ', 1)[1] for line in log.splitlines() if 'SETTINGS_STARTUP ' in line]
            self.assertEqual(len(lines), 1, log)
            return json.loads(lines[0])

    def test_first_frame_uses_saved_glass_smoked_or_saver_without_default_theme(self):
        for style, saver in (('liquid', False), ('smoked', False), ('liquid', True)):
            with self.subTest(style=style, saver=saver):
                result = self.run_settings(style, saver)
                self.assertTrue(result['frames'])
                for frame in result['frames']:
                    self.assertTrue(frame['ready'], frame)
                    self.assertEqual(frame['liquid'], style == 'liquid' and not saver)
                    self.assertEqual(frame['opacity'], 1 if saver else .63 if style == 'liquid' else .81)
                    self.assertEqual(frame['font'], 'DejaVu Sans')
                    self.assertEqual(frame['saver'], saver)
                    self.assertEqual(frame['animations'], not saver)
                    self.assertEqual(frame['blur'], style == 'liquid' and not saver)

    def test_backend_reconnect_keeps_the_loaded_window_and_theme(self):
        result = self.run_settings('liquid', restart=True)
        self.assertTrue(result['disconnected'])
        self.assertTrue(result['remainedVisible'])
        self.assertTrue(result['visible'])

    def test_initial_backend_failure_shows_a_recoverable_window(self):
        result = self.run_settings('liquid', fail=True)
        self.assertTrue(result['visible'])
        self.assertTrue(result['frames'])
        self.assertFalse(result['frames'][-1]['ready'])

    def test_repeated_gear_requests_queue_the_last_page_without_restarting(self):
        result = self.run_settings('liquid', reopen=True)
        self.assertTrue(result['frames'])
        self.assertTrue(all(frame['ready'] and frame['liquid'] and frame['page'] == 'behavior' for frame in result['frames']))


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'private Wayland Settings startup')
class NativeSettingsStartupCase(unittest.TestCase):
    run_settings = SettingsStartupCase.run_settings

    def test_native_first_frame_and_repeated_gear_requests(self):
        result = self.run_settings('liquid', reopen=True, native=True)
        self.assertTrue(result['frames'])
        self.assertTrue(all(frame['ready'] and frame['liquid'] and frame['blur']
                            and frame['page'] == 'behavior' for frame in result['frames']))
