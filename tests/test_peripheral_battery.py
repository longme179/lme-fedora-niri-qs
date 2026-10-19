"""Peripheral battery normalization, disconnects and existing polling cadence."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_backend import Fixture, FakeRunner, backend
from test_polling import BLUEZ
from bluetooth_agent import BluetoothAgent
from peripheral_battery import bluetooth_device, kernel_batteries, merge_batteries, percentage
from settings_transfer import document, validate_document

ADAPTER = '/org/bluez/hci0'
DEVICE = ADAPTER + '/dev_AA_BB_CC_DD_EE_FF'


def objects():
    return {ADAPTER: {'org.bluez.Adapter1': {'Alias': 'Adapter', 'Powered': True}},
            DEVICE: {'org.bluez.Device1': {'Alias': 'Headphones', 'Address': 'AA:BB:CC:DD:EE:FF',
                                          'Icon': 'audio-headphones', 'Paired': True, 'Connected': True},
                     'org.bluez.Battery1': {'Percentage': 0}}}


class PeripheralBatteryCase(Fixture, unittest.TestCase):
    def supply(self, name, **values):
        for key, value in dict(type='Battery', scope='Device', **values).items():
            self.put(f'sys/class/power_supply/{name}/{key}', str(value))

    def test_percentages_preserve_zero_and_reject_unknown_or_invalid_values(self):
        for value in [None, '', '20', True, -1, 101, float('nan'), float('inf'), 10**500]:
            with self.subTest(value=str(value)[:40]): self.assertIsNone(percentage(value))
        for value in [0, 20, 56.5, 100]: self.assertEqual(percentage(value), value)
        data = objects(); data[DEVICE]['org.bluez.Battery1']['Percentage'] = {'type': 'y', 'data': 0}
        device = bluetooth_device(DEVICE, data[DEVICE], backend.DesktopBackend.bluez_value)
        self.assertEqual((device['percentage'], device['id'], device['kind']), (0, 'bluetooth:AA:BB:CC:DD:EE:FF', 'headphones'))
        data[DEVICE]['org.bluez.Device1']['Connected'] = False
        self.assertIsNone(bluetooth_device(DEVICE, data[DEVICE], backend.DesktopBackend.bluez_value)['percentage'])

    def test_kernel_devices_do_not_change_laptop_percentage_and_merge_by_identity(self):
        self.put('sys/class/power_supply/BAT0/type', 'Battery')
        self.put('sys/class/power_supply/BAT0/capacity', '73')
        self.supply('headset', capacity=20, serial_number='aa-bb-cc-dd-ee-ff', model_name='Headphones', status='Charging')
        self.supply('keyboard', capacity='bad', model_name='Wireless keyboard', status='Unknown')
        self.supply('missing', capacity=9, model_name='Mouse', present=0)
        live = self.make_backend()
        self.assertEqual(live.battery()['percent'], 73)
        self.assertEqual([d['name'] for d in live.battery()['devices']], ['BAT0'])
        kernel = kernel_batteries(live.sysfs, live.read)
        self.assertEqual(len(kernel), 2)
        keyboard = next(device for device in kernel if device['kind'] == 'keyboard')
        self.assertEqual((keyboard['percentage'], keyboard['charging']), (None, None))
        device = bluetooth_device(DEVICE, objects()[DEVICE], live.bluez_value)
        merged = merge_batteries([device], kernel)
        self.assertEqual(len(merged), 2)
        headset = next(d for d in merged if d['kind'] == 'headphones')
        self.assertEqual((headset['percentage'], headset['charging']), (0, True))
        device['percentage'] = None
        self.assertEqual(merge_batteries([device], kernel)[0]['percentage'], 20)
        device['connected'] = False
        self.assertEqual(merge_batteries([device], kernel), [keyboard])

    def test_snapshot_reuses_bluez_probe_and_clears_disconnected_or_removed_batteries(self):
        data = objects()
        other = '/org/bluez/hci1'
        data[other] = {'org.bluez.Adapter1': {'Alias': 'Other', 'Powered': True}}
        data[other + '/dev_11_22_33_44_55_66'] = {'org.bluez.Device1': {
            'Address': '11:22:33:44:55:66', 'Alias': 'Keyboard', 'Icon': 'input-keyboard', 'Connected': True}}
        runner = FakeRunner({BLUEZ: json.dumps({'data': [data]})}); live = self.make_backend(runner)
        with patch.object(backend.time, 'monotonic', return_value=100) as clock:
            first = copy.deepcopy(live.snapshot()['system'])
            self.assertEqual([d['percentage'] for d in first['peripheralBatteries']], [0, None])
            self.assertEqual(len(first['bluetooth']['devices']), 1)
            data[DEVICE]['org.bluez.Device1']['Connected'] = False
            runner.responses[BLUEZ] = json.dumps({'data': [data]})
            clock.return_value = 104.9
            self.assertEqual(live.snapshot()['system']['peripheralBatteries'], first['peripheralBatteries'])
            self.assertEqual(runner.calls.count(BLUEZ), 1)
            clock.return_value = 105
            state = live.snapshot()['system']
            self.assertEqual([d['name'] for d in state['peripheralBatteries']], ['Keyboard'])
            self.assertIsNone(state['bluetooth']['devices'][0]['percentage'])
            self.assertEqual(runner.calls.count(BLUEZ), 2)
            runner.responses[BLUEZ] = backend.CommandError('BlueZ stopped')
            clock.return_value = 110
            self.assertEqual(live.snapshot()['system']['peripheralBatteries'], [])
            data[DEVICE]['org.bluez.Device1']['Connected'] = True
            del data[DEVICE]['org.bluez.Battery1']
            runner.responses[BLUEZ] = json.dumps({'data': [data]})
            clock.return_value = 115
            self.assertIsNone(live.snapshot()['system']['peripheralBatteries'][0]['percentage'])

    def test_pairing_agent_updates_battery_signals_without_lingering_values(self):
        agent = BluetoothAgent.__new__(BluetoothAgent)
        agent.objects = objects(); agent.adapter = ADAPTER; agent.preferred = ''; frames = []
        agent.publish = lambda: frames.append(agent.devices())
        def changed(interface, changes, invalidated=()):
            agent.changed(None, None, DEVICE, 'org.freedesktop.DBus.Properties', 'PropertiesChanged',
                          SimpleNamespace(unpack=lambda: (interface, changes, invalidated)))
        changed('org.bluez.Battery1', {'Percentage': 18})
        self.assertEqual(frames[-1][0]['percentage'], 18)
        changed('org.bluez.Battery1', {}, ['Percentage'])
        self.assertIsNone(frames[-1][0]['percentage'])
        changed('org.bluez.Battery1', {'Percentage': 0})
        self.assertEqual(frames[-1][0]['percentage'], 0)
        changed('org.bluez.Device1', {'Connected': False})
        self.assertIsNone(frames[-1][0]['percentage'])
        changed('org.bluez.Device1', {'Connected': True})
        self.assertEqual(frames[-1][0]['percentage'], 0)
        agent.changed(None, None, '/', 'org.freedesktop.DBus.ObjectManager', 'InterfacesRemoved',
                      SimpleNamespace(unpack=lambda: (DEVICE, ['org.bluez.Battery1'])))
        self.assertIsNone(frames[-1][0]['percentage'])

    def test_alert_preferences_are_validated_and_portable(self):
        self.assertTrue(backend.DEFAULT_PREFERENCES['peripheralBatteryAlerts'])
        self.assertEqual(backend.DEFAULT_PREFERENCES['peripheralBatteryThreshold'], 20)
        for key, invalid in [('peripheralBatteryAlerts', [1, 'true', None]),
                             ('peripheralBatteryThreshold', [True, 0, 51, 20.5, '20'])]:
            for value in invalid:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    backend.validate_preference(key, value)
        values = dict(backend.DEFAULT_PREFERENCES, peripheralBatteryAlerts=False, peripheralBatteryThreshold=35)
        restored = validate_document(document(values, 'preset'), backend.validate_preference, backend.DEFAULT_PREFERENCES)
        self.assertEqual((restored['peripheralBatteryAlerts'], restored['peripheralBatteryThreshold']), (False, 35))
