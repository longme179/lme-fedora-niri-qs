"""Golden main/Settings/worker schema contracts, frozen before M5 implementation."""
import copy
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_backend import backend
import clipboard
from desktop_features import APPEARANCE_KEYS
from settings_transfer import PORTABLE
from schema_fixture import frozen, outcome

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'tests/fixtures'
GOLDEN=json.loads((FIXTURES/'settings-defaults.json').read_text())
MATRIX=json.loads((FIXTURES/'settings-validation.json').read_text())
MEMBERS=json.loads((FIXTURES/'settings-membership.json').read_text())


class SchemaParityCase(unittest.TestCase):
    def test_full_default_keys_types_values_and_order(self):
        self.assertEqual(list(backend.DEFAULT_PREFERENCES),list(GOLDEN))
        self.assertEqual({k:frozen(v) for k,v in backend.DEFAULT_PREFERENCES.items()},GOLDEN)

    def test_validation_matrix_every_key_and_unknown_key(self):
        self.assertEqual(set(MATRIX),set(GOLDEN)|{'notASetting'})
        for key,rows in MATRIX.items():
            for value,expected in rows:
                with self.subTest(key=key,value=value):
                    self.assertEqual(outcome(backend.validate_preference,key,value),expected)

    def test_portable_and_appearance_membership_exact(self):
        self.assertEqual(sorted(PORTABLE),MEMBERS['portable'])
        self.assertEqual(list(APPEARANCE_KEYS),MEMBERS['appearance'])

    def test_defaults_in_both_home_contexts_and_live_settings_demo_modes(self):
        for home in ('/tmp/schema-home-a','/tmp/schema-home-b'):
            code='''from pathlib import Path
from unittest.mock import patch
import json
with patch.object(Path, 'home', return_value=Path(%r)):
 import desktop_backend as backend
 print(json.dumps(backend.DEFAULT_PREFERENCES,sort_keys=True))
''' % home
            result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'scripts')),
                                  capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            actual=json.loads(result.stdout)
            expected={k:json.loads(v[1].replace('<HOME>',home).replace('<ROOT>',str(ROOT))) for k,v in GOLDEN.items()}
            self.assertEqual(actual,expected)
        with tempfile.TemporaryDirectory() as temporary:
            preferences=backend.Preferences(Path(temporary)/'settings.json')
            self.assertEqual({k:frozen(v) for k,v in preferences.values.items()},GOLDEN)
            from test_backend import FakeRunner
            for settings_only in (False,True):
                app=backend.DesktopBackend(runner=FakeRunner(),preferences=preferences,demo=True,settings_only=settings_only,weather_fetch=False)
                try:self.assertEqual({k:frozen(v) for k,v in app.snapshot()['preferences'].items()},GOLDEN)
                finally:
                    app.feature_executor.shutdown(wait=True);app.charge_executor.shutdown(wait=True)

    def test_worker_and_main_share_three_defaults_but_keep_reload_error_policy(self):
        keys=('clipboardEnabled','clipboardImages','clipboardLimit')
        with tempfile.TemporaryDirectory() as temporary,patch.dict(os.environ,{'XDG_CONFIG_HOME':temporary}):
            path=Path(temporary)/'lme-shell/settings.json';path.parent.mkdir()
            main=backend.Preferences(path)
            self.assertEqual(clipboard.preferences(),{k:main.values[k] for k in keys})
            for value in (19,20,500,501,True,100.0):
                path.write_text(json.dumps({'clipboardLimit':value,'clipboardEnabled':False,'clipboardImages':False}))
                main.reload(force=True)
                self.assertEqual(clipboard.preferences(),{k:main.values[k] for k in keys})
            path.write_text('{broken');main.reload(force=True)
            self.assertEqual(main.values['clipboardEnabled'],False)
            self.assertEqual(clipboard.preferences(),{k:backend.DEFAULT_PREFERENCES[k] for k in keys})

    def test_realistic_old_file_preserves_values_backup_and_permissions(self):
        old=json.loads((FIXTURES/'settings-old.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'lme-shell/settings.json';path.parent.mkdir(mode=0o700)
            path.write_text(json.dumps(old,indent=2)+'\n');path.chmod(0o600);original=path.read_bytes()
            preferences=backend.Preferences(path)
            self.assertEqual(path.read_bytes(),original)
            for key,value in old.items():self.assertEqual(preferences.values[key],backend.validate_preference(key,value))
            expected=copy.deepcopy(preferences.values)
            preferences.update({'osdMargin':42},backup=True)
            saved=json.loads(path.read_text());expected['osdMargin']=42
            self.assertEqual(saved,expected)
            self.assertEqual(backend.Preferences(path).values,saved)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE(path.with_suffix('.lock').stat().st_mode),0o600)
            backups=list(path.parent.glob('settings-before-import-*.json'))
            self.assertEqual(len(backups),1)
            self.assertEqual(json.loads(backups[0].read_text())['settings']['osdMargin'],old['osdMargin'])
            self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode),0o600)

    def test_token_patch_delete_stale_merge_and_invalid_token_preserve_protocol(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'settings.json'
            first,second=backend.Preferences(path),backend.Preferences(path)
            first.set('themeOverrides','#123456',token='buttonFill')
            second.set('themeOverrides','#ABCDEF',token='barFill')
            first.set('fontOverrides','Roboto',token='body')
            second.set('themeOverrides','',token='buttonFill')
            first.set('liquidGlass',.8,token='opacity')
            state=json.loads(path.read_text())
            self.assertEqual(state['themeOverrides'],{'barFill':'#abcdef'})
            self.assertEqual(state['fontOverrides'],{'body':'Roboto'})
            self.assertEqual(state['liquidGlass']['opacity'],.8)
            before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'Invalid setting token'):first.set('themeOverrides','#123456',token=[])
            self.assertEqual(path.read_bytes(),before)


@unittest.skipUnless((ROOT/'scripts/settings_schema.py').exists(),'M5 schema interface not implemented (test-first contracts)')
class SchemaOwnershipCase(unittest.TestCase):
    def test_unique_ownership_rejects_duplicates_missing_and_unknown_keys(self):
        from settings_schema import assemble
        legacy={'order':['one','two'],'appearanceOrder':[], 'preferences':{'one':{'type':'boolean','default':True}}}
        migrated={'two':{'type':'integer','default':20}}
        schema=assemble(legacy,[migrated])
        self.assertEqual(set(schema),{'one','two'})
        with self.assertRaisesRegex(ValueError,'Duplicate'):assemble(legacy,[{'one':migrated['two']},migrated])
        with self.assertRaisesRegex(ValueError,'Missing'):assemble(legacy,[])
        with self.assertRaisesRegex(ValueError,'Unknown'):assemble(legacy,[migrated,{'three':migrated['two']}])
        with self.assertRaises(TypeError):schema['one']['default']=False

    def test_shared_schema_interface_and_disabled_descriptor_keep_owned_preferences(self):
        from settings_schema import Schema
        schema=backend.PREFERENCE_SCHEMA
        self.assertEqual(schema.defaults(),backend.DEFAULT_PREFERENCES)
        self.assertEqual(set(schema.portable_keys()),set(PORTABLE))
        self.assertEqual(tuple(schema.appearance_keys()),tuple(APPEARANCE_KEYS))
        self.assertEqual(set(schema.definitions),set(GOLDEN))
        worker=Schema()
        self.assertEqual(worker.defaults('clipboard'),clipboard.preferences())
        self.assertEqual(worker.validate('clipboardLimit',500),500)
        self.assertEqual(schema.validate('weatherUnit','fahrenheit'),'fahrenheit')
        with self.assertRaises(ValueError):worker.validate('clipboardLimit',True)
