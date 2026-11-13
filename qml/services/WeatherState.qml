// SPDX-License-Identifier: GPL-3.0-or-later
// Role: WeatherState.qml (weather layer, fan-in 1) — Q5 native weather client.
// REL: scripts/weather.py::WeatherClient – DEPRECATED(Q5->Q6); the section shape (available/
// configured/automatic/location/loading/stale/error/search) and the scheduling constants
// (geo 3600/120, forecast 900/120, keep-last-good) are frozen by tests/test_native_weather_lyrics.py.
// INVARIANT: fixture modes (demo/preview, LME_SHELL_BACKEND_DEMO, standalone Settings) never
// touch the network — sync() is inert there and the backend section keeps serving them.
// GOTCHA: XMLHttpRequest materializes the reply before the 1 MiB post-hoc size check (the
// Python reader truncated at the socket; open-meteo replies are ~10-50 KB).
pragma Singleton
import QtQuick
import Quickshell
import "WeatherModel.js" as Weather

QtObject {
    id: root

    // Test seams mirroring the Python opener/clock/wall_clock injection (tests swap these).
    property var loader
    property var clock
    property var wallClock
    readonly property bool inert: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
        || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1" || Quickshell.env("LME_SHELL_SETTINGS") === "1"

    property var data: ({})
    property string error: ""
    property var autoLocation: ({})
    property string geoError: ""
    property real geoDue: 0
    property real forecastDue: 0
    property string forecastKey: ""
    property bool geoPending: false
    property bool forecastPending: false
    property var searchState: ({query: "", loading: false, results: [], error: ""})
    property var lastPreferences: ({})
    // A plain assigned property, not a binding: consumers read it immediately after sync()
    // returns, and a queued binding evaluation would hand them the previous section (seen
    // as a read race on the real machine).
    property var section: null

    // The default transport: bounded GET with the Python client's User-Agent and timeout.
    readonly property var xhrLoader: (url, onDone, onFail) => {
        const request = new XMLHttpRequest();
        request.open("GET", url);
        request.setRequestHeader("User-Agent", "LME-Shell/1.0 (desktop weather)");
        request.setRequestHeader("Accept", "application/json");
        request.timeout = 7000;
        const fail = () => onFail("Weather service is unavailable. Check your connection and retry.");
        request.onload = () => {
            try {
                const body = String(request.responseText || "");
                if (body.length > 1048576) throw new Error("Weather response is too large.");
                const parsed = JSON.parse(body);
                if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Invalid weather response.");
                onDone(parsed);
            } catch (failure) { fail(); }
        };
        request.onerror = fail;
        request.ontimeout = fail;
        request.send();
    }
    property var built: ({})

    function transport() { return loader || xhrLoader; }
    function now() { return clock ? clock() : Date.now() / 1000; }
    function today() { return wallClock ? wallClock() : Date.now() / 1000; }
    function place() { return lastPreferences.weatherAutoLocation === undefined || lastPreferences.weatherAutoLocation === true
        ? autoLocation : (lastPreferences.weatherLocation || {}); }
    function unit() { return lastPreferences.weatherUnit === undefined ? "celsius" : lastPreferences.weatherUnit; }
    function keyOf(value) { return value && value.latitude !== undefined ? JSON.stringify([value.latitude, value.longitude, unit()]) : ""; }

    // Snapshot hook (ShellState.accept calls this at the 2 s poll cadence; Night Light reads
    // the resolved place right after, exactly like the backend's weather section fed it).
    function sync(preferences) {
        lastPreferences = preferences || {};
        if (inert) return;
        prepared = true;
        const time = now();
        if ((lastPreferences.weatherAutoLocation === undefined || lastPreferences.weatherAutoLocation === true)
                && time >= geoDue && !geoPending) detect();
        const spot = place(), key = keyOf(spot);
        if (key !== forecastKey && !forecastPending) { forecastKey = key; data = {}; error = ""; forecastDue = 0; }
        if (spot && key && !forecastPending && time >= forecastDue) {
            forecastPending = true;
            transport()(Weather.FORECAST_URL + Weather.forecastParams(spot, unit()), value => {
                try { data = Weather.normalizeForecast(value, unit(), today()); error = ""; forecastDue = now() + 900; }
                catch (failure) { error = String(failure.message || failure).slice(0, 180); forecastDue = now() + 120; }
                forecastPending = false; sync(lastPreferences);
            }, message => { error = String(message).slice(0, 180); forecastDue = now() + 120; forecastPending = false; sync(lastPreferences); });
        }
        rebuild();
    }

    function detect() {
        geoPending = true;
        transport()(Weather.DETECT_URL + Weather.query({fields: "success,message,city,country,latitude,longitude"}), value => {
            try { autoLocation = Weather.detectLocation(value); geoError = ""; geoDue = now() + 3600; }
            catch (failure) { geoError = String(failure.message || failure).slice(0, 180); geoDue = now() + 120; }
            geoPending = false; sync(lastPreferences);
        }, message => { geoError = String(message).slice(0, 180); geoDue = now() + 120; geoPending = false; sync(lastPreferences); });
    }

    function rebuild() {
        const automatic = lastPreferences.weatherAutoLocation === undefined || lastPreferences.weatherAutoLocation === true;
        const spot = place(), key = keyOf(spot);
        const matches = key !== "" && key === forecastKey;
        built = Object.assign(matches ? data : {}, {
            available: matches && Object.keys(data).length > 0, configured: automatic || !!spot, automatic: automatic,
            location: spot || {}, loading: geoPending || forecastPending,
            stale: !!error || (automatic && !!geoError), error: automatic && geoError ? geoError : error,
            search: searchState});
        section = inert || !prepared ? null : built;
    }

    // ---- Q5 action surface (weatherSelect stays backend: it writes preferences, Q6 scope) ----
    readonly property var handledActions: ["weatherSearch", "weatherDetect", "weatherRefresh"]
    function handles(action) { return handledActions.includes(action); }
    function canRoute(action, payload, context) { return true; }

    function perform(action, request, done, context) {
        if (action === "weatherSearch") {
            const query = request && request.query;
            if (typeof query !== "string" || query.trim().length < 2 || query.trim().length > 100)
                return done(false, "Enter a city name of 2–100 characters.");
            if (searchState.loading) return done(false, "A location search is already running.");
            const trimmed = query.trim();
            searchState = {query: trimmed, loading: true, results: [], error: ""};
            rebuild();
            transport()(Weather.GEOCODE_URL + Weather.query({name: trimmed, count: 6, language: "en", format: "json"}), value => {
                let results = [], message = "";
                try { results = Weather.normalizeSearch(value); }
                catch (failure) { message = String(failure.message || failure).slice(0, 180); }
                searchState = {query: trimmed, loading: false, results: results, error: message};
                rebuild();
            }, message => { searchState = {query: trimmed, loading: false, results: [], error: String(message).slice(0, 180)}; rebuild(); });
            return done(true, "Searching locations");
        }
        if (action === "weatherDetect") { geoDue = 0; sync(lastPreferences); return done(true, "Detecting approximate location"); }
        if (action === "weatherRefresh") {
            forecastDue = 0;
            if (lastPreferences.weatherAutoLocation === undefined || lastPreferences.weatherAutoLocation === true) geoDue = 0;
            sync(lastPreferences);
            return done(true, "Refreshing weather");
        }
        return done(false, "Unknown weather action");
    }

    property bool prepared: false
}
