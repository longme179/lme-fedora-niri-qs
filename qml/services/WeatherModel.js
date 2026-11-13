// SPDX-License-Identifier: GPL-3.0-or-later
// Role: WeatherModel.js (weather layer, fan-in 1) — pure contracts for the Q5 native weather.
// REL: scripts/weather.py (CONDITIONS/location/_forecast/_search/_detect) – DEPRECATED(Q5->Q6);
// the response shapes and every error string are frozen by tests/test_native_weather_lyrics.py.
// INVARIANT: validation mirrors the Python module exactly — same bounds, same messages.
// GOTCHA: query encoding uses encodeURIComponent (%20) rather than urlencode's '+'; both are
// accepted by the endpoints and the difference is pinned by tests.
.pragma library

var CONDITIONS = {
    0: ['Clear sky', 'weather-sun'], 1: ['Mostly clear', 'weather-sun'],
    2: ['Partly cloudy', 'weather-cloud'], 3: ['Overcast', 'weather-cloud'],
    45: ['Fog', 'weather-cloud'], 48: ['Freezing fog', 'weather-cloud'],
    51: ['Light drizzle', 'weather-rain'], 53: ['Drizzle', 'weather-rain'], 55: ['Heavy drizzle', 'weather-rain'],
    56: ['Freezing drizzle', 'weather-rain'], 57: ['Freezing drizzle', 'weather-rain'],
    61: ['Light rain', 'weather-rain'], 63: ['Rain', 'weather-rain'], 65: ['Heavy rain', 'weather-rain'],
    66: ['Freezing rain', 'weather-rain'], 67: ['Freezing rain', 'weather-rain'],
    71: ['Light snow', 'weather-snow'], 73: ['Snow', 'weather-snow'], 75: ['Heavy snow', 'weather-snow'],
    77: ['Snow grains', 'weather-snow'], 80: ['Rain showers', 'weather-rain'],
    81: ['Rain showers', 'weather-rain'], 82: ['Heavy showers', 'weather-rain'],
    85: ['Snow showers', 'weather-snow'], 86: ['Snow showers', 'weather-snow'],
    95: ['Thunderstorm', 'weather-storm'], 96: ['Thunderstorm with hail', 'weather-storm'],
    99: ['Thunderstorm with hail', 'weather-storm']
};

function isNumber(value) { return typeof value === 'number' && isFinite(value); }

function location(value) {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) return null;
    if (!('name' in value) || !('latitude' in value) || !('longitude' in value)) return null;
    var name = value.name, country = value.country === undefined ? '' : value.country;
    if (typeof name !== 'string' || !name.trim() || name.trim().length > 120) return null;
    if (typeof country !== 'string' || country.length > 100) return null;
    var bounds = {latitude: 90, longitude: 180};
    for (var key in bounds) {
        var raw = value[key];
        if (!isNumber(raw) || raw < -bounds[key] || raw > bounds[key]) return null;
    }
    return {name: name.trim(), country: country.trim(),
            latitude: Math.round(value.latitude * 1e6) / 1e6, longitude: Math.round(value.longitude * 1e6) / 1e6};
}

// The invalid-location message the callers surface (matches scripts/weather_actions.py).
var INVALID_LOCATION = 'A location needs a name, latitude and longitude.';

function query(params) {
    var parts = [];
    for (var key in params) parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(params[key]));
    return parts.join('&');
}

function forecastParams(place, unit) {
    return query({latitude: place.latitude, longitude: place.longitude, timezone: 'auto', forecast_days: 3,
        temperature_unit: unit, wind_speed_unit: unit === 'fahrenheit' ? 'mph' : 'kmh',
        current: 'temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,wind_speed_10m',
        daily: 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max'});
}

var FORECAST_URL = 'https://api.open-meteo.com/v1/forecast?';
var GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search?';
var DETECT_URL = 'https://ipwho.is/?';

function detectLocation(data) {
    if (!data || typeof data !== 'object' || data.success !== true)
        throw new Error('Automatic location is unavailable. Retry or choose a city in Settings.');
    var place = location({name: data.city || data.country || 'Current location', country: data.country === undefined ? '' : data.country,
        latitude: data.latitude, longitude: data.longitude});
    if (!place) throw new Error('Automatic location is unavailable. Retry or choose a city in Settings.');
    return place;
}

function normalizeSearch(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data))
        throw new Error('The location service returned an invalid response. Retry.');
    var items = data.results === undefined || data.results === null ? [] : data.results;
    if (!Array.isArray(items)) throw new Error('The location service returned an invalid response. Retry.');
    var results = [];
    for (var i = 0; i < items.length && results.length < 6; i++) {
        var item = items[i];
        if (!item || typeof item !== 'object') continue;
        var admin = item.admin1 && item.admin1 !== item.name ? ', ' + item.admin1 : '';
        var place = location({name: String(item.name === undefined ? '' : item.name) + admin,
            country: item.country === undefined ? '' : String(item.country),
            latitude: item.latitude, longitude: item.longitude});
        if (place) results.push(place);
    }
    return results;
}

var NO_TEMPERATURE = 'The weather service returned no valid temperature.';
var BAD_FORECAST = 'The weather service returned an invalid forecast. Retry.';

function normalizeForecast(data, unit, updatedAt) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error(NO_TEMPERATURE);
    var current = data.current;
    var temperature = current && typeof current === 'object' ? current.temperature_2m : undefined;
    if (!isNumber(temperature)) throw new Error(NO_TEMPERATURE);
    function number(value) { return isNumber(value) ? value : null; }
    var code = current.weather_code;
    var entry = typeof code === 'number' && isFinite(code) && Math.round(code) === code ? CONDITIONS[code] : null;
    var pair = entry || ['Unknown conditions', 'weather-cloud'];
    var daily = data.daily === undefined || data.daily === null ? {} : data.daily;
    if (!daily || typeof daily !== 'object' || Array.isArray(daily)) throw new Error(BAD_FORECAST);
    var dates = daily.time === undefined || daily.time === null ? [] : daily.time;
    if (!Array.isArray(dates)) throw new Error(BAD_FORECAST);
    var forecast = [];
    for (var i = 0; i < dates.length && i < 3; i++) {
        if (typeof dates[i] !== 'string') continue;
        forecast.push((function (index) {
            function day(key) {
                var values = daily[key];
                if (values === undefined || values === null) return null;
                if (!Array.isArray(values)) throw new Error(BAD_FORECAST);
                return index < values.length ? number(values[index]) : null;
            }
            return {date: dates[index], min: day('temperature_2m_min'), max: day('temperature_2m_max'),
                    rainChance: day('precipitation_probability_max')};
        })(i));
    }
    return {temperature: temperature, feelsLike: number(current.apparent_temperature),
            humidity: number(current.relative_humidity_2m), wind: number(current.wind_speed_10m),
            condition: pair[0], icon: pair[1], daily: forecast,
            unit: unit === 'fahrenheit' ? '°F' : '°C', windUnit: unit === 'fahrenheit' ? 'mph' : 'km/h',
            updatedAt: updatedAt};
}
