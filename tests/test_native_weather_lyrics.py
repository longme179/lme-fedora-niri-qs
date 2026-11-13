"""Q5 leg 1 native tests: weather (WeatherModel/WeatherState) + lyrics (LyricsModel/LyricsState).

Contract: test_native_weather_lyrics.py (pins the Q5 weather/lyrics port; source strings and
engine flows freeze the shapes both sides keep).
REL: scripts/weather.py + weather_actions.py + lyrics.py -- DEPRECATED(Q5->Q6) sources;
qml/services/WeatherModel.js + WeatherState.qml + LyricsModel.js + LyricsState.qml.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class WeatherLyricsContractCase(unittest.TestCase):
    def read(self, name):
        return (REPO / name).read_text()

    def test_shell_state_routes_the_native_weather(self):
        text = self.read("qml/services/ShellState.qml")
        self.assertIn('readonly property var weather: NativeState.weather(snapshot.weather) // Q5', text)
        self.assertIn('if (WeatherState.handles(action)) return WeatherState; // Q5: weather search/detect/refresh', text)
        self.assertIn('WeatherState.sync(preferences); // Q5: resolves the native weather place', text)
        self.assertIn('NightLightState.sync(preferences, ((WeatherState.section || {}).location)', text)
        # Real sessions spawn the backend fetch-idle; fixtures keep the backend weather.
        self.assertIn('["--no-weather"]', text)
        self.assertEqual(text.count('"--no-weather"'), 1)

    def test_backend_flag_and_deprecated_markers(self):
        text = self.read("scripts/desktop_backend.py")
        self.assertIn('--no-weather", action="store_true"', text)
        self.assertIn('weather_fetch=not (args.once or args.no_weather)', text)
        self.assertIn('DEPRECATED(Q5->Q6): real sessions fetch natively', text)
        for name in ("scripts/weather.py", "scripts/weather_actions.py"):
            self.assertIn("DEPRECATED(Q5->Q6)", self.read(name), name)

    def test_singletons_registered_and_worker_retired(self):
        qmldir = self.read("qml/services/qmldir")
        self.assertIn("singleton WeatherState 1.0 WeatherState.qml", qmldir)
        self.assertIn("singleton LyricsState 1.0 LyricsState.qml", qmldir)
        session = self.read("qml/components/LyricsSession.qml")
        self.assertIn("LyricsState.lookup(song, value => {", session)
        self.assertNotIn("scripts/lyrics.py\"]; stdinEnabled", session)  # the worker protocol is retired
        self.assertIn("'--store' in sys.argv", self.read("scripts/lyrics.py"))

    def test_state_files_keep_the_injection_seams(self):
        weather = self.read("qml/services/WeatherState.qml")
        for seam in ("property var loader", "property var clock", "property var wallClock"):
            self.assertIn(seam, weather)
        self.assertIn('["weatherSearch", "weatherDetect", "weatherRefresh"]', weather)
        self.assertIn("weatherSelect stays backend", weather)
        lyrics = self.read("qml/services/LyricsState.qml")
        self.assertIn("cacheSlug", lyrics)  # the store/read key stays the model slug
        self.assertIn("storedAt", lyrics)   # TTL lives inside the JSON (FileView has no mtime)
        self.assertIn('"--store"', lyrics)
        model = self.read("qml/services/LyricsModel.js")
        self.assertIn("MAX_BYTES = 512 * 1024", model)
        self.assertIn("MAX_LINES = 4000", model)


class LyricsStoreCase(unittest.TestCase):
    def test_store_writes_stored_at_and_is_best_effort(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            payload = json.dumps({"directory": str(target), "filename": "slug~one",
                                  "raw": "[00:01]Hello", "status": "ready"})
            reply = subprocess.run([sys.executable, "-u", str(REPO / "scripts/lyrics.py"), "--store"],
                                   input=payload + "\n", capture_output=True, text=True, timeout=20)
            self.assertEqual(reply.returncode, 0, reply.stderr)
            written = json.loads((target / "slug~one.json").read_text())
            self.assertEqual(written["raw"], "[00:01]Hello")
            self.assertEqual(written["status"], "ready")
            self.assertIsInstance(written["storedAt"], float)
            # A path-traversal filename is rejected silently (cache writes never fail loudly).
            bad = json.dumps({"directory": str(target), "filename": "../escape", "raw": "x", "status": "ready"})
            subprocess.run([sys.executable, "-u", str(REPO / "scripts/lyrics.py"), "--store"],
                           input=bad + "\n", capture_output=True, text=True, timeout=20)
            self.assertFalse((target.parent / "escape.json").exists())


try:
    sys.path.insert(0, str(REPO / "tests"))
    from test_local_qml import LocalQmlCase  # noqa: E402
except ImportError:  # pragma: no cover - the engine cases need the local harness
    LocalQmlCase = None


@unittest.skipIf(LocalQmlCase is None or not Path("/usr/bin/quickshell").exists(), "Quickshell is required for native QML checks")
class WeatherLyricsModelCase(LocalQmlCase):
    def test_weather_model_contracts(self):
        result = self.run_qml('import "qml/services/WeatherModel.js" as Weather', '''
    property var checks: ({})
    Component.onCompleted: {
        let ok = true;
        try {
            checks.conditions = Weather.CONDITIONS[0][0] === "Clear sky" && Weather.CONDITIONS[61][1] === "weather-rain";
            const place = Weather.location({name: " Da Nang ", country: " VN ", latitude: 16.0549, longitude: 108.2});
            checks.location = place.name === "Da Nang" && place.country === "VN" && place.latitude === 16.0549;
            checks.rejects = !Weather.location({name: "X", latitude: 91, longitude: 0}) && !Weather.location({name: "", latitude: 0, longitude: 0})
                && !Weather.location({name: "X", latitude: "a", longitude: 0}) && !Weather.location(null);
            const forecast = Weather.normalizeForecast({current: {temperature_2m: 29, apparent_temperature: 32, relative_humidity_2m: 76,
                weather_code: 61, wind_speed_10m: 10},
                daily: {time: ["2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16"], temperature_2m_min: [25, 24, 25, 99],
                    temperature_2m_max: [31, 30, 32, 99], precipitation_probability_max: [30, 65, 20, 99]}}, "celsius", 123456);
            checks.forecast = forecast.temperature === 29 && forecast.feelsLike === 32 && forecast.condition === "Light rain"
                && forecast.icon === "weather-rain" && forecast.unit === "\\u00b0C" && forecast.windUnit === "km/h"
                && forecast.updatedAt === 123456 && forecast.daily.length === 3 && forecast.daily[2].rainChance === 20;
            let thrown = "";
            try { Weather.normalizeForecast({current: {temperature_2m: "x"}}, "celsius", 0); } catch (error) { thrown = error.message; }
            checks.noTemperature = thrown === "The weather service returned no valid temperature.";
            thrown = "";
            try { Weather.normalizeForecast({current: {temperature_2m: 1}, daily: {time: 5}}, "celsius", 0); } catch (error) { thrown = error.message; }
            checks.badForecast = thrown === "The weather service returned an invalid forecast. Retry.";
            const unknown = Weather.normalizeForecast({current: {temperature_2m: 1, weather_code: 42}}, "fahrenheit", 0);
            checks.unknown = unknown.condition === "Unknown conditions" && unknown.icon === "weather-cloud" && unknown.unit === "\\u00b0F";
            const search = Weather.normalizeSearch({results: [{name: "Da Nang", admin1: "Da Nang", country: "VN", latitude: 16, longitude: 108},
                {name: "Hue", admin1: "Thua Thien", country: "VN", latitude: 16.4, longitude: 107.6}, "junk"]});
            checks.search = search.length === 2 && search[0].name === "Da Nang" && search[1].name === "Hue, Thua Thien";
            thrown = "";
            try { Weather.normalizeSearch({results: 5}); } catch (error) { thrown = error.message; }
            checks.badSearch = thrown === "The location service returned an invalid response. Retry.";
            checks.detect = Weather.detectLocation({success: true, city: "Da Nang", country: "VN", latitude: 16, longitude: 108}).name === "Da Nang";
            thrown = "";
            try { Weather.detectLocation({success: false}); } catch (error) { thrown = error.message; }
            checks.detectFail = thrown === "Automatic location is unavailable. Retry or choose a city in Settings.";
        } catch (error) { ok = error; }
        done.start();  // quit during startup is dropped: finish from a Timer tick
    }
    Timer { id: done; interval: 100; onTriggered: fixture.finish(checks) }
''')
        self.assertEqual(result, dict(conditions=True, location=True, rejects=True, forecast=True, noTemperature=True,
                                      badForecast=True, unknown=True, search=True, badSearch=True, detect=True, detectFail=True))

    def test_lyrics_model_contracts(self):
        result = self.run_qml('import "qml/services/LyricsModel.js" as Lyrics', '''
    property var checks: ({})
    Component.onCompleted: {
        let thrown = "";
        try { Lyrics.parse("x".repeat(600000)); } catch (error) { thrown = error.message; }
        checks.tooLarge = thrown === "Lyrics are too large or invalid";
        const synced = Lyrics.parse("[00:01.50]Hello\\n[00:01.5]Hello again\\n[01:02]Bye");
        checks.synced = synced.synced === true && synced.lines.length === 2 && synced.lines[0].time === 1.5
            && synced.lines[0].text === "Hello\\nHello again" && synced.lines[1].text === "Bye";
        const offset = Lyrics.parse("[offset:500]\\n[00:01.00]Shifted");
        checks.offset = offset.lines[0].time === 0.5;
        const plain = Lyrics.parse("Just a line\\n[ar:Artist]\\nAnother");
        checks.plain = plain.synced === false && plain.plain === "Just a line\\nAnother" && plain.lines.length === 0;
        checks.bom = Lyrics.parse("\\ufeff[00:01]Bom").lines[0].text === "Bom";
        thrown = "";
        try { Lyrics.track({title: "x", duration: 90000}); } catch (error) { thrown = error.message; }
        checks.badDuration = thrown === "Invalid duration";
        const song = Lyrics.track({title: " T ", artist: "A", album: "", url: "", embedded: "", duration: 100.6, online: true});
        checks.track = song.title === "T" && song.duration === 101 && song.online === true;
        checks.result = Lyrics.result("[00:01]Hi", "LRCLIB").status === "ready"
            && Lyrics.result("", "LRCLIB").status === "none"
            && Lyrics.result("", "LRCLIB", true).status === "instrumental";
        checks.slug = Lyrics.cacheSlug({title: "a b", artist: "c/d", album: "", duration: 0}) === "a%20b~c%2Fd~0~0";
        done.start();  // quit during startup is dropped: finish from a Timer tick
    }
    Timer { id: done; interval: 100; onTriggered: fixture.finish(checks) }
''')
        self.assertEqual(result, dict(tooLarge=True, synced=True, offset=True, plain=True, bom=True,
                                      badDuration=True, track=True, result=True, slug=True))


@unittest.skipIf(LocalQmlCase is None or not Path("/usr/bin/quickshell").exists(), "Quickshell is required for native QML checks")
class WeatherLyricsStateCase(LocalQmlCase):
    """The state machines with injected transports/clocks — the engine equivalent of
    test_features.WeatherCase: auto-detect → forecast, failure backoff with kept data,
    unit switch hiding stale results, and the lyrics chain (embedded/sidecar/cache/online)."""

    def test_weather_state_flow_detect_forecast_backoff_and_unit_switch(self):
        result = self.run_qml('import "qml/services"', '''
    property var now: [0]
    property var urls: []
    property var geo: ({success: true, city: "Da Nang", country: "Vietnam", latitude: 16.05, longitude: 108.2})
    property var forecast: ({current: {temperature_2m: 29, apparent_temperature: 32, relative_humidity_2m: 76, weather_code: 61, wind_speed_10m: 10},
        daily: {time: ["2026-11-13", "2026-11-14", "2026-11-15"], temperature_2m_min: [25, 24, 25], temperature_2m_max: [31, 30, 32], precipitation_probability_max: [30, 65, 20]}})
    property bool geoFail: false
    property bool forecastFail: false
    property var searchDone: null
    Component.onCompleted: {
        WeatherState.loader = (url, onDone, onFail) => {
            fixture.urls.push(url);
            if (url.indexOf("ipwho.is") >= 0) { if (fixture.geoFail) onFail("unreachable"); else onDone(fixture.geo); return; }
            if (url.indexOf("geocoding-api") >= 0) { onDone({results: [{name: "Da Nang", country: "Vietnam", latitude: 16.05, longitude: 108.2}]}); return; }
            if (fixture.forecastFail) { onFail("unreachable"); return; }
            onDone(JSON.parse(JSON.stringify(fixture.forecast)));
        };
        WeatherState.clock = () => fixture.now[0];
        WeatherState.wallClock = () => 123456;
        const checks = ({});
        WeatherState.sync({weatherAutoLocation: true, weatherUnit: "celsius"});
        let state = WeatherState.section;
        checks.autoDetect = state.automatic === true && state.available === true && state.location.name === "Da Nang"
            && state.condition === "Light rain" && state.icon === "weather-rain" && state.unit === "\\u00b0C"
            && state.daily.length === 3 && state.updatedAt === 123456 && state.loading === false && state.stale === false;
        checks.urlParams = fixture.urls[1].indexOf("latitude=16.05") >= 0 && fixture.urls[1].indexOf("temperature_unit=celsius") >= 0
            && fixture.urls[1].indexOf("timezone=auto") >= 0;
        fixture.now[0] = 3600; fixture.geoFail = true;
        WeatherState.sync({weatherAutoLocation: true, weatherUnit: "celsius"});
        state = WeatherState.section;
        checks.geoKeepsData = state.available === true && state.stale === true && state.error.indexOf("choose a city") >= 0;
        fixture.now[0] = 3600 + 121; fixture.geoFail = false;  // past the 120 s backoff
        WeatherState.sync({weatherAutoLocation: true, weatherUnit: "celsius"});
        checks.geoRetries = WeatherState.section.stale === false;
        fixture.now[0] = 3721 + 900;
        WeatherState.sync({weatherAutoLocation: false, weatherLocation: {name: "Manual", latitude: 0, longitude: 0}, weatherUnit: "celsius"});
        state = WeatherState.section;
        checks.manual = state.available === true && state.location.name === "Manual" && state.automatic === false;
        fixture.now[0] = 3721 + 1800; fixture.forecastFail = true;  // same key: the failure keeps the last good data
        WeatherState.sync({weatherAutoLocation: false, weatherLocation: {name: "Manual", latitude: 0, longitude: 0}, weatherUnit: "celsius"});
        state = WeatherState.section;
        checks.forecastFailKeepsData = state.available === true && state.stale === true && state.error === "unreachable";
        WeatherState.perform("weatherSearch", {query: "da nang"}, (ok, message) => { fixture.searchDone = {ok: ok, message: message}; });
        checks.search = fixture.searchDone.ok === true && WeatherState.section.search.loading === false
            && WeatherState.section.search.results.length === 1 && WeatherState.section.search.results[0].name === "Da Nang";
        WeatherState.perform("weatherSearch", {query: "x"}, (ok, message) => { fixture.searchDone = {ok: ok, message: message}; });
        checks.badQuery = fixture.searchDone.ok === false && fixture.searchDone.message === "Enter a city name of 2\\u2013100 characters.";
        done.start();  // quit during startup is dropped: finish from a Timer tick
    }
    Timer { id: done; interval: 100; onTriggered: fixture.finish(checks) }
''', {"LME_SHELL_DEMO": "0", "NIRI_SOCKET": "/nonexistent-lme-q5-test"})
        self.assertEqual(result, dict(autoDetect=True, urlParams=True, geoKeepsData=True, geoRetries=True,
                                      manual=True, forecastFailKeepsData=True, search=True, badQuery=True))

    def test_lyrics_state_chain_embedded_sidecar_cache_online_store(self):
        import tempfile
        import time
        import urllib.parse
        with tempfile.TemporaryDirectory() as directory:
            sidecar = Path(directory) / "song.lrc"
            sidecar.write_text("[00:02]Sidecar line")
            slug = "~".join(urllib.parse.quote(part, safe="-_.!~*'()")
                            for part in ["Cached", "Artist", "", "0"])
            cache = Path(directory) / "cache" / "lme-shell" / "lyrics"
            cache.mkdir(parents=True)
            (cache / (slug + ".json")).write_text(json.dumps(
                {"storedAt": time.time() - 60, "raw": "[00:05]Cached line", "status": "ready"}))
            body = '''
    property var checks: ({})
    property int phase: 0
    property var reply: null
    function run(song) { fixture.reply = null; LyricsState.lookup(song, value => { fixture.reply = value; }); }
    Timer { interval: 100; running: true; repeat: true; onTriggered: {
        if (fixture.reply === null && fixture.phase > 0) return;  // wait for the async read
        switch (fixture.phase) {
        case 0:
            fixture.run({title: "T", artist: "A", duration: 0, embedded: "[00:01]Embedded line", url: "", online: false});
            fixture.phase = 1; break;
        case 1:
            fixture.checks.embedded = fixture.reply.status === "ready" && fixture.reply.source === "Player metadata" && fixture.reply.lines[0].text === "Embedded line";
            fixture.run({title: "T", artist: "A", duration: 0, url: "file://" + SIDE, online: false});
            fixture.phase = 2; break;
        case 2:
            fixture.checks.sidecar = fixture.reply.source === "Local LRC" && fixture.reply.lines[0].text === "Sidecar line";
            fixture.run({title: "", artist: "", duration: 0, url: "", online: false});
            fixture.phase = 3; break;
        case 3:
            fixture.checks.metadata = fixture.reply.status === "metadata";
            fixture.run({title: "Cached", artist: "Artist", album: "", duration: 0, url: "", online: false});
            fixture.phase = 4; break;
        case 4:
            fixture.checks.cacheHit = fixture.reply.source === "LRCLIB \u00b7 cached" && fixture.reply.lines[0].text === "Cached line";
            fixture.run({title: "Fresh", artist: "Artist", album: "", duration: 0, url: "", online: true});
            fixture.phase = 5; break;
        case 5:
            fixture.checks.online = fixture.reply.status === "ready" && fixture.reply.source === "LRCLIB" && fixture.reply.lines[0].text === "Online line";
            fixture.run({title: "OfflineOnly", artist: "Artist", album: "", duration: 0, url: "", online: false});
            fixture.phase = 6; break;
        case 6:
            fixture.checks.offline = fixture.reply.status === "offline";
            fixture.phase = 7; break;  // give lyrics.py --store a beat before quit
        case 7:
            fixture.finish(fixture.checks); break;
        }
    } }
    Component.onCompleted: { LyricsState.loader = (url, onDone, onFail) => onDone({syncedLyrics: "[00:09]Online line"}); }
'''.replace("SIDE", json.dumps(str(sidecar)))
            result = self.run_qml('import "qml/services"', body,
                                  {"LME_SHELL_DEMO": "0", "XDG_CACHE_HOME": str(Path(directory) / "cache"),
                                   "NIRI_SOCKET": "/nonexistent-lme-q5-test"})
            self.assertEqual(result, dict(embedded=True, sidecar=True, metadata=True, cacheHit=True,
                                          online=True, offline=True))
            stored = Path(directory) / "cache" / "lme-shell" / "lyrics"
            fresh = "~".join(urllib.parse.quote(part, safe="-_.!~*'()") for part in ["Fresh", "Artist", "", "0"]) + ".json"
            written = stored / fresh
            self.assertTrue(written.exists(), "the online lookup stored its cache entry via lyrics.py --store")
            payload = json.loads(written.read_text())
            self.assertEqual(payload["raw"], "[00:09]Online line")
            self.assertEqual(payload["status"], "ready")
            self.assertIsInstance(payload["storedAt"], float)


if __name__ == "__main__":
    unittest.main()
