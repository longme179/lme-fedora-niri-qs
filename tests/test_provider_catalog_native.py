"""Copied-checkout provider faults must settle shell and standalone Settings."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from light_feature_fixture import LightWorld


@unittest.skipUnless(os.environ.get('LME_TEST_LIGHT_FEATURES') == '1', 'private Wayland provider catalog fault checks')
@unittest.skipUnless((Path(__file__).resolve().parents[1]/'scripts/backend_providers.py').exists(),
                     'descriptor backend capability absent on unmodified main')
class NativeProviderCatalogCase(unittest.TestCase):
    def test_invalid_or_unbound_provider_settles_and_retains_legacy_navigation(self):
        for feature, entry, factory in [('keybinds', 'keybind_actions', 'missing'),
                                         ('fileSearch', 'file_search_actions', 'provide')]:
            with self.subTest(feature=feature), tempfile.TemporaryDirectory(prefix='provider-ui-') as temporary:
                world = LightWorld(Path(temporary))
                descriptor = world.root/'config'/f'{feature}.json'
                data = json.loads(descriptor.read_text())
                data['sources'] = list(set(data.get('sources', [])) | {'scripts/'+entry+'.py'})
                data['backend'] = dict(entry='scripts/'+entry+'.py', factory=factory)
                descriptor.write_text(json.dumps(data))
                saved = world.settings.read_bytes()
                for mode in ('demo', 'settings'):
                    with world.launch(mode) as probe:
                        state = probe.wait(lambda s: s['ready'])
                        self.assertIn('appearance', state['pages']); self.assertNotIn('keybinds', state['pages'])
                        if mode == 'settings':
                            self.assertEqual(probe.call('startupPending', target='settings'), 'false')
                            self.assertEqual(probe.call('openPage', 'appearance', target='settings'), 'true')
                            probe.wait(lambda s: s['page'] == 'appearance')
                        else:
                            probe.call('toggle', 'control', target='shell')
                            probe.wait(lambda s: s['panelOpen'] and s['progress'] == 1)
                            probe.call('close', target='shell')
                            probe.wait(lambda s: not s['panelOpen'])
                        probe.log.seek(0)
                        self.assertIn('Feature catalog:', probe.log.read())
                self.assertEqual(world.settings.read_bytes(), saved)
