"""Network workflow UI; mocks establish integration, never hardware NM support."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from feature_catalog import canonical_index
from network_fixture import DEV, UUIDS
from network_ui_fixture import NetworkWorld

READY = (Path(__file__).resolve().parents[1]/'qml/panels/NetworkConnectionsPopup.qml').exists()


@unittest.skipUnless(os.environ.get('LME_TEST_NETWORK_UI')=='1','private Wayland network workflow UI')
@unittest.skipUnless(READY,'W2 UI absent before implementation')
class NativeNetworkCase(unittest.TestCase):
    def state(self, probe): return json.loads(probe.call('state'))

    def open(self, probe):
        probe.call('open');probe.wait(lambda s:s['button'])
        self.assertEqual(probe.call('click','networkDetails'),'true')
        return probe.wait(lambda s:s['popup'] and s['model'].get('available'))

    def test_wired_connect_readback_reopen_and_worker_isolation(self):
        with tempfile.TemporaryDirectory(prefix='network-ui-') as d:
            world=NetworkWorld(Path(d));saved=world.settings.read_bytes()
            with world.launch() as probe:
                probe.call('open');probe.wait(lambda s:s['button'])
                self.assertFalse(any('connection.uuid' in ' '.join(c) for c in world.commands()))
                self.open(probe)
                self.assertEqual(probe.call('click','networkConnect-'+UUIDS[2]),'true')
                probe.wait(lambda s:any(a['uuid']==UUIDS[2] and a['deviceId']==DEV[2] for a in s['model'].get('active',[])))
                self.open(probe);self.assertTrue(self.state(probe)['popup'])
                self.assertEqual(probe.call('click','networkClose'),'true')
                probe.wait(lambda s:not s['popup'])
            self.assertEqual(world.settings.read_bytes(),saved)

    def test_hotspot_warning_cancel_and_stale_confirmation_never_activate(self):
        with tempfile.TemporaryDirectory(prefix='network-plan-') as d:
            world=NetworkWorld(Path(d))
            with world.launch() as probe:
                self.open(probe)
                self.assertEqual(probe.call('click','networkConnect-'+UUIDS[4]),'true')
                probe.wait(lambda s:'disconnect' in s['warning'].lower())
                self.assertFalse(any('up' in c for c in world.commands()))
                self.assertEqual(probe.call('click','networkHotspotCancel'),'true')
                probe.wait(lambda s:not s['warning'])
                self.assertFalse(any('up' in c for c in world.commands()))
                probe.call('click','networkConnect-'+UUIDS[4]);probe.wait(lambda s:bool(s['warning']))
                value=json.loads(world.nm.read_text());value['model']['devices'][0]['GENERAL.CON-PATH']='/org/freedesktop/NetworkManager/ActiveConnection/999'
                world.nm.write_text(json.dumps(value))
                self.assertEqual(probe.call('click','networkHotspotConfirm'),'true')
                probe.wait(lambda s:bool(s['model'].get('error')) and not s['pending'].get('networkHotspotStart'))
                self.assertFalse(any('up' in c for c in world.commands()))

    def test_error_is_redacted_and_retry_uses_the_same_selected_profile(self):
        with tempfile.TemporaryDirectory(prefix='network-retry-') as d:
            world=NetworkWorld(Path(d));world.update(error='password=TOP-SECRET no secrets were provided')
            with world.launch() as probe:
                self.open(probe);probe.call('click','networkConnect-'+UUIDS[2])
                state=probe.wait(lambda s:bool(s['model'].get('error')))
                self.assertNotIn('TOP-SECRET',str(state));self.assertIn('credentials',state['model']['error'])
                world.update(error='');self.open(probe)
                self.assertEqual(probe.call('click','networkConnect-'+UUIDS[2]),'true')
                probe.wait(lambda s:any(a['uuid']==UUIDS[2] for a in s['model'].get('active',[])))

    def test_withdrawal_keeps_wifi_and_settings_and_settings_context_cannot_start_workers(self):
        with tempfile.TemporaryDirectory(prefix='network-withdraw-') as d:
            world=NetworkWorld(Path(d));path=world.root/'config/features.json';index=json.loads(path.read_text())
            next(r for r in index['features'] if r['id']=='wifi')['enabled']=False;path.write_text(canonical_index(index))
            saved=world.settings.read_bytes()
            with world.launch() as probe:
                probe.call('open');probe.wait(lambda s:s['panelOpen'])
                self.assertFalse(self.state(probe)['button'])
                self.assertFalse(any('connection.uuid' in ' '.join(c) for c in world.commands()))
            self.assertEqual(world.settings.read_bytes(),saved)
            with world.launch('settings') as probe:
                probe.call('send','networkRefresh','{}')
                state=probe.wait(lambda s:s['result'].get('action')=='networkRefresh')
                self.assertEqual(state['result']['message'],'This action is unavailable in the settings app')
                self.assertFalse(any('connection.uuid' in ' '.join(c) for c in world.commands()))

    def test_hotspot_confirmed_start_reports_actual_ap_without_internet_claim(self):
        with tempfile.TemporaryDirectory(prefix='network-start-') as d:
            world=NetworkWorld(Path(d))
            with world.launch() as probe:
                self.open(probe);probe.call('click','networkConnect-'+UUIDS[4])
                probe.wait(lambda s:'disconnect' in s['warning'].lower())
                self.assertEqual(probe.call('click','networkHotspotConfirm'),'true')
                state=probe.wait(lambda s:any(a['uuid']==UUIDS[4] for a in s['model'].get('active',[])) and not s['pending'].get('networkHotspotStart'))
                self.assertTrue(state['result']['ok']);self.assertIn('not verified',state['result']['message'])
                self.assertTrue(any(a['uuid']==UUIDS[1] for a in state['model']['active']))

    def test_cancel_after_activation_stops_only_the_attempt_and_releases_pending(self):
        with tempfile.TemporaryDirectory(prefix='network-cancel-') as d:
            world=NetworkWorld(Path(d));world.update(delay=4)
            with world.launch() as probe:
                self.open(probe);probe.call('click','networkConnect-'+UUIDS[2])
                probe.wait(lambda _:any(a['uuid']==UUIDS[2] for a in json.loads(world.nm.read_text())['model']['active']))
                self.open(probe)
                self.assertEqual(probe.call('click','networkCancel'),'true')
                state=probe.wait(lambda s:not s['pending'].get('networkConnect'))
                self.assertIn('cancel',state['result']['message'].lower())
                self.assertFalse(any(a['uuid']==UUIDS[2] for a in state['model']['active']))
                self.assertTrue(any(a['uuid']==UUIDS[1] for a in state['model']['active']))
                self.assertFalse(state['model']['operation'])
