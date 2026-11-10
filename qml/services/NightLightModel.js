// Role: NightLightModel.js (shared layer) — the Night Light schedule math (Q4
// night-light/idle families; plan §5 Q4).
// REL: scripts/night_light.py – clock_minutes, solar_times and desired_state verbatim:
// the Almanac for Computers (1990) solar approximation with the exact constants and
// operation order, the schedule modes (manual/schedule/sunset), the midnight-wrapping
// window test and the error corpus.
// INVARIANT: desiredState returns [wanted, start, end] or throws the backend's exact
// message; solar times are Date objects built like the backend's UTC datetimes (the
// caller formats them in local time). GOTCHA: the JS Date keeps the local timezone for
// getHours/getMinutes, matching Python's astimezone(now.tzinfo).strftime('%H:%M') on the
// same machine; the day-of-year uses the UTC calendar fields of the local date.
.pragma library

function clockMinutes(value) {
    if (typeof value !== "string" || !/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value))
        throw "Use a time in HH:MM format";
    const parts = value.split(":");
    return Number(parts[0]) * 60 + Number(parts[1]);
}

function dayOfYear(date) {
    return Math.floor((Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())
        - Date.UTC(date.getFullYear(), 0, 1)) / 86400000) + 1;
}

function solarTimes(date, latitude, longitude) {
    // Python's `type(v) in (int, float)` admits booleans; the schedule comes from the
    // validated preferences, so the numeric check mirrors the value contract instead.
    if (typeof latitude !== "number" || typeof longitude !== "number"
            || !isFinite(latitude) || !isFinite(longitude)
            || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180)
        throw "Invalid sunset coordinates";
    const result = [];
    for (const rising of [true, false]) {
        const t = dayOfYear(date) + ((rising ? 6 : 18) - longitude / 15) / 24;
        const anomaly = 0.9856 * t - 3.289;
        const rad = anomaly * Math.PI / 180;
        const solar = (anomaly + 1.916 * Math.sin(rad) + 0.020 * Math.sin(2 * rad) + 282.634) % 360;
        let ascension = (Math.atan(0.91764 * Math.tan(solar * Math.PI / 180)) * 180 / Math.PI) % 360;
        ascension += Math.floor(solar / 90) * 90 - Math.floor(ascension / 90) * 90;
        const declination = Math.asin(0.39782 * Math.sin(solar * Math.PI / 180));
        const denominator = Math.cos(declination) * Math.cos(latitude * Math.PI / 180);
        if (Math.abs(denominator) < 1e-9)
            throw "Sunset scheduling is unavailable at this latitude; choose a time schedule";
        const cosine = (Math.cos(90.833 * Math.PI / 180)
            - Math.sin(declination) * Math.sin(latitude * Math.PI / 180)) / denominator;
        if (!(cosine >= -1 && cosine <= 1))
            throw "No sunrise or sunset today; choose a time schedule";
        const angle = Math.acos(cosine) * 180 / Math.PI;
        const hour = (rising ? 360 - angle : angle) / 15;
        const utcHour = (hour + ascension / 15 - 0.06571 * t - 6.622 - longitude / 15) % 24;
        // Python's % is always non-negative; wrap the same way so the Date matches the
        // backend's datetime-on-the-base-date (the HH:MM is identical either way).
        const wrapped = (utcHour % 24 + 24) % 24;
        result.push(new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) + wrapped * 3600000));
    }
    return result;
}

function hhmm(date) {
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    return hours + ":" + minutes;
}

function desiredState(preferences, place, now) {
    const mode = preferences.nightLightMode;
    let start = preferences.nightLightStart, end = preferences.nightLightEnd;
    if (mode === "sunset") {
        if (!place)
            throw "Waiting for location. Choose a location in Weather or use a time schedule.";
        const times = solarTimes(now, place.latitude, place.longitude);
        end = hhmm(times[0]);   // sunrise
        start = hhmm(times[1]); // sunset
    }
    const first = clockMinutes(start), last = clockMinutes(end);
    const minute = now.getHours() * 60 + now.getMinutes();
    const scheduled = first < last ? (first <= minute && minute < last) : (minute >= first || minute < last);
    return [preferences.nightLightEnabled === true && (mode === "manual" || scheduled), start, end];
}
