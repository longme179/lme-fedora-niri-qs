"""Current navigation contracts; production remains unchanged for the before run."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from navigation_fixture import session


TITLES = ['Controls', 'Audio', 'Devices', 'Agenda', 'Notifications', 'System']
IDS = ['controls', 'audio', 'devices', 'agenda', 'notifications', 'system']


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is required')
class TabContractCase(unittest.TestCase):
    def test_order_numeric_mapping_and_invalid_numeric_fallback(self):
        with session() as p:
            p.call('open')
            for number, title in enumerate(TITLES):
                p.call('globalNumber', number)
                state = p.wait(lambda s: s['current'] == number and s['selected'] == title)
                self.assertEqual(state['tabs'], TITLES)
                self.assertEqual(state['global'], number)
                if number != 4: self.assertEqual(state['kind'], IDS[number])
            for number in (-1, 99):
                p.call('number', number)
                state = p.wait(lambda s: s['current'] == number and s['kind'] == 'system')
                self.assertEqual(state['global'], number)
                self.assertEqual(state['selected'], '')

    def test_named_env_mapping_and_invalid_name_falls_back_to_controls(self):
        for number, name in [*enumerate(IDS), (0, 'unknown-tab')]:
            with self.subTest(name=name), session(environment={'LME_SHELL_CONTROL_TAB': name}) as p:
                p.call('seed'); p.call('open')
                state = p.wait(lambda s: s['current'] == number and s['selected'] == TITLES[number])
                self.assertEqual(state['unread'], 0 if number == 4 else 7)

    def test_refresh_and_mark_read_guards_keep_the_existing_conditions(self):
        with session() as p:
            p.call('open'); p.wait(lambda s: s['refreshes'] == 1)
            self.assertEqual(p.call('initializedGuard'), 'true')
            p.call('setVisible', 'false')
            self.assertEqual(p.wait(lambda s: True)['refreshes'], 1)
            p.call('setVisible', 'true'); p.wait(lambda s: s['refreshes'] == 2)
            p.call('number', 1); p.call('seed')
            self.assertEqual(p.wait(lambda s: s['current'] == 1)['unread'], 7)
            p.call('number', 2)
            state = p.wait(lambda s: s['refreshes'] == 3)
            self.assertEqual(state['unread'], 7)
            p.call('number', 4)
            state = p.wait(lambda s: s['unread'] == 0)
            self.assertEqual(state['refreshes'], 3)
            self.assertEqual(p.call('backendGuard'), 'true')
            self.assertEqual(p.wait(lambda s: s['current'] == 1)['refreshes'], 3)

    def test_quick_notes_visibility_and_agenda_legacy_fallback(self):
        with session() as p:
            p.call('agendaNumber', 0)
            self.assertTrue(p.wait(lambda s: s['notes'])['notes'])
            p.call('agendaNumber', 1)
            self.assertTrue(p.wait(lambda s: s['tasks'])['tasks'])
            for number in (2, -1, 99):
                p.call('agendaNumber', number)
                self.assertTrue(p.wait(lambda s: s['timer'])['timer'])
            p.call('agendaNumber', 3); p.wait(lambda s: s['editor'])
            p.call('setting', 'quickNotes', 'false')
            state = p.wait(lambda s: not s['notes'] and s['preferences']['quickNotes'] is False)
            self.assertTrue(state['editor'])  # Existing selection survives hiding its tab.
            p.call('agendaNumber', 0)
            self.assertFalse(p.wait(lambda s: not s['editor'])['notes'])


@unittest.skipUnless(os.environ.get('LME_TEST_UPGRADE_UI') == '1', 'private Wayland navigation checks')
class NativeTabCase(unittest.TestCase):
    def routes(self, catalog=None):
        self.assertTrue(os.environ.get('LME_TEST_POINTER'), 'private pointer helper required')
        with session(native=True, catalog=catalog) as p:
            p.call('open'); p.wait(lambda s: s['selected'] == 'Controls')
            for name in ('audio', 'devices', 'agenda', 'system'):
                p.call('setting', 'barGestures', json.dumps({'audio': {'left': name}}))
                p.wait(lambda s: s['preferences'].get('barGestures', {}).get('audio', {}).get('left') == name)
                p.call('closePanels')
                p.click('navigationBar')
                state = p.wait(lambda s: s['current'] == IDS.index(name) and s['kind'] == name)
                self.assertTrue(state['controlOpen'])
                self.assertEqual(state['global'], IDS.index(name))
                self.assertEqual(state['selected'], TITLES[IDS.index(name)])
            p.call('number', 0); p.wait(lambda s: s['kind'] == 'controls')
            p.click('System monitor')
            state = p.wait(lambda s: s['kind'] == 'system')
            self.assertEqual(state['current'], 5)
            self.assertEqual(state['selected'], 'System')
            print('NAVIGATION_ORDER ' + json.dumps(state['tabs']), flush=True)
            p.call('number', 0); p.wait(lambda s: s['selected'] == 'Controls')
            p.call('focus')
            subprocess.run(['wtype', '-M', 'ctrl', '-k', 'Tab', '-m', 'ctrl'], env=p.env, check=True, timeout=4)
            expected = catalog['tabs'][1]['title'] if catalog and 'tabs' in catalog else 'Audio'
            self.assertEqual(p.wait(lambda s: s['selected'] == expected)['selected'], expected)

    def test_gesture_targets_monitor_shortcut_keyboard_and_selection(self):
        self.routes()

    def test_routes_with_reordered_and_inserted_test_catalog_entries(self):
        catalog = json.loads((Path(__file__).resolve().parents[1]/'config/control-grid.json').read_text())
        entries = ['ControlDashboard', 'AudioMixer', 'DeviceControls', 'Agenda', 'NotificationCenter', 'SystemMonitor']
        tabs = [dict(id=id, title=title, entry=entry, legacyIndex=i) for i, (id, title, entry) in enumerate(zip(IDS, TITLES, entries))]
        tabs[0]['refresh'] = tabs[2]['refresh'] = True
        tabs[4]['markRead'] = tabs[5]['fallback'] = True
        extra = dict(id='test-page', title='Test page', entry='AudioMixer', legacyIndex=6)
        # Old hosts ignore the extra metadata; the routing contract stays identical.
        catalog['tabs'] = [tabs[0], tabs[1], extra, tabs[5], tabs[3], tabs[2], tabs[4]]
        self.routes(catalog)
