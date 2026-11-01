"""Actual private virtual audio capability, isolated from all user sockets/hardware."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from audio_session_fixture import AudioSession
from test_backend import Fixture, backend


@unittest.skipUnless(os.environ.get('LME_TEST_AUDIO_SESSION')=='1','opt-in private virtual PipeWire/Pulse session')
class PrivateAudioCase(Fixture,unittest.TestCase):
    def test_pulse_stream_mapping_and_one_of_two_apps_moves_to_private_headset(self):
        with AudioSession() as session:
            before=session.streams();stream=before[0];other=before[1]
            dump=json.loads(subprocess.check_output([session.tools['pw-dump']],env=session.env,text=True,timeout=3))
            nodes={str(o.get('info',{}).get('props',{}).get('object.serial')):o['id']
                for o in dump if o['type']=='PipeWire:Interface:Node'}
            for item in before:self.assertIn(item['properties']['object.serial'],nodes)
            self.assertTrue(any(item['index']!=nodes[item['properties']['object.serial']] for item in before))
            from audio_pipewire import route_plan, apply_route
            sink=next(s for s in session.json('list','sinks') if s['name']=='TestHeadset');target=sink['index']
            route=route_plan(session.json('info'),dump,stream['properties']['object.serial'],sink['properties']['object.serial'])
            apply_route(lambda *argv:subprocess.check_output(argv,env=session.env,text=True,timeout=3),route)
            session.wait(lambda:next(s for s in session.json('list','sink-inputs') if s['index']==stream['index'])['sink']==target)
            after=session.json('list','sink-inputs')
            self.assertEqual(next(s for s in after if s['index']==other['index'])['sink'],other['sink'])

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'scripts/audio_devices.py').exists(),
        'W1 provider absent on unmodified baseline')
    def test_registry_moves_a_real_private_stream_and_confirms_the_actual_destination(self):
        with AudioSession() as session,patch.dict(os.environ,session.env):
            session.streams();runner=backend.CommandRunner();live=self.make_backend(runner)
            self.addCleanup(runner.close);self.addCleanup(live.charge_executor.shutdown)
            self.addCleanup(live.feature_executor.shutdown)
            def perform(request):
                result=live.handle(request);self.assertTrue(result['pending'])
                live.feature_jobs[request['action']].result(timeout=8);live.finish_features()
                self.assertTrue(live.last_result['ok'],live.last_result)
            perform({'action':'audioDevicesRefresh'})
            model=live.action_state()['audioDevices'];target=next(s for s in model['sinks'] if s['name']=='TestHeadset')
            perform(dict(action='audioRoute',serverId=model['serverId'],streamId=model['streams'][0]['id'],sinkId=target['id']))
            actual=live.action_state()['audioDevices']
            self.assertEqual(actual['streams'][0]['sinkId'],target['id'])
            self.assertNotEqual(actual['streams'][1]['sinkId'],target['id'])
            self.assertFalse(live.feature_jobs)

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'scripts/audio_pipewire.py').exists(),
        'W1 native routing absent on baseline')
    def test_explicit_client_target_can_move_to_the_default_sink_without_moving_other_apps(self):
        with AudioSession() as session,patch.dict(os.environ,session.env):
            session.streams();session.pulse('--','set-default-sink','TestHeadset')
            session.wait(lambda:session.json('info')['default_sink_name']=='TestHeadset')
            from audio_devices import AudioDevices
            runner=backend.CommandRunner();self.addCleanup(runner.close)
            devices=AudioDevices(runner.run,runner.available);m=devices.refresh()['state']
            target=next(s for s in m['sinks'] if s['name']=='TestHeadset')
            result=devices.change('audioRoute',dict(serverId=m['serverId'],streamId=m['streams'][0]['id'],sinkId=target['id']))
            self.assertEqual(result['state']['streams'][0]['sinkId'],target['id'])
            self.assertEqual(result['state']['streams'][1]['sinkId'],m['streams'][1]['sinkId'])
