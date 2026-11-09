"""Network identity, bounded metadata and side-effect recovery at the NM boundary.
Contract: test_network_boundaries.py covers network_boundaries behavior/contracts; check imports for fixtures/helpers under test.
"""
import copy
import importlib
import json
from pathlib import Path
import unittest

from action_test_helpers import complete_action
from network_fixture import DEV, UUIDS, NetworkRunner, connection_text, device_text, profile_text
from test_backend import Fixture, backend

READY = (Path(__file__).resolve().parents[1]/'scripts/network_inventory.py').exists()


@unittest.skipUnless(READY, 'W2 inventory absent on unmodified baseline')
class NetworkBoundariesCase(Fixture, unittest.TestCase):
    def normalize(self, data):
        module = importlib.import_module('network_inventory')
        return module.inventory('a'*64, device_text(data), module.connections(connection_text(data), backend.split_nmcli),
            profile_text(data), ':'.join(data['radio']), backend.split_nmcli)

    def live(self):
        runner = NetworkRunner(); live = self.make_backend(runner)
        self.addCleanup(live.feature_executor.shutdown); self.addCleanup(live.charge_executor.shutdown)
        self.addCleanup(live.weather.close)
        self.assertTrue(complete_action(live, {'action': 'networkRefresh'})['ok'])
        return live, runner, live.action_state()['networkConnections']

    def test_duplicate_devices_bad_uuids_and_unknown_radio_fail_closed(self):
        for change in (lambda d:d['devices'].append(copy.deepcopy(d['devices'][0])),
                       lambda d:d['profiles'][0].update({'connection.uuid': 'not-a-uuid'}),
                       lambda d:d.update(radio=['unknown', 'enabled'])):
            d = NetworkRunner().model; change(d)
            with self.subTest(change=change), self.assertRaises(ValueError): self.normalize(d)

    def test_native_colon_backslash_names_are_labels_not_identity(self):
        d = NetworkRunner().model; d['profiles'][0]['connection.id'] = 'Work: VPN \\ 東京'
        model = self.normalize(d)
        self.assertEqual(model['profiles'][0]['name'], 'Work: VPN \\ 東京')
        self.assertEqual(model['profiles'][0]['uuid'], UUIDS[0])

    def test_extra_secret_properties_are_not_projected(self):
        d = NetworkRunner().model; d['profiles'][0]['vpn.secrets'] = 'SUPER-SECRET'
        self.assertNotIn('SUPER-SECRET', json.dumps(self.normalize(d)))

    def test_profile_inventory_limit_is_an_error_not_a_partial_model(self):
        d = NetworkRunner().model; template = d['profiles'][0]
        d['profiles'] = [dict(template, **{'connection.uuid': f'10000000-0000-0000-0000-{i:012d}'}) for i in range(65)]
        d['active'] = []
        with self.assertRaisesRegex(ValueError, '64 profiles'): self.normalize(d)

    def test_metadata_type_race_is_refused(self):
        d = NetworkRunner().model; module = importlib.import_module('network_inventory')
        rows = module.connections(connection_text(d), backend.split_nmcli)
        d['profiles'][0]['connection.type'] = 'wireguard'
        with self.assertRaisesRegex(ValueError, 'types changed'):
            module.inventory('a'*64, device_text(d), rows, profile_text(d), 'enabled:enabled', backend.split_nmcli)

    def test_malformed_bus_json_clears_pending_instead_of_crashing_completion(self):
        live, runner, _ = self.live(); original = runner.run
        runner.run = lambda name,*a,**k: '[]' if name == 'busctl' else original(name,*a,**k)
        result = complete_action(live, {'action': 'networkRefresh'})
        self.assertFalse(result['ok']); self.assertFalse(live.feature_jobs)

    def test_ap_capability_and_hardware_radio_are_checked_without_mutation(self):
        for scenario in ('capability', 'radio'):
            live, runner, m = self.live()
            if scenario == 'radio': runner.model['radio'][0] = 'disabled'
            else: runner.model['devices'][0]['WIFI-PROPERTIES.AP'] = 'no'
            result = complete_action(live, dict(action='networkHotspotPlan', serverId=m['serverId'], uuid=UUIDS[4], deviceId=DEV[0]))
            self.assertFalse(result['ok']); self.assertFalse(runner.writes)

    def test_shared_active_path_cannot_disconnect_another_adapter(self):
        live, runner, m = self.live()
        selected = runner.model['active'][1]
        runner.model['active'].append(dict(selected, device=DEV[2]))
        result = complete_action(live, dict(action='networkDisconnect', serverId=m['serverId'], uuid=selected['uuid'],
            deviceId=DEV[1], activePath=selected['path']))
        self.assertFalse(result['ok']); self.assertFalse(runner.writes)

    def test_hotspot_security_race_stops_only_the_attempted_ap(self):
        live, runner, m = self.live(); args = dict(serverId=m['serverId'], uuid=UUIDS[4], deviceId=DEV[0])
        self.assertTrue(complete_action(live, dict(action='networkHotspotPlan', **args))['ok'])
        token = live.action_state()['networkConnections']['hotspotPlan']['token']; original = runner.mutate
        def mutate(argv):
            original(argv)
            if 'up' in argv:
                next(p for p in runner.model['profiles'] if p['connection.uuid'] == UUIDS[4])['802-11-wireless-security.key-mgmt'] = ''
        runner.mutate = mutate
        result = complete_action(live, dict(action='networkHotspotStart', **args, confirmed=True, planToken=token))
        self.assertFalse(result['ok'])
        self.assertFalse(any(a['uuid'] == UUIDS[4] for a in runner.model['active']))
        self.assertTrue(any(a['uuid'] == UUIDS[1] for a in runner.model['active']))
        self.assertIn('apath', runner.writes[-1])

    def test_connect_does_not_reissue_an_already_activating_vpn(self):
        live, runner, m = self.live()
        runner.model['active'].append(dict(uuid=UUIDS[0], device=DEV[1],
            path='/org/freedesktop/NetworkManager/ActiveConnection/4', state='activating'))
        result = complete_action(live, dict(action='networkConnect', serverId=m['serverId'], uuid=UUIDS[0], deviceId=DEV[1]))
        self.assertFalse(result['ok']); self.assertFalse(runner.writes)

    def test_retry_hint_keeps_only_the_selected_adapter_for_the_same_server_epoch(self):
        live, runner, m = self.live()
        runner.fail = backend.CommandError('No secrets were provided')
        result = complete_action(live, dict(action='networkConnect', serverId=m['serverId'], uuid=UUIDS[0], deviceId=DEV[1]))
        self.assertFalse(result['ok'])
        self.assertEqual(live.action_state()['networkConnections']['lastRequest']['deviceId'], DEV[1])
        self.assertTrue(complete_action(live, {'action': 'networkRefresh'})['ok'])
        self.assertEqual(live.action_state()['networkConnections']['lastRequest']['deviceId'], DEV[1])
        runner.model['owner'] = ':1.999'
        self.assertTrue(complete_action(live, {'action': 'networkRefresh'})['ok'])
        self.assertFalse(live.action_state()['networkConnections'].get('lastRequest'))

    def test_oversized_object_identity_cannot_escape_the_snapshot_bound(self):
        module = importlib.import_module('network_inventory')
        for kind in ('Devices', 'ActiveConnection'):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                module.path(module.BASE+kind+'/'+'1'*4096, kind)
