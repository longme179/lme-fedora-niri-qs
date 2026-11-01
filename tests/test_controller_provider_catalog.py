"""Controller selection moves; controller execution, state and ownership do not."""
from dataclasses import fields
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import Mock

from backend_providers import provider_factories
from feature_catalog import canonical_index, load_catalog
from mirror_actions import MirrorCapabilities, provide as mirror
from saver_actions import SaverCapabilities, provide as saver
from weather_actions import WeatherCapabilities, provide as weather
from test_backend import Fixture, backend

ROOT = Path(__file__).resolve().parents[1]
FAMILY = {'weather': 'weather_actions', 'batterySaver': 'saver_actions', 'mirroring': 'mirror_actions'}
BINDINGS = ('nightLight', 'idle', 'keybinds', *FAMILY)
COMPLETE = all(json.loads((ROOT/'config'/f'{name}.json').read_text()).get('backend') for name in FAMILY)
PLACE = dict(name='Oslo', country='Norway', latitude=59.91, longitude=10.75)
REQUESTS = [dict(action='mirrorRefresh'), dict(action='mirrorStart', source='eDP-1', target='HDMI-A-1'),
    dict(action='mirrorStop'), dict(action='weatherSearch', query='Oslo'), dict(action='weatherDetect'),
    dict(action='weatherRefresh'), dict(action='weatherSelect', location=PLACE),
    dict(action='batterySaver', enabled=True), dict(action='batterySaver', enabled=False)]


class ControllerFixture(Fixture):
    def copy(self):
        path = self.root/'checkout'
        shutil.copytree(ROOT, path, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        return path

    def environment(self, root):
        return dict(os.environ, PYTHONPATH=str(root/'scripts'), PYTHONDONTWRITEBYTECODE='1',
            XDG_CONFIG_HOME=str(self.root/'user-config'), XDG_STATE_HOME=str(self.root/'user-state'),
            XDG_CACHE_HOME=str(self.root/'user-cache'), XDG_DATA_HOME=str(self.root/'user-data'),
            XDG_RUNTIME_DIR=str(self.root/'user-runtime'), DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(self.root/'no-system-bus'),
            NIRI_SOCKET=str(self.root/'no-niri'))

    def demo(self, root, settings=False):
        result = subprocess.run([sys.executable, str(root/'scripts/desktop_backend.py'), '--demo',
            *(['--settings'] if settings else [])], env=self.environment(root),
            input=''.join(json.dumps(request)+'\n' for request in REQUESTS), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        states = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(states), len(REQUESTS)+1)
        for sequence, (request, state) in enumerate(zip(REQUESTS, states[1:]), 1):
            denied = settings and request['action'] == 'weatherRefresh'
            self.assertEqual(state['lastResult'], dict(action=request['action'], ok=not denied, sequence=sequence,
                message='This action is unavailable in the settings app' if denied else 'Demo preview: no system command executed'))
            self.assertEqual(state['actionPending'], dict(acknowledged=0, active=[]))
        self.assertFalse((self.root/'user-config/lme-shell/settings.json').exists())
        end = states[-1]
        return dict(results=[state['lastResult'] for state in states], saver=end['batterySaver'],
            mirror=end['mirror'], location=end['preferences']['weatherLocation'], search=end['weather']['search'],
            outputs=[output['name'] for output in end['displays']['outputs']]), states, result.stderr


class ControllerProviderParityCase(ControllerFixture, unittest.TestCase):
    def test_provider_specs_and_registration_remain_pure(self):
        both = frozenset({'shell', 'settings'})
        for factory, capability, expected in (
            (weather, WeatherCapabilities, [('weatherSearch', both, 'sync', False), ('weatherDetect', both, 'sync', False),
                ('weatherRefresh', frozenset({'shell'}), 'sync', False), ('weatherSelect', both, 'sync', False)]),
            (saver, SaverCapabilities, [('batterySaver', both, 'worker', True)]),
            (mirror, MirrorCapabilities, [(name, both, 'sync', False) for name in ('mirrorRefresh', 'mirrorStart', 'mirrorStop')])):
            callbacks = [Mock() for _ in fields(capability)]
            specs, project = factory(capability(*callbacks))
            self.assertEqual([(spec.name, spec.contexts, spec.execution, callable(spec.prepare)) for spec in specs], expected)
            self.assertEqual(project(), {})
            for callback in callbacks: callback.assert_not_called()

    def test_demo_protocol_contexts_state_and_zero_settings_writes(self):
        for settings in (False, True):
            end, states, errors = self.demo(ROOT, settings)
            self.assertEqual(errors, '')
            self.assertFalse(end['saver']['active']); self.assertFalse(end['mirror']['active'])
            self.assertEqual(end['location'], PLACE); self.assertEqual(end['search']['query'], 'Oslo')
            self.assertEqual(end['outputs'], ['eDP-1', 'HDMI-A-1'])
            self.assertTrue(states[-2]['batterySaver']['active'])

    def test_disabled_and_missing_metadata_keep_original_controller_access(self):
        root = self.copy()
        original = [self.demo(root, settings)[0] for settings in (False, True)]
        index = root/'config/features.json'; data = json.loads(index.read_text())
        for record in data['features']:
            if record['id'] in FAMILY: record['enabled'] = False
        index.write_text(canonical_index(data))
        self.assertNotIn('weather', [item['key'] for item in load_catalog(root)['settingsPage']])
        marker = self.root/'retained-journal'; marker.write_bytes(b'unchanged data')
        for name in FAMILY:
            path = root/'config'/f'{name}.json'; descriptor = json.loads(path.read_text())
            descriptor.pop('backend', None); path.write_text(json.dumps(descriptor))
        for settings in (False, True):
            end, _, errors = self.demo(root, settings)
            self.assertEqual(end, original[int(settings)]); self.assertEqual(errors, '')
        self.assertEqual(marker.read_bytes(), b'unchanged data')

    def test_broken_index_keeps_controller_protocol_and_reports_fault(self):
        root = self.copy()
        original = [self.demo(root, settings)[0] for settings in (False, True)]
        (root/'config/features.json').write_text('{broken')
        for settings in (False, True):
            end, states, errors = self.demo(root, settings)
            self.assertEqual(end, original[int(settings)])
            self.assertIn('Feature catalog:', errors)
            self.assertTrue(all(state['catalogValidation']['error'] for state in states))


@unittest.skipUnless(COMPLETE, 'controller-provider descriptor family absent on unmodified main')
class ControllerDescriptorCase(ControllerFixture, unittest.TestCase):
    def test_complete_binding_ownership_factory_identity_and_unchanged_schema(self):
        providers = provider_factories(load_catalog(ROOT), backend.BACKEND_PROVIDER_FALLBACKS)
        self.assertEqual(tuple(providers), BINDINGS)
        for name, factory in (('weather', weather), ('batterySaver', saver), ('mirroring', mirror)):
            self.assertIs(providers[name], factory)
            descriptor = json.loads((ROOT/'config'/f'{name}.json').read_text())
            self.assertEqual(descriptor['backend'], dict(entry='scripts/'+FAMILY[name]+'.py', factory='provide'))
            self.assertIn(descriptor['backend']['entry'], descriptor['sources'])
        policy = json.loads((ROOT/'config/architecture.json').read_text())
        self.assertNotIn('batterySaver', policy['legacyFeatures'])
        for source in ('scripts/mirror_actions.py', 'scripts/display_mirror.py'):
            self.assertNotIn(source, policy['legacyFeatures']['display'])
        self.assertEqual(len(backend.PREFERENCE_SCHEMA.definitions), 147)
        self.assertEqual(len(backend.PREFERENCE_SCHEMA.legacy_keys), 68)

    def test_each_copied_descriptor_selects_its_own_factory_without_host_edits(self):
        for name, module in FAMILY.items():
            with self.subTest(feature=name):
                path = self.root/name
                shutil.copytree(ROOT, path, ignore=shutil.ignore_patterns('.git', '__pycache__'))
                source = path/'scripts'/f'{module}.py'
                source.write_text(source.read_text()+f'\ndef catalog_probe(cap):\n    specs, _ = provide(cap)\n'
                    f'    return specs, lambda: {{"catalogOwner":{name!r}}}\n')
                descriptor = path/'config'/f'{name}.json'; data = json.loads(descriptor.read_text())
                data['backend']['factory'] = 'catalog_probe'; descriptor.write_text(json.dumps(data))
                result = subprocess.run([sys.executable, '-c',
                    'import json,desktop_backend as b; b.initialize_catalog(); '
                    'x=b.DesktopBackend(demo=True,settings_only=True,weather_fetch=False); '
                    'print(json.dumps(x.action_state())); x.feature_executor.shutdown(); x.charge_executor.shutdown(); x.weather.close()'],
                    env=self.environment(path), capture_output=True, text=True, timeout=8)
                self.assertEqual(result.returncode, 0, result.stderr); self.assertEqual(result.stderr, '')
                self.assertEqual(json.loads(result.stdout), dict(launchpadJobs={}, catalogOwner=name))
                self.assertEqual((path/'scripts/desktop_backend.py').read_bytes(), (ROOT/'scripts/desktop_backend.py').read_bytes())

    def test_invalid_family_reference_falls_back_atomically(self):
        root = self.copy()
        for name in FAMILY:
            path = root/'config'/f'{name}.json'; original = path.read_text(); data = json.loads(original)
            data['backend']['factory'] = 'missing'; path.write_text(json.dumps(data))
            _, states, errors = self.demo(root)
            self.assertIn('Feature catalog:', errors)
            self.assertTrue(all(state['catalogValidation']['error'] for state in states))
            path.write_text(original)
