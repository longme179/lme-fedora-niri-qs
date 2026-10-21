"""Position and inert metadata contracts precede the Clipboard conversion."""
import json
from pathlib import Path
import tempfile
import unittest

import feature_catalog as reader
from catalog_fixture import inject


@unittest.skipUnless('after' in reader.FIELDS['bar'], 'M4b position metadata not implemented on baseline')
class CatalogPositionCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in ('config', 'qml/bar', 'qml/settings', 'qml/panels'):
            (self.root/directory).mkdir(parents=True, exist_ok=True)
        self.descriptor = inject(self.root)
        self.path = self.root/'config/feature-fixture.json'
        self.index = self.root/'config/features.json'

    def save(self):
        self.path.write_text(json.dumps(self.descriptor))

    def test_anchor_validation_including_disabled_self_cycles_and_missing(self):
        for after in ('missing', 'catalogFixture', '../bad'):
            with self.subTest(after=after):
                self.descriptor['bar']['after'] = after; self.save()
                with self.assertRaises(reader.CatalogError):
                    reader.load_catalog(self.root, legacy={'bar': ['first']})
        self.descriptor['bar']['after'] = 'first'; self.save()
        data = reader.load_catalog(self.root, legacy={'bar': ['first']})
        self.assertEqual(data['bar'][0]['after'], 'first')
        index = json.loads(self.index.read_text()); index['features'][0]['enabled'] = False
        self.index.write_text(json.dumps(index))
        self.descriptor['bar']['after'] = 'missing'; self.save()
        with self.assertRaises(reader.CatalogError): reader.load_catalog(self.root, legacy={'bar': ['first']})
        self.descriptor['bar']['after'] = 'second'; self.save()
        second = dict(id='second', bar=dict(self.descriptor['bar'], id='second', after='catalogFixture'))
        (self.root/'config/second.json').write_text(json.dumps(second))
        index['features'].append(dict(id='second', descriptor='config/second.json', enabled=True))
        self.index.write_text(json.dumps(index))
        with self.assertRaises(reader.CatalogError): reader.load_catalog(self.root)

    def test_new_presentation_resources_are_contained_and_metadata_is_inert(self):
        self.descriptor.update(panel=dict(id='catalogFixture', entry='qml/panels/CatalogFixture.qml', centered=True, scrim=.4),
            bootstrap=dict(id='catalogFixture', entry='qml/panels/CatalogFixture.qml'),
            gesture=dict(id='catalogFixture', title='Fixture', after='launchpad'),
            preferenceMetadata={'clipboardEnabled': dict(type='boolean', default=True),
                                'clipboardLimit': dict(type='integer', default=100, min=20, max=500)})
        self.save(); data = reader.load_catalog(self.root, setting_keys=['clipboardEnabled', 'clipboardLimit'])
        self.assertNotIn('clipboardEnabled', data['preferences'])
        self.assertEqual(data['preferenceMetadata']['clipboardLimit']['max'], 500)
        self.assertEqual(data['panel'][0]['scrim'], .4)
        self.descriptor['bootstrap']['entry'] = '../outside.qml'; self.save()
        with self.assertRaises(reader.CatalogError): reader.load_catalog(self.root)

    def test_active_schema_collision_and_duplicate_ui_rules_are_not_weakened(self):
        self.descriptor['preferences']['clipboardEnabled'] = dict(type='boolean', default=True); self.save()
        with self.assertRaisesRegex(reader.CatalogError, 'Duplicate setting in legacy'):
            reader.load_catalog(self.root, setting_keys=['clipboardEnabled'])
        self.descriptor['preferences'].pop('clipboardEnabled')
        self.descriptor['gesture'] = dict(id='catalogFixture', title='Fixture'); self.save()
        with self.assertRaisesRegex(reader.CatalogError, 'legacy'):
            reader.load_catalog(self.root, legacy={'gesture': ['catalogFixture']})

    def test_startup_extensions_match_descriptor_and_preserve_page_admission(self):
        self.descriptor['bar']['after'] = 'first'
        self.descriptor['panel'] = dict(id='catalogFixture', entry='qml/panels/CatalogFixture.qml', centered=True)
        self.save(); index = json.loads(self.index.read_text())
        index['features'][0]['startup'] = {kind: self.descriptor[kind] for kind in ('bar', 'panel', 'settingsPage')}
        self.index.write_text(reader.canonical_index(index))
        data = reader.load_catalog(self.root, legacy={'bar': ['first']})
        self.assertEqual(data['panel'][0]['id'], 'catalogFixture')
        index['features'][0]['startup']['bar']['after'] = 'other'; self.index.write_text(json.dumps(index))
        with self.assertRaisesRegex(reader.CatalogError, 'Conflicting startup'): reader.load_catalog(self.root)

    def test_existing_legacy_sources_gate_all_namespaces_before_bootstrap(self):
        if not hasattr(reader, 'legacy_ids'): self.skipTest('M4b all-namespace legacy adapter absent before extraction')
        (self.root/'qml/services').mkdir()
        (self.root/'qml/services/ShellState.qml').write_text('QtObject { readonly property var legacyPanels: ["control", "launcher"] }')
        (self.root/'qml/settings/SettingsRegistry.qml').write_text('QtObject { readonly property var legacyPages: [{key: "appearance"}] }')
        self.descriptor.update(panel=dict(id='control', entry='qml/panels/CatalogFixture.qml'),
                               bootstrap=dict(id='catalogFixture', entry='qml/panels/CatalogFixture.qml'))
        self.save(); legacy = reader.legacy_ids(self.root)
        self.assertEqual(legacy['panel'], ['control', 'launcher'])
        with self.assertRaisesRegex(reader.CatalogError, 'Duplicate panel ID in legacy'):
            reader.load_catalog(self.root, legacy=legacy)
        self.descriptor['panel']['id'] = 'catalogFixture'
        self.descriptor['settingsPage']['after'] = 'missingPage'; self.save()
        with self.assertRaisesRegex(reader.CatalogError, 'Missing settingsPage anchor'):
            reader.load_catalog(self.root, legacy=legacy)
