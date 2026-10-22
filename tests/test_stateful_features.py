"""Characterize existing stateful pages, public routes, defaults and desktop lifetime."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from stateful_feature_fixture import FEATURES, ROOT, StatefulWorld, converted, catalog_id
from test_backend import backend
from feature_catalog import load_catalog, legacy_ids

FROZEN=json.loads((ROOT/'tests/fixtures/catalog-legacy.json').read_text())['pages']
QUERIES=['','wallpaper','notification','desktop','scripts']

class StatefulContractsCase(unittest.TestCase):
    def test_defaults_validation_and_catalog_ownership_preserve_existing_inventory(self):
        from schema_fixture import frozen
        defaults=json.loads((ROOT/'tests/fixtures/settings-defaults.json').read_text())
        for key in defaults:
            self.assertEqual(frozen(backend.DEFAULT_PREFERENCES[key]),defaults[key],key)
        load_catalog(ROOT,legacy=legacy_ids(ROOT),setting_keys=backend.PREFERENCE_SCHEMA.legacy_keys)

    def test_converted_pages_have_no_legacy_registration_or_schema_owner(self):
        selected=[f for f in FEATURES if converted(f)]
        if not selected: self.skipTest('M4c-2 conversion absent on unmodified main; ownership N/A')
        registry=(ROOT/'qml/settings/SettingsRegistry.qml').read_text()
        view=(ROOT/'qml/settings/SettingsView.qml').read_text()
        cli=(ROOT/'scripts/settings.sh').read_text().split('case "$page" in',1)[1].split('    *)',1)[0]
        for feature in selected:
            self.assertNotIn('key: "'+feature+'"',registry)
            self.assertNotIn('root.page === "'+feature+'"',view)
            self.assertNotIn(FEATURES[feature][0]+' 1.0',(ROOT/'qml/settings/qmldir').read_text())
            self.assertNotIn(feature,cli)
            descriptor=json.loads((ROOT/'config'/f'{catalog_id(feature)}.json').read_text())
            for key in descriptor['preferences']: self.assertNotIn(key,backend.PREFERENCE_SCHEMA.legacy_keys)

@unittest.skipUnless(os.environ.get('LME_TEST_STATEFUL_UI')=='1','private Wayland stateful feature checks')
class NativeStatefulCase(unittest.TestCase):
    def world(self):
        directory=tempfile.TemporaryDirectory(prefix='stateful-');self.addCleanup(directory.cleanup)
        return StatefulWorld(Path(directory.name))

    def test_cli_sidebar_search_and_page_reopen_preserve_order(self):
        world=self.world();expected=[p['key'] for p in FROZEN]
        searches=[[p['key'] for p in FROZEN if all(w in (p['title']+' '+p['description']+' '+p['keywords']).lower()
                    for w in q.split())] for q in QUERIES]
        for feature,(_,mark) in FEATURES.items():
            with self.subTest(page=feature),world.launch('settings',page=feature) as probe:
                state=probe.wait(lambda s:mark in s['marks'])
                self.assertEqual(state['pages'],expected);self.assertEqual(state['searches'],searches)
                self.assertEqual(state['page'],feature)
                self.assertEqual(probe.call('startupPending',target='settings'),'false')
                self.assertEqual(probe.call('openPage','appearance',target='settings'),'true')
                probe.wait(lambda s:s['page']=='appearance')
                self.assertEqual(probe.call('search',FROZEN[expected.index(feature)]['title']),'true')
                probe.wait(lambda s:s['page']==feature and mark in s['marks'])

    def test_existing_cross_page_buttons_use_existing_ids(self):
        world=self.world()
        with world.launch() as probe:
            for source,button,target in [('notifications','Font families…','elements'),('utilities','Open awww controls','wallpaper'),
                                         ('nightLight','Weather location settings','weather')]:
                probe.call('open',source);probe.wait(lambda s:s['page']==source)
                self.assertEqual(probe.call('button',button),'true')
                probe.wait(lambda s:s['page']==target)
                probe.call('close',target='shell');probe.wait(lambda s:not s['panelOpen'])

    def test_desktop_output_edit_geometry_and_restore_lifecycle(self):
        world=self.world()
        saved=json.loads(world.settings.read_text())
        record=dict(type='clock',output='primary',x=.2,y=.3,width=320,height=220,enabled=True,interactive=False)
        saved.update(desktopEnabled=True,desktopShapes=True,desktopWidgets={'clock-test':record})
        world.settings.write_text(json.dumps(saved))
        with world.launch('shell') as probe:
            state=probe.wait(lambda s:len(s['windows'])==1 and s['ambient']>=1)
            window=state['windows'][0]
            self.assertEqual((window['width'],window['height']),(320,220));self.assertTrue(window['clickthrough'])
            self.assertEqual(probe.call('desktopEdit',target='shell'),'true')
            state=probe.wait(lambda s:s['editing'] and s['windows'][0]['layer']!=window['layer'])
            self.assertFalse(state['windows'][0]['clickthrough'])
            self.assertNotEqual(state['windows'][0]['keyboard'],window['keyboard'])
            self.assertEqual(probe.call('desktopEdit',target='shell'),'true')
            probe.wait(lambda s:not s['editing'] and s['windows'][0]['layer']==window['layer'])
            probe.call('setting','desktopEnabled','false');probe.wait(lambda s:not s['windows'])
            probe.call('setting','desktopEnabled','true');probe.wait(lambda s:len(s['windows'])==1)
            self.assertEqual(probe.wait(lambda s:True)['preferences']['desktopWidgets'],saved['desktopWidgets'])
        with world.launch('shell') as probe:
            state=probe.wait(lambda s:len(s['windows'])==1)
            self.assertEqual(state['windows'][0],window)

    def test_withdrawal_keeps_schema_data_and_saved_layout_bytes(self):
        selected=[f for f in FEATURES if converted(f)]
        if not selected: self.skipTest('M4c-2 conversion absent on unmodified main; withdrawal N/A')
        for feature in selected:
            with self.subTest(feature=feature):
                world=self.world();world.toggle(catalog_id(feature),False)
                saved=json.loads(world.settings.read_text())
                saved.update(desktopEnabled=True,desktopShapes=True,barLayout=backend.PREFERENCE_SCHEMA.defaults()['barLayout'])
                world.settings.write_text(json.dumps(saved));original=world.settings.read_bytes()
                data=world.home/'state/lme-shell/notes.txt';data.write_text('Preserve saved widget notes')
                history=world.home/'config/lme-shell/notification-history.json';history.write_text('[]')
                with world.launch('shell') as probe:
                    state=probe.wait(lambda s:s['ready']);self.assertNotIn(feature,state['pages'])
                    if feature=='desktop':
                        self.assertNotIn('desktop',state['bars']);self.assertFalse(state['windows']);self.assertEqual(state['ambient'],0)
                        self.assertEqual(probe.call('desktopEdit',target='shell'),'false')
                with world.launch('settings') as probe:
                    self.assertNotIn(feature,probe.wait(lambda s:s['ready'])['pages'])
                    if feature=='wallpaper':
                        probe.call('openPage','utilities',target='settings')
                        probe.wait(lambda s:'Wallpaper engine' in s['marks'])
                        self.assertEqual(probe.call('button','Open awww controls'),'false')
                    reply=subprocess.run([str(world.root/'scripts/settings.sh'),'--page',feature],env=probe.env,capture_output=True,text=True,timeout=5)
                    self.assertEqual((reply.returncode,reply.stderr),(2,'Error: unknown settings page: '+feature+'\n'))
                self.assertEqual(world.settings.read_bytes(),original)
                self.assertEqual(data.read_text(),'Preserve saved widget notes');self.assertEqual(history.read_text(),'[]')
                world.toggle(catalog_id(feature),True)
                with world.launch('settings',page=feature) as probe:
                    probe.wait(lambda s:FEATURES[feature][1] in s['marks'])
