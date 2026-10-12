"""Persisted corner/outline settings and live connected/island surfaces."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from test_backend import backend, Fixture
from settings_transfer import document, validate_document


class BarStylingCase(Fixture, unittest.TestCase):
    def test_old_settings_keep_pill_defaults_and_new_settings_roundtrip(self):
        self.preferences.set('accent', '#123456')
        corners = {'topLeft': 0, 'topRight': -1, 'bottomLeft': 8, 'bottomRight': 32}
        self.preferences.update({'barCorners': corners, 'barBorderWidth': 0,
                                 'themeOverrides': {'barBorder': '#80112233'}})
        saved = backend.Preferences(self.preferences.path)
        self.assertEqual(saved.values['barCorners'], corners)
        values = validate_document(document(saved.values, 'preset'), backend.validate_preference, backend.DEFAULT_PREFERENCES)
        self.assertEqual(values['barBorderWidth'], 0)
        self.assertEqual(values['barCorners'], corners)
        self.assertEqual(values['themeOverrides']['barBorder'], '#80112233')
        self.assertEqual(backend.DEFAULT_PREFERENCES['barCorners'], dict.fromkeys(corners, -1))
        other = backend.Preferences(self.root/'old.json')
        self.assertEqual(other.values['barBorderWidth'], 1)
        self.assertEqual(other.values['barCorners'], dict.fromkeys(corners, -1))

    def test_malformed_corners_and_outline_do_not_replace_valid_settings(self):
        original = dict(self.preferences.values['barCorners'])
        for value in ({}, [], {**original, 'missing': 0}, {**original, 'topLeft': True},
                      {**original, 'bottomRight': 33}, {**original, 'topRight': -2}):
            with self.assertRaises(ValueError): self.preferences.set('barCorners', value)
        for value in (-1, 5, 1.5, True):
            with self.assertRaises(ValueError): self.preferences.set('barBorderWidth', value)
        self.assertEqual(self.preferences.values['barCorners'], original)
        self.assertFalse(self.preferences.path.exists())


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'opt-in private Wayland bar styling')
class BarStylingUiCase(unittest.TestCase):
    def test_presets_independent_corners_height_clamp_color_and_islands(self):
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
import "qml/panels"
import "qml/settings"
import "qml/services"
import "qml/theme"
ShellRoot {
    function items(item) {
        let result = [item];
        for (const child of item.children || []) result = result.concat(items(child));
        return result;
    }
    Component.onCompleted: Quickshell.watchFiles = false
    FloatingWindow { fullscreen: true
        Bar { id: bar; width: 1100; height: Theme.barHeight; x: 80; y: 10 }
        Flickable { x: 80; y: 100; width: 1000; height: 600; contentHeight: settings.implicitHeight; clip: true
            TopBarPage { id: settings; width: parent.width }
        }
    }
    IpcHandler {
        target: "barTest"
        function state(): string {
            const surfaces = items(bar).filter(c => c.objectName === "barSurface" && c.visible);
            return JSON.stringify({ready: ShellState.backendReady, preset: items(settings).find(c => c.objectName === "barCornerPreset").currentIndex,
                surfaces: surfaces.map(s => ({radii: [s.topLeftRadius, s.topRightRadius, s.bottomLeftRadius, s.bottomRightRadius],
                    width: s.border.width, color: s.border.color.toString(), clip: s.clip}))});
        }
        function preset(index: int): void {
            const selector = items(settings).find(c => c.objectName === "barCornerPreset");
            while (selector.currentIndex < index) selector.incrementCurrentIndex();
            while (selector.currentIndex > index) selector.decrementCurrentIndex();
            selector.activated(index);
        }
        function setting(key: string, value: string): void { ShellState.run("setting", {key: key, value: JSON.parse(value)}); }
    }
}''')
            env = dict(os.environ, LME_SHELL_DEMO='1', XDG_CONFIG_HOME=str(root/'home'),
                       XDG_STATE_HOME=str(root/'state'), XDG_DATA_HOME=str(root/'data'))
            with (root/'gui.log').open('w+') as log:
                process = subprocess.Popen(['quickshell', '-p', str(entry)], env=env, stdout=log, stderr=log)
                def ipc(method, *args):
                    return subprocess.run(['quickshell', '-p', str(entry), 'ipc', 'call', 'barTest', method, *args], env=env, capture_output=True, text=True, timeout=4).stdout.strip()
                def wait(radii, count=1, width=1, color=None):
                    deadline = time.monotonic()+6
                    while time.monotonic() < deadline:
                        try: state = json.loads(ipc('state'))
                        except ValueError: state = {}
                        surfaces = state.get('surfaces', [])
                        if state.get('ready') and len(surfaces) == count and all(s['radii'] == radii and s['width'] == width and not s['clip'] and (color is None or s['color'] == color) for s in surfaces): return state
                        time.sleep(.04)
                    log.seek(0); self.fail(str(state)+'\n'+log.read())
                try:
                    self.assertEqual(wait([21]*4)['preset'], 0)
                    ipc('preset', '2'); self.assertEqual(wait([0, 21, 0, 21])['preset'], 2)
                    ipc('preset', '3'); self.assertEqual(wait([21, 0, 21, 0])['preset'], 3)
                    ipc('setting', 'barCorners', json.dumps({'topLeft': 8, 'topRight': 32, 'bottomLeft': 0, 'bottomRight': -1}))
                    self.assertEqual(wait([8, 21, 0, 21])['preset'], 4)
                    ipc('setting', 'barHeight', '64'); wait([8, 32, 0, 32])
                    ipc('setting', 'barBorderWidth', '0'); wait([8, 32, 0, 32], width=0)
                    ipc('setting', 'themeOverrides', '{"barBorder":"#80112233"}'); wait([8, 32, 0, 32], width=0, color='#80112233')
                    ipc('setting', 'barBorderWidth', '4'); wait([8, 32, 0, 32], width=4, color='#80112233')
                    ipc('setting', 'barStyle', '"islands"'); wait([8, 32, 0, 32], count=3, width=4, color='#80112233')
                    log.seek(0); output = log.read()
                    for problem in ('TypeError', 'ReferenceError', 'Binding loop', 'Unable to assign', 'Failed to load configuration'):
                        self.assertNotIn(problem, output)
                finally:
                    process.terminate(); process.wait(timeout=5)
