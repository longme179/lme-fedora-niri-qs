"""Legacy parity first; new data-only reader and copied-checkout contracts."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from catalog_fixture import REPO, inject, session


class CatalogContractCase(unittest.TestCase):
    def reader(self):
        path = REPO/'scripts/feature_catalog.py'
        if not path.exists(): self.skipTest('M4a reader absent on unmodified baseline')
        spec = importlib.util.spec_from_file_location('catalog_contract_reader', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    @unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is required')
    def test_empty_catalog_preserves_exact_bar_page_tab_metadata_and_defaults(self):
        expected = json.loads((REPO/'tests/fixtures/catalog-legacy.json').read_text())
        with session() as probe:
            state = probe.wait(lambda state: len(state['pages']) == len(expected['pages']))
            for kind in ('bars', 'pages'):
                state[kind] = [{key: value for key, value in entry.items()
                                if key not in ('entry', 'after')} for entry in state[kind]]
            self.assertEqual({key: state[key] for key in expected}, expected)

    def test_cli_invalid_page_message_exit_and_missing_argument_are_unchanged(self):
        for args, message in [(['--page', 'unknown-page'], 'Error: unknown settings page: unknown-page\n'),
                              (['--page'], 'Error: --page requires a page name.\n')]:
            result = subprocess.run([str(REPO/'scripts/settings.sh'), *args], capture_output=True, text=True)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (2, '', message))

    def fixture(self, root):
        for folder in ('config', 'qml/bar', 'qml/settings', 'qml/panels'): (root/folder).mkdir(parents=True, exist_ok=True)
        return inject(root)

    def test_empty_index_and_disabled_ids_retain_schema_but_hide_ui(self):
        reader = self.reader()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            data = json.loads((root/'config/features.json').read_text()); data['features'][0]['enabled'] = False
            (root/'config/features.json').write_text(json.dumps(data))
            result = reader.load_catalog(root)
            self.assertEqual(result['ids']['bar'], ['catalogFixture'])
            self.assertEqual(result['bar'], [])
            self.assertEqual(result['preferences']['catalogFixtureSetting']['default'], True)
            (root/'config/features.json').write_text('{"version":1,"features":[]}')
            self.assertEqual(reader.load_catalog(root)['settingsPage'], [])

    def test_rejects_invalid_version_shapes_and_duplicate_json_keys(self):
        reader = self.reader()
        invalid = ['{"version":2,"features":[]}', '{"version":true,"features":[]}',
            '{"version":1,"features":{}}', '{"version":1,"version":1,"features":[]}',
            '{"version":1,"features":[{"id":"../bad","enabled":true,"descriptor":"x"}]}',
            '{"version":1,"features":[],"callback":"evil()"}', '{"version":NaN,"features":[]}']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            for text in invalid:
                with self.subTest(text=text):
                    (root/'config/features.json').write_text(text)
                    with self.assertRaises(reader.CatalogError): reader.load_catalog(root)

    def test_rejects_duplicate_feature_projection_and_preference_ids(self):
        reader = self.reader()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); descriptor = self.fixture(root)
            index = json.loads((root/'config/features.json').read_text())
            index['features'] *= 2
            (root/'config/features.json').write_text(json.dumps(index))
            with self.assertRaisesRegex(reader.CatalogError, 'Duplicate'): reader.load_catalog(root)
            index['features'][1] = {'id': 'second', 'descriptor': 'config/second.json', 'enabled': False}
            (root/'config/features.json').write_text(json.dumps(index))
            descriptor['id'] = 'second'; (root/'config/second.json').write_text(json.dumps(descriptor))
            with self.assertRaisesRegex(reader.CatalogError, 'Duplicate'): reader.load_catalog(root)
            descriptor.pop('bar'); descriptor.pop('settingsPage'); descriptor.pop('controlTab')
            (root/'config/second.json').write_text(json.dumps(descriptor))
            with self.assertRaisesRegex(reader.CatalogError, 'Duplicate setting'): reader.load_catalog(root)

    def test_rejects_legacy_collisions_even_when_disabled(self):
        reader = self.reader()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            index = json.loads((root/'config/features.json').read_text()); index['features'][0]['enabled'] = False
            (root/'config/features.json').write_text(json.dumps(index))
            for kind in ('bar', 'settingsPage', 'controlTab'):
                with self.subTest(kind=kind), self.assertRaisesRegex(reader.CatalogError, 'legacy'):
                    reader.load_catalog(root, legacy={kind: ['catalogFixture']})
            with self.assertRaisesRegex(reader.CatalogError, 'setting'):
                reader.load_catalog(root, setting_keys=['catalogFixtureSetting'])

    def test_rejects_missing_resources_traversal_absolute_and_symlink_escape(self):
        reader = self.reader()
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory); descriptor = self.fixture(root)
            target = Path(outside)/'outside.qml'; target.write_text('import QtQuick\nItem {}')
            (root/'qml/bar/escape.qml').symlink_to(target)
            for path in ('qml/bar/missing.qml', '../outside.qml', str(target), 'qml/bar/escape.qml', 'qml/bar/../bar/CatalogFixture.qml'):
                with self.subTest(path=path):
                    descriptor['bar']['entry'] = path
                    (root/'config/feature-fixture.json').write_text(json.dumps(descriptor))
                    with self.assertRaises(reader.CatalogError): reader.load_catalog(root)
            descriptor['bar']['entry'] = 'qml/bar/CatalogFixture.qml'; descriptor['sources'] = ['missing.py']
            (root/'config/feature-fixture.json').write_text(json.dumps(descriptor))
            with self.assertRaises(reader.CatalogError): reader.load_catalog(root)
            for path in ('../descriptor.json', str(root/'config/feature-fixture.json')):
                (root/'config/features.json').write_text(json.dumps({'version': 1, 'features': [
                    {'id': 'catalogFixture', 'enabled': True, 'descriptor': path}]}))
                with self.assertRaises(reader.CatalogError): reader.load_catalog(root)
            (root/'config/features.json').unlink()
            index = Path(outside)/'features.json'; index.write_text('{"version":1,"features":[]}')
            (root/'config/features.json').symlink_to(index)
            with self.assertRaises(reader.CatalogError): reader.load_catalog(root)

    def test_rejects_mismatched_descriptor_and_executable_metadata(self):
        reader = self.reader()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); descriptor = self.fixture(root)
            for key, value in [('id', 'wrong'), ('callback', 'evil()'), ('controlTab', {'id': 'bad', 'entry': 'scripts/evil.py'})]:
                with self.subTest(key=key):
                    changed = dict(descriptor, **{key: value})
                    (root/'config/feature-fixture.json').write_text(json.dumps(changed))
                    with self.assertRaises(reader.CatalogError): reader.load_catalog(root)


@unittest.skipUnless(os.environ.get('LME_TEST_UPGRADE_UI') == '1', 'private Wayland catalog injection')
class NativeCatalogCase(unittest.TestCase):
    def setUp(self):
        if not (REPO/'scripts/feature_catalog.py').exists(): self.skipTest('M4a reader absent on unmodified baseline')

    def test_copied_checkout_injects_bar_page_tab_without_host_edits(self):
        with session(native=True, prepare=inject) as probe:
            state = probe.wait(lambda state: any(page['key'] == 'catalogFixture' for page in state['pages']))
            self.assertEqual(state['bars'][-1]['id'], 'catalogFixture')
            self.assertEqual(state['tabs'][-1]['id'], 'catalogFixture')
            probe.call('entries')
            probe.wait(lambda state: state['barLoaded'] and state['pageLoaded'])
            probe.call('control')
            probe.wait(lambda state: state['tabLoaded'])
            (probe.root/'config/features.json').write_text('{"version":1,"features":[]}')
            self.assertEqual(probe.wait(lambda state: True)['bars'][-1]['id'], 'catalogFixture')
            inject(probe.root)
            reply = subprocess.run([str(probe.root/'scripts/settings.sh'), '--page', 'catalogFixture', '--daemonize'],
                env=probe.env, capture_output=True, text=True, timeout=15)
            self.assertEqual(reply.returncode, 0, reply.stderr)
            entry = str(probe.root/'settings-demo.qml')
            try:
                deadline = time.monotonic() + 12
                confirmed = False
                while time.monotonic() < deadline:
                    reply = subprocess.run(['quickshell', '-p', entry, 'ipc', 'call', 'settings', 'openPage', 'catalogFixture'],
                        env=probe.env, capture_output=True, text=True, timeout=4)
                    if reply.stdout.strip() == 'true': confirmed = True; break
                    time.sleep(.03)
                self.assertTrue(confirmed, reply.stdout + reply.stderr)
                pending = subprocess.check_output(['quickshell', '-p', entry, 'ipc', 'call', 'settings', 'startupPending'],
                    env=probe.env, text=True, timeout=4).strip()
                self.assertEqual(pending, 'false')
            finally:
                subprocess.run(['quickshell', '-p', entry, 'kill'], env=probe.env, capture_output=True, timeout=5)

    def test_copied_checkout_disabled_entry_retains_identity_without_ui(self):
        with session(native=True, prepare=lambda root: inject(root, False)) as probe:
            state = probe.wait(lambda state: len(state['bars']) == 19)
            self.assertNotIn('catalogFixture', [page['key'] for page in state['pages']])
            reply = subprocess.run([str(probe.root/'scripts/settings.sh'), '--page', 'catalogFixture'],
                env=probe.env, capture_output=True, text=True, timeout=5)
            self.assertEqual((reply.returncode, reply.stderr), (2, 'Error: unknown settings page: catalogFixture\n'))
