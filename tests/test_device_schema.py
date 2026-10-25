"""Device scalar schema contracts, before and after descriptor ownership."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from test_backend import backend
import settings_transfer as transfer

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = dict(peripheralBatteryAlerts=True, peripheralBatteryThreshold=20,
                batterySaverBrightness=70, mirroringEnabled=True)
GROUPS = {'peripherals': ('peripheralBatteryAlerts', 'peripheralBatteryThreshold'),
          'batterySaver': ('batterySaverBrightness',), 'mirroring': ('mirroringEnabled',)}


class DeviceSchemaContractsCase(unittest.TestCase):
    def test_defaults_types_portable_membership_and_exact_errors(self):
        schema = backend.PREFERENCE_SCHEMA
        for key, expected in DEFAULTS.items():
            with self.subTest(key=key):
                actual = schema.defaults()[key]
                self.assertEqual(actual, expected)
                self.assertIs(type(actual), type(expected))
                self.assertIn(key, schema.portable_keys())
                self.assertNotIn(key, schema.appearance_keys())
                valid = (False, True) if type(expected) is bool else ((5, 20, 50) if key == 'peripheralBatteryThreshold' else (1, 70, 100))
                invalid = (None, '', 'true', [], {}, float('nan'), float('inf'), -float('inf'))
                invalid += (0, 1, 1.) if type(expected) is bool else (False, True, 1., 0, -1, 51 if key == 'peripheralBatteryThreshold' else 101)
                for value in valid:
                    self.assertEqual(backend.validate_preference(key, value), value)
                for value in invalid:
                    with self.subTest(value=value), self.assertRaises(ValueError) as caught:
                        backend.validate_preference(key, value)
                    self.assertEqual(str(caught.exception), 'Invalid preference: '+key)

    def test_existing_file_stale_writers_and_preset_round_trip(self):
        values = dict(peripheralBatteryAlerts=False, peripheralBatteryThreshold=5,
                      batterySaverBrightness=100, mirroringEnabled=False)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'settings.json'
            path.write_text(json.dumps(values, indent=2)+'\n'); path.chmod(0o600)
            original = path.read_bytes()
            first, second = backend.Preferences(path), backend.Preferences(path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual({k:first.values[k] for k in values}, values)
            first.set('peripheralBatteryThreshold', 50)
            second.set('batterySaverBrightness', 1)
            first.reload(force=True)
            values.update(peripheralBatteryThreshold=50, batterySaverBrightness=1)
            self.assertEqual({k:first.values[k] for k in values}, values)
            preset = Path(directory)/'preset.json'
            transfer.export_document(str(preset), first.values, 'preset')
            imported = transfer.read_document(str(preset), backend.validate_preference, backend.DEFAULT_PREFERENCES)
            self.assertEqual({k:imported[k] for k in values}, values)
            backup = first.update(imported, backup=True)
            self.assertEqual(backend.Preferences(path).values, first.values)
            for file in (path, path.with_suffix('.lock'), preset, backup):
                self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)
            path.write_text('{broken')
            first.reload(force=True)
            self.assertEqual({k:first.values[k] for k in values}, values)

    def copied(self, mutate, code):
        with tempfile.TemporaryDirectory(prefix='device-schema-') as directory:
            root = Path(directory)/'checkout'; root.mkdir()
            for name in ('scripts', 'qml', 'config'):
                shutil.copytree(ROOT/name, root/name, ignore=shutil.ignore_patterns('__pycache__'))
            mutate(root)
            env = dict(os.environ, PYTHONPATH=str(root/'scripts'), XDG_CONFIG_HOME=str(root/'private'))
            result = subprocess.run([sys.executable, '-c', code], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)

    def authority(self, group, key, changes, valid, invalid):
        def mutate(root):
            path = root/'config'/f'{group}.json'
            data = json.loads(path.read_text()); data['preferences'][key].update(changes)
            path.write_text(json.dumps(data))
        code = f'''
import desktop_backend as b
from settings_schema import Schema
from functools import partial
Schema = partial(Schema, resolvers=b.PREFERENCE_SCHEMA._resolvers)
assert b.DEFAULT_PREFERENCES[{key!r}] == {changes['default']!r}
assert Schema().defaults()[{key!r}] == {changes['default']!r}
assert b.validate_preference({key!r}, {valid!r}) == {valid!r}
for value in {invalid!r}:
 try: b.validate_preference({key!r}, value)
 except ValueError as error: assert str(error) == 'Invalid preference: '+{key!r}
 else: raise AssertionError(value)
'''
        self.copied(mutate, code)

    @unittest.skipUnless((ROOT/'config/peripherals.json').exists(), 'Peripheral schema fragment is N/A before extraction')
    def test_peripheral_fragment_is_authoritative(self):
        self.authority('peripherals', 'peripheralBatteryThreshold', dict(default=25, min=10, max=40), 40, (5, 50, True))

    @unittest.skipUnless((ROOT/'config/batterySaver.json').exists(), 'Saver schema fragment is N/A before extraction')
    def test_saver_fragment_is_authoritative(self):
        self.authority('batterySaver', 'batterySaverBrightness', dict(default=60, min=10, max=90), 90, (1, 100, True))

    @unittest.skipUnless((ROOT/'config/mirroring.json').exists(), 'Mirroring schema fragment is N/A before extraction')
    def test_mirroring_fragment_is_authoritative(self):
        self.authority('mirroring', 'mirroringEnabled', dict(default=False), True, (1, 0, 'true'))

    @unittest.skipUnless(all((ROOT/'config'/f'{g}.json').exists() for g in GROUPS),
                         'All device schema fragments are N/A before extraction')
    def test_unique_ownership_empty_startup_and_no_new_ui_or_provider_entries(self):
        legacy = json.loads((ROOT/'config/preferences-legacy.json').read_text())
        index = json.loads((ROOT/'config/features.json').read_text())
        for group, keys in GROUPS.items():
            record = next(item for item in index['features'] if item['id'] == group)
            self.assertEqual(record['startup'], {})
            descriptor = json.loads((ROOT/record['descriptor']).read_text())
            self.assertEqual(set(descriptor), {'id', 'preferences'})
            self.assertEqual(set(descriptor['preferences']), set(keys))
            for key in keys:
                self.assertNotIn(key, legacy['preferences'])
                owners = [r['id'] for r in index['features']
                          if key in json.loads((ROOT/r['descriptor']).read_text()).get('preferences', {})]
                self.assertEqual(owners, [group])

    def test_index_failure_or_disable_retains_defaults_and_user_file_bytes(self):
        for mode in ('disabled', 'missing', 'malformed', 'empty'):
            def mutate(root):
                private = root/'private/lme-shell'; private.mkdir(parents=True)
                (private/'settings.json').write_text(json.dumps(dict(DEFAULTS, unrelatedUserKey='keep')))
                path = root/'config/features.json'
                if mode == 'missing': path.unlink()
                elif mode == 'malformed': path.write_text('{broken')
                elif mode == 'empty': path.write_text('{"version":1,"features":[]}')
                else:
                    data = json.loads(path.read_text())
                    for record in data['features']:
                        if record['id'] in GROUPS: record['enabled'] = False
                    path.write_text(json.dumps(data))
            code = f'''
from pathlib import Path
path = Path('private/lme-shell/settings.json'); before = path.read_bytes()
import desktop_backend as b
for key, value in {DEFAULTS!r}.items():
 assert b.DEFAULT_PREFERENCES[key] == value
 assert b.validate_preference(key, value) == value
assert path.read_bytes() == before
'''
            with self.subTest(mode=mode): self.copied(mutate, code)
