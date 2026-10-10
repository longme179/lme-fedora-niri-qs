# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, asynchronous Open-Meteo weather with optional IP geolocation."""
from concurrent.futures import ThreadPoolExecutor
import json
import math
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CONDITIONS = {
    0: ('Clear sky', 'weather-sun'), 1: ('Mostly clear', 'weather-sun'),
    2: ('Partly cloudy', 'weather-cloud'), 3: ('Overcast', 'weather-cloud'),
    45: ('Fog', 'weather-cloud'), 48: ('Freezing fog', 'weather-cloud'),
    51: ('Light drizzle', 'weather-rain'), 53: ('Drizzle', 'weather-rain'), 55: ('Heavy drizzle', 'weather-rain'),
    56: ('Freezing drizzle', 'weather-rain'), 57: ('Freezing drizzle', 'weather-rain'),
    61: ('Light rain', 'weather-rain'), 63: ('Rain', 'weather-rain'), 65: ('Heavy rain', 'weather-rain'),
    66: ('Freezing rain', 'weather-rain'), 67: ('Freezing rain', 'weather-rain'),
    71: ('Light snow', 'weather-snow'), 73: ('Snow', 'weather-snow'), 75: ('Heavy snow', 'weather-snow'),
    77: ('Snow grains', 'weather-snow'), 80: ('Rain showers', 'weather-rain'),
    81: ('Rain showers', 'weather-rain'), 82: ('Heavy showers', 'weather-rain'),
    85: ('Snow showers', 'weather-snow'), 86: ('Snow showers', 'weather-snow'),
    95: ('Thunderstorm', 'weather-storm'), 96: ('Thunderstorm with hail', 'weather-storm'),
    99: ('Thunderstorm with hail', 'weather-storm'),
}


def location(value):
    if value == {}:
        return {}
    if not isinstance(value, dict) or not {'name', 'latitude', 'longitude'} <= value.keys():
        raise ValueError('A location needs a name, latitude and longitude.')
    name, country = value['name'], value.get('country', '')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120 or not isinstance(country, str) or len(country) > 100:
        raise ValueError('Invalid location name.')
    for key, bound in [('latitude', 90), ('longitude', 180)]:
        if type(value[key]) not in (int, float) or not math.isfinite(value[key]) or not -bound <= value[key] <= bound:
            raise ValueError('Invalid location coordinates.')
    return {'name': name.strip(), 'country': country.strip(),
            'latitude': round(value['latitude'], 6), 'longitude': round(value['longitude'], 6)}


def fetch_json(url):
    request = Request(url, headers={'User-Agent': 'LME-Shell/1.0 (desktop weather)', 'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=7) as response:
            body = response.read(1024 * 1024 + 1)
            if len(body) > 1024 * 1024:
                raise ValueError('Weather response is too large.')
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError('Invalid weather response.')
            return result
    except (OSError, URLError, ValueError) as error:
        raise ValueError('Weather service is unavailable. Check your connection and retry.') from error


class WeatherClient:
    def __init__(self, opener=fetch_json, executor=None, clock=time.monotonic, wall_clock=time.time):
        self.opener, self.clock, self.wall_clock = opener, clock, wall_clock
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix='lme-weather')
        self.forecast_job = self.geo_job = self.search_job = None
        self.forecast_key = None
        self.data = {}
        self.auto_location = {}
        self.forecast_due = self.geo_due = 0
        self.error = self.geo_error = ''
        self.search_state = {'query': '', 'loading': False, 'results': [], 'error': ''}

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)

    def detect(self):
        if self.geo_job is None:
            self.geo_job = self.executor.submit(self._detect)

    def refresh(self, automatic=True):
        self.forecast_due = 0
        if automatic:
            self.geo_due = 0
            self.detect()

    def search(self, query):
        if not isinstance(query, str) or not 2 <= len(query.strip()) <= 100:
            raise ValueError('Enter a city name of 2–100 characters.')
        if self.search_job is not None:
            raise ValueError('A location search is already running.')
        self.search_state = {'query': query.strip(), 'loading': True, 'results': [], 'error': ''}
        self.search_job = self.executor.submit(self._search, query.strip())

    def _detect(self):
        data = self.opener('https://ipwho.is/?' + urlencode({'fields': 'success,message,city,country,latitude,longitude'}))
        if data.get('success') is not True:
            raise ValueError('Automatic location is unavailable. Retry or choose a city in Settings.')
        return location({'name': data.get('city') or data.get('country') or 'Current location',
                         'country': data.get('country', ''), 'latitude': data.get('latitude'), 'longitude': data.get('longitude')})

    def _search(self, query):
        data = self.opener('https://geocoding-api.open-meteo.com/v1/search?' + urlencode({'name': query, 'count': 6, 'language': 'en', 'format': 'json'}))
        results = []
        for item in data.get('results', [])[:6]:
            try:
                results.append(location({'name': item['name'] + (', ' + item['admin1'] if item.get('admin1') and item['admin1'] != item['name'] else ''),
                                         'country': item.get('country', ''), 'latitude': item['latitude'], 'longitude': item['longitude']}))
            except (ValueError, KeyError, TypeError):
                continue
        return results

    def _forecast(self, place, unit):
        params = {'latitude': place['latitude'], 'longitude': place['longitude'], 'timezone': 'auto', 'forecast_days': 3,
                  'temperature_unit': unit, 'wind_speed_unit': 'mph' if unit == 'fahrenheit' else 'kmh',
                  'current': 'temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,wind_speed_10m',
                  'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max'}
        data = self.opener('https://api.open-meteo.com/v1/forecast?' + urlencode(params))
        current = data.get('current', {})
        temperature = current.get('temperature_2m')
        if type(temperature) not in (int, float) or not math.isfinite(temperature):
            raise ValueError('The weather service returned no valid temperature.')
        def number(value):
            return value if type(value) in (int, float) and math.isfinite(value) else None
        code = current.get('weather_code')
        condition, icon = CONDITIONS.get(code, ('Unknown conditions', 'weather-cloud'))
        daily, forecast = data.get('daily', {}), []
        dates = daily.get('time', [])
        for i, date in enumerate(dates[:3]):
            def day(key):
                values = daily.get(key, [])
                return number(values[i]) if i < len(values) else None
            forecast.append({'date': date, 'min': day('temperature_2m_min'), 'max': day('temperature_2m_max'),
                             'rainChance': day('precipitation_probability_max')})
        return {'temperature': temperature, 'feelsLike': number(current.get('apparent_temperature')),
                'humidity': number(current.get('relative_humidity_2m')), 'wind': number(current.get('wind_speed_10m')),
                'condition': condition, 'icon': icon, 'daily': forecast,
                'unit': '°F' if unit == 'fahrenheit' else '°C', 'windUnit': 'mph' if unit == 'fahrenheit' else 'km/h',
                'updatedAt': self.wall_clock()}

    def snapshot(self, preferences, allow_fetch=True):
        now = self.clock()
        if self.search_job is not None and self.search_job.done():
            try:
                self.search_state.update(results=self.search_job.result(), error='')
            except Exception as error:
                self.search_state.update(results=[], error=str(error)[:180])
            self.search_state['loading'] = False
            self.search_job = None
        if self.geo_job is not None and self.geo_job.done():
            try:
                self.auto_location = self.geo_job.result()
                self.geo_error = ''
                self.geo_due = now + 3600
            except Exception as error:
                self.geo_error = str(error)[:180]
                self.geo_due = now + 120
            self.geo_job = None
        if self.forecast_job is not None and self.forecast_job.done():
            try:
                self.data = self.forecast_job.result()
                self.error = ''
                self.forecast_due = now + 900
            except Exception as error:
                self.error = str(error)[:180]
                self.forecast_due = now + 120
            self.forecast_job = None
        automatic = preferences.get('weatherAutoLocation', True)
        if automatic and allow_fetch and now >= self.geo_due and self.geo_job is None:
            self.detect()
        place = self.auto_location if automatic else preferences.get('weatherLocation', {})
        unit = preferences.get('weatherUnit', 'celsius')
        key = (place.get('latitude'), place.get('longitude'), unit) if place else None
        if key != self.forecast_key and self.forecast_job is None:
            self.forecast_key = key
            self.data, self.error, self.forecast_due = {}, '', 0
        if place and allow_fetch and self.forecast_job is None and (now >= self.forecast_due or key != self.forecast_key):
            if key == self.forecast_key:
                self.forecast_job = self.executor.submit(self._forecast, place, unit)
        # Hide results belonging to an old location/unit while its request completes.
        matches = key == self.forecast_key
        return {**(self.data if matches else {}), 'available': bool(self.data) and matches,
                'configured': automatic or bool(place), 'automatic': automatic,
                'location': place, 'loading': self.geo_job is not None or self.forecast_job is not None,
                'stale': bool(self.error) or (automatic and bool(self.geo_error)), 'error': self.geo_error if automatic and self.geo_error else self.error,
                'search': dict(self.search_state)}
