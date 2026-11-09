"""pactl v17 uses availability strings for ports and available booleans for profiles.
Contract: test_audio_port_availability.py covers audio_port_availability behavior/contracts; check imports for fixtures/helpers under test.
"""
import unittest

from audio_device_fixture import documents, PulseRunner
from audio_inventory import normalize
from action_test_helpers import complete_action
from test_backend import Fixture


def native_ports(data):
    # src/utils/pactl.c: pa_{sink,source}_port_info_to_json_array/get_available_str.
    for group in ('sinks', 'sources'):
        for device in data[group]:
            for port in device['ports']:
                port['availability'] = 'available' if port.pop('available') == 'yes' else 'not available'
    return data


class NativePortAvailabilityCase(Fixture, unittest.TestCase):
    def test_native_port_strings_preserve_unavailable_input_and_output_choices(self):
        d = native_ports(documents())
        model = normalize(d['info'], d['cards'], d['sinks'], d['sources'], d['sink-inputs'])
        for group in ('sinks', 'sources'):
            for device in model[group]:
                self.assertEqual([port['available'] for port in device['ports']], [True, False])

    def test_unplugged_native_port_is_rejected_before_the_command(self):
        runner = PulseRunner(); runner.docs = native_ports(runner.docs)
        live = self.make_backend(runner)
        self.addCleanup(live.feature_executor.shutdown)
        self.addCleanup(live.charge_executor.shutdown)
        self.assertTrue(complete_action(live, {'action': 'audioDevicesRefresh'})['ok'])
        model = live.action_state()['audioDevices']
        for device in (model['sinks'][0], model['sources'][0]):
            result = complete_action(live, dict(action='audioPort', serverId=model['serverId'],
                deviceId=device['id'], port=device['ports'][1]['name']))
            self.assertFalse(result['ok'])
            self.assertEqual(result['message'], 'This audio option is unavailable')
        self.assertFalse(runner.mutations)

    def test_native_unknown_is_selectable_and_native_unavailable_overrides_a_legacy_alias(self):
        from audio_inventory import options
        items = [dict(name='unknown', availability='availability unknown'),
                 dict(name='unplugged', availability='not available', available='yes')]
        self.assertEqual([p['available'] for p in options(items)], [True, False])
