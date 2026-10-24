"""Freeze selection/application transactions and demo isolation before extraction."""
import copy
import os
import shlex
import unittest
from unittest.mock import Mock, call, patch

import liquid_glass
from test_backend import Fixture, FakeRunner, backend

ACTIONS = ('paletteApply', 'glassBlurApply', 'gowallSetup', 'weatherSelect')
DEMO = 'Demo preview: no system command executed'
PLACE = dict(name='  Da Nang  ', country=' VN ', latitude=16.0544067, longitude=108.2021667, extra=True)
NORMAL = dict(name='Da Nang', country='VN', latitude=16.054407, longitude=108.202167)
COLORS = dict(accent='#ABCDEF', text='#FEDCBA')


class SelectionActionCase(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'),
            XDG_STATE_HOME=str(self.root/'state'), XDG_RUNTIME_DIR=str(self.root/'runtime'))
        env.start(); self.addCleanup(env.stop)
        self.instances = 0

    def configured(self, demo=False, settings=False):
        self.instances += 1
        self.preferences = backend.Preferences(self.root/f'case{self.instances}/settings.json')
        live = self.make_backend(FakeRunner(available={'gowall'}), demo=demo)
        live.settings_only = settings
        for owner in (live.charge_executor, live.feature_executor, live.weather, live.capture, live.mirror):
            self.addCleanup(owner.shutdown if hasattr(owner, 'shutdown') else owner.close)
        live.palette_preview = dict(colors=COLORS, path='literal image.png',
            **{key:live.preferences.values[key] for key in ('paletteScheme','paletteMode','paletteContrast')})
        return live

    def test_context_demo_result_sequence_service_calls_and_state(self):
        for demo in (False, True):
            for settings in (False, True):
                live = self.configured(demo, settings)
                before = copy.deepcopy(live.preferences.values)
                with patch.object(live.image_utilities, 'setup', return_value='Setup started') as setup:
                    requests = (dict(path='literal image.png'), {}, dict(path='literal;$(input).png'), dict(location=PLACE))
                    messages = ('Wallpaper palette applied; element overrides preserved',
                        f'Saved {live.preferences.path.parent}/liquid-blur.kdl. Include it after popup-blur.kdl in niri, then validate. Included files reload when applied. This changes compositor-wide blur.',
                        'Setup started', 'Weather location updated')
                    for sequence, (action, request, message) in enumerate(zip(ACTIONS, requests, messages), 1):
                        self.assertEqual(live.handle(dict(action=action, clientSerial=sequence+30, **request)),
                            dict(ok=True, action=action, message=DEMO if demo else message, sequence=sequence))
                        self.assertEqual(live.client_serial, sequence+30)
                        self.assertFalse(live.feature_jobs)
                    if demo: setup.assert_not_called()
                    else: setup.assert_called_once_with('literal;$(input).png', before['terminal'])
                expected = dict(before, weatherLocation=NORMAL, weatherAutoLocation=False)
                if not demo: expected.update(wallpaperPalette=dict(accent='#abcdef', text='#fedcba'), paletteSource='wallpaper', accent='#abcdef')
                self.assertEqual(live.preferences.values, expected)
                self.assertEqual(live.preferences.path.exists(), not demo)
                if not demo:
                    self.assertEqual(backend.Preferences(live.preferences.path).values, expected)
                    self.assertEqual(live.preferences.path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(live.palette_preview['colors'], COLORS)
                self.assertFalse(live.runner.calls); self.assertFalse(live.runner.spawns)

    def test_palette_validation_precedes_matching_and_failed_apply_preserves_bytes(self):
        live = self.configured()
        live.preferences.set('themeOverrides', {'buttonFill':'#123456'})
        baseline = live.preferences.path.read_bytes()
        valid = copy.deepcopy(live.palette_preview)
        cases = [(dict(valid, colors={'accent':'invalid'}, path='wrong'), 'Invalid wallpaper palette'),
                 (dict(valid, colors={}), 'Generate a preview for this image first'),
                 (dict(valid, path='wrong'), 'Generate a preview for this image first')]
        for key in ('paletteScheme','paletteMode','paletteContrast'):
            cases.append((dict(valid, **{key:'stale'}), 'Generate a preview for this image first'))
        for sequence, (preview, message) in enumerate(cases, 1):
            live.palette_preview = preview
            self.assertEqual(live.handle(dict(action='paletteApply', path='literal image.png')),
                dict(ok=False, action='paletteApply', message=message, sequence=sequence))
            self.assertEqual(live.preferences.path.read_bytes(), baseline)
        live.palette_preview = valid
        with patch.object(live.preferences, 'update', wraps=live.preferences.update) as update:
            self.assertTrue(live.handle(dict(action='paletteApply', path='literal image.png'))['ok'])
            update.assert_called_once_with(dict(wallpaperPalette={'accent':'#abcdef','text':'#fedcba'}, paletteSource='wallpaper', accent='#abcdef'))
        self.assertEqual(live.preferences.values['themeOverrides'], {'buttonFill':'#123456'})

    def test_palette_and_weather_write_failure_does_not_publish_success(self):
        for action, request in (('paletteApply', dict(path='literal image.png')), ('weatherSelect', dict(location=PLACE))):
            live = self.configured(settings=True); before = copy.deepcopy(live.preferences.values)
            with patch.object(live.preferences, 'update', side_effect=OSError('Read-only preferences')):
                self.assertEqual(live.handle(dict(action=action, **request)),
                    dict(ok=False, action=action, message='Read-only preferences', sequence=1))
            self.assertEqual(live.preferences.values, before); self.assertFalse(live.feature_jobs)

    def test_blur_owned_content_permissions_user_file_and_symlink_guards(self):
        live = self.configured(); path = live.preferences.path.parent/'liquid-blur.kdl'
        live.preferences.set('liquidGlass', {'passes':3, 'offset':2.5})
        settings = live.preferences.path.read_bytes()
        self.assertTrue(live.handle(dict(action='glassBlurApply'))['ok'])
        self.assertEqual(path.read_text(), liquid_glass.MARKER+'blur {\n    passes 3\n    offset 2.5\n}\n')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        target = self.put('protected.kdl', 'user-owned')
        for symlink in (False, True):
            path.unlink()
            if symlink: path.symlink_to(target)
            else: path.write_text('user-owned')
            result = live.handle(dict(action='glassBlurApply'))
            self.assertEqual(result['message'], 'Refusing to replace a user-owned liquid-blur.kdl. Move it before applying.')
            self.assertFalse(result['ok']); self.assertEqual(path.read_text(), 'user-owned')
            self.assertEqual(target.read_text(), 'user-owned')
        self.assertEqual(live.preferences.path.read_bytes(), settings)

    def test_gowall_prefix_guard_precedes_setup_and_actual_setup_keeps_literal_argv(self):
        live = self.configured()
        for key in ('gowallThemes','gowallGenerate','gowallUnknown'):
            live.feature_jobs = {key:object()}
            with patch.object(live.image_utilities, 'setup') as setup:
                self.assertEqual(live.handle(dict(action='gowallSetup'))['message'], 'A gowall operation is already running')
                setup.assert_not_called()
        live.feature_jobs = {'wallpaperScan':object()}
        source = self.put('images/a space;$(literal).png', 'fixture')
        live.preferences.values['terminal'] = 'custom-terminal --flag'
        with patch.object(live.launchpad, 'run', return_value='Started setup') as run:
            self.assertEqual(live.handle(dict(action='gowallSetup', path=str(source)))['message'], 'Started setup')
            run.assert_called_once_with('gowall-setup', {'gowall-setup':dict(name='Gowall upscale setup',
                command=shlex.join(['/usr/bin/gowall','upscale',str(source),'--preview','false']),
                kind='command',terminal=True,cwd='')}, 'custom-terminal --flag')
        live.feature_jobs = {}

    def test_weather_validation_normalization_and_single_live_transaction(self):
        invalid = [({}, 'Select a city first.'), (None,'A location needs a name, latitude and longitude.'),
            (dict(PLACE, name=' '), 'Invalid location name.'),
            *[(dict(PLACE, latitude=value),'Invalid location coordinates.') for value in (True,float('nan'),float('inf'),91)]]
        for demo in (False, True):
            live = self.configured(demo)
            with patch.object(live.preferences, 'update', wraps=live.preferences.update) as update:
                for sequence, (value, message) in enumerate(invalid, 1):
                    self.assertEqual(live.handle(dict(action='weatherSelect', location=value)),
                        dict(ok=False, action='weatherSelect', message=message, sequence=sequence))
                update.assert_not_called()
                self.assertTrue(live.handle(dict(action='weatherSelect', location=PLACE))['ok'])
                if demo: update.assert_not_called()
                else: update.assert_called_once_with(dict(weatherLocation=NORMAL, weatherAutoLocation=False))

    def test_demo_permissive_apply_setup_zero_io_and_legacy_prefix_errors(self):
        for settings in (False, True):
            live = self.configured(demo=True, settings=settings)
            live.feature_jobs = {'gowallGenerate':object()}
            with patch('subprocess.Popen', side_effect=AssertionError('demo spawn')), \
                    patch('io.open', side_effect=AssertionError('demo file IO')), \
                    patch('os.open', side_effect=AssertionError('demo fd')), \
                    patch('os.mkdir', side_effect=AssertionError('demo mkdir')):
                for action in ACTIONS[:-1]:
                    self.assertTrue(live.handle(dict(action=action, path=None))['ok'])
                self.assertTrue(live.handle(dict(action='weatherSelect', location=PLACE))['ok'])
                self.assertEqual(live.preferences.values['weatherLocation'], NORMAL)
                result = live.handle(dict(action='gowallUnknown'))
                self.assertEqual(result['ok'], not settings)
                for action in ('paletteApplyExtra','glassBlurApplyExtra','weatherSelectExtra'):
                    self.assertEqual(live.handle(dict(action=action))['message'],
                        'This action is unavailable in the settings app' if settings else 'Unknown action: '+action)
            self.assertFalse(live.runner.calls); self.assertFalse(live.runner.spawns)

    @unittest.skipUnless(hasattr(liquid_glass, 'provide_blur'), 'selection providers absent on baseline; ownership-only N/A')
    def test_registered_ownership_no_fallback_and_pure_registration(self):
        folder, values = Mock(), Mock()
        specs, project = liquid_glass.provide_blur(folder, values)
        self.assertEqual([spec.name for spec in specs], ['glassBlurApply']); self.assertEqual(project(), {})
        folder.assert_not_called(); values.assert_not_called()
        live = self.configured(settings=True)
        for action in ACTIONS:
            self.assertEqual(live.actions.get(action).contexts, {'shell','settings'})
            self.assertEqual(live.actions.get(action).execution, 'sync')
        with patch.object(live, 'perform', side_effect=AssertionError('legacy fallback')), \
                patch.object(live.image_utilities, 'setup', side_effect=ValueError('setup failure')):
            self.assertEqual(live.handle(dict(action='gowallSetup')),
                dict(ok=False, action='gowallSetup', message='setup failure', sequence=1))


if __name__ == '__main__': unittest.main()
