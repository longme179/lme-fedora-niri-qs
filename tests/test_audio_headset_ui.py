"""Audio UI characterization and later controls run only in private sessions."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from audio_ui_fixture import AudioWorld


@unittest.skipUnless(os.environ.get('LME_TEST_AUDIO_UI') == '1', 'private Wayland audio/headset UI')
class NativeAudioBaselineCase(unittest.TestCase):
    def test_existing_mixer_opens_closes_and_reopens_in_the_actual_shell(self):
        with tempfile.TemporaryDirectory(prefix='audio-ui-') as directory:
            world=AudioWorld(Path(directory))
            with world.launch('demo') as probe:
                for _ in range(2):
                    probe.call('open',target='audioHeadset')
                    probe.wait(lambda _:json.loads(probe.call('state',target='audioHeadset'))['heading'])
                    state=json.loads(probe.call('state',target='audioHeadset'))
                    self.assertEqual(state['labels'],['Audio devices & mixer','Output device','Input device','Applications'])
                    self.assertTrue(state['open'])
                    probe.call('close',target='shell')
                    probe.wait(lambda s:not s['panelOpen'])


@unittest.skipUnless(os.environ.get('LME_TEST_AUDIO_UI')=='1','private Wayland audio/headset UI')
@unittest.skipUnless((Path(__file__).resolve().parents[1]/'qml/panels/AudioHardware.qml').exists(),
    'W1 device UI absent on unmodified baseline')
class NativeAudioControlsCase(unittest.TestCase):
    def state(self,probe):return json.loads(probe.call('state',target='audioHeadset'))

    def test_demo_profile_and_app_output_follow_observed_state_and_reopen(self):
        with tempfile.TemporaryDirectory(prefix='audio-demo-') as directory:
            world=AudioWorld(Path(directory));world.fake_audio()
            with world.launch('demo') as probe:
                probe.call('open',target='audioHeadset')
                probe.wait(lambda _:self.state(probe)['audio'].get('available'))
                self.assertEqual(probe.call('select','audioProfile-card/1/101','1',target='audioHeadset'),'true')
                probe.wait(lambda _:self.state(probe)['audio']['cards'][0]['activeProfile']=='headset')
                self.assertEqual(probe.call('select','audioRoute-stream/20/120','1',target='audioHeadset'),'true')
                probe.wait(lambda _:self.state(probe)['audio']['streams'][0]['sinkId']=='sink/11/111')
                self.assertFalse(world.audio_calls.exists())
                probe.call('close',target='shell');probe.wait(lambda s:not s['panelOpen'])
                probe.call('open',target='audioHeadset')
                probe.wait(lambda _:self.state(probe)['heading'])
                self.assertFalse(world.audio_calls.exists())

    def test_unavailable_option_and_failed_readback_do_not_change_the_displayed_profile(self):
        with tempfile.TemporaryDirectory(prefix='audio-fail-') as directory:
            world=AudioWorld(Path(directory));world.fake_audio()
            with world.launch() as probe:
                probe.call('open',target='audioHeadset');probe.wait(lambda _:self.state(probe)['audio'].get('available'))
                name='audioProfile-card/1/101'
                choice=json.loads(probe.call('choice',name,target='audioHeadset'))
                self.assertEqual(choice['index'],0);self.assertEqual(choice['disabled'],[2])
                self.assertEqual(probe.call('select',name,'2',target='audioHeadset'),'true')
                self.assertFalse(any(json.loads(line)[0]=='--' for line in world.audio_calls.read_text().splitlines()))
                data=json.loads(world.audio_file.read_text());data['apply']=False;world.audio_file.write_text(json.dumps(data))
                self.assertEqual(probe.call('select',name,'1',target='audioHeadset'),'true')
                probe.wait(lambda _:self.state(probe)['result'].get('action')=='audioProfile' and not self.state(probe)['result'].get('pending'))
                current=self.state(probe)
                self.assertFalse(current['result']['ok']);self.assertFalse(current['pending'].get('audioProfile'))
                self.assertEqual(current['audio']['cards'][0]['activeProfile'],'output:stereo')
                self.assertEqual(json.loads(probe.call('choice',name,target='audioHeadset'))['index'],0)

    def test_disabled_audio_addon_keeps_legacy_mixer_and_settings_bytes_without_queries(self):
        from feature_catalog import canonical_index
        with tempfile.TemporaryDirectory(prefix='audio-withdraw-') as directory:
            world=AudioWorld(Path(directory));world.fake_audio();path=world.root/'config/features.json'
            index=json.loads(path.read_text());next(r for r in index['features'] if r['id']=='audio')['enabled']=False
            path.write_text(canonical_index(index));saved=world.settings.read_bytes()
            with world.launch() as probe:
                probe.call('open',target='audioHeadset');probe.wait(lambda _:self.state(probe)['heading'])
                self.assertNotIn('audioRefresh',self.state(probe)['fields'])
                self.assertFalse(world.audio_calls.exists())
            self.assertEqual(world.settings.read_bytes(),saved)

    @unittest.skipUnless(os.environ.get('LME_TEST_AUDIO_SESSION')=='1','opt-in private virtual PipeWire/Pulse session')
    def test_actual_mixer_selects_a_real_private_stream_destination(self):
        from audio_session_fixture import AudioSession
        with AudioSession() as session,tempfile.TemporaryDirectory(prefix='audio-native-') as directory:
            session.streams();world=AudioWorld(Path(directory))
            for key in ('PIPEWIRE_RUNTIME_DIR','PIPEWIRE_REMOTE','PULSE_SERVER','PULSE_COOKIE','PIPEWIRE_CONFIG_DIR','PIPEWIRE_MODULE_DIR','SPA_PLUGIN_DIR'):
                world.env[key]=session.env[key]
            with world.launch() as probe:
                probe.call('open',target='audioHeadset');probe.wait(lambda _:len(self.state(probe)['audio'].get('streams',[]))==2)
                model=self.state(probe)['audio'];stream=model['streams'][0];target=next(x for x in model['sinks'] if x['name']=='TestHeadset')
                index=model['sinks'].index(target)
                self.assertEqual(probe.call('select','audioRoute-'+stream['id'],str(index),target='audioHeadset'),'true')
                probe.wait(lambda _:self.state(probe)['result'].get('action')=='audioRoute' and not self.state(probe)['result'].get('pending'))
                state=self.state(probe)
                self.assertTrue(state['result']['ok'],state)
                self.assertEqual(next(x for x in state['audio']['streams'] if x['id']==stream['id'])['sinkId'],target['id'])
