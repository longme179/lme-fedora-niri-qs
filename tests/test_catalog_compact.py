"""Inline startup presentation is identical; heavy metadata is fetched on demand."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import catalog_fixture as fixture
import test_feature_catalog as contracts


def compact(root, enabled=True):
    descriptor = fixture.inject(root, enabled)
    path = root/'config/features.json'
    index = json.loads(path.read_text())
    index['features'][0]['startup'] = {kind: descriptor.pop(kind) for kind in ('bar', 'settingsPage', 'controlTab')}
    path.write_text(json.dumps(index))
    (root/'config/feature-fixture.json').write_text(json.dumps(descriptor))


class CompactCatalogCase(unittest.TestCase):
    def test_inline_matches_legacy_descriptor_projection_and_schema(self):
        reader = contracts.CatalogContractCase().reader()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contracts.CatalogContractCase().fixture(root)
            expected = reader.load_catalog(root)
            compact(root)
            self.assertEqual(reader.load_catalog(root), expected)

    def test_conflicting_or_escaping_inline_metadata_is_rejected(self):
        reader = contracts.CatalogContractCase().reader()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contracts.CatalogContractCase().fixture(root); compact(root)
            path = root/'config/features.json'; index = json.loads(path.read_text())
            descriptor_path = root/'config/feature-fixture.json'
            descriptor = json.loads(descriptor_path.read_text())
            descriptor['bar'] = dict(index['features'][0]['startup']['bar'], title='Conflicting title')
            descriptor_path.write_text(json.dumps(descriptor))
            with self.assertRaises(reader.CatalogError): reader.load_catalog(root)
            descriptor.pop('bar'); descriptor_path.write_text(json.dumps(descriptor))
            index['features'][0]['startup']['bar']['entry'] = '../outside.qml'
            path.write_text(json.dumps(index))
            with self.assertRaises(reader.CatalogError): reader.load_catalog(root)


@unittest.skipUnless(os.environ.get('LME_TEST_UPGRADE_UI') == '1', 'private Wayland lazy catalog')
class NativeCompactCatalogCase(unittest.TestCase):
    def check_lazy(self, enabled):
        qml = fixture.QML.replace('bars: BarRegistry.modules',
            'catalogReady: FeatureCatalog.settled && FeatureCatalog.verified, heavy: FeatureCatalog.descriptors.catalogFixture || null, heavyCount: Object.keys(FeatureCatalog.descriptors).length, bars: BarRegistry.modules')
        qml = qml.replace('function entries(): void',
            'function requestDescriptor(): bool { return FeatureCatalog.descriptor("catalogFixture") !== null; }\n        function entries(): void')
        with patch.object(fixture, 'QML', qml), fixture.session(native=True, prepare=lambda root: compact(root, enabled)) as probe:
            state = probe.wait(lambda state: state['catalogReady'] and len(state['pages']) == (17 if enabled else 16))
            self.assertIsNone(state['heavy'])
            self.assertEqual(state['heavyCount'], 0)
            self.assertEqual('catalogFixture' in [item['id'] for item in state['bars']], enabled)
            self.assertEqual(probe.call('requestDescriptor'), 'false')
            state = probe.wait(lambda state: state['heavy'] is not None)
            self.assertTrue(state['heavy']['preferences']['catalogFixtureSetting']['default'])
            self.assertEqual(state['heavyCount'], 1)
            self.assertEqual(probe.call('requestDescriptor'), 'true')

    def test_enabled_entry_projects_without_reading_heavy_descriptor_until_use(self):
        self.check_lazy(True)

    def test_disabled_entry_keeps_lazy_schema_without_projecting_ui(self):
        self.check_lazy(False)
