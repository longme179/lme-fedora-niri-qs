"""Selected desktop port regressions using private fixtures."""
import json
import unittest
from test_backend import backend, Fixture, FakeRunner
from privacy import captures

class PrivacyCase(Fixture, unittest.TestCase):
    def node(self, ident, media, **props):
        return {'id':ident,'type':'PipeWire:Interface:Node','info':{'state':'running','props':{'media.class':media,**props}}}
    def test_muted_and_virtual_nodes_do_not_hide_another_capture(self):
        muted=self.node(1,'Stream/Input/Audio');muted['info']['params']={'Props':[{'mute':True}]}
        nodes=[muted,self.node(2,'Stream/Input/Audio',**{'application.name':'Meeting'}),self.node(3,'Stream/Input/Audio',**{'stream.capture.sink':'true'}),self.node(4,'Stream/Input/Audio',**{'node.name':'cava'}),self.node(5,'Video/Source',**{'node.name':'niri-screencast'})]
        self.assertEqual([(c['id'],c['kind']) for c in captures(nodes)],[(2,'microphone'),(5,'screen')])
        nodes[1]['info']['state']='suspended'
        self.assertEqual([c['kind'] for c in captures(nodes)],['screen'])
    def test_invalid_or_unavailable_pipewire_is_not_active(self):
        live=self.make_backend(FakeRunner({('pw-dump',):'invalid'}))
        self.assertFalse(live.privacy()['available'])
        self.assertEqual(live.privacy()['captures'],[])

class TransferCase(Fixture, unittest.TestCase):
    def test_portable_excludes_private_data_and_rejects_partial_invalid_import(self):
        from settings_transfer import document, validate_document, export_document
        values={**backend.DEFAULT_PREFERENCES,'tasks':[{'id':'note','text':'Private','done':False}],'weatherLocation':{'latitude':1,'longitude':2}}
        data=document(values,'preset')
        self.assertFalse(set(data['settings']) & {'tasks','weatherLocation','wallpaper','bluetoothAdapter','niriConfigPath','displayLayout'})
        self.assertIn('barLayout',data['settings'])
        validate_document(data,backend.validate_preference,backend.DEFAULT_PREFERENCES)
        path=self.root/'preset.json';export_document(str(path),values,'preset')
        with self.assertRaises(FileExistsError): export_document(str(path),values,'preset')
        self.preferences.set('accent','#123456')
        before=self.preferences.path.read_bytes()
        path.write_text(json.dumps({'schema':1,'kind':'preset','settings':{'accent':'#ffffff','opacity':0}}))
        result=self.make_backend().handle({'action':'settingsImport','path':str(path)})
        self.assertFalse(result['ok']);self.assertEqual(self.preferences.path.read_bytes(),before)
    def test_restore_creates_private_backup_before_applying(self):
        from settings_transfer import export_document
        self.preferences.set('accent','#123456')
        path=self.root/'preset.json';export_document(str(path),{**backend.DEFAULT_PREFERENCES,'accent':'#abcdef'},'preset')
        result=self.make_backend().handle({'action':'settingsImport','path':str(path)})
        self.assertTrue(result['ok'],result);self.assertEqual(self.preferences.values['accent'],'#abcdef')
        backups=list(self.preferences.path.parent.glob('settings-before-import-*.json'))
        self.assertEqual(len(backups),1);self.assertEqual(json.loads(backups[0].read_text())['settings']['accent'],'#123456')
        self.assertEqual(backups[0].stat().st_mode & 0o777,0o600)
