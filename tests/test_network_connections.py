"""W2 characterization first; new network contracts are N/A before implementation.
Contract: test_network_connections.py covers network_connections behavior/contracts; check imports for fixtures/helpers under test.
"""
import importlib
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from action_test_helpers import complete_action
from network_fixture import DEV, UUIDS, NetworkRunner
from test_backend import Fixture, backend
from wifi_actions import ACTIONS, WifiCapabilities, provide

READY = (Path(__file__).resolve().parents[1]/'scripts/network_profiles.py').exists()
NEW = ('networkRefresh', 'networkConnect', 'networkDisconnect', 'networkHotspotPlan', 'networkHotspotStart', 'networkEdit', 'networkCancel')


class NetworkBaselineCase(Fixture, unittest.TestCase):
    def test_wifi_specs_and_registration_remain_pure(self):
        def unexpected(*args, **kwargs): raise AssertionError('Registration performed network I/O')
        specs, projection = provide(WifiCapabilities(unexpected, unexpected, unexpected))
        self.assertEqual(tuple(s.name for s in specs), ACTIONS)
        self.assertTrue(all(s.contexts == {'shell'} and s.execution == 'worker' for s in specs))
        self.assertEqual(projection(), {})

    def test_new_backend_keeps_startup_projection_and_does_not_query_profiles(self):
        runner = NetworkRunner(); live = self.make_backend(runner)
        self.addCleanup(live.feature_executor.shutdown); self.addCleanup(live.charge_executor.shutdown)
        self.assertEqual(live.action_state(), {'launchpadJobs': {}})
        self.assertFalse(runner.calls)
        self.assertFalse(self.preferences.path.exists())


@unittest.skipUnless(READY, 'W2 connection provider absent on unmodified main')
class NetworkContractsCase(Fixture, unittest.TestCase):
    def live(self, demo=False, settings=False):
        runner = NetworkRunner(); live = self.make_backend(runner, demo=demo); live.settings_only = settings
        self.addCleanup(live.feature_executor.shutdown); self.addCleanup(live.charge_executor.shutdown)
        self.addCleanup(live.weather.close)
        return live, runner

    def refresh(self, live):
        result = complete_action(live, {'action': 'networkRefresh'})
        self.assertTrue(result['ok'], result)
        return live.action_state()['networkConnections']

    def test_inventory_retains_duplicate_names_filters_slave_and_wifi_and_bounds_state(self):
        live, runner = self.live(); model = self.refresh(live)
        self.assertEqual([p['kind'] for p in model['profiles']], ['vpn', 'ethernet', 'ethernet', 'wireguard', 'hotspot'])
        self.assertEqual(len({p['uuid'] for p in model['profiles']}), 5)
        self.assertEqual([p['name'] for p in model['profiles']].count('Office'), 2)
        self.assertFalse(any('--show-secrets' in str(call) for call in runner.calls))
        self.assertTrue(all(o.get('max_output') for o in runner.options))

    def test_selected_wired_uuid_and_adapter_readback_and_no_other_device_disconnect(self):
        live, runner = self.live(); model = self.refresh(live)
        result = complete_action(live, dict(action='networkConnect', serverId=model['serverId'], uuid=UUIDS[2], deviceId=DEV[2]))
        self.assertTrue(result['ok'], result)
        self.assertTrue(any(a['uuid'] == UUIDS[2] and a['deviceId'] == DEV[2] for a in live.action_state()['networkConnections']['active']))
        self.assertTrue(any(a['uuid'] == UUIDS[1] and a['device'] == DEV[1] for a in runner.model['active']))

    def test_stale_epoch_missing_profile_and_incompatible_device_never_mutate(self):
        for scenario in ('epoch', 'profile', 'device'):
            live, runner = self.live(); model = self.refresh(live)
            request = dict(action='networkConnect', serverId=model['serverId'], uuid=UUIDS[2], deviceId=DEV[2])
            if scenario == 'epoch': runner.model['owner'] = ':1.99'
            elif scenario == 'profile': runner.model['profiles'] = [p for p in runner.model['profiles'] if p['connection.uuid'] != UUIDS[2]]
            else: request['deviceId'] = DEV[0]
            result = complete_action(live, request)
            self.assertFalse(result['ok'], result); self.assertFalse(runner.writes)

    def test_hotspot_requires_confirmed_fresh_plan_and_blocks_changed_wifi(self):
        live, runner = self.live(); m = self.refresh(live)
        args = dict(serverId=m['serverId'], uuid=UUIDS[4], deviceId=DEV[0])
        self.assertTrue(complete_action(live, dict(action='networkHotspotPlan', **args))['ok'])
        plan = live.action_state()['networkConnections']['hotspotPlan']
        self.assertTrue(plan['disconnectWifi']); self.assertEqual(plan['deviceId'], DEV[0])
        result = live.handle(dict(action='networkHotspotStart', **args, planToken=plan['token'], confirmed=False))
        self.assertFalse(result['ok']); self.assertFalse(runner.writes)
        runner.model['devices'][0]['GENERAL.CON-PATH'] = '/org/freedesktop/NetworkManager/ActiveConnection/999'
        result = complete_action(live, dict(action='networkHotspotStart', **args, planToken=plan['token'], confirmed=True))
        self.assertFalse(result['ok']); self.assertFalse(runner.writes)

    def test_open_insecure_or_nonshared_hotspot_is_refused_without_activation(self):
        for field, value in (('802-11-wireless-security.key-mgmt', ''), ('ipv4.method', 'auto')):
            live, runner = self.live(); m = self.refresh(live)
            p = next(p for p in runner.model['profiles'] if p['connection.uuid'] == UUIDS[4]); p[field] = value
            result = complete_action(live, dict(action='networkHotspotPlan', serverId=m['serverId'], uuid=UUIDS[4], deviceId=DEV[0]))
            self.assertFalse(result['ok']); self.assertFalse(runner.writes)

    def test_failure_is_sanitized_and_pending_clears_then_retry_works(self):
        live, runner = self.live(); m = self.refresh(live)
        runner.fail = backend.CommandError('nmcli failed (4): password=SUPER-SECRET no secrets were provided')
        args = dict(action='networkConnect', serverId=m['serverId'], uuid=UUIDS[2], deviceId=DEV[2])
        result = complete_action(live, args)
        self.assertFalse(result['ok']); self.assertNotIn('SUPER-SECRET', str(live.action_state())+str(result))
        self.assertFalse(live.feature_jobs)
        runner.fail = None; self.assertTrue(complete_action(live, args)['ok'])

    def test_no_confirmation_after_cli_success_without_actual_activation(self):
        live, runner = self.live(); m = self.refresh(live); runner.apply = False
        result = complete_action(live, dict(action='networkConnect', serverId=m['serverId'], uuid=UUIDS[2], deviceId=DEV[2]))
        self.assertFalse(result['ok']); self.assertIn('confirm', result['message'].lower())

    def test_settings_context_precedes_live_or_demo_and_demo_never_spawns_or_writes(self):
        for demo in (False, True):
            live, runner = self.live(demo, settings=True)
            for action in NEW:
                result = live.handle({'action': action})
                self.assertEqual(result['message'], 'This action is unavailable in the settings app')
            self.assertFalse(runner.calls)
        live, runner = self.live(demo=True)
        with patch('subprocess.Popen', side_effect=AssertionError('demo spawn')), patch('os.replace', side_effect=AssertionError('demo write')):
            self.refresh(live)
        self.assertFalse(runner.calls); self.assertFalse(self.preferences.path.exists())

    def test_vpn_uses_selected_uplink_and_wireguard_uses_its_saved_virtual_interface(self):
        live, runner = self.live(); m = self.refresh(live)
        self.assertTrue(complete_action(live, dict(action='networkConnect', serverId=m['serverId'], uuid=UUIDS[0], deviceId=DEV[1]))['ok'])
        self.assertEqual(runner.writes[-1][-2:], ('ifname', 'enp1s0'))
        self.assertTrue(any(a['uuid'] == UUIDS[1] for a in runner.model['active']))
        self.assertTrue(complete_action(live, dict(action='networkConnect', serverId=m['serverId'], uuid=UUIDS[3], deviceId='virtual/'+UUIDS[3]))['ok'])
        self.assertNotIn('ifname', runner.writes[-1])

    def test_disconnect_targets_one_active_path_not_every_activation_of_the_uuid(self):
        live, runner = self.live()
        other = '/org/freedesktop/NetworkManager/ActiveConnection/3'
        runner.model['active'].append(dict(uuid=UUIDS[1], device=DEV[2], path=other, state='activated'))
        m = self.refresh(live)
        selected = next(a for a in m['active'] if a['uuid'] == UUIDS[1] and a['deviceId'] == DEV[1])
        result = complete_action(live, dict(action='networkDisconnect', serverId=m['serverId'], uuid=UUIDS[1], deviceId=DEV[1], activePath=selected['path']))
        self.assertTrue(result['ok'], result)
        self.assertEqual(runner.writes[-1][-2:], ('apath', selected['path']))
        self.assertTrue(any(a['path'] == other for a in runner.model['active']))

    def test_wifi_mutations_conflict_and_cancellation_releases_ownership_after_completion(self):
        live, runner = self.live(); m = self.refresh(live); runner.block = True
        ack = live.handle(dict(action='networkConnect', serverId=m['serverId'], uuid=UUIDS[2], deviceId=DEV[2]))
        self.assertTrue(ack['pending']); self.assertTrue(runner.started.wait(1))
        try:
            denied = live.handle({'action': 'wifiDisconnect'})
            self.assertFalse(denied['ok']); self.assertIn('running', denied['message'])
            self.assertTrue(live.handle({'action': 'networkCancel'})['ok'])
            live.feature_jobs['networkConnect'].result(timeout=2); live.finish_features()
        finally: runner.release.set()
        self.assertIn('cancel', live.last_result['message'].lower())
        self.assertFalse(live.feature_jobs)
        self.assertTrue(any(a['uuid'] == UUIDS[5] for a in runner.model['active']))

    def test_hotspot_confirmed_start_reports_ap_and_does_not_claim_internet(self):
        live, runner = self.live(); m = self.refresh(live)
        args = dict(serverId=m['serverId'], uuid=UUIDS[4], deviceId=DEV[0])
        self.assertTrue(complete_action(live, dict(action='networkHotspotPlan', **args))['ok'])
        plan = live.action_state()['networkConnections']['hotspotPlan']
        result = complete_action(live, dict(action='networkHotspotStart', **args, planToken=plan['token'], confirmed=True))
        self.assertTrue(result['ok'], result)
        self.assertTrue(any(a['uuid'] == UUIDS[4] for a in live.action_state()['networkConnections']['active']))
        self.assertIn('not verified', result['message'])

    def test_edit_uses_literal_known_uuid_and_no_inline_network_setting_writes(self):
        live, runner = self.live(); m = self.refresh(live)
        result = complete_action(live, dict(action='networkEdit', serverId=m['serverId'], uuid=UUIDS[1]))
        self.assertTrue(result['ok'], result)
        self.assertEqual(runner.spawns, [['/usr/bin/nm-connection-editor', '--edit='+UUIDS[1]]])
        self.assertFalse(runner.writes); self.assertFalse(self.preferences.path.exists())
