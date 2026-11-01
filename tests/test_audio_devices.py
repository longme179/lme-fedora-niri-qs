"""W1 inventory/registry contracts; provider-only cases are N/A on baseline."""
import copy
import importlib
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from audio_device_fixture import documents, PulseRunner
from action_test_helpers import complete_action
from test_backend import Fixture, backend

PRESENT=(Path(__file__).resolve().parents[1]/'scripts/audio_devices.py').exists()


@unittest.skipUnless(PRESENT,'W1 inventory not present on unmodified baseline')
class AudioInventoryCase(unittest.TestCase):
    def normalize(self, data=None):
        d=data or documents()
        return importlib.import_module('audio_inventory').normalize(d['info'],d['cards'],d['sinks'],d['sources'],d['sink-inputs'])

    def test_realistic_json_shapes_ids_current_ports_profiles_and_stream_routes(self):
        model=self.normalize()
        self.assertEqual(model['cards'][0]['activeProfile'],'output:stereo')
        self.assertEqual(model['sinks'][1]['activePort'],'headphones')
        self.assertEqual(model['streams'][0]['sinkId'],model['sinks'][0]['id'])
        self.assertEqual(model['streams'][0]['serial'],'120')
        self.assertNotEqual(model['streams'][0]['index'],int(model['streams'][0]['serial']))
        self.assertFalse(model['cards'][0]['profiles'][2]['available'])
        self.assertEqual(len(model['serverId']),64)
        self.assertNotIn('cookie',model)
        self.assertLess(len(json.dumps(model).encode()),256*1024)

    def test_profile_list_and_active_object_variants_and_empty_virtual_ports(self):
        d=documents(); card=d['cards'][0]
        card['profiles']=[dict(name=k,**v) for k,v in card['profiles'].items()]
        card['active_profile']={'name':'output:stereo'}
        d['sinks'][0]['ports']=[];d['sinks'][0]['active_port']=None
        model=self.normalize(d)
        self.assertEqual(model['cards'][0]['activeProfile'],'output:stereo')
        self.assertEqual(model['sinks'][0]['ports'],[])

    def test_duplicate_identity_and_malformed_index_serial_or_top_level_fail_closed(self):
        for field,value in [('index',True),('index',-1),('index',2**32),('properties',{'object.serial':'bad'})]:
            d=documents();d['sink-inputs'][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):self.normalize(d)
        d=documents();d['sink-inputs'][1]['properties']['object.serial']='120'
        with self.assertRaises(ValueError):self.normalize(d)
        d=documents();d['cards']={}
        with self.assertRaises(ValueError):self.normalize(d)

    def test_server_identity_changes_and_limits_do_not_silently_drop_devices(self):
        d=documents();before=self.normalize(d);d['info']['cookie']='changed'
        self.assertNotEqual(before['serverId'],self.normalize(d)['serverId'])
        d['sinks']=[dict(documents()['sinks'][0],index=i) for i in range(129)]
        with self.assertRaises(ValueError):self.normalize(d)


@unittest.skipUnless(PRESENT,'W1 provider not present on unmodified baseline')
class AudioDeviceActionsCase(Fixture, unittest.TestCase):
    def live(self,demo=False,settings=False):
        runner=PulseRunner();live=self.make_backend(runner,demo=demo);live.settings_only=settings
        self.addCleanup(live.charge_executor.shutdown);self.addCleanup(live.feature_executor.shutdown)
        return live,runner

    def inventory(self,live):
        self.assertTrue(complete_action(live,{'action':'audioDevicesRefresh'})['ok'])
        return copy.deepcopy(live.action_state()['audioDevices'])

    def test_refresh_ack_then_completion_and_normalized_snapshot(self):
        live,runner=self.live();ack=live.handle({'action':'audioDevicesRefresh'})
        self.assertEqual((ack['ok'],ack['pending'],ack['message'],ack['sequence']),(True,True,'Working…',1))
        live.feature_jobs['audioDevicesRefresh'].result(timeout=2);live.finish_features()
        self.assertEqual(live.last_result,dict(ok=True,action='audioDevicesRefresh',message='Audio devices refreshed',sequence=2))
        self.assertFalse(live.feature_jobs);self.assertTrue(live.action_state()['audioDevices']['available'])
        self.assertTrue(all(o.get('max_output') for o in runner.options))

    def test_port_source_profile_and_two_app_routes_use_literal_pulse_ids_and_readback(self):
        live,runner=self.live();model=self.inventory(live)
        cases=[('audioPort',{'deviceId':model['sources'][0]['id'],'port':'mic'},'set-source-port'),
            ('audioPort',{'deviceId':model['sinks'][1]['id'],'port':'headphones'},'set-sink-port'),
            ('audioProfile',{'cardId':model['cards'][0]['id'],'profile':'output:headset+input:headset'},'set-card-profile'),
            ('audioRoute',{'streamId':model['streams'][0]['id'],'sinkId':model['sinks'][1]['id']},'move-sink-input')]
        for action,request,command in cases:
            with self.subTest(action=action):
                result=complete_action(live,dict(action=action,serverId=model['serverId'],**request))
                self.assertTrue(result['ok'],result);self.assertEqual(runner.mutations[-1][1:3],('--',command))
        state=live.action_state()['audioDevices']
        self.assertEqual(state['streams'][0]['sinkId'],state['sinks'][1]['id'])
        self.assertEqual(state['streams'][1]['sinkId'],state['sinks'][0]['id'])
        self.assertFalse(self.preferences.path.exists())

    def test_stale_server_or_reused_stream_and_unavailable_profile_never_mutate(self):
        for scenario in ('server','stream','profile'):
            live,runner=self.live();m=self.inventory(live)
            request=dict(action='audioRoute',serverId=m['serverId'],streamId=m['streams'][0]['id'],sinkId=m['sinks'][1]['id'])
            if scenario=='server':runner.docs['info']['cookie']='restarted'
            elif scenario=='stream':runner.docs['sink-inputs'][0]['properties']['object.serial']='999'
            else:request=dict(action='audioProfile',serverId=m['serverId'],cardId=m['cards'][0]['id'],profile='output:absent')
            result=complete_action(live,request)
            self.assertFalse(result['ok']);self.assertFalse(runner.mutations);self.assertFalse(live.feature_jobs)

    def test_failed_command_and_unconfirmed_readback_are_errors_not_optimistic_success(self):
        live,runner=self.live();m=self.inventory(live);runner.apply=False
        with patch('audio_devices.time.sleep',return_value=None):
            result=complete_action(live,dict(action='audioRoute',serverId=m['serverId'],streamId=m['streams'][0]['id'],sinkId=m['sinks'][1]['id']))
        self.assertFalse(result['ok']);self.assertIn('confirm',result['message'].lower())
        self.assertEqual(live.action_state()['audioDevices']['streams'][0]['sinkId'],m['sinks'][0]['id'])
        runner.error=backend.CommandError('pactl disconnected')
        result=complete_action(live,{'action':'audioDevicesRefresh'})
        self.assertFalse(result['ok']);self.assertFalse(live.feature_jobs)
        self.assertTrue(live.action_state()['audioDevices']['error'])

    def test_invalid_request_is_rejected_before_io_and_settings_before_demo(self):
        live,runner=self.live()
        for request in ({'action':'audioRoute','streamId':True},{'action':'audioProfile','cardId':[]},
                        {'action':'audioPort','deviceId':'sink/1/1','serverId':'bad','port':'p'}):
            self.assertFalse(live.handle(request)['ok'])
        self.assertEqual(runner.calls,[])
        for demo in (False,True):
            live,runner=self.live(demo,settings=True)
            result=live.handle({'action':'audioDevicesRefresh'})
            self.assertEqual(result['message'],'This action is unavailable in the settings app')
            self.assertEqual(runner.calls,[])

    def test_audio_actions_share_admission_and_clear_pending_after_completion(self):
        live,runner=self.live();started=threading.Event();release=threading.Event();original=runner.run
        def run(*args,**kwargs):
            started.set();release.wait(2);return original(*args,**kwargs)
        runner.run=run
        try:
            self.assertTrue(live.handle({'action':'audioDevicesRefresh'})['pending']);self.assertTrue(started.wait(1))
            result=live.handle({'action':'audioProfile','serverId':'a'*64,'cardId':'card/1/101','profile':'output:stereo'})
            self.assertFalse(result['ok']);self.assertIn('running',result['message'])
        finally:release.set()
        live.feature_jobs['audioDevicesRefresh'].result(timeout=2);live.finish_features()
        self.assertFalse(live.feature_jobs)

    def test_demo_inventory_and_changes_never_spawn_or_write_and_unknown_stays_legacy(self):
        live,runner=self.live(demo=True)
        with patch('subprocess.Popen',side_effect=AssertionError('demo spawn')),patch('os.replace',side_effect=AssertionError('demo write')):
            m=self.inventory(live)
            self.assertTrue(live.handle(dict(action='audioRoute',serverId=m['serverId'],streamId=m['streams'][0]['id'],sinkId=m['sinks'][1]['id']))['ok'])
        self.assertEqual(runner.calls,[]);self.assertEqual(runner.spawns,[])
        self.assertFalse(self.preferences.path.exists())
        self.assertFalse(live.handle({'action':'audioUnknown'})['ok'])
