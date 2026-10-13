"""Screenshot notification routing through real private D-Bus and QML clicks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from test_clipboard import PNG


@unittest.skipUnless(os.environ.get('LME_TEST_ANNOTATION_UI') == '1', 'Enable only in a private Wayland session')
class AnnotationInterfaceCase(unittest.TestCase):
    def test_live_screenshot_toast_launches_editor_with_a_preserved_image_copy(self):
        pointer = os.environ.get('LME_TEST_POINTER')
        if not pointer: raise unittest.SkipTest('Set LME_TEST_POINTER')
        fixture = Path(__file__).resolve().parents[1] / 'shell.qml'
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryFile(mode='w+') as log:
            root = Path(root); config = root / 'config'; (config / 'lme-shell').mkdir(parents=True)
            (config / 'lme-shell/settings.json').write_text(json.dumps({'captureEditor': 'satty', 'clipboardEnabled': False, 'weatherAutoLocation': False}))
            (config / 'user-dirs.dirs').write_text('XDG_PICTURES_DIR="' + str(root / 'Pictures') + '"\n')
            marker = root / 'editor-argv.json'; binary = root / 'bin/satty'; binary.parent.mkdir()
            binary.write_text('#!' + sys.executable + '\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["LME_ANNOTATION_MARKER"]).write_text(json.dumps(sys.argv[1:]))\n')
            binary.chmod(0o700)
            source = root / 'screenshot.png'; source.write_bytes(PNG)
            env = dict(os.environ, LME_SHELL_DEMO='0', LME_SHELL_BACKEND_DEMO='0', LME_ANNOTATION_MARKER=str(marker),
                       XDG_CONFIG_HOME=str(config), XDG_STATE_HOME=str(root / 'state'), PATH=str(binary.parent) + os.pathsep + os.environ['PATH'])
            process = subprocess.Popen(['quickshell', '-p', str(fixture)], env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    reply = subprocess.run(['quickshell', '-p', str(fixture), 'ipc', 'call', 'shell', 'idleStatus'], capture_output=True, text=True, env=env, timeout=4)
                    try: ready = bool(json.loads(reply.stdout))
                    except ValueError: ready = False
                    if ready: break
                    time.sleep(.1)
                self.assertTrue(ready)
                subprocess.run(['busctl', '--user', 'call', 'org.freedesktop.Notifications', '/org/freedesktop/Notifications',
                    'org.freedesktop.Notifications', 'Notify', 'susssasa{sv}i', 'niri', '0', source.as_uri(),
                    'Screenshot captured', '', '0', '0', '15000'], check=True, capture_output=True, env=env, timeout=4)
                time.sleep(.4)
                # The private test output is 1920×1080; hit the toast summary above its Annotate button.
                subprocess.run([pointer, '1750', '108'], check=True, env=env, timeout=4)
                deadline = time.monotonic() + 8
                while not marker.exists() and time.monotonic() < deadline: time.sleep(.1)
                if not marker.exists():
                    log.seek(0); self.fail('Toast did not launch editor: ' + log.read())
                args = json.loads(marker.read_text())
                self.assertEqual(args[0], '-f')
                saved = Path(args[1]); self.assertNotEqual(saved, source)
                self.assertEqual(saved.parent, root / 'Pictures/Screenshots')
                self.assertEqual(saved.read_bytes(), PNG)
                self.assertEqual(source.read_bytes(), PNG)
            finally:
                process.terminate(); process.wait(timeout=8)

    def test_screenshot_notification_opens_annotation_and_ordinary_icons_do_not(self):
        pointer = os.environ.get('LME_TEST_POINTER')
        if not pointer: raise unittest.SkipTest('Set LME_TEST_POINTER')
        fixture = Path(__file__).resolve().parents[1] / 'native-features-demo.qml'
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryFile(mode='w+') as log:
            root = Path(root)
            image = root / 'screenshot with spaces.png'; image.write_bytes(PNG)
            env = dict(os.environ, LME_SHELL_DEMO='0', LME_SHELL_BACKEND_DEMO='1', LME_TEST_FEATURES='1',
                       XDG_CONFIG_HOME=str(root / 'config'), XDG_STATE_HOME=str(root / 'state'))
            process = subprocess.Popen(['quickshell', '-p', str(fixture)], env=env, stdout=log, stderr=log)
            def ipc(method, *args):
                return subprocess.check_output(['quickshell', '-p', str(fixture), 'ipc', 'call', 'featuresFixture', method, *args], env=env, text=True, timeout=4).strip()
            def wait(predicate):
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    try: state = json.loads(ipc('annotationStatus'))
                    except (ValueError, subprocess.CalledProcessError): state = {}
                    if predicate(state): return state
                    time.sleep(.1)
                log.seek(0); raise AssertionError('Annotation state did not settle: ' + str(state) + '\n' + log.read())
            def notify(app, summary):
                reply = subprocess.check_output(['busctl', '--user', 'call', 'org.freedesktop.Notifications',
                    '/org/freedesktop/Notifications', 'org.freedesktop.Notifications', 'Notify', 'susssasa{sv}i',
                    app, '0', image.as_uri(), summary, 'Captured image', '0', '0', '15000'], env=env, text=True, timeout=4)
                return int(reply.split()[1])
            try:
                wait(lambda s: s.get('ready'))
                ordinary = notify('Browser', 'Message')
                state = wait(lambda s: any(e['id'] == ordinary for e in s.get('notifications', [])))
                self.assertEqual(next(e for e in state['notifications'] if e['id'] == ordinary)['imagePath'], '')
                screenshot = notify('niri', 'Screenshot captured')
                state = wait(lambda s: any(e['id'] == screenshot for e in s.get('notifications', [])))
                self.assertEqual(next(e for e in state['notifications'] if e['id'] == screenshot)['imagePath'], image.as_uri())
                ipc('openNotifications'); wait(lambda s: s.get('visible'))
                time.sleep(.2)
                point = json.loads(ipc('buttonPosition', 'notificationAnnotate-' + str(screenshot)))
                subprocess.run([pointer, str(point['x']), str(point['y'])], check=True, env=env, timeout=4)
                state = wait(lambda s: not s.get('visible') and (s.get('lastResult') or {}).get('action') == 'imageAnnotate')
                self.assertTrue(state['lastResult']['ok'])
                sequence = state['lastResult']['sequence']
                screenshot = notify('niri', 'Screenshot captured')
                wait(lambda s: any(e['id'] == screenshot for e in s.get('notifications', [])))
                ipc('openNotifications'); wait(lambda s: s.get('visible'))
                time.sleep(.2)
                point = json.loads(ipc('buttonPosition', 'notificationCard-' + str(screenshot)))
                subprocess.run([pointer, str(point['x']), str(point['y'])], check=True, env=env, timeout=4)
                state = wait(lambda s: not s.get('visible') and (s.get('lastResult') or {}).get('sequence', 0) > sequence and s['lastResult']['action'] == 'imageAnnotate')
                self.assertTrue(state['lastResult']['ok'])
            finally:
                process.terminate(); process.wait(timeout=6)
            log.seek(0)
            for error in ['ReferenceError', 'TypeError', 'Failed to load configuration', 'Unable to assign']:
                self.assertNotIn(error, log.read()); log.seek(0)
