"""Golden coordinator contracts captured before M7a; fake I/O in disposable roots."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from test_backend import Fixture, FakeRunner, backend
from action_test_helpers import complete_action

BT = '/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF'
DEMO = 'Demo preview: no system command executed'
CASES = {
 'local': [('calculate', {'query': '2+3*4'}), ('calculate', {'query': '__import__("os")'}),
           ('calculate', {'query': None}), ('copyText', {'text': 'hi λ'}), ('copyText', {'text': 2}),
           ('notificationSave', {'entries': []}), ('notificationSave', {'entries': [dict(id='one', appName='App', summary='hello', body='body', timestamp=123, urgency=8), {'bad': True}]}),
           ('notificationSave', {'entries': {}}), ('notesInit', {})],
 'audio': [('volume', {'value': v}) for v in (0, 100, 12.5, True, -1, 101, float('nan'), float('inf'), '20')] +
          [('volume', {'delta': v}) for v in (-100, 0, 100, -101, True)] +
          [('mute', {}), ('micVolume', {'value': 33}), ('micVolume', {'value': False}),
           ('micMute', {}), ('brightness', {'value': 1}), ('brightness', {'value': 70}), ('brightness', {'value': 0}),
           ('bluetoothToggle', {}), ('bluetoothDevice', {'path': BT, 'connected': False}),
           ('bluetoothDevice', {'path': BT, 'connected': 1}), ('bluetoothDevice', {'path': '/bad', 'connected': True})],
 'windows': [('launch', {'id': 'kitty.desktop'}), ('launch', {'id': 'terminal.desktop'}),
             ('launch', {'id': 'missing'}), ('launch', {'id': []}), ('fileOpen', {'path': '$ROOT/file.txt'}),
             ('fileOpen', {'path': '$ROOT/missing'}), ('nativeOverview', {})] +
            [(a, {'id': v}) for a in ('focusWindow', 'workspace') for v in (2, 99, True, '2', -1)] +
            [('moveWindow', {'id': 1, 'workspaceId': 2}), ('moveWindow', {'id': 99, 'workspaceId': 2}), ('moveWindow', {'id': 1, 'workspaceId': False})],
 'appearance': [('appearanceSave', {'name': 'Mine'}), ('appearanceApply', {'name': 'mine'}),
                ('appearanceDelete', {'name': 'Mine'}), ('appearanceDelete', {'name': 'Dracula'}),
                ('appearanceSave', {'name': 'Dracula'}), ('appearanceApply', {'name': 2}),
                ('palettePreset', {'id': 'nord'}), ('palettePreset', {'id': 'missing'}), ('paletteReset', {}),
                ('settingsExport', {'path': '$ROOT/export.json', 'kind': 'preset'}),
                ('settingsExport', {'path': '$ROOT/export.json', 'kind': 'preset'}),
                ('settingsExport', {'path': '', 'kind': 'preset'}),
                ('settingsImport', {'path': '$ROOT/import.json'}), ('settingsImport', {'path': '$ROOT/bad.json'})]
}


class SyncFixture(Fixture):
    def configured(self, demo=False, settings=False, gio=True, terminal=True):
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'), XDG_STATE_HOME=str(self.root/'state'), XDG_RUNTIME_DIR=str(self.root/'run'))
        env.start(); self.addCleanup(env.stop)
        runner = FakeRunner(available={'wpctl', 'brightnessctl', 'wl-copy', 'niri', 'busctl'} | ({'gio'} if gio else set()))
        runner.details = []
        original_run = runner.run
        def run(*args, **kwargs):
            runner.details.append([args, kwargs]); return original_run(*args, **kwargs)
        runner.run = run
        live = self.make_backend(runner=runner, demo=demo); live.settings_only = settings
        self.addCleanup(live.charge_executor.shutdown); self.addCleanup(live.feature_executor.shutdown)
        self.put('file.txt', 'fixture')
        self.put('import.json', json.dumps(dict(schema=1, kind='preset', settings={'accent': '#123456'})))
        self.put('bad.json', '{}')
        live.file_search['entries'] = [{'path': str(self.root/'file.txt')}]
        live.applications.entries = {i: dict(name=i, terminal=t, argv=['/bin/echo', 'a b', '$(no shell)'], path='/apps/'+i)
                                    for i, t in [('kitty.desktop', False), ('terminal.desktop', True)]}
        niri = copy.deepcopy(live.demo_snapshot()['niri'])
        live.niri = copy.deepcopy(niri)
        live.niri_state = lambda: copy.deepcopy(niri)
        live.niri_action = lambda payload: runner.run('niri-json', json.dumps(payload, sort_keys=True))
        runner.names.add('niri-json')
        bluetooth = copy.deepcopy(live.demo_snapshot()['system']['bluetooth'])
        live.bluetooth = lambda: copy.deepcopy(bluetooth)
        live.system_cache = {key: {'sentinel': True} for key in ('audio', 'microphone', 'brightness', 'other')}
        live.privacy_cache = {'sentinel': True}; live.bluetooth_cache = {'sentinel': True}
        live.saver_snapshot = lambda: {'active': False, 'busy': False}
        which = patch('shutil.which', return_value='/usr/bin/kitty' if terminal else None)
        which.start(); self.addCleanup(which.stop)
        return live

    def clean(self, value):
        text = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=True)
        return json.loads(text.replace(str(self.root), '$ROOT').replace(str(Path.home()), '$HOME'))

    def observations(self, group):
        rows = []
        for demo in (False, True):
            for settings in (False, True):
                live = self.configured(demo, settings)
                initial = copy.deepcopy(self.preferences.values)
                output = []
                with patch('time.time', return_value=123), patch('time.time_ns', return_value=123):
                    for ordinal, (action, args) in enumerate(CASES[group], 1):
                        args = json.loads(json.dumps(args).replace('$ROOT', str(self.root)))
                        result = complete_action(live, dict(action=action, **args))
                        # This golden pins commands/end state; worker tests pin ack/sequence.
                        if action == "bluetoothDevice" and not demo and not settings: result = dict(result, sequence=ordinal)
                        demo_state = live._demo_state
                        output.append(dict(result=result, calls=live.runner.details[:], spawns=live.runner.spawns[:],
                            system=copy.deepcopy({k: demo_state['system'][k] for k in ('audio', 'microphone', 'brightness', 'bluetooth')}),
                            calculator=demo_state.get('calculator'), niri=copy.deepcopy(demo_state['niri'] if demo else live.niri),
                            history=live.notification_history, caches=[copy.deepcopy(live.system_cache),live.privacy_cache,live.bluetooth_cache],
                            preferences={k: copy.deepcopy(v) for k,v in self.preferences.values.items() if v != initial[k]}))
                rows.append(self.clean(dict(demo=demo, settings=settings, results=output)))
                for path in (self.root/'export.json', self.preferences.path):
                    if path.exists(): path.unlink()
                self.preferences.values = copy.deepcopy(backend.DEFAULT_PREFERENCES)
        return rows

    def golden(self, group):
        expected = json.loads((Path(__file__).parent/'fixtures'/('sync-'+group+'.json')).read_text())
        self.assertEqual(self.observations(group), expected)

    def assert_context_and_demo_isolation(self, group):
        live = self.configured(demo=True)
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch('subprocess.Popen', side_effect=AssertionError('demo spawn')), patch('os.replace', side_effect=AssertionError('demo write')):
            for action, args in CASES[group]: live.handle(dict(action=action, **args))
        self.assertEqual(live.runner.calls, []); self.assertEqual(live.runner.spawns, [])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        live.settings_only = True
        if group != 'appearance':
            for action, args in CASES[group]:
                self.assertEqual(live.handle(dict(action=action, **args))['message'], 'This action is unavailable in the settings app')


class LocalContentCase(SyncFixture, unittest.TestCase):
    def test_golden(self): self.golden('local')
    def test_demo_context(self): self.assert_context_and_demo_isolation('local')
    def test_text_bound_and_private_files(self):
        live = self.configured()
        self.assertTrue(live.handle(dict(action='copyText', text='λ'*(backend.MAX_TEXT//2)))['ok'])
        self.assertEqual(live.handle(dict(action='copyText', text='λ'*(backend.MAX_TEXT//2+1)))['message'], 'Invalid copy text')
        self.assertTrue(live.handle(dict(action='notesInit'))['ok'])
        self.assertEqual((self.root/'state/lme-shell/notes.txt').stat().st_mode & 0o777, 0o600)
        self.assertTrue(live.handle(dict(action='notificationSave', entries=[]))['ok'])
        self.assertEqual(live.notification_path.read_bytes(), b'[]')
        self.assertEqual(live.notification_path.stat().st_mode & 0o777, 0o600)


class AudioActionsCase(SyncFixture, unittest.TestCase):
    def test_golden(self): self.golden('audio')
    def test_demo_context(self): self.assert_context_and_demo_isolation('audio')
    def test_command_failure_still_invalidates_only_the_affected_fields(self):
        live = self.configured(); live.runner.run = lambda *a,**k: (_ for _ in ()).throw(backend.CommandError('denied'))
        self.assertEqual(live.handle(dict(action='micMute')), dict(ok=False, action='micMute', message='denied', sequence=1))
        self.assertEqual(set(live.system_cache), {'audio','brightness','other'}); self.assertIsNone(live.privacy_cache)


class WindowActionsCase(SyncFixture, unittest.TestCase):
    def test_golden(self): self.golden('windows')
    def test_demo_context(self): self.assert_context_and_demo_isolation('windows')
    def test_literal_fallback_terminal_unavailable_and_workspace_readback(self):
        live = self.configured(gio=False, terminal=False)
        self.assertTrue(live.handle(dict(action='launch', id='kitty.desktop'))['ok'])
        self.assertEqual(live.runner.spawns, [['/bin/echo', 'a b', '$(no shell)']])
        self.assertEqual(live.handle(dict(action='launch', id='terminal.desktop'))['message'], 'The configured terminal is unavailable')
        live.niri['workspaces'] = []
        self.assertTrue(live.handle(dict(action='workspace', id=2))['ok'])
        self.assertEqual(live.runner.calls[-1], ('niri-json', '{"FocusWorkspace": {"reference": {"Id": 2}}}'))
        self.assertTrue(live.launcher_history.snapshot())


class AppearanceActionsCase(SyncFixture, unittest.TestCase):
    def test_golden(self): self.golden('appearance')
    def test_demo_context(self): self.assert_context_and_demo_isolation('appearance')
    def test_unknown_prefix_and_import_backup_permissions(self):
        live = self.configured()
        self.assertEqual(live.handle(dict(action='appearanceUnknown', name='missing'))['message'], 'Unknown profile, or the built-in Dracula profile cannot be deleted')
        reply = live.handle(dict(action='settingsImport', path=str(self.root/'import.json')))
        self.assertTrue(reply['ok']); self.assertEqual(self.preferences.values['accent'], '#123456')
        for path in [self.preferences.path, *self.preferences.path.parent.glob('settings-before-import-*.json')]:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


@unittest.skipUnless((Path(__file__).resolve().parents[1]/'scripts/local_content_actions.py').exists(),
                     'M7a providers absent on baseline; registry ownership N/A')
class SyncOwnershipCase(SyncFixture, unittest.TestCase):
    def test_registered_errors_never_fall_back_and_prefixes_stay_legacy(self):
        live = self.configured()
        from backend_actions import ActionSpec
        from unittest.mock import Mock
        legacy = Mock(side_effect=AssertionError('registered action fell back'))
        for action in ('calculate', 'volume', 'launch', 'settingsImport'):
            if live.actions.get(action) is None: continue
            for demo in (False, True):
                live.demo = demo
                spec = live.actions.get(action)
                fail = Mock(side_effect=ValueError('provider error'))
                live.actions._specs[action] = ActionSpec(action, spec.contexts, fail, fail)
                with patch.object(live, 'perform', legacy), patch.object(live, 'perform_demo', legacy):
                    self.assertEqual(live.handle(dict(action=action))['message'], 'provider error')
                legacy.assert_not_called()
        live.demo = False
        self.assertEqual(live.handle(dict(action='volumeExtra'))['message'], 'Unknown action: volumeExtra')
