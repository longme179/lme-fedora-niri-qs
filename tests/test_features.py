"""Wallpaper lifecycle, real kernel charge contracts and asynchronous weather."""
from concurrent.futures import Future
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from test_backend import backend, Fixture, FakeRunner
from charge_control import ChargeControl
from weather import WeatherClient, location, fetch_json


class ManualExecutor:
    """Keep work pending until a test completes it, without network or threads."""
    def __init__(self):
        self.jobs = []

    def submit(self, function, *args):
        future = Future()
        self.jobs.append((future, function, args))
        return future

    def complete(self):
        future, function, args = self.jobs.pop(0)
        try:
            future.set_result(function(*args))
        except Exception as error:
            future.set_exception(error)

    def shutdown(self, **kwargs):
        pass


class WallpaperCase(Fixture, unittest.TestCase):
    def test_missing_daemon_starts_once_and_waits_before_applying(self):
        class StartingRunner(FakeRunner):
            def run(self, name, *args, **kwargs):
                output = super().run(name, *args, **kwargs)
                if (name, *args) == ('awww', 'query') and self.calls.count(('awww', 'query')) < 3:
                    raise backend.CommandError('Socket not ready')
                return output
        runner = StartingRunner(available={'awww', 'awww-daemon'})
        live = self.make_backend(runner)
        path = self.put('images/wallpaper.png', 'fixture')
        with patch.object(backend.time, 'sleep'):
            result = live.handle({'action': 'wallpaper', 'path': str(path)})
        self.assertTrue(result['ok'], result)
        self.assertEqual(runner.spawns, [['/usr/bin/awww-daemon']])
        self.assertEqual(runner.calls[-1], ('awww', 'img', str(path), '--transition-type', 'fade'))
        self.assertEqual(self.preferences.values['wallpaper'], str(path))

    def test_apply_failure_does_not_save_and_restore_does_not_change_preferences(self):
        runner = FakeRunner(available={'awww'})
        live = self.make_backend(runner)
        path = self.put('images/a.png', 'fixture')
        command = ('awww', 'img', str(path), '--transition-type', 'fade')
        runner.responses[command] = backend.CommandError('Image decoding failed')
        self.assertFalse(live.handle({'action': 'wallpaper', 'path': str(path)})['ok'])
        self.assertFalse(self.preferences.path.exists())
        live.apply_wallpaper(str(path), save=False, animate=False)
        self.assertEqual(runner.calls[-1][-1], 'none')
        self.assertFalse(self.preferences.path.exists())

    def test_missing_daemon_and_unready_daemon_do_not_save(self):
        path = self.put('images/a.png', 'fixture')
        for tools in ({'awww'}, {'awww', 'awww-daemon'}):
            runner = FakeRunner({('awww', 'query'): backend.CommandError('No socket')}, available=tools)
            live = self.make_backend(runner)
            with patch.object(backend.time, 'monotonic', side_effect=[0, 5]), patch.object(backend.time, 'sleep'):
                result = live.handle({'action': 'wallpaper', 'path': str(path)})
            self.assertFalse(result['ok'])
            self.assertFalse(any(call[1] == 'img' for call in runner.calls))
            self.assertFalse(self.preferences.path.exists())

    def test_restore_cli_rejects_demo_before_constructing_live_backend(self):
        with patch.object(backend, 'DesktopBackend', side_effect=AssertionError('Live backend')):
            with self.assertRaises(SystemExit) as error:
                backend.main(['--demo', '--restore-wallpaper', '/tmp/image.png'])
        self.assertEqual(error.exception.code, 2)

    def test_startup_demo_skips_wallpaper_and_preserves_config_argument(self):
        executable = self.put('bin/quickshell', '#!/bin/sh\nprintf "%s\\n" "$@"\n')
        executable.chmod(0o755)
        script = Path(__file__).resolve().parents[1] / 'scripts/start.sh'
        import os
        env = {**os.environ, 'PATH': str(executable.parent) + ':' + os.environ['PATH']}
        result = subprocess.run(['bash', str(script), '--demo', '--wallpaper', '/missing.png', '--config', 'demo config'], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '-c\ndemo config\n')
        self.assertNotIn('Warning', result.stderr)


class ChargingCase(Fixture, unittest.TestCase):
    def battery(self, end=None, start=None, types=None):
        self.put('sys/class/power_supply/BAT0/type', 'Battery')
        base = self.root / 'sys/class/power_supply/BAT0'
        for name, value in [('charge_control_end_threshold', end), ('charge_control_start_threshold', start), ('charge_types', types)]:
            if value is not None: self.put(str((base / name).relative_to(self.root)), str(value))
        return base

    def controller(self):
        return ChargeControl(self.root / 'sys')

    def test_numeric_85_and_100_are_verified_with_valid_start_threshold(self):
        base = self.battery(100, 95)
        control = self.controller()
        self.assertTrue(control.state()['supports85'])
        state = control.set_mode(85)
        self.assertEqual(state['limitPercent'], 85)
        self.assertEqual(state['mode'], 'conservation')
        self.assertEqual((base / 'charge_control_start_threshold').read_text().strip(), '80')
        self.assertEqual(control.set_mode(100)['mode'], 'max')
        self.assertEqual((base / 'charge_control_start_threshold').read_text().strip(), '80')

    def test_ideapad_firmware_mode_never_claims_an_exact_85_percent(self):
        path = self.put('sys/bus/platform/devices/VPC2004:00/conservation_mode', '0')
        control = self.controller()
        state = control.set_mode(85)
        self.assertEqual(path.read_text().strip(), '1')
        self.assertFalse(state['supports85'])
        self.assertIsNone(state['limitPercent'])
        self.assertIn('fixed firmware limit', state['reason'])
        self.assertEqual(control.set_mode(100)['mode'], 'max')

    def test_new_ideapad_charge_types_writes_exact_kernel_enum_and_verifies(self):
        base = self.battery(types='[Standard] Long Life')
        path = base / 'charge_types'
        original = Path.write_text
        writes = []
        def emulate_sysfs(target, value, **kwargs):
            if target == path:
                writes.append(value.strip())
                value = '[Standard] Long Life' if value.strip() == 'Standard' else 'Standard [Long Life]'
            return original(target, value, **kwargs)
        with patch.object(Path, 'write_text', emulate_sysfs):
            state = self.controller().set_mode(85)
            self.assertEqual(state['kind'], 'charge-types')
            self.assertEqual(state['mode'], 'conservation')
            self.assertFalse(state['supports85'])
            self.assertEqual(self.controller().set_mode(100)['mode'], 'max')
        self.assertEqual(writes, ['Long Life', 'Standard'])

    def test_rejected_end_write_restores_start_threshold(self):
        base = self.battery(100, 95)
        original = Path.write_text
        def deny_end(target, value, **kwargs):
            if target == base / 'charge_control_end_threshold':
                raise PermissionError('Driver rejected write')
            return original(target, value, **kwargs)
        with patch.object(Path, 'write_text', deny_end), self.assertRaises(PermissionError):
            self.controller().set_mode(85)
        self.assertEqual((base / 'charge_control_start_threshold').read_text().strip(), '95')
        self.assertEqual(self.controller().state()['limitPercent'], 100)

    def test_zero_exit_without_kernel_change_is_an_error(self):
        self.battery(100)
        runner = FakeRunner(available={'pkexec'})
        live = self.make_backend(runner)
        with patch.object(backend.os, 'access', return_value=False), patch.object(backend, 'trusted_helper', return_value=True):
            with self.assertRaisesRegex(ValueError, 'did not confirm'):
                live.set_charge(85)
        self.assertEqual(runner.calls, [('pkexec', '--disable-internal-agent', '/usr/bin/python3', '-I', '/usr/local/libexec/lme-shell-charge', '85')])

    def test_helper_unavailable_and_invalid_modes_never_request_privileges(self):
        self.battery(100)
        runner = FakeRunner(available={'pkexec'})
        live = self.make_backend(runner)
        with patch.object(backend.os, 'access', return_value=False), patch.object(backend, 'trusted_helper', return_value=False):
            for value in [True, '85', 84, 101, 85]:
                self.assertFalse(live.handle({'action': 'chargeMode', 'value': value})['ok'])
        self.assertEqual(runner.calls, [])
        self.assertIsNone(live.charge_job)

    def test_charge_job_keeps_backend_responsive_and_acknowledges_actual_result(self):
        self.battery(100)
        live = self.make_backend()
        pool = ManualExecutor()
        live.charge_executor = pool
        pending = live.handle({'action': 'chargeMode', 'value': 85})
        self.assertTrue(pending['pending'])
        self.assertTrue(live.charging()['busy'])
        # Another action runs before the charge worker completes.
        self.assertTrue(live.handle({'action': 'setting', 'key': 'barFontSize', 'value': 14})['ok'])
        self.assertEqual(live.snapshot()['lastResult']['action'], 'setting')
        pool.complete()
        state = live.snapshot()
        self.assertEqual(state['lastResult']['action'], 'chargeMode')
        self.assertTrue(state['lastResult']['ok'])
        self.assertFalse(state['system']['charging']['busy'])
        self.assertEqual(state['system']['charging']['limitPercent'], 85)

    def test_charge_completion_cannot_hide_another_actions_acknowledgement(self):
        self.battery(100)
        live = self.make_backend()
        live.charge_executor = ManualExecutor()
        live.handle({'action': 'chargeMode', 'value': 85})
        live.snapshot()
        live.charge_executor.complete()
        live.handle({'action': 'setting', 'key': 'barFontSize', 'value': 14})
        acknowledgement = live.snapshot()['lastResult']
        self.assertEqual(acknowledgement['action'], 'setting')
        completion = live.snapshot()['lastResult']
        self.assertEqual(completion['action'], 'chargeMode')
        self.assertTrue(completion['ok'])
        self.assertGreater(completion['sequence'], acknowledgement['sequence'])

    def test_unsupported_machine_and_demo_do_not_write_hardware(self):
        live = self.make_backend()
        self.assertFalse(live.charging()['available'])
        self.assertFalse(live.handle({'action': 'chargeMode', 'value': 85})['ok'])
        demo = self.make_backend(demo=True)
        with patch.object(ChargeControl, 'set_mode', side_effect=AssertionError('Hardware mutation')):
            for value in [100, 85]:
                self.assertTrue(demo.handle({'action': 'chargeMode', 'value': value})['ok'])
                self.assertEqual(demo.snapshot()['system']['charging']['limitPercent'], value)
        self.assertFalse(self.preferences.path.exists())
        self.assertEqual(demo.runner.calls, [])


class WeatherCase(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.pool, self.now, self.urls = ManualExecutor(), [0], []
        self.geo = {'success': True, 'city': 'Da Nang', 'country': 'Vietnam', 'latitude': 16.05, 'longitude': 108.2}
        self.forecast = {'current': {'temperature_2m': 29, 'apparent_temperature': 32, 'relative_humidity_2m': 76, 'weather_code': 61, 'wind_speed_10m': 10},
                         'daily': {'time': ['2026-10-11', '2026-10-12', '2026-10-13'], 'temperature_2m_min': [25, 24, 25], 'temperature_2m_max': [31, 30, 32], 'precipitation_probability_max': [30, 65, 20]}}
        def opener(url):
            self.urls.append(url)
            if urlparse(url).hostname == 'ipwho.is': return copy.deepcopy(self.geo)
            if urlparse(url).hostname == 'geocoding-api.open-meteo.com':
                return {'results': [{'name': 'Da Nang', 'country': 'Vietnam', 'latitude': 16.05, 'longitude': 108.2}]}
            if isinstance(self.forecast, Exception): raise self.forecast
            return copy.deepcopy(self.forecast)
        self.client = WeatherClient(opener=opener, executor=self.pool, clock=lambda: self.now[0], wall_clock=lambda: 123456)
        self.prefs = copy.deepcopy(backend.DEFAULT_PREFERENCES)

    def settle(self):
        self.client.snapshot(self.prefs)
        self.pool.complete()
        self.client.snapshot(self.prefs)
        self.pool.complete()
        return self.client.snapshot(self.prefs)

    def test_default_automatically_detects_location_then_fetches_weather_without_blocking(self):
        state = self.client.snapshot(self.prefs)
        self.assertTrue(state['automatic'])
        self.assertTrue(state['loading'])
        self.assertFalse(state['available'])
        self.assertEqual(self.urls, [])  # The worker has not run; snapshot already returned.
        self.pool.complete()
        self.assertEqual(self.client.snapshot(self.prefs)['location']['name'], 'Da Nang')
        self.pool.complete()
        state = self.client.snapshot(self.prefs)
        self.assertTrue(state['available'])
        self.assertEqual(state['condition'], 'Light rain')
        self.assertEqual(state['icon'], 'weather-rain')
        self.assertEqual(state['unit'], '°C')
        self.assertEqual(len(state['daily']), 3)
        params = parse_qs(urlparse(self.urls[-1]).query)
        self.assertEqual(params['latitude'], ['16.05'])
        self.assertEqual(params['temperature_unit'], ['celsius'])
        self.assertEqual(params['timezone'], ['auto'])
        self.assertEqual(state['updatedAt'], 123456)

    def test_geo_failure_backoff_and_manual_fallback(self):
        self.geo['success'] = False
        self.client.snapshot(self.prefs)
        self.pool.complete()
        state = self.client.snapshot(self.prefs)
        self.assertIn('choose a city', state['error'])
        self.assertFalse(state['loading'])
        self.now[0] = 119
        self.client.snapshot(self.prefs)
        self.assertEqual(len(self.urls), 1)
        self.now[0] = 120
        self.assertTrue(self.client.snapshot(self.prefs)['loading'])
        self.pool.complete()
        self.prefs.update(weatherAutoLocation=False, weatherLocation=location({'name': 'Manual', 'latitude': 0, 'longitude': 0}))
        self.client.snapshot(self.prefs)
        self.pool.complete()
        state = self.client.snapshot(self.prefs)
        self.assertTrue(state['available'])
        self.assertFalse(state['stale'])
        self.assertEqual(state['location']['name'], 'Manual')

    def test_fifteen_minute_refresh_keeps_last_good_data_after_failure(self):
        good = self.settle()
        self.now[0] = 899
        self.client.snapshot(self.prefs)
        self.assertEqual(self.pool.jobs, [])
        self.now[0] = 900
        self.client.snapshot(self.prefs)
        self.forecast = ValueError('Weather service unavailable')
        self.pool.complete()
        state = self.client.snapshot(self.prefs)
        self.assertTrue(state['available'])
        self.assertTrue(state['stale'])
        self.assertEqual(state['temperature'], good['temperature'])
        self.now[0] = 1019
        self.client.snapshot(self.prefs)
        self.assertEqual(self.pool.jobs, [])
        self.now[0] = 1020
        self.assertTrue(self.client.snapshot(self.prefs)['loading'])

    def test_location_or_unit_changes_hide_old_forecasts_until_new_data_arrives(self):
        self.settle()
        self.prefs['weatherUnit'] = 'fahrenheit'
        state = self.client.snapshot(self.prefs)
        self.assertFalse(state['available'])
        self.forecast['current']['temperature_2m'] = 84
        self.pool.complete()
        state = self.client.snapshot(self.prefs)
        self.assertEqual(state['unit'], '°F')
        self.assertEqual(state['temperature'], 84)
        params = parse_qs(urlparse(self.urls[-1]).query)
        self.assertEqual(params['wind_speed_unit'], ['mph'])
        self.prefs.update(weatherAutoLocation=False, weatherLocation=location({'name': 'Hanoi', 'latitude': 21, 'longitude': 105.8}))
        self.assertFalse(self.client.snapshot(self.prefs)['available'])
        self.pool.complete()
        self.assertEqual(self.client.snapshot(self.prefs)['location']['name'], 'Hanoi')

    def test_city_query_is_url_encoded_and_search_does_not_change_preferences(self):
        before = copy.deepcopy(self.prefs)
        self.client.search('Đà Nẵng & test')
        self.assertTrue(self.client.snapshot(self.prefs, allow_fetch=False)['search']['loading'])
        self.pool.complete()
        state = self.client.snapshot(self.prefs, allow_fetch=False)
        self.assertEqual(parse_qs(urlparse(self.urls[-1]).query)['name'], ['Đà Nẵng & test'])
        self.assertEqual(state['search']['results'][0]['name'], 'Da Nang')
        self.assertEqual(self.prefs, before)
        self.assertEqual(urlparse(self.urls[-1]).hostname, 'geocoding-api.open-meteo.com')

    def test_bad_coordinates_units_and_temperature_are_rejected(self):
        for value in [{'name': 'Bad', 'latitude': 91, 'longitude': 0}, {'name': 'Bad', 'latitude': True, 'longitude': 0}, {'name': 'Bad', 'latitude': 0, 'longitude': float('nan')}, {'name': '', 'latitude': 0, 'longitude': 0}]:
            with self.subTest(value=value), self.assertRaises(ValueError): location(value)
        for key, value in [('weatherUnit', 'kelvin'), ('weatherAutoLocation', 'yes')]:
            with self.assertRaises(ValueError): backend.validate_preference(key, value)
        self.forecast['current']['temperature_2m'] = float('nan')
        state = self.settle()
        self.assertFalse(state['available'])
        self.assertIn('valid temperature', state['error'])

    def test_settings_only_does_not_automatically_access_network_but_detection_is_available(self):
        live = backend.DesktopBackend(runner=FakeRunner(), preferences=self.preferences, settings_only=True, weather=self.client)
        live.snapshot()
        self.assertEqual(self.pool.jobs, [])
        self.assertTrue(live.handle({'action': 'weatherDetect'})['ok'])
        self.pool.complete()
        self.assertEqual(live.snapshot()['weather']['location']['name'], 'Da Nang')
        self.assertEqual(self.pool.jobs, [])
        self.assertFalse(live.handle({'action': 'chargeMode', 'value': 85})['ok'])

    def test_manual_selection_is_atomic_and_preserves_other_clients_settings(self):
        stale = backend.Preferences(self.preferences.path)
        self.preferences.set('barFontSize', 16)
        live = backend.DesktopBackend(runner=FakeRunner(), preferences=stale, settings_only=True, weather=self.client)
        place = {'name': 'Da Nang', 'latitude': 16.05, 'longitude': 108.2, 'country': 'Vietnam'}
        self.assertTrue(live.handle({'action': 'weatherSelect', 'location': place})['ok'])
        saved = json.loads(self.preferences.path.read_text())
        self.assertFalse(saved['weatherAutoLocation'])
        self.assertEqual(saved['weatherLocation'], place)
        self.assertEqual(saved['barFontSize'], 16)
        self.assertEqual(self.urls, [])

    def test_demo_weather_never_calls_services_or_saves(self):
        live = self.make_backend(demo=True)
        live.weather = self.client
        for request in [{'action': 'weatherRefresh'}, {'action': 'weatherDetect'}, {'action': 'weatherSearch', 'query': 'Da Nang'},
                        {'action': 'weatherSelect', 'location': {'name': 'Da Nang', 'latitude': 16.05, 'longitude': 108.2}}]:
            self.assertTrue(live.handle(request)['ok'])
        self.assertEqual(live.snapshot()['weather']['location']['name'], 'Da Nang')
        self.assertFalse(live.snapshot()['preferences']['weatherAutoLocation'])
        self.assertEqual(self.urls, [])
        self.assertEqual(self.pool.jobs, [])
        self.assertFalse(self.preferences.path.exists())


if __name__ == '__main__':
    unittest.main()
