"""Frozen page/order contracts before four light features leave the legacy hosts."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from light_feature_fixture import FEATURES, QUERIES, ROOT, LightWorld, converted
from feature_catalog import load_catalog, legacy_ids, canonical_index
from test_backend import backend

FROZEN = json.loads((ROOT/'tests/fixtures/catalog-legacy.json').read_text())['pages']


class LightFeatureContractsCase(unittest.TestCase):
    def test_schema_ownership_defaults_and_portability_are_unchanged(self):
        defaults = json.loads((ROOT/'tests/fixtures/settings-defaults.json').read_text())
        from schema_fixture import frozen
        for key in ('nightLightEnabled', 'nightLightMode', 'nightLightTemperature', 'nightLightStart',
                    'nightLightEnd', 'idleEnabled', 'idleProfiles', 'idleLockBeforeSleep', 'niriConfigPath',
                    'weatherAutoLocation', 'weatherLocation', 'weatherUnit'):
            self.assertEqual(frozen(backend.DEFAULT_PREFERENCES[key]), defaults[key])
        for feature in converted():
            record = next(r for r in json.loads((ROOT/'config/features.json').read_text())['features'] if r['id'] == feature)
            descriptor = json.loads((ROOT/record['descriptor']).read_text())
            self.assertEqual(descriptor['settingsPage'], record['startup']['settingsPage'])
            for key in descriptor['preferences']:
                self.assertNotIn(key, backend.PREFERENCE_SCHEMA.legacy_keys)
                self.assertIn(key, backend.DEFAULT_PREFERENCES)
        load_catalog(ROOT, legacy=legacy_ids(ROOT), setting_keys=backend.PREFERENCE_SCHEMA.legacy_keys)

    def test_converted_pages_leave_all_legacy_hosts_in_the_same_slice(self):
        if not converted(): self.skipTest('M4c-1 conversions absent on unmodified main; ownership contract N/A')
        registry=(ROOT/'qml/settings/SettingsRegistry.qml').read_text().split('legacyPages:',1)[1].split('\n    function',1)[0]
        view=(ROOT/'qml/settings/SettingsView.qml').read_text()
        allowlist=(ROOT/'qml/services/ShellState.qml').read_text()
        legacy_cli=(ROOT/'scripts/settings.sh').read_text().split('case "$page" in',1)[1].split('    *)',1)[0]
        for feature in converted():
            page_type = FEATURES[feature][0]
            self.assertNotIn('key: "'+feature+'"',registry)
            self.assertNotIn('root.page === "'+feature+'"',view)
            self.assertNotIn(page_type+' {}',view)
            self.assertNotIn(page_type+' 1.0', (ROOT/'qml/settings/qmldir').read_text())
            self.assertNotIn('"'+feature+'"',allowlist.split('function openSettingsPage',1)[0].split('function settingsPageAvailable',1)[-1])
            self.assertNotIn(feature,legacy_cli)


@unittest.skipUnless(os.environ.get('LME_TEST_LIGHT_FEATURES') == '1', 'private Wayland light-feature catalog checks')
class NativeLightFeatureCase(unittest.TestCase):
    def world(self):
        temp=tempfile.TemporaryDirectory(prefix='light-');self.addCleanup(temp.cleanup)
        return LightWorld(Path(temp.name))

    def test_sidebar_search_cli_pages_and_shell_routes_match_unmodified_order(self):
        world=self.world()
        expected=[page['key'] for page in FROZEN]
        searches=[[page['key'] for page in FROZEN if all(word in (page['title']+' '+page['description']+' '+page['keywords']).lower()
                    for word in query.lower().strip().split())] for query in QUERIES]
        for feature,(_,mark,key,value) in FEATURES.items():
            with self.subTest(page=feature),world.launch('settings',page=feature) as probe:
                state=probe.wait(lambda s:mark in s['marks'])
                self.assertEqual(state['page'],feature);self.assertEqual(state['pages'],expected)
                self.assertEqual(state['searches'],searches)
                self.assertEqual(probe.call('startupPending',target='settings'),'false')
                self.assertEqual(probe.call('openPage', 'appearance',target='settings'),'true')
                probe.wait(lambda s:s['page']=='appearance')
                self.assertEqual(probe.call('search', FROZEN[expected.index(feature)]['title']),'true')
                probe.wait(lambda s:s['page']==feature and mark in s['marks'])
                sequence=state['lastResult'].get('sequence',0)
                probe.call('setting',key,json.dumps(value))
                probe.wait(lambda s:s['preferences'].get(key)==value and s['lastResult'].get('sequence',0)>sequence)
            self.assertEqual(json.loads(world.settings.read_text())[key],value)
        with world.launch() as probe:
            for feature,(_,mark,_,_) in FEATURES.items():
                probe.call('open',feature);probe.wait(lambda s:s['page']==feature and mark in s['marks'])
                probe.call('close',target='shell');probe.wait(lambda s:not s['panelOpen'])
            probe.call('toggle','control',target='shell');probe.wait(lambda s:s['weatherGear'])
            self.assertEqual(probe.call('gear'),'true')
            probe.wait(lambda s:s['page']=='weather' and FEATURES['weather'][1] in s['marks'])

    def test_disabled_entries_withdraw_ui_and_routes_but_keep_settings_and_data(self):
        if not converted(): self.skipTest('M4c-1 conversions absent on unmodified main; withdrawal N/A')
        for feature in converted():
            with self.subTest(feature=feature):
                world=self.world();world.toggle(feature,False)
                saved=json.loads(world.settings.read_text())
                saved.update(controlLayout=backend.DEFAULT_CONTROL_LAYOUT,controlGrid=backend.DEFAULT_CONTROL_GRID)
                if feature=='weather': saved['nightLightMode']='sunset'
                world.settings.write_text(json.dumps(saved))
                original=world.settings.read_bytes()
                marker=world.home/'state/preserved-data';marker.write_text('keep me')
                descriptor=(world.root/'config'/f'{feature}.json').read_bytes()
                with world.launch() as probe:
                    state=probe.wait(lambda s:s['ready']);self.assertNotIn(feature,state['pages'])
                    self.assertEqual(state['preferences']['controlLayout'],saved['controlLayout'])
                    self.assertEqual(state['preferences']['controlGrid'],saved['controlGrid'])
                    self.assertNotIn(feature,state['searches'][0])
                    probe.call('open',feature);self.assertFalse(probe.wait(lambda s:True)['panelOpen'])
                    probe.call('toggle','control',target='shell')
                    state=probe.wait(lambda s:s['panelOpen'])
                    probe.wait(lambda s:s['progress']==1)
                    state=probe.wait(lambda s:True)
                    if feature=='nightLight': self.assertFalse(state['nightTile'])
                    if feature=='idle': self.assertFalse(state['idleTile'])
                    if feature=='weather':
                        self.assertFalse(state['weatherCard']);self.assertFalse(state['weatherGear'])
                with world.launch('settings') as probe:
                    self.assertNotIn(feature,probe.wait(lambda s:s['ready'])['pages'])
                    if feature=='weather':
                        probe.call('openPage','nightLight',target='settings')
                        state=probe.wait(lambda s:FEATURES['nightLight'][1] in s['marks'])
                        self.assertFalse(state['weatherRouteEnabled'])
                    reply=subprocess.run([str(world.root/'scripts/settings.sh'),'--page',feature],env=probe.env,capture_output=True,text=True,timeout=5)
                    self.assertEqual((reply.returncode,reply.stderr),(2,'Error: unknown settings page: '+feature+'\n'))
                self.assertEqual(world.settings.read_bytes(),original);self.assertEqual(marker.read_text(),'keep me')
                self.assertEqual((world.root/'config'/f'{feature}.json').read_bytes(),descriptor)
                world.toggle(feature,True)
                with world.launch('settings',page=feature) as probe:
                    probe.wait(lambda s:FEATURES[feature][1] in s['marks'])
                    self.assertIn(feature,probe.wait(lambda s:True)['pages'])

    def test_fifth_page_and_schema_need_only_own_files_descriptor_and_index(self):
        world=self.world();root=world.root
        before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
        page=root/'qml/settings/FifthFeature.qml'
        page.write_text('import QtQuick\nItem { implicitHeight:100; Text { text:"Fifth feature" } }\n')
        descriptor=dict(id='fifthFeature',sources=['qml/settings/FifthFeature.qml'],
            settingsPage=dict(key='fifthFeature',title='Fifth feature',icon='settings',description='A comparable page',keywords='fifth',
                              entry='qml/settings/FifthFeature.qml',after='keybinds'),
            preferences={'fifthEnabled':dict(type='boolean',default=True,validator='boolean',portable=False,appearance=False)})
        (root/'config/fifthFeature.json').write_text(json.dumps(descriptor))
        index=root/'config/features.json';data=json.loads(index.read_text())
        data['features'].append(dict(id='fifthFeature',descriptor='config/fifthFeature.json',enabled=True,startup={'settingsPage':descriptor['settingsPage']}))
        index.write_text(canonical_index(data))
        self.assertEqual([name for name,content in before.items() if (root/name).read_bytes()!=content],['config/features.json'])
        with world.launch('settings',page='fifthFeature') as probe:
            state=probe.wait(lambda s:'Fifth feature' in s['marks'])
            self.assertTrue(state['preferences']['fifthEnabled']);self.assertEqual(state['page'],'fifthFeature')
