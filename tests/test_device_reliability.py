"""Bluetooth worker and Wi-Fi admission contracts with fake devices only."""
import copy
import os
from threading import Event
import time
import unittest
from unittest.mock import Mock, patch

import audio_actions
import test_wifi_actions as wifi
from action_test_helpers import complete_action
from test_backend import Fixture, FakeRunner, backend
from test_features import ManualExecutor

BT = '/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF'
REQUEST = dict(action='bluetoothDevice', path=BT, connected=True)
WORKER = next(s for s in audio_actions.provide(audio_actions.AudioCapabilities(*[Mock() for _ in range(5)]))[0]
              if s.name == 'bluetoothDevice').execution == 'worker'


class BluetoothReliabilityCase(Fixture, unittest.TestCase):
    def configured(self, *, demo=False, settings=False, manual=True):
        env=patch.dict(os.environ, XDG_STATE_HOME=str(self.root/'state'), XDG_CONFIG_HOME=str(self.root/'config'))
        env.start();self.addCleanup(env.stop)
        live=self.make_backend(FakeRunner(available=('busctl','wpctl')),demo=demo);live.settings_only=settings
        state=dict(devices=[dict(path=BT,connected=False)],enabled=True,available=True,batteries=[])
        live.bluetooth=Mock(side_effect=lambda:copy.deepcopy(state))
        live.charge_executor.shutdown();self.addCleanup(live.feature_executor.shutdown)
        if manual: live.feature_executor.shutdown();live.feature_executor=ManualExecutor()
        live._test_bluetooth=state
        return live

    def test_current_context_demo_messages_and_fresh_validation(self):
        for demo in (False,True):
            for settings in (False,True):
                live=self.configured(demo=demo,settings=settings)
                if not demo and not settings:
                    # Complete manually if the new worker contract is available.
                    initial=live.handle(REQUEST)
                    if initial.get('pending'): live.feature_executor.complete();live.finish_features();initial=live.last_result
                    self.assertEqual(initial['message'],'Bluetooth device connected')
                    self.assertTrue(initial['ok'])
                    self.assertEqual(live.runner.calls[-1],('busctl','--system','call','org.bluez',BT,'org.bluez.Device1','Connect'))
                else:
                    result=live.handle(REQUEST)
                    self.assertEqual(result['ok'],not settings)
                    self.assertEqual(result['message'],'This action is unavailable in the settings app' if settings else 'Demo preview: no system command executed')
                    self.assertFalse(live.feature_jobs);self.assertFalse(live.runner.calls)
        live=self.configured();live.bluetooth.return_value=None
        live._test_bluetooth['devices']=[]
        result=live.handle(REQUEST)
        if result.get('pending'): live.feature_executor.complete();live.finish_features();result=live.last_result
        self.assertEqual(result['message'],'Unknown Bluetooth device or state');self.assertFalse(live.runner.calls)

    @unittest.skipUnless(WORKER,'Bluetooth remains synchronous on baseline')
    def test_ack_volume_then_completion_preserve_sequences_and_invalidate_midflight_readback(self):
        live=self.configured();live.bluetooth_cache={'old':True};live.system_cache={'other':True}
        ack=live.handle(REQUEST)
        self.assertEqual(ack,dict(action='bluetoothDevice',ok=True,message='Working…',pending=True,sequence=1))
        live.bluetooth.assert_not_called();self.assertFalse(live.runner.calls)
        self.assertEqual(live.handle(dict(action='volume',value=25)),dict(action='volume',ok=True,message='Volume 25%',sequence=2))
        # Simulate an ordinary snapshot refilling read-back while Connect is pending.
        live.bluetooth_cache={'midflight':True};live.system_cache={'bluetooth':{'connected':False}}
        def run(name,*args,**kwargs):
            if name=='busctl' and args[-1]=='Connect':
                self.assertEqual(kwargs,dict(timeout=15.0));live._test_bluetooth['devices'][0]['connected']=True
            return ''
        live.runner.run=run
        live.feature_executor.complete();live.finish_features()
        self.assertEqual(live.last_result,dict(action='bluetoothDevice',ok=True,message='Bluetooth device connected',sequence=3))
        self.assertFalse(live.feature_jobs);self.assertIsNone(live.bluetooth_cache);self.assertIsNone(live.system_cache)
        self.assertTrue(live.snapshot()['system']['bluetooth']['devices'][0]['connected'])

    @unittest.skipUnless(WORKER,'Bluetooth remains synchronous on baseline')
    def test_failure_duplicate_and_unplug_clear_pending_without_legacy_fallback(self):
        for unplug in (False,True):
            live=self.configured()
            with patch.object(live,'perform',side_effect=AssertionError('legacy fallback')):
                self.assertTrue(live.handle(REQUEST)['pending'])
                self.assertEqual(live.handle(REQUEST)['message'],'This operation is already running')
                live.bluetooth_cache={'midflight':True}
                if unplug: live._test_bluetooth['devices']=[]
                else: live.runner.run=Mock(side_effect=backend.CommandError('Device unavailable'))
                live.feature_executor.complete();live.finish_features()
            self.assertFalse(live.last_result['ok']);self.assertEqual(live.last_result['sequence'],3)
            self.assertEqual(live.last_result['message'],'Unknown Bluetooth device or state' if unplug else 'Device unavailable')
            self.assertFalse(live.feature_jobs);self.assertIsNone(live.bluetooth_cache)

    @unittest.skipUnless(WORKER,'Bluetooth remains synchronous on baseline')
    def test_real_blocked_worker_does_not_block_volume_or_snapshot(self):
        live=self.configured(manual=False);started=Event();release=Event();self.addCleanup(release.set)
        def run(name,*args,**kwargs):
            if name=='busctl' and args[-1]=='Connect':
                started.set()
                if not release.wait(3): raise AssertionError('Test did not release Connect')
            return ''
        live.runner.run=run
        begin=time.monotonic();ack=live.handle(REQUEST)
        self.assertTrue(ack['pending']);self.assertTrue(started.wait(1))
        self.assertTrue(live.handle(dict(action='volume',value=30))['ok'])
        live.snapshot();self.assertLess(time.monotonic()-begin,1)
        release.set();live.feature_jobs['bluetoothDevice'].result(timeout=2);live.finish_features()
        self.assertFalse(live.feature_jobs)


class WifiAdmissionCase(Fixture,unittest.TestCase):
    configured=wifi.WifiDispatchCase.configured

    def test_current_scan_can_coexist_with_connection_and_contexts_stay_isolated(self):
        live=self.configured()
        self.assertTrue(live.handle(dict(action='wifiConnect',**wifi.REQUEST))['pending'])
        self.assertTrue(live.handle(dict(action='wifiScan',**wifi.REQUEST))['pending'])
        self.assertEqual(set(live.feature_jobs),{'wifiScan','wifiConnect'})
        for demo in (False,True):
            other=self.configured(demo=demo,settings=True)
            self.assertEqual(other.handle(dict(action='wifiConnect'))['message'],wifi.CONTEXT)
            self.assertFalse(other.feature_jobs)
        demo=self.configured(demo=True)
        for action in (*wifi.ACTIONS,'wifiToggle'): self.assertTrue(demo.handle(dict(action=action,**wifi.REQUEST))['ok'])
        self.assertFalse(demo.feature_jobs);self.assertFalse(demo.runner.calls)

    def test_conflicting_mutations_reject_before_io_and_own_no_job(self):
        for owner in ('wifiConnect','wifiSaved','wifiDisconnect','wifiForget'):
            live=self.configured();live.handle(dict(action=owner,**wifi.REQUEST));jobs=dict(live.feature_jobs)
            with patch.object(live.runner,'run',side_effect=AssertionError('Rejected operation ran a command')):
                for action in ('wifiConnect','wifiSaved','wifiDisconnect','wifiForget','wifiToggle'):
                    result=live.handle(dict(action=action,**wifi.REQUEST))
                    self.assertEqual(result['message'],'This operation is already running')
                    self.assertFalse(result['ok']);self.assertNotIn('pending',result)
                    self.assertEqual(live.feature_jobs,jobs)
            live.network.assert_not_called()
            with self.assertRaisesRegex(ValueError,'already running'):
                live.wifi_action('wifiDisconnect',wifi.REQUEST)

    def test_completed_but_unpublished_job_still_owns_admission_and_error_releases_it(self):
        live=self.configured();live.handle(dict(action='wifiSaved',**wifi.REQUEST))
        with patch.object(live.runner,'run',side_effect=backend.CommandError('Bad password')):
            live.feature_executor.complete()
        self.assertFalse(live.handle(dict(action='wifiForget',**wifi.REQUEST))['ok'])
        live.finish_features();self.assertFalse(live.last_result['ok']);self.assertFalse(live.feature_jobs)
        self.assertTrue(live.handle(dict(action='wifiConnect',**wifi.REQUEST))['pending'])

    def test_idle_radio_toggle_retains_literal_commands_and_unknown_routes(self):
        live=self.configured();live.runner.responses[('nmcli','radio','wifi')]='enabled'
        self.assertEqual(live.handle(dict(action='wifiToggle'))['message'],'Wi-Fi toggled')
        self.assertEqual(live.runner.calls[-2:],[('nmcli','radio','wifi'),('nmcli','radio','wifi','off')])
        self.assertEqual(live.handle(dict(action='wifiUnknown'))['message'],'Unknown action: wifiUnknown')
