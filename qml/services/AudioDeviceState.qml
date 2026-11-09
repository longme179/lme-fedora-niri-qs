// Role: AudioDeviceState.qml (audio layer, fan-in 1) — native audio device inventory and the
// port/profile/route writes (QML-first plan Q3 final leg).
// REL: scripts/audio_devices.py + scripts/audio_device_actions.py – the worker contracts this
// ports (read/change/observed/confirm cadence, deadlines, message strings); qml/services/
// AudioDeviceModel.js – the pure validation/selection helpers; qml/services/CommandRunner.qml –
// the queued pactl/pw-dump/pw-metadata one-shots (argv allowlist by construction).
// INVARIANT: the section mirrors the backend projection's audioDevices shape exactly (tests/
// test_native_inventory.py freezes normalize parity against audio_inventory.py); every dispatch
// settles exactly once through done(ok, message) with the backend's exact strings, errors ride
// the observed state like AudioFailure did. The read double-checks the server identity; the
// pw-tools route falls back to the pactl argv when the tools are missing (the backend's
// available() gate). Fixture modes never reach this singleton (the router gates them out).
pragma Singleton
import QtQuick
import "AudioDeviceModel.js" as AudioDeviceModel

QtObject {
    id: root

    property var section: null
    property CommandRunner tools: CommandRunner { id: runner }
    property var settleNext: null

    readonly property var handledActions: ["audioDevicesRefresh", "audioPort", "audioProfile", "audioRoute"]
    function handles(action) { return handledActions.includes(action); }
    // The service produces the backend's canonical errors itself (a missing pactl keeps the
    // install message), so real sessions always route here; fixture modes never reach the router.
    function canRoute(action, payload, context) { return true; }

    function perform(action, request, done, context) {
        const deadline = Date.now() + (action === "audioDevicesRefresh" ? 6000 : 8000);
        try { AudioDeviceModel.validate(action, request); }
        catch (error) { return done(false, String(error)); }  // prepare-time rejection: no state install
        read(deadline, model => {
            if (action === "audioDevicesRefresh") { install(model, ""); return done(true, "Audio devices refreshed"); }
            change(action, request, deadline, model, done);
        }, error => {
            install(null, error);
            done(false, error.slice(0, 400));
        });
    }

    // scripts/audio_devices.py::read — info, the four list groups, then info again; the server
    // identity must hold across the whole read.
    function read(deadline, ok, fail) {
        const argvs = [["pactl", "--format=json", "info"], ["pactl", "--format=json", "list", "cards"],
            ["pactl", "--format=json", "list", "sinks"], ["pactl", "--format=json", "list", "sources"],
            ["pactl", "--format=json", "list", "sink-inputs"], ["pactl", "--format=json", "info"]];
        const values = [];
        function step(index) {
            if (index >= argvs.length) {
                try {
                    if (AudioDeviceModel.serverId(values[0]) !== AudioDeviceModel.serverId(values[5]))
                        throw "Audio server changed while reading devices; refresh";
                    const model = AudioDeviceModel.normalize(values[0], values[1], values[2], values[3], values[4]);
                    model.checkedAt = Date.now();
                    ok(model);
                } catch (error) { fail(String(error)); }
                return;
            }
            query(deadline, argvs[index], value => { values.push(value); step(index + 1); }, fail);
        }
        step(0);
    }

    function query(deadline, argv, ok, fail) {
        if (deadline - Date.now() <= 0) return fail("Audio operation timed out; refresh to check the actual state");
        runner.dispatch("pactl", argv, Math.min(2000, deadline - Date.now()), 1024 * 1024, (succeeded, text, error) => {
            if (!succeeded) {
                if (error === "Required command is unavailable: pactl")
                    return fail("Install pulseaudio-utils (pactl) to use ports, profiles and app outputs");
                return fail(error);
            }
            let value;
            try { value = JSON.parse(text); }
            catch (parse) { return fail("Audio server returned invalid JSON"); }
            ok(value);
        });
    }

    // scripts/audio_devices.py::change — select, mutate, settle-wait, confirm on a fresh read.
    function change(action, request, deadline, initial, done) {
        let change;
        try { change = AudioDeviceModel.selection(initial, action, request); }
        catch (error) { install(initial, String(error)); return done(false, String(error)); }
        if (action === "audioRoute") return route(request, deadline, initial, change, done);
        pactlArgv(deadline, initial, change, request, done);
    }

    function pactlArgv(deadline, initial, change, request, done) {
        runner.dispatch("pactl", ["pactl", "--"].concat(change.argv), Math.min(2000, deadline - Date.now()), 1024 * 1024,
            (succeeded, text, error) => {
                if (!succeeded) return failChange(error, true, initial, deadline, done);
                settle(0, deadline, initial, change, request, done);
            });
    }

    // The audioRoute fast path: prove the local PipeWire core, then the two pw-metadata writes;
    // missing pw tools fall back to the pactl argv (the backend's available() gate).
    function route(request, deadline, initial, change, done) {
        query(deadline, ["pactl", "--format=json", "info"], info => {
            let id;
            try { id = AudioDeviceModel.serverId(info); }
            catch (error) { return failChange(String(error), false, initial, deadline, done); }
            if (id !== request.serverId) return failChange("Audio server changed; refresh devices", false, initial, deadline, done);
            if (deadline - Date.now() <= 0) return failChange("Audio operation timed out; refresh to check the actual state", false, initial, deadline, done);
            runner.dispatch("pw-dump", ["pw-dump"], Math.min(2000, deadline - Date.now()), 2 * 1024 * 1024, (succeeded, text, error) => {
                if (!succeeded) {
                    if (error === "Required command is unavailable: pw-dump") return pactlArgv(deadline, initial, change, request, done);
                    return failChange(error, false, initial, deadline, done);
                }
                let objects;
                try { objects = JSON.parse(text); }
                catch (parse) { return failChange("Invalid PipeWire inventory", false, initial, deadline, done); }
                let plan;
                try { plan = AudioDeviceModel.routePlan(info, objects, request.streamId.split("/").pop(), request.sinkId.split("/").pop()); }
                catch (planning) { return failChange(String(planning), false, initial, deadline, done); }
                metadata(plan, 0, deadline, initial, change, request, done);
            });
        }, error => failChange(error, false, initial, deadline, done));
    }

    function metadata(plan, index, deadline, initial, change, request, done) {
        const argvs = AudioDeviceModel.applyRouteArgv(plan[0], plan[1]);
        if (index >= argvs.length) return settle(0, deadline, initial, change, request, done);
        runner.dispatch("pw-metadata", argvs[index], Math.min(2000, deadline - Date.now()), 1024 * 1024, (succeeded, text, error) => {
            if (!succeeded) {
                if (index === 0 && error === "Required command is unavailable: pw-metadata") return pactlArgv(deadline, initial, change, request, done);
                return failChange(error, true, initial, deadline, done);
            }
            metadata(plan, index + 1, deadline, initial, change, request, done);
        });
    }

    // Pulse acknowledges before WirePlumber finishes linking: only this change's affected list
    // is retried (8 reads, 150 ms apart), then the confirmation re-reads the whole inventory.
    function settle(attempt, deadline, initial, change, request, done) {
        const group = change.group === "streams" ? "sink-inputs" : change.group;
        query(deadline, ["pactl", "--format=json", "list", group], data => {
            let matched = false;
            try { matched = AudioDeviceModel.observed(data, change); }
            catch (error) { return failChange(String(error), true, initial, deadline, done); }
            if (matched || attempt >= 7) return confirm(deadline, initial, change, request, done);
            root.settleNext = () => root.settle(attempt + 1, deadline, initial, change, request, done);
            settleTimer.restart();
        }, error => failChange(error, true, initial, deadline, done));
    }

    property Timer settleTimer: Timer {
        interval: 150
        onTriggered: if (root.settleNext) { const next = root.settleNext; root.settleNext = null; next(); }
    }

    function confirm(deadline, initial, change, request, done) {
        read(deadline, model => {
            if (model.serverId !== request.serverId) return failExact("Audio server changed before confirmation; refresh", model, done);
            const row = (model[change.group] || []).find(item => item.id === change.id);
            if (row && row[change.field] === change.value) { install(model, ""); return done(true, change.message); }
            failExact("Unable to confirm the requested audio change; showing the observed state", model, done);
        }, error => failChange(error, true, initial, deadline, done));
    }

    // The backend's except arm: after a mutation was attempted, refresh the observed state
    // best-effort (same deadline) before surfacing; otherwise the initial read rides along.
    function failChange(message, attempted, initial, deadline, done) {
        if (!attempted) return failExact(message, initial, done);
        read(deadline, model => failExact(message, model, done), () => failExact(message, null, done));
    }

    function failExact(message, model, done) {
        install(model, message);
        done(false, message.slice(0, 400));
    }

    // scripts/audio_device_actions.py::install — the observed model with the error attached, or
    // the stale fallback when nothing was observed.
    function install(model, message) {
        if (model) section = message ? Object.assign({}, model, {error: String(message).slice(0, 400)}) : model;
        else section = {available: false, cards: [], sinks: [], sources: [], streams: [],
            stale: true, error: String(message || "").slice(0, 400)};
    }
}
