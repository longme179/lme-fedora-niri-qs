"""Freeze lyric/search/radio preferences without changing worker or UI policy."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_backend import backend
import settings_transfer as transfer

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {'lyrics': ('lyricsEnabled', 'lyricsOnline', 'lyricsMode', 'lyricsFollow', 'activityLyrics'),
          'fileSearch': ('fileSearchEnabled', 'fileSearchRoots'),
          'bluetooth': ('bluetoothPairing', 'bluetoothAdapter')}
SCALARS = dict(lyricsEnabled=True, lyricsOnline=False, lyricsMode='scroll', lyricsFollow=True,
               activityLyrics=True, fileSearchEnabled=True, bluetoothPairing=True, bluetoothAdapter='')
PRIVATE = {'fileSearchRoots', 'bluetoothAdapter'}


class ContentSchemaContractsCase(unittest.TestCase):
    def test_defaults_home_context_and_membership(self):
        for home in ('/tmp/content-home-one', '/tmp/content-home-two'):
            defaults = backend.PREFERENCE_SCHEMA.defaults(dict(home=home))
            for key, value in SCALARS.items():
                self.assertEqual(defaults[key], value)
                self.assertIs(type(defaults[key]), type(value))
            self.assertEqual(defaults['fileSearchRoots'],
                             [str(Path(home)/name) for name in ('Documents', 'Desktop', 'Downloads', 'Pictures')])
        for key in (*SCALARS, 'fileSearchRoots'):
            self.assertEqual(key in backend.PREFERENCE_SCHEMA.portable_keys(), key not in PRIVATE)
            self.assertNotIn(key, backend.PREFERENCE_SCHEMA.appearance_keys())

    def test_exact_boolean_mode_and_adapter_validation(self):
        invalid = (None, [], {}, 0, 1, 1., float('nan'), float('inf'), -float('inf'), '', 'true')
        for key, default in SCALARS.items():
            if type(default) is bool:
                for value in (True, False): self.assertIs(backend.validate_preference(key, value), value)
                rejected = invalid
            elif key == 'lyricsMode':
                for value in ('scroll', 'line'): self.assertEqual(backend.validate_preference(key, value), value)
                rejected = (*invalid, True, False, 'LINE', 'line\n')
            else:
                for value in ('', '/org/bluez/hci0', '/org/bluez/hci12'):
                    self.assertEqual(backend.validate_preference(key, value), value)
                rejected = tuple(v for v in invalid if v != '') + (True, False, '/org/bluez/hci-1', '/org/bluez/hci0/dev_x', '/org/bluez/hci0\n')
            for value in rejected:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError) as error:
                    backend.validate_preference(key, value)
                self.assertEqual(str(error.exception), 'Invalid preference: '+key)

    def test_roots_normalize_deduplicate_without_mutating_and_keep_exact_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            first = str(Path(directory)/'one/../two')
            second = str(Path(directory)/'two')
            roots = [first, second, '~/Documents']; before = copy.deepcopy(roots)
            self.assertEqual(backend.validate_preference('fileSearchRoots', roots),
                             [second, str(Path.home()/'Documents')])
            self.assertEqual(roots, before)
            eight = [str(Path(directory)/str(n)) for n in range(8)]
            self.assertEqual(backend.validate_preference('fileSearchRoots', eight), eight)
            for value in (None, False, 'folder', [], eight+['/ninth'], [''], [True], ['bad\npath'], ['x'*4097]):
                with self.subTest(value=value), self.assertRaises(ValueError) as error:
                    backend.validate_preference('fileSearchRoots', value)
                self.assertEqual(str(error.exception), 'Choose one to eight local search folders')

    def test_old_file_merge_preset_privacy_backup_and_last_valid_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'settings.json'
            values = {**SCALARS, 'lyricsMode': 'line', 'lyricsOnline': True,
                      'fileSearchRoots': [directory], 'bluetoothAdapter': '/org/bluez/hci12'}
            path.write_text(json.dumps(values, indent=2)+'\n'); path.chmod(0o600); original = path.read_bytes()
            first, second = backend.Preferences(path), backend.Preferences(path)
            self.assertEqual(path.read_bytes(), original)
            first.set('lyricsFollow', False); second.set('bluetoothPairing', False); first.reload(force=True)
            values.update(lyricsFollow=False, bluetoothPairing=False)
            self.assertEqual({k:first.values[k] for k in values}, values)
            preset = transfer.document(first.values, 'preset')
            self.assertFalse(PRIVATE & preset['settings'].keys())
            imported = transfer.validate_document(preset, backend.validate_preference, backend.DEFAULT_PREFERENCES)
            backup = first.update(imported, backup=True)
            self.assertEqual({k:backend.Preferences(path).values[k] for k in values}, values)
            self.assertEqual(json.loads(backup.read_text())['settings']['bluetoothAdapter'], '/org/bluez/hci12')
            for key in PRIVATE:
                bad = copy.deepcopy(preset); bad['settings'][key] = values[key]
                with self.assertRaises(ValueError) as error:
                    transfer.validate_document(bad, backend.validate_preference, backend.DEFAULT_PREFERENCES)
                self.assertEqual(str(error.exception), 'Unknown or private settings in this document')
            path.write_text('{broken'); first.reload(force=True)
            self.assertEqual({k:first.values[k] for k in values}, values)

    def copied(self, mutate, code):
        with tempfile.TemporaryDirectory(prefix='content-schema-') as directory:
            root = Path(directory)/'checkout'; root.mkdir()
            for name in ('scripts', 'qml', 'config'):
                shutil.copytree(ROOT/name, root/name, ignore=shutil.ignore_patterns('__pycache__'))
            mutate(root)
            result = subprocess.run([sys.executable, '-c', code], cwd=root,
                env=dict(os.environ, PYTHONPATH=str(root/'scripts'), XDG_CONFIG_HOME=str(root/'private')),
                capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)

    def authority(self, group, key, default, extra=''):
        def mutate(root):
            path = root/'config'/f'{group}.json'; data = json.loads(path.read_text())
            data['preferences'][key]['default'] = default; path.write_text(json.dumps(data))
        self.copied(mutate, f'''import desktop_backend as b
assert b.DEFAULT_PREFERENCES[{key!r}] == {default!r}
assert b.PREFERENCE_SCHEMA.defaults()[{key!r}] == {default!r}
assert b.validate_preference({key!r}, {default!r}) == {default!r}
'''+extra)

    @unittest.skipUnless((ROOT/'config/lyrics.json').exists(), 'Lyrics fragment is N/A before extraction')
    def test_lyrics_fragment_authority_and_bound_mode_callback(self):
        self.authority('lyrics', 'lyricsMode', 'line', "assert b.validate_preference('lyricsMode', 'scroll') == 'scroll'\n")

    @unittest.skipUnless((ROOT/'config/fileSearch.json').exists(), 'Search fragment is N/A before extraction')
    def test_search_fragment_authority_and_direct_existing_validator(self):
        self.authority('fileSearch', 'fileSearchEnabled', False,
                       "assert b.PREFERENCE_SCHEMA._validators['fileSearchRoots'] is b.search_roots\n")

    @unittest.skipUnless((ROOT/'config/bluetooth.json').exists(), 'Bluetooth fragment is N/A before extraction')
    def test_bluetooth_fragment_authority_and_private_adapter_callback(self):
        self.authority('bluetooth', 'bluetoothAdapter', '/org/bluez/hci12',
                       "assert 'bluetoothAdapter' not in b.PREFERENCE_SCHEMA.portable_keys()\n")

    @unittest.skipUnless(all((ROOT/'config'/f'{g}.json').exists() for g in GROUPS),
                         'All content schema fragments are N/A before extraction')
    def test_unique_ownership_and_no_ui_bootstrap_or_provider_entries(self):
        legacy = json.loads((ROOT/'config/preferences-legacy.json').read_text())
        records = json.loads((ROOT/'config/features.json').read_text())['features']
        for group, keys in GROUPS.items():
            record = next(item for item in records if item['id'] == group)
            self.assertEqual(record['startup'], {})
            descriptor = json.loads((ROOT/record['descriptor']).read_text())
            self.assertEqual(set(descriptor), {'id', 'preferences'})
            self.assertEqual(set(descriptor['preferences']), set(keys))
            for key in keys:
                self.assertNotIn(key, legacy['preferences'])
                owners = [r['id'] for r in records if key in json.loads((ROOT/r['descriptor']).read_text()).get('preferences', {})]
                self.assertEqual(owners, [group])

    def test_disabled_broken_or_empty_index_keeps_schema_and_user_bytes(self):
        for mode in ('disabled', 'missing', 'malformed', 'empty'):
            def mutate(root):
                private = root/'private/lme-shell'; private.mkdir(parents=True)
                (private/'settings.json').write_text(json.dumps(SCALARS))
                path = root/'config/features.json'
                if mode == 'missing': path.unlink()
                elif mode == 'malformed': path.write_text('{broken')
                elif mode == 'empty': path.write_text('{"version":1,"features":[]}')
                else:
                    data = json.loads(path.read_text())
                    for record in data['features']:
                        if record['id'] in GROUPS: record['enabled'] = False
                    path.write_text(json.dumps(data))
            code = f'''from pathlib import Path
path = Path('private/lme-shell/settings.json'); before = path.read_bytes()
import desktop_backend as b
for key, value in {SCALARS!r}.items(): assert b.DEFAULT_PREFERENCES[key] == value
assert len(b.DEFAULT_PREFERENCES['fileSearchRoots']) == 4
assert path.read_bytes() == before
'''
            with self.subTest(mode=mode): self.copied(mutate, code)
