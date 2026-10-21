"""Broken catalogs fall back to usable legacy UI without a stuck startup barrier."""
import json
import os
import unittest

from catalog_failure_fixture import FAULTS, REPO, session


@unittest.skipUnless(os.environ.get('LME_TEST_UPGRADE_UI') == '1', 'private Wayland catalog failures')
class NativeCatalogFailureCase(unittest.TestCase):
    def check_fault(self, mode, fault):
        legacy = json.loads((REPO/'tests/fixtures/catalog-legacy.json').read_text())
        with session(mode, fault) as probe:
            state = probe.wait(lambda state: state['ready'] and state['settled'] and bool(state['error']))
            self.assertIn('Feature catalog:', state['status'])
            self.assertEqual(state['bars'], [item['id'] for item in legacy['bars']])
            self.assertEqual(state['pages'], [item['key'] for item in legacy['pages']])
            self.assertEqual(state['tabs'], [item['id'] for item in legacy['tabs']])
            self.assertIsNone(probe.process.poll())
            if mode == 'settings':
                probe.wait(lambda state: state['ready'] and bool(state['error']))
                self.assertEqual(probe.ipc('settings', 'openPage', 'appearance'), 'true')
                self.assertEqual(probe.ipc('settings', 'startupPending'), 'false')
                self.assertEqual(probe.ipc('settings', 'openPage', 'clipboard'), 'true')
                probe.wait(lambda state: state['page'] == 'clipboard')
            else:
                probe.ipc('shell', 'toggle', 'control')
                probe.wait(lambda state: state['control'])
                probe.ipc('shell', 'close')
                probe.wait(lambda state: not state['control'])
            probe.log.seek(0)
            self.assertIn('Feature catalog:', probe.log.read())


def case(mode, fault):
    def test(self): self.check_fault(mode, fault)
    return test


for _mode in ('shell', 'settings'):
    for _fault in FAULTS:
        setattr(NativeCatalogFailureCase, 'test_'+_mode+'_'+_fault, case(_mode, _fault))
