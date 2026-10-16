"""Selected desktop port regressions using private fixtures."""
import json
import os
import signal
import sys
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
    def test_legacy_favorites_are_ignored_without_losing_other_backup_settings(self):
        from settings_transfer import validate_document
        values = {'accent': '#123456', 'favoriteApps': ['app'], 'wallpaperFavorites': ['/image.png']}
        restored = validate_document({'schema': 1, 'kind': 'backup', 'settings': values}, backend.validate_preference, backend.DEFAULT_PREFERENCES)
        self.assertEqual(restored, {'accent': '#123456'})
        self.preferences.path.parent.mkdir(parents=True, exist_ok=True)
        self.preferences.path.write_text(json.dumps(values))
        loaded = backend.Preferences(self.preferences.path)
        self.assertEqual(loaded.values['accent'], '#123456')
        for key in ['favoriteApps', 'wallpaperFavorites']:
            self.assertNotIn(key, loaded.values)
            with self.assertRaises(ValueError): loaded.set(key, [])
        with self.assertRaises(ValueError):
            validate_document({'schema': 1, 'kind': 'backup', 'settings': {**values, 'unknown': True}}, backend.validate_preference, backend.DEFAULT_PREFERENCES)

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

class BatteryCase(Fixture, unittest.TestCase):
    def test_energy_units_and_charging_time(self):
        for key,value in {'type':'Battery','capacity':'50','status':'Discharging','energy_now':'20000000','energy_full':'40000000','energy_full_design':'50000000','power_now':'10000000'}.items(): self.put('sys/class/power_supply/BAT0/'+key,value)
        live=self.make_backend();state=live.battery()
        self.assertEqual((state['health'],state['powerW'],state['secondsRemaining']),(80,10,7200))
        self.put('sys/class/power_supply/BAT0/status','Charging')
        self.assertEqual(live.battery()['secondsRemaining'],7200)
    def test_charge_units_zero_power_and_unknown_are_not_guessed(self):
        for key,value in {'type':'Battery','capacity':'60','status':'Discharging','charge_now':'3000000','charge_full':'5000000','charge_full_design':'6000000','current_now':'1000000','voltage_now':'12000000'}.items(): self.put('sys/class/power_supply/BAT0/'+key,value)
        live=self.make_backend();state=live.battery()
        self.assertEqual((state['powerW'],state['secondsRemaining']),(12,10800))
        self.assertAlmostEqual(state['health'],83.3)
        self.put('sys/class/power_supply/BAT0/current_now','0')
        self.assertIsNone(live.battery()['secondsRemaining'])
        self.put('sys/class/power_supply/BAT0/charge_full_design','NaN')
        self.assertIsNone(live.battery()['health'])

class OsdSettingsCase(unittest.TestCase):
    def test_positions_and_limits(self):
        self.assertEqual(backend.validate_preference('osdMargin',0),0)
        self.assertEqual(backend.validate_preference('osdPosition','center-right'),'center-right')
        for key,value in [('osdMargin',True),('osdMargin',97),('osdPosition','outside'),('osdLayout','diagonal'),('osdOutput','bad\nname')]:
            with self.assertRaises(ValueError): backend.validate_preference(key,value)

class VisualizerCase(unittest.TestCase):
    def test_real_frames_are_bounded_and_malformed_frames_are_discarded(self):
        from audio_visualizer import frame
        self.assertEqual(frame(';'.join(['50']*16)+';'),[.5]*16)
        self.assertEqual(frame(';'.join(['-5','200']*8)),[0,1]*8)
        for text in ['1;2',';'.join(['NaN']*16),';'.join(['invalid']*16)]: self.assertIsNone(frame(text))

class NotesCase(Fixture, unittest.TestCase):
    def test_initialization_keeps_existing_text_and_private_permissions(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ,XDG_STATE_HOME=str(self.root/'state')):
            live=self.make_backend();self.assertTrue(live.handle({'action':'notesInit'})['ok'])
            path=self.root/'state/lme-shell/notes.txt';path.write_text('Private meeting notes')
            live.handle({'action':'notesInit'})
            self.assertEqual(path.read_text(),'Private meeting notes');self.assertEqual(path.stat().st_mode & 0o777,0o600)

class PaletteCase(Fixture,unittest.TestCase):
    def test_dark_roles_are_validated_before_theme_changes(self):
        from wallpaper_palette import ROLES,colors_from_json
        raw=json.dumps({'colors':{role:{'dark':'#123456','light':'#ffffff'} for role in set(ROLES.values())}})
        self.assertEqual(colors_from_json('warning\n'+raw)['accent'],'#123456')
        with self.assertRaises(ValueError): colors_from_json(raw.replace('#123456','bad'))
        live=self.make_backend();self.preferences.set('themeOverrides',{'buttonFill':'#abcdef'})
        before=self.preferences.path.read_bytes();live.palette_preview={'colors':{},'path':'image.png'}
        self.assertFalse(live.handle({'action':'paletteApply','path':'image.png'})['ok']);self.assertEqual(before,self.preferences.path.read_bytes())
        live.palette_preview={'colors':colors_from_json(raw),'path':'image.png', 'paletteScheme':'tonal-spot','paletteMode':'dark','paletteContrast':0.0}
        self.assertTrue(live.handle({'action':'paletteApply','path':'image.png'})['ok'])
        self.assertEqual(self.preferences.values['themeOverrides'],{'buttonFill':'#abcdef'})
        self.assertEqual(self.preferences.values['paletteSource'],'wallpaper')
        self.assertTrue(live.handle({'action':'paletteReset'})['ok']);self.assertEqual(self.preferences.values['paletteSource'],'dracula')

class FileSearchCase(Fixture,unittest.TestCase):
    def test_bounded_search_ignores_hidden_and_symlink_paths(self):
        from file_search import search
        from threading import Event
        self.put('files/report.txt','text');self.put('files/.hidden/report-secret.txt','private');self.put('outside/report-other.txt','outside')
        (self.root/'files/link').symlink_to(self.root/'outside',target_is_directory=True)
        result=search('report',[str(self.root/'files')],Event())
        self.assertEqual([e['name'] for e in result['entries']],['report.txt'])
        event=Event();event.set();self.assertEqual(search('report',[str(self.root/'files')],event)['entries'],[])
        self.assertTrue(search('report',[str(self.root/'files')],Event(),max_paths=0)['truncated'])
    def test_open_only_search_results_and_keep_uri_boundaries(self):
        target=self.put('files/report #1.txt','text');runner=FakeRunner(available={'gio'});live=self.make_backend(runner)
        self.assertFalse(live.handle({'action':'fileOpen','path':str(target)})['ok'])
        live.file_search={'entries':[{'path':str(target)}]}
        self.assertTrue(live.handle({'action':'fileOpen','path':str(target)})['ok'])
        self.assertEqual(runner.spawns,[['/usr/bin/gio','open',target.as_uri()]])

class RecorderCase(Fixture,unittest.TestCase):
    def test_stop_signals_only_owned_child_and_decodes_result(self):
        import signal,time
        from screen_recording import Recorder
        from unittest.mock import Mock
        runner=FakeRunner(available={'ffmpeg'});recorder=Recorder(runner,self.root/'sys')
        path=self.put('record.mkv','video fixture');child=Mock();child.poll.return_value=None;child.returncode=0
        def wait(**_):child.poll.return_value=0;return 0
        child.wait.side_effect=wait
        recorder.child=child;recorder.path=path;recorder.started=time.monotonic();recorder.log=__import__('tempfile').TemporaryFile(mode='w+')
        recorder.info={'active':True,'owned':True,'path':str(path),'error':''}
        self.assertIn('Saved recording',recorder.stop());child.send_signal.assert_called_once_with(signal.SIGINT)
        self.assertEqual(runner.calls,[('ffmpeg','-v','error','-i',str(path),'-t','0.1','-f','null','-')])
        with self.assertRaises(ValueError): recorder.stop()
        child.poll.return_value=None;recorder.child=child;recorder.log=__import__('tempfile').TemporaryFile(mode='w+')
        runner.run=Mock(side_effect=backend.CommandError('Invalid video'))
        with self.assertRaises(ValueError): recorder.stop()
        self.assertIn('decode check failed',recorder.state()['error']);self.assertTrue(path.exists())
    def test_invalid_modes_and_non_amd_devices_cannot_start_process(self):
        from screen_recording import Recorder
        runner=FakeRunner({('ffmpeg','-hide_banner','-encoders'):' V..... libvpx-vp9\n V..... h264_vaapi'},available={'wf-recorder'})
        recorder=Recorder(runner,self.root/'sys')
        self.put('sys/class/drm/renderD129/device/vendor','0x10de')
        with self.assertRaises(ValueError): recorder.start(str(self.root/'videos'),'output','eDP-1','none','radeon')
        with self.assertRaises(ValueError): recorder.start(str(self.root/'videos'),'invalid','eDP-1','none','cpu')
        self.assertIsNone(recorder.child);self.assertFalse((self.root/'videos').exists())
        self.assertFalse(any('nvidia' in str(call) for call in runner.calls))

class RecorderPreparationCase(Fixture,unittest.TestCase):
    def test_preparation_does_not_block_state_and_shutdown_prevents_late_spawn(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from screen_recording import Recorder
        ready,release=Event(),Event()
        class Runner(FakeRunner):
            def run(self,*args,**kwargs):
                ready.set();release.wait(3);return ' V..... libvpx-vp9'
        runner=Runner(available={'wf-recorder'});recorder=Recorder(runner,self.root/'sys')
        with ThreadPoolExecutor(max_workers=1) as executor:
            future=executor.submit(recorder.start,str(self.root/'videos'),'output','eDP-1','none','cpu')
            try:
                self.assertTrue(ready.wait(1));self.assertTrue(recorder.state()['preparing'])
                recorder.close();release.set()
                with self.assertRaises(ValueError):future.result(timeout=2)
                self.assertIsNone(recorder.child);self.assertFalse((self.root/'videos').exists())
            finally: release.set()

class NotesClipboardCase(Fixture,unittest.TestCase):
    def test_text_copy_returns_while_the_clipboard_owner_keeps_its_descriptors(self):
        owner = self.root / 'owner.pid'
        received = self.root / 'received.txt'
        binary = self.put('wl-copy', f'''#!{sys.executable}
import os, sys, time
from pathlib import Path
Path({str(received)!r}).write_bytes(sys.stdin.buffer.read())
pid = os.fork()
if pid:
    Path({str(owner)!r}).write_text(str(pid))
    os._exit(0)
time.sleep(30)
''')
        binary.chmod(0o755)
        runner = backend.CommandRunner()
        runner.commands['wl-copy'] = str(binary)
        live = self.make_backend(runner)
        text = 'Calculator 42 · Emoji 🐈 · Xin chào'
        try:
            result = live.handle({'action': 'copyText', 'text': text})
            self.assertTrue(result['ok'], result)
            self.assertEqual(received.read_bytes(), text.encode())
            os.kill(int(owner.read_text()), 0)
        finally:
            if owner.exists():
                try: os.kill(int(owner.read_text()), signal.SIGTERM)
                except ProcessLookupError: pass
        binary.write_text('#!/bin/sh\nexit 7\n')
        result = live.handle({'action': 'copyText', 'text': text})
        self.assertFalse(result['ok'])
        self.assertIn('wl-copy failed (7)', result['message'])

    def test_long_unicode_notes_use_existing_clipboard_bound(self):
        from clipboard import MAX_TEXT
        class Runner(FakeRunner):
            def run(self,name,*args,**kwargs): self.text=kwargs.get('input');return ''
        runner=Runner(available={'wl-copy'});live=self.make_backend(runner);text='é'*100000
        self.assertTrue(live.handle({'action':'copyText','text':text})['ok']);self.assertEqual(runner.text,text)
        self.assertFalse(live.handle({'action':'copyText','text':'x'*(MAX_TEXT+1)})['ok'])
