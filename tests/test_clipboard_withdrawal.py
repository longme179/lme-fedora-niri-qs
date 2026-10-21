"""Withdrawal preserves user data; a second entry does not change host switches."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from clipboard_slice_fixture import ROOT, World

CONVERTED = (ROOT/'config/clipboard.json').exists()


@unittest.skipUnless(CONVERTED, 'M4b descriptor absent on baseline')
class ClipboardOwnershipCase(unittest.TestCase):
    def test_host_registration_removal_and_metadata_only_schema(self):
        descriptor = json.loads((ROOT/'config/clipboard.json').read_text())
        self.assertNotIn('preferences', descriptor)
        self.assertEqual(set(descriptor['preferenceMetadata']), {'clipboardEnabled', 'clipboardImages', 'clipboardLimit'})
        self.assertEqual(descriptor['preferenceMetadata']['clipboardLimit'], dict(type='integer', default=100, min=20, max=500))
        for path in ('qml/settings/SettingsView.qml', 'qml/services/ShellState.qml', 'qml/settings/qmldir'):
            self.assertNotIn('clipboard', (ROOT/path).read_text().lower(), path)
        for path, start, end in [('qml/bar/BarRegistry.qml', 'legacyModules:', '\n    function'),
                                 ('qml/settings/SettingsRegistry.qml', 'legacyPages:', '\n    function')]:
            self.assertNotIn('clipboard', (ROOT/path).read_text().split(start, 1)[1].split(end, 1)[0])
        self.assertNotIn('Clipboard', (ROOT/'shell.qml').read_text())
        source = (ROOT/'scripts/desktop_backend.py').read_text().split('BAR_MODULES = ', 1)[1].split('FEATURE_CATALOG_ERROR', 1)[0]
        self.assertNotIn('clipboard', source)
        self.assertIn('singleton ClipboardState 1.0 ClipboardState.qml', (ROOT/'qml/services/qmldir').read_text())


@unittest.skipUnless(CONVERTED and os.environ.get('LME_TEST_CLIPBOARD_UI') == '1',
                     'private Wayland converted Clipboard withdrawal')
class NativeWithdrawalCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='clip-withdraw-'); self.addCleanup(self.temp.cleanup)
        self.world = World(Path(self.temp.name))

    def toggle(self, enabled):
        path = self.world.root/'config/features.json'; data = json.loads(path.read_text())
        next(record for record in data['features'] if record['id'] == 'clipboard')['enabled'] = enabled
        path.write_text(json.dumps(data))

    def test_disable_preserves_layout_preferences_schema_history_and_reenable(self):
        layout = dict(left=['launcher'], center=['activity'], right=['clipboard', 'settings'])
        prefs = json.loads(self.world.settings.read_text()); prefs['barLayout'] = layout
        self.world.settings.write_text(json.dumps(prefs))
        original = self.world.settings.read_bytes()
        history = self.world.home/'state/lme-shell/clipboard'
        files = {path.relative_to(history): path.read_bytes() for path in history.rglob('*') if path.is_file()}
        schema = (self.world.root/'config/clipboard.json').read_bytes()
        self.toggle(False)
        with self.world.launch() as probe:
            state = probe.wait(lambda state: state['ready'])
            self.assertNotIn('clipboard', state['bars']); self.assertNotIn('clipboard', state['pages'])
            self.assertNotIn('clipboard', state['gestures']); self.assertFalse(state['started'])
            self.assertEqual(state['preferences']['barLayout'], layout)
            probe.call('toggle', 'clipboard', target='shell')
            self.assertFalse(probe.wait(lambda state: True)['open'])
            self.assertEqual(probe.call('point', 'barAction-clipboard'), 'null')
            self.assertEqual(self.world.workers(), [])
            reply = subprocess.run([str(self.world.root/'scripts/settings.sh'), '--page', 'clipboard'],
                env=probe.env, capture_output=True, text=True, timeout=5)
            self.assertEqual((reply.returncode, reply.stderr), (2, 'Error: unknown settings page: clipboard\n'))
        with self.world.launch('settings', page='appearance') as probe:
            self.assertEqual(probe.call('search', 'clipboard'), 'true')
            self.assertNotIn('clipboard', probe.wait(lambda state: state['ready'])['pages'])
            self.assertEqual(self.world.workers(), [])
        self.assertEqual(self.world.settings.read_bytes(), original)
        self.assertEqual({path.relative_to(history): path.read_bytes() for path in history.rglob('*') if path.is_file()}, files)
        self.assertEqual((self.world.root/'config/clipboard.json').read_bytes(), schema)
        self.toggle(True)
        with self.world.launch() as probe:
            probe.wait(lambda state: state['workerReady'] and state['count'] == 2)
            probe.click('barAction-clipboard'); probe.wait(lambda state: state['open'] and state['history'])
            self.assertEqual(len(self.world.workers()), 1)
        with self.world.launch('settings') as probe:
            self.assertEqual(probe.call('page'), 'clipboard')
            self.assertEqual(len(self.world.workers()), 1)

    def test_second_entry_needs_only_own_files_and_index_record(self):
        root = self.world.root
        before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}
        folder = root/'qml/panels/SlicePeer'; folder.mkdir()
        (folder/'Bar.qml').write_text('import QtQuick\nimport "../../bar"\nActionBarButton { moduleId: "slicePeer" }\n')
        (folder/'Panel.qml').write_text('import QtQuick\nItem { implicitWidth: 400; implicitHeight: 250; Text { text: "slicePeerPanel" } }\n')
        (folder/'Page.qml').write_text('import QtQuick\nItem { implicitWidth: 400; implicitHeight: 250; Text { text: "slicePeerPage" } }\n')
        (folder/'Bootstrap.qml').write_text('import QtQuick\nimport "../../services"\nQtObject { Component.onCompleted: ShellState.statusMessage = "slicePeerStarted" }\n')
        descriptor = dict(id='slicePeer', bar=dict(id='slicePeer', title='Slice peer', icon='applications', entry='qml/panels/SlicePeer/Bar.qml'),
            panel=dict(id='slicePeer', entry='qml/panels/SlicePeer/Panel.qml', centered=True),
            settingsPage=dict(key='slicePeer', title='Slice peer', description='slicePeerPage', keywords='slicePeer', icon='settings', entry='qml/panels/SlicePeer/Page.qml'),
            bootstrap=dict(id='slicePeer', entry='qml/panels/SlicePeer/Bootstrap.qml'))
        path = root/'config/slicePeer.json'; path.write_text(json.dumps(descriptor))
        index = root/'config/features.json'; data = json.loads(index.read_text())
        data['features'].append(dict(id='slicePeer', descriptor='config/slicePeer.json', enabled=True,
            startup={key: value for key, value in descriptor.items() if key != 'id'}))
        from feature_catalog import canonical_index
        index.write_text(canonical_index(data))
        prefs = json.loads(self.world.settings.read_text()); prefs['barLayout'] = dict(left=['slicePeer'], center=[], right=[])
        self.world.settings.write_text(json.dumps(prefs))
        changed = [name for name, content in before.items() if (root/name).read_bytes() != content]
        self.assertEqual(changed, ['config/features.json'])
        with self.world.launch() as probe:
            self.assertIn('slicePeer', probe.wait(lambda state: state['ready'])['bars'])
            probe.wait(lambda state: state['status'] == 'slicePeerStarted')
            probe.click('barAction-slicePeer')
            probe.wait(lambda state: state['panelKind'] == 'slicePeer' and state['panelOpen'])
            self.assertNotEqual(probe.call('point', 'slicePeerPanel'), 'null')
            probe.call('toggle', 'slicePeer', target='shell')
            probe.wait(lambda state: not state['panelOpen'])
        with self.world.launch('settings', page='slicePeer') as probe:
            self.assertEqual(probe.call('startupPending', target='settings'), 'false')
            self.assertNotEqual(probe.call('point', 'slicePeerPage'), 'null')
