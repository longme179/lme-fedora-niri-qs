"""Characterize numeric/context contracts before extending the existing catalog."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import feature_catalog as reader
import catalog_fixture as fixture
from stateful_feature_fixture import StatefulWorld

A='legacyIndex' in reader.FIELDS['controlTab']
B='contexts' in reader.FIELDS['bootstrap']

class CapabilityContractsCase(unittest.TestCase):
    def test_six_existing_integer_ids_and_agenda_mapping_are_frozen(self):
        data=json.loads((fixture.REPO/'config/control-grid.json').read_text())
        catalog=reader.load_catalog(fixture.REPO)
        tabs=data['tabs']+catalog['controlTab']
        self.assertEqual({t['id']:t['legacyIndex'] for t in tabs},dict(controls=0,audio=1,devices=2,agenda=3,notifications=4,system=5))
        self.assertEqual({t['id']:t['legacyIndex'] for t in data['agendaTabs']},dict(calendar=0,tasks=1,timer=2,notes=3))

    @unittest.skipUnless(A,'capability A absent on unmodified main; extension validation N/A')
    def test_integer_metadata_and_collisions_are_validated_for_both_namespaces(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('config','qml/bar','qml/settings','qml/panels'): (root/name).mkdir(parents=True,exist_ok=True)
            descriptor=fixture.inject(root)
            for kind in ('controlTab','agendaTab'):
                descriptor[kind]=dict(id='catalogFixture',title='Fixture',entry='qml/panels/CatalogFixture.qml',legacyIndex=7)
            file=root/'config/feature-fixture.json'
            for bad in (True,-1,1.5,'7',None,2147483648):
                descriptor['controlTab']['legacyIndex']=bad;file.write_text(json.dumps(descriptor))
                with self.subTest(value=bad),self.assertRaises(reader.CatalogError):reader.load_catalog(root)
            descriptor['controlTab']['legacyIndex']=7;file.write_text(json.dumps(descriptor))
            self.assertEqual(reader.load_catalog(root)['agendaTab'][0]['legacyIndex'],7)
            (root/'config/control-grid.json').write_text(json.dumps(dict(tabs=[dict(id='legacy',legacyIndex=7)],agendaTabs=[])))
            with self.assertRaisesRegex(reader.CatalogError,'legacyIndex'):reader.load_catalog(root)

    @unittest.skipUnless(B,'capability B absent on unmodified main; contexts validation N/A')
    def test_context_allowlist_is_explicit_bounded_and_not_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('config','qml/bar','qml/settings','qml/panels'): (root/name).mkdir(parents=True,exist_ok=True)
            descriptor=fixture.inject(root)
            descriptor['bootstrap']=dict(id='catalogFixture',entry='qml/panels/CatalogFixture.qml')
            file=root/'config/feature-fixture.json'
            for bad in ('demo',[],['unknown'],['demo','demo'],[True],['live-main','callback()']):
                descriptor['bootstrap']['contexts']=bad;file.write_text(json.dumps(descriptor))
                with self.subTest(contexts=bad),self.assertRaises(reader.CatalogError):reader.load_catalog(root)
            descriptor['bootstrap']['contexts']=['live-main','demo','preview','settings'];file.write_text(json.dumps(descriptor))
            self.assertEqual(reader.load_catalog(root)['bootstrap'][0]['contexts'],descriptor['bootstrap']['contexts'])

@unittest.skipUnless(os.environ.get('LME_TEST_CAPABILITY_UI')=='1','private copied-checkout capability checks')
class NativeCapabilityCase(unittest.TestCase):
    @unittest.skipUnless(A,'capability A absent on unmodified main; native extension N/A')
    def test_declared_control_and_agenda_entries_render_by_integer_id_and_env(self):
        def prepare(root):
            descriptor=fixture.inject(root)
            descriptor['controlTab']['legacyIndex']=7
            descriptor['agendaTab']=dict(id='catalogAgenda',title='Catalog agenda',entry='qml/panels/CatalogFixture.qml',legacyIndex=8)
            (root/'config/feature-fixture.json').write_text(json.dumps(descriptor))
            index=root/'config/features.json';data=json.loads(index.read_text())
            data['features'][0]['startup'].update(controlTab=descriptor['controlTab'],agendaTab=descriptor['agendaTab'])
            index.write_text(reader.canonical_index(data))
        qml=fixture.QML.replace('Loader { id: center;', 'Loader { id: agenda; active:false; sourceComponent: Agenda {} }\n        Loader { id: center;')
        qml=qml.replace('barLoaded: find(', 'current:center.item ? center.item.currentTab : -1, agendaLoaded:find(agenda.item,"injectedTab"), barLoaded: find(')
        qml=qml.replace('        function entries()', '''
        function envOpen(): void { center.active=true; }
        function number(value: int): void { center.item.currentTab=value; }
        function agendaEntry(id: bool): void { center.active=false;agenda.active=true; if(id)agenda.item.selectTab("catalogAgenda");else agenda.item.tab=8; }
        function entries()''')
        with patch.object(fixture,'QML',qml),patch.dict(os.environ,LME_SHELL_CONTROL_TAB='catalogFixture'),fixture.session(native=True,prepare=prepare) as probe:
            state=probe.wait(lambda s:len(s['tabs'])==7)
            self.assertEqual([t['legacyIndex'] for t in state['tabs']],[0,1,2,3,4,5,7])
            probe.call('envOpen');probe.wait(lambda s:s['current']==7 and s['tabLoaded'])
            probe.call('number','0');probe.wait(lambda s:s['current']==0 and not s['tabLoaded'])
            probe.call('number','7');probe.wait(lambda s:s['tabLoaded'])
            probe.call('control');probe.wait(lambda s:s['current']==7 and s['tabLoaded'])
            for by_id in ('false','true'):
                probe.call('agendaEntry',by_id);probe.wait(lambda s:s['agendaLoaded'])

    @unittest.skipUnless(B,'capability B absent on unmodified main; native contexts N/A')
    def test_context_bootstraps_once_and_clipboard_retains_main_only_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            world=StatefulWorld(Path(directory))
            index=world.root/'config/features.json';data=json.loads(index.read_text())
            for context in ('live-main','demo','preview','settings'):
                ident='context'+context.replace('-','')
                path='qml/panels/'+ident+'.qml'
                (world.root/path).write_text('import QtQuick\nQtObject { Component.onCompleted: console.log("BOOT_'+context+'") }\n')
                boot=dict(id=ident,entry=path,contexts=[context])
                descriptor='config/'+ident+'.json';(world.root/descriptor).write_text(json.dumps(dict(id=ident,bootstrap=boot)))
                data['features'].append(dict(id=ident,descriptor=descriptor,enabled=True,startup=dict(bootstrap=boot)))
            index.write_text(reader.canonical_index(data))
            for mode,context in [('shell','live-main'),('demo','demo'),('preview','preview'),('settings','settings')]:
                before=len(world.workers())
                with self.subTest(mode=mode),world.launch(mode) as probe:
                    probe.wait(lambda s:('BOOT_'+context).encode() in os.pread(probe.log.fileno(),1048576,0))
                    output=os.pread(probe.log.fileno(),1048576,0).decode()
                    for other in ('live-main','demo','preview','settings'):
                        self.assertEqual(output.count('BOOT_'+other),int(other==context),output)
                    self.assertEqual(len(world.workers())-before,int(mode=='shell'))
