"""Native position validation orders all IDs before filtering disabled entries."""
import json
import os
import unittest
from unittest.mock import patch

import catalog_fixture as fixture
import feature_catalog as reader


@unittest.skipUnless('after' in reader.FIELDS['bar'], 'M4b position metadata absent on baseline')
@unittest.skipUnless(os.environ.get('LME_TEST_UPGRADE_UI') == '1', 'private Wayland catalog position checks')
class NativePositionCase(unittest.TestCase):
    def prepare(self, root):
        descriptor = fixture.inject(root)
        descriptor['bar']['after'] = 'privacy'
        path = root/'config/feature-fixture.json'; path.write_text(json.dumps(descriptor))
        index = root/'config/features.json'; data = json.loads(index.read_text())
        data['features'][0]['startup']['bar']['after'] = 'privacy'
        for ident, after, enabled in [('peerSecond', 'privacy', True), ('peerHidden', 'catalogFixture', False),
                                      ('peerChild', 'peerHidden', True)]:
            bar = dict(descriptor['bar'], id=ident, after=after)
            relative = 'config/'+ident+'.json'
            (root/relative).write_text(json.dumps(dict(id=ident, bar=bar)))
            data['features'].append(dict(id=ident, descriptor=relative, enabled=enabled, startup=dict(bar=bar)))
        index.write_text(reader.canonical_index(data))

    def test_same_anchor_index_order_and_hidden_anchor_descendant(self):
        qml = fixture.QML.replace('bars: BarRegistry.modules', 'known: BarRegistry.knownModules, bars: BarRegistry.modules')
        with patch.object(fixture, 'QML', qml), fixture.session(native=True, prepare=self.prepare) as probe:
            state = probe.wait(lambda state: any(item['id'] == 'peerChild' for item in state['bars']))
            ids = [item['id'] for item in state['bars']]
            peers = ['catalogFixture', 'peerSecond', 'peerHidden', 'peerChild']
            self.assertEqual([ident for ident in ids if ident in peers], ['catalogFixture', 'peerChild', 'peerSecond'])
            self.assertIn('peerHidden', [item['id'] for item in state['known']])
            expected = json.loads((fixture.REPO/'tests/fixtures/catalog-legacy.json').read_text())
            self.assertEqual([ident for ident in ids if ident not in peers], [item['id'] for item in expected['bars']])

    def test_missing_page_anchor_settles_with_legacy_only_diagnostic(self):
        def prepare(root):
            descriptor = fixture.inject(root)
            descriptor['settingsPage']['after'] = 'missingPage'
            (root/'config/feature-fixture.json').write_text(json.dumps(descriptor))
            index = root/'config/features.json'; data = json.loads(index.read_text())
            data['features'][0]['startup']['settingsPage']['after'] = 'missingPage'
            index.write_text(reader.canonical_index(data))
        qml = fixture.QML.replace('bars: BarRegistry.modules', 'error: FeatureCatalog.error, bars: BarRegistry.modules')
        with patch.object(fixture, 'QML', qml), fixture.session(native=True, prepare=prepare) as probe:
            state = probe.wait(lambda state: bool(state['error']))
            self.assertIn('Missing settingsPage anchor', state['error'])
            legacy = fixture.legacy_expected()
            self.assertEqual(state['pages'], legacy['pages'])
            self.assertEqual(state['bars'], legacy['bars'])
