"""Failure/race contracts audited after combining audio and controller providers.
Contract: test_audio_merge_audit.py covers audio_merge_audit behavior/contracts; check imports for fixtures/helpers under test.
"""
import json
import unittest

from action_test_helpers import complete_action
from audio_device_fixture import PulseRunner
from test_backend import Fixture, backend


class AudioMergeAuditCase(Fixture, unittest.TestCase):
    def live(self):
        runner = PulseRunner()
        live = self.make_backend(runner)
        self.addCleanup(live.feature_executor.shutdown)
        self.addCleanup(live.charge_executor.shutdown)
        self.addCleanup(live.weather.close)
        return live, runner

    def inventory(self, live):
        self.assertTrue(complete_action(live, {'action': 'audioDevicesRefresh'})['ok'])
        return live.action_state()['audioDevices']

    def test_timeout_clears_pending_and_next_refresh_recovers(self):
        live, runner = self.live()
        runner.error = backend.CommandError('pactl timed out')
        failed = complete_action(live, {'action': 'audioDevicesRefresh'})
        self.assertFalse(failed['ok'])
        self.assertFalse(live.feature_jobs)
        self.assertFalse(live.action_state()['audioDevices']['available'])
        runner.error = None
        recovered = complete_action(live, {'action': 'audioDevicesRefresh'})
        self.assertTrue(recovered['ok'])
        self.assertGreater(recovered['sequence'], failed['sequence'])
        self.assertTrue(live.action_state()['audioDevices']['available'])
        self.assertFalse(live.feature_jobs)

    def test_server_restart_during_inventory_never_issues_mutation(self):
        live, runner = self.live()
        model = self.inventory(live)
        original, reads = runner.run, []
        def run(name, *args, **kwargs):
            if args == ('--format=json', 'info'):
                reads.append(1)
                if len(reads) == 2: runner.docs['info']['cookie'] = 'restarted'
            return original(name, *args, **kwargs)
        runner.run = run
        result = complete_action(live, dict(action='audioProfile', serverId=model['serverId'],
            cardId=model['cards'][0]['id'], profile='output:stereo'))
        self.assertFalse(result['ok'])
        self.assertIn('server changed', result['message'])
        self.assertFalse(runner.mutations)
        self.assertFalse(live.feature_jobs)

    def test_partial_metadata_failure_reports_observed_side_effect_not_success(self):
        live, runner = self.live()
        model = self.inventory(live)
        runner.names.update(('pw-dump', 'pw-metadata'))
        objects = [dict(type='PipeWire:Interface:Core', info=dict(cookie=0x1234abcd))]
        for ident, serial, kind in ((5, '120', 'Stream/Output/Audio'), (7, '111', 'Audio/Sink')):
            objects.append(dict(id=ident, type='PipeWire:Interface:Node',
                info={'props': {'object.serial': serial, 'media.class': kind}}))
        original, metadata = runner.run, []
        def run(name, *args, **kwargs):
            if name == 'pw-dump': return json.dumps(objects)
            if name == 'pw-metadata':
                metadata.append(args)
                if args[3] == 'target.object': runner.docs['sink-inputs'][0]['sink'] = 11
                else: raise backend.CommandError('metadata cleanup failed')
                return ''
            return original(name, *args, **kwargs)
        runner.run = run
        result = complete_action(live, dict(action='audioRoute', serverId=model['serverId'],
            streamId=model['streams'][0]['id'], sinkId=model['sinks'][1]['id']))
        observed = live.action_state()['audioDevices']
        self.assertFalse(result['ok'])
        self.assertEqual(result['message'], 'metadata cleanup failed')
        self.assertEqual(observed['streams'][0]['sinkId'], model['sinks'][1]['id'])
        self.assertEqual(observed['streams'][1]['sinkId'], model['streams'][1]['sinkId'])
        self.assertEqual(len(metadata), 2)
        self.assertFalse(live.feature_jobs)

    def test_reused_destination_index_cannot_be_confirmed_as_the_original_device(self):
        live, runner = self.live()
        model = self.inventory(live)
        original = runner.run
        def run(name, *args, **kwargs):
            value = original(name, *args, **kwargs)
            if args[:2] == ('--', 'move-sink-input'):
                runner.docs['sinks'][1]['properties']['object.serial'] = '999'
            return value
        runner.run = run
        result = complete_action(live, dict(action='audioRoute', serverId=model['serverId'],
            streamId=model['streams'][0]['id'], sinkId=model['sinks'][1]['id']))
        self.assertFalse(result['ok'])
        self.assertIn('confirm', result['message'])
        self.assertEqual(live.action_state()['audioDevices']['streams'][0]['sinkId'], 'sink/11/999')
        self.assertFalse(live.feature_jobs)
