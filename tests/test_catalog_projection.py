"""Projection publication is batched; repeated module lookups reuse the registry cache."""
import os
import unittest
from unittest.mock import patch

import catalog_fixture as fixture
from test_catalog_compact import compact


@unittest.skipUnless(os.environ.get('LME_TEST_UPGRADE_UI') == '1', 'private Wayland batched catalog projection')
class NativeCatalogProjectionCase(unittest.TestCase):
    def test_module_lookup_does_not_reproject_and_lazy_reads_do_not_republish(self):
        def prepare(root):
            compact(root)
            path = root/'qml/services/FeatureCatalog.qml'
            text = path.read_text().replace('    id: root\n',
                '    id: root\n    property var metrics: ({calls: 0, publications: 0})\n    onDataChanged: if (metrics) metrics.publications++\n')
            text = text.replace('function project(kind, legacy, key, includeDisabled = false) {',
                'function project(kind, legacy, key, includeDisabled = false) {\n        metrics.calls++;')
            path.write_text(text)
        qml = fixture.QML.replace('bars: BarRegistry.modules', 'settled: FeatureCatalog.settled, publications: FeatureCatalog.metrics.publications, heavy: FeatureCatalog.descriptors.catalogFixture || null, bars: BarRegistry.modules')
        qml = qml.replace('function entries(): void', '''function lookup(): int {
            const before = FeatureCatalog.metrics.calls;
            for (let i = 0; i < 100; i++) BarRegistry.info(i % 2 ? "catalogFixture" : "audio");
            return FeatureCatalog.metrics.calls-before;
        }
        function heavy(): void { FeatureCatalog.descriptor("catalogFixture"); }
        function entries(): void''')
        with patch.object(fixture, 'QML', qml), fixture.session(native=True, prepare=prepare) as probe:
            state = probe.wait(lambda state: state['settled'] and len(state['bars']) == 20)
            self.assertEqual(probe.call('lookup'), '0')
            self.assertLessEqual(state['publications'], 2)
            probe.call('heavy')
            later = probe.wait(lambda state: state['heavy'] is not None)
            self.assertEqual(later['publications'], state['publications'])
            self.assertEqual(probe.call('lookup'), '0')
