"""Existing light-provider behavior first; descriptor resolution is a separate contract."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from feature_catalog import CatalogError, load_catalog, canonical_index
from test_backend import Fixture, FakeRunner, backend

ROOT = Path(__file__).resolve().parents[1]
PILOTS = ('nightLight', 'idle', 'keybinds')
READY = (ROOT/'scripts/backend_providers.py').exists()


class ProviderParityCase(Fixture, unittest.TestCase):
    def test_registration_keeps_projection_and_does_no_action_work(self):
        runner = FakeRunner()
        live = self.make_backend(runner)
        self.addCleanup(live.feature_executor.shutdown); self.addCleanup(live.charge_executor.shutdown)
        self.assertEqual(runner.calls, []); self.assertEqual(runner.spawns, [])
        self.assertEqual(live.feature_jobs, {})
        self.assertEqual(live.action_state(), {'launchpadJobs': {}})
        for action in ('nightLightRefresh', 'idleRefresh', 'idleInhibit', 'keybindRefresh'):
            self.assertEqual(live.actions.get(action).execution, 'sync')

    def copy(self):
        root = self.root/'checkout'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        return root

    def demo(self, root, settings=False):
        env = dict(os.environ, XDG_CONFIG_HOME=str(self.root/'private-config'),
                   XDG_STATE_HOME=str(self.root/'private-state'), XDG_CACHE_HOME=str(self.root/'private-cache'),
                   XDG_RUNTIME_DIR=str(self.root/'private-runtime'))
        requests = [{'action': action} for action in ('nightLightRefresh', 'idleRefresh', 'keybindRefresh')]
        requests += [dict(action='idleInhibit', value=True), dict(action='idleRefreshExtra')]
        result = subprocess.run([sys.executable, str(root/'scripts/desktop_backend.py'), '--demo',
                                 *(['--settings'] if settings else [])], env=env,
                                input=''.join(json.dumps(r)+'\n' for r in requests),
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        states = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(states), 6)
        for sequence, state in enumerate(states[1:], 1):
            action = requests[sequence-1]['action']
            error = (settings and action in ('idleInhibit', 'idleRefreshExtra')) or action == 'idleRefreshExtra'
            expected = ('This action is unavailable in the settings app' if settings else
                        'Unknown action: idleRefreshExtra') if error else 'Demo preview: no system command executed'
            self.assertEqual(state['lastResult'], dict(action=action, ok=not error, message=expected, sequence=sequence))
            self.assertEqual(state['actionPending'], {'acknowledged': 0, 'active': []})
        self.assertFalse((self.root/'private-config/lme-shell/settings.json').exists())
        return states, result.stderr

    def test_disabled_pilot_entries_hide_pages_but_keep_demo_actions_and_state(self):
        root = self.copy()
        states, _ = self.demo(root)
        index = root/'config/features.json'; data = json.loads(index.read_text())
        for record in data['features']:
            if record['id'] in PILOTS: record['enabled'] = False
        index.write_text(canonical_index(data))
        self.assertFalse(set(PILOTS) & {item['key'] for item in load_catalog(root)['settingsPage']})
        for settings in (False, True):
            withdrawn, errors = self.demo(root, settings)
            self.assertEqual(errors, '')
            for old, new in zip(states, withdrawn):
                for key in ('idle', 'nightLight', 'keybinds'):
                    self.assertEqual(new[key], old[key])

    def test_broken_catalog_keeps_actions_and_publishes_existing_diagnostic(self):
        root = self.copy(); (root/'config/features.json').write_text('{broken')
        for settings in (False, True):
            states, errors = self.demo(root, settings)
            self.assertIn('Feature catalog:', errors)
            self.assertTrue(all(state['catalogValidation']['error'] for state in states))

    def test_absent_pilot_index_entries_keep_the_compatibility_actions(self):
        root = self.copy(); index = root/'config/features.json'; data = json.loads(index.read_text())
        # Empty index is an existing supported fault/withdrawal fixture.
        data['features'] = []; index.write_text(canonical_index(data))
        for settings in (False, True):
            states, errors = self.demo(root, settings)
            self.assertEqual(errors, '')
            self.assertTrue(all(not state['catalogValidation']['error'] for state in states))


@unittest.skipUnless(READY, 'descriptor backend capability absent on unmodified main')
class ProviderCatalogCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); (self.root/'config').mkdir(); (self.root/'scripts').mkdir()
        self.entry = 'scripts/catalog_test_provider.py'
        (self.root/self.entry).write_text('def provide(capabilities):\n    return capabilities\n')
        self.descriptor = dict(id='testProvider', sources=[self.entry], backend=dict(entry=self.entry, factory='provide'))
        self.index = dict(version=1, features=[dict(id='testProvider', descriptor='config/test.json', enabled=True, startup={})])
        self.write()

    def write(self):
        (self.root/'config/test.json').write_text(json.dumps(self.descriptor))
        (self.root/'config/features.json').write_text(canonical_index(self.index))

    def factories(self, data=None, bindings=None):
        from backend_providers import provider_factories
        return provider_factories(data or load_catalog(self.root), bindings or {'testProvider': Mock()}, root=self.root)

    def test_resolves_declared_factory_without_calling_it_or_capabilities(self):
        callbacks = Mock(); factory = self.factories()['testProvider']
        callbacks.assert_not_called()
        self.assertIs(factory(callbacks), callbacks)
        self.assertEqual(factory.__module__, self.factories()['testProvider'].__module__)
        self.assertIs(factory, self.factories()['testProvider'])

    def test_disabled_provider_is_retained_and_absent_metadata_uses_original_factory(self):
        self.index['features'][0]['enabled'] = False; self.write()
        self.assertEqual(self.factories()['testProvider'](23), 23)
        self.descriptor.pop('backend'); self.write(); fallback = Mock()
        self.assertIs(self.factories(bindings={'testProvider': fallback})['testProvider'], fallback)
        fallback.assert_not_called()

    def test_rejects_unbound_capabilities_and_duplicate_factory_owners(self):
        with self.assertRaisesRegex(CatalogError, 'Unbound backend feature'):
            self.factories(bindings={'other': Mock()})
        other = dict(self.descriptor, id='other')
        (self.root/'config/other.json').write_text(json.dumps(other))
        self.index['features'].append(dict(id='other', descriptor='config/other.json', enabled=False, startup={}))
        self.write()
        with self.assertRaisesRegex(CatalogError, 'Duplicate backend provider'):
            load_catalog(self.root)

    def test_rejects_bad_shape_factory_source_and_resource_paths(self):
        variants = [None, {}, dict(entry=self.entry, factory='provide', callback='run()'),
            dict(entry='../escape.py', factory='provide'), dict(entry='/tmp/escape.py', factory='provide'),
            dict(entry='scripts/missing.py', factory='provide'), dict(entry=self.entry, factory='missing'),
            dict(entry=self.entry, factory='provide()'), dict(entry=self.entry, factory='__import__')]
        for value in variants:
            with self.subTest(value=value):
                self.descriptor['backend'] = value; self.write()
                with self.assertRaises(CatalogError): load_catalog(self.root)
        self.descriptor['backend'] = dict(entry=self.entry, factory='provide')
        self.descriptor['sources'] = []; self.write()
        with self.assertRaisesRegex(CatalogError, 'declared source'): load_catalog(self.root)

    def test_rejects_symlink_escape_non_python_and_non_function_factory(self):
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside)/'escape.py'; path.write_text('def provide(cap): return cap\n')
            target = self.root/self.entry; target.unlink(); target.symlink_to(path)
            with self.assertRaises(CatalogError): load_catalog(self.root)
            target.unlink(); target.write_text('provide = 1\n')
            with self.assertRaises(CatalogError): load_catalog(self.root)
            target.write_text('async def provide(cap): return cap\n')
            with self.assertRaises(CatalogError): load_catalog(self.root)
        path = self.root/'scripts/not-python.qml'; path.write_text('Item {}')
        self.descriptor.update(sources=['scripts/not-python.qml'], backend=dict(entry='scripts/not-python.qml', factory='provide'))
        self.write()
        with self.assertRaises(CatalogError): load_catalog(self.root)

    def test_resolution_failure_does_not_mutate_original_bindings_or_execute_fallback(self):
        fallback = Mock(); bindings = {'testProvider': fallback}
        (self.root/self.entry).write_text('raise RuntimeError("broken import")\ndef provide(cap): return cap\n')
        with self.assertRaisesRegex(CatalogError, 'broken import'): self.factories(bindings=bindings)
        self.assertEqual(bindings, {'testProvider': fallback}); fallback.assert_not_called()

    def test_internal_symlink_alias_cannot_bypass_provider_ownership(self):
        path = self.root/self.entry; target = path.with_name('actual_provider.py')
        path.rename(target); path.symlink_to(target)
        with self.assertRaisesRegex(CatalogError, 'canonical scripts source'): load_catalog(self.root)

    def test_provider_factory_error_is_never_retried_with_original_factory(self):
        from backend_actions import ActionRegistry
        fallback = Mock(); cap = Mock()
        (self.root/self.entry).write_text('def provide(cap):\n    cap()\n    raise ValueError("factory failed")\n')
        factory = self.factories(bindings={'testProvider': fallback})['testProvider']
        cap.assert_not_called(); fallback.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'factory failed'): ActionRegistry().provide([(factory, cap)])
        cap.assert_called_once_with(); fallback.assert_not_called()


@unittest.skipUnless(READY, 'descriptor backend capability absent on unmodified main')
class ProviderHostCase(ProviderParityCase):
    def test_slow_provider_import_falls_back_within_existing_validation_deadline(self):
        root = self.copy(); path = root/'config/keybinds.json'; data = json.loads(path.read_text())
        source = 'scripts/catalog_slow_provider.py'
        (root/source).write_text('import time\ntime.sleep(10)\ndef provide(cap): return (), lambda: {}\n')
        data['sources'].append(source); data['backend'] = dict(entry=source, factory='provide')
        path.write_text(json.dumps(data))
        env = dict(os.environ, **{f'XDG_{key}_HOME': str(self.root/key.lower())
                                  for key in ('CONFIG', 'STATE', 'CACHE', 'DATA')})
        result = subprocess.run([sys.executable, str(root/'scripts/desktop_backend.py'), '--demo', '--once'],
                                env=env, capture_output=True, text=True, timeout=6)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Validation timed out', result.stderr)
        self.assertTrue(json.loads(result.stdout)['catalogValidation']['error'])

    def test_copied_descriptor_selects_own_factory_without_composition_edits(self):
        root = self.copy(); path = root/'scripts/keybind_actions.py'
        path.write_text(path.read_text()+'\ndef catalog_provide(capabilities):\n'
            '    from dataclasses import replace\n    specs, project = provide(capabilities)\n'
            '    return tuple(replace(spec, demo=lambda request: capabilities.install({"path":"catalog-provider-fixture"})) for spec in specs), project\n')
        descriptor = root/'config/keybinds.json'; data = json.loads(descriptor.read_text())
        data['backend']['factory'] = 'catalog_provide'; descriptor.write_text(json.dumps(data))
        states, errors = self.demo(root)
        self.assertEqual(errors, '')
        self.assertEqual(states[-1]['keybinds']['path'], 'catalog-provider-fixture')

    def test_invalid_provider_uses_atomic_catalog_fallback_and_original_factories(self):
        root = self.copy(); path = root/'config/keybinds.json'; data = json.loads(path.read_text())
        data['backend']['factory'] = 'missing'; path.write_text(json.dumps(data))
        states, errors = self.demo(root)
        self.assertIn('Feature catalog:', errors)
        self.assertTrue(all(state['catalogValidation']['error'] for state in states))
        self.assertEqual(states[-1]['keybinds']['path'], str(root/'config/niri/lme-shell.kdl'))

    def test_pilot_capability_order_and_exact_registered_set_remain_unchanged(self):
        from backend_providers import provider_factories
        data = load_catalog(ROOT)
        data = dict(data, backend={key: value for key, value in data.get('backend', {}).items() if key in PILOTS})
        providers = provider_factories(data, {key: Mock() for key in PILOTS})
        self.assertEqual(tuple(providers), PILOTS)
        callbacks = Mock()
        self.assertEqual([spec.name for spec in providers['idle'](callbacks)[0]], ['idleRefresh', 'idleInhibit'])
        callbacks.assert_not_called()
