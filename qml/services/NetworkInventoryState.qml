// Role: NetworkInventoryState.qml (wifi layer, fan-in 1) — native saved connections, device
// inventory and the connect/disconnect/hotspot flows (QML-first plan Q3 final leg).
// REL: scripts/network_profiles.py + scripts/wifi_actions.py::provide_connections – the
// worker contracts this ports (read/inspect/change/cancel cadence, deadlines, message
// strings, the operation projection and lastRequest hint); qml/services/NetworkModel.js +
// NetworkPlans.js – the pure helpers; qml/services/CommandRunner.qml – the queued nmcli/
// busctl one-shots (argv allowlist by construction).
// INVARIANT: the section mirrors the backend projection's networkConnections shape; every
// dispatch settles exactly once with the backend's exact strings, command failures mapped
// through safe_error, errors installing the observed model (or the unavailable fallback).
// Known native edge: networkEdit spawns nm-connection-editor detached — quickshell reports
// no spawn failure, so a missing editor is silent where the backend toasted the generic
// NetworkManager failure. GOTCHA: cancel only stops the mutation command; reads never
// observe the cancellation (the backend's observe hook is mutation-only), and a cancel that
// lands during the confirmation read lets the flow finish normally.
pragma Singleton
import QtQuick
import "NetworkModel.js" as NetworkModel
import "NetworkPlans.js" as NetworkPlans

QtObject {
    id: root

    property var section: null
    property var activation: null
    property CommandRunner tools: CommandRunner { id: runner }

    readonly property var projection: {
        if (!activation) return Object.assign({}, section || {}, {operation: {}});
        return Object.assign({}, section || {}, {operation: {action: activation.action, uuid: activation.uuid,
            deviceId: activation.deviceId,
            cancellable: activation.action === "networkConnect" || activation.action === "networkHotspotStart",
            cancelling: activation.cancelling === true}});
    }

    readonly property var handledActions: ["networkRefresh", "networkConnect", "networkDisconnect", "networkHotspotPlan", "networkHotspotStart", "networkEdit", "networkCancel"]
    function handles(action) { return handledActions.includes(action); }
    // The service produces the backend's canonical errors itself (missing tools keep the
    // install message), so real sessions always route here; fixture modes never reach the router.
    function canRoute(action, payload, context) { return true; }

    function perform(action, request, done, context) {
        if (action === "networkCancel") return cancel(done);
        try { NetworkPlans.validate(action, request); }
        catch (error) { return done(false, String(error)); }  // prepare-time rejection: no install
        const deadline = Date.now() + 40000;
        const mutation = NetworkPlans.MUTATIONS.indexOf(action) >= 0;
        if (mutation) activation = {action: action, uuid: request.uuid, deviceId: String(request.deviceId || ""),
            request: request, done: done, deadline: deadline, cancelling: false, attempted: false,
            mutating: false, finished: false, profile: null, device: null, before: []};
        read(mutation ? Math.min(deadline, Date.now() + 10000) : Date.now() + 10000, model => {
            if (mutation && action !== "networkEdit") return change(action, request, deadline, model, done);
            inspect(action, request, model, done);
        }, error => failed(error, null, done));
    }

    // ---- scripts/network_profiles.py::read — identity, radio, devices, listing, details ----

    function command(deadline, argv, mutation, ok, fail) {
        const remaining = deadline - Date.now();
        if (remaining <= 0) return fail(NetworkModel.safeError("Network operation timed out"));
        runner.dispatch(argv[0], argv, Math.min(mutation ? 18000 : 2000, remaining), 1024 * 1024, (succeeded, text, error) => {
            if (!succeeded) {
                if (error === "Required command is unavailable: nmcli" || error === "Required command is unavailable: busctl")
                    return fail("Install NetworkManager/nmcli and systemd busctl to manage connections");
                return fail(NetworkModel.safeError(error));
            }
            ok(text);
        });
    }

    function epoch(deadline, ok, fail) {
        command(deadline, ["busctl", "--system", "--json=short", "call", "org.freedesktop.DBus",
            "/org/freedesktop/DBus", "org.freedesktop.DBus", "GetId"], false, busRaw => {
            command(deadline, ["busctl", "--system", "--json=short", "call", "org.freedesktop.DBus",
                "/org/freedesktop/DBus", "org.freedesktop.DBus", "GetNameOwner", "s", "org.freedesktop.NetworkManager"], false, ownerRaw => {
                try { ok(NetworkPlans.epochId(NetworkPlans.busIdentity(busRaw), NetworkPlans.busIdentity(ownerRaw))); }
                catch (error) { fail(String(error)); }
            }, fail);
        }, fail);
    }

    function read(deadline, ok, fail) {
        epoch(deadline, server => {
            command(deadline, ["nmcli", "-t", "-f", "WIFI-HW,WIFI", "general"], false, radio => {
                command(deadline, ["nmcli", "-t", "-m", "multiline", "-f", NetworkModel.DEVICE_FIELDS, "device", "show"], false, deviceRaw => {
                    listConnections(deadline, server, deviceRaw, radio, ok, fail);
                }, fail);
            }, fail);
        }, fail);
    }

    function listConnections(deadline, server, deviceRaw, radio, ok, fail) {
        command(deadline, ["nmcli", "-t", "-f", NetworkModel.LIST_FIELDS, "connection", "show"], false, listing => {
            let rows, ids;
            try { rows = NetworkModel.connections(listing); ids = NetworkModel.candidates(rows); }
            catch (error) { return fail(String(error)); }
            if (!ids.length) return buildModel(deadline, server, deviceRaw, rows, "", radio, ok, fail);
            const argv = ["nmcli", "-t", "-m", "multiline", "-f", NetworkModel.PROFILE_FIELDS.join(","), "connection", "show"];
            for (const id of ids) { argv.push("uuid"); argv.push(id); }
            command(deadline, argv, false, detailRaw => buildModel(deadline, server, deviceRaw, rows, detailRaw, radio, ok, fail), fail);
        }, fail);
    }

    function buildModel(deadline, server, deviceRaw, rows, detailRaw, radio, ok, fail) {
        let model;
        try { model = NetworkModel.inventory(server, deviceRaw, rows, detailRaw, radio); }
        catch (error) { return fail(String(error)); }
        epoch(deadline, second => {
            if (second !== server) return fail("NetworkManager changed during inspection; refresh");
            model.checkedAt = Date.now();
            ok(model);
        }, fail);
    }

    // scripts/network_profiles.py::inspect — refresh, the hotspot warning plan, and the
    // detached system editor. Non-mutations (refresh/hotspotPlan) carry no activation record,
    // so their dispatch settles through done() directly — settleDone(record) alone would
    // drop it and leave pendingActions stuck (the busy gate then deadlocks the family).
    function inspect(action, request, model, done) {
        if (action === "networkHotspotPlan") {
            try { model.hotspotPlan = NetworkPlans.hotspotPlan(model, request); }
            catch (error) { return failed(error, model, done); }
        }
        if (action === "networkEdit") {
            if (model.serverId !== request.serverId || !model.profiles.some(profile => profile.uuid === request.uuid))
                return failed("Saved connection changed; refresh before editing", model, done);
            runner.spawnDetached(["nm-connection-editor", "--edit=" + request.uuid]);
        }
        const record = activation;
        install(model, "", NetworkPlans.MUTATIONS.indexOf(action) >= 0 ? hintFor(action, request) : null);
        const message = action === "networkEdit" ? "Network editor opened" : "Network connections refreshed";
        if (record) settleDone(record, true, message); else done(true, message);
    }

    // scripts/network_profiles.py::change — select, mutate, confirm on a fresh read.
    function change(action, request, deadline, model, done) {
        let plan;
        try { plan = NetworkPlans.planChange(action, request, model); }
        catch (error) { return failed(error, model, done); }
        if (plan.already) {
            install(model, "", hintFor(action, request));
            settleDone(activation, true, "Connection is already active (NetworkManager)");
            return;
        }
        activation.profile = plan.profile; activation.device = plan.device;
        activation.before = plan.existing.map(entry => entry.path);
        if (activation.cancelling) return cancelled(false);
        activation.attempted = true; activation.mutating = true;
        command(deadline, ["nmcli", "--wait", "15"].concat(plan.args), true, () => {
            activation.mutating = false;
            if (activation.cancelling) return cancelled(true);
            read(Math.min(deadline, Date.now() + 10000), fresh =>
                confirm(action, request, deadline, fresh, plan.profile, plan.device, activation.before, done),
                error => failed(error, null, done));
        }, error => { activation.mutating = false; failed(error, null, done); });
    }

    function confirm(action, request, deadline, model, profile, device, before, done) {
        if (model.serverId !== request.serverId) return failed("NetworkManager changed before confirmation; refresh", model, done);
        const actual = NetworkPlans.activeFor(model, profile, device);
        let message;
        if (action === "networkDisconnect") {
            if (model.active.some(entry => entry.path === request.activePath))
                return failed("Unable to confirm disconnection; showing observed state", model, done);
            message = "Selected connection disconnected";
        } else {
            if (!actual.some(entry => entry.state === "activated"))
                return failed("Unable to confirm activation; showing observed state", model, done);
            if (action === "networkHotspotStart") {
                const current = model.profiles.find(entry => entry.uuid === profile.uuid) || null;
                if (!current || current.kind !== "hotspot" || current.settings["ipv4.method"] !== "shared"
                        || (current.security !== "wpa-psk" && current.security !== "sae")) {
                    const complaint = "Hotspot settings changed during activation; check the observed state before retrying";
                    return stopAttempt(model, profile, device, before, deadline, () => {
                        read(Math.min(deadline, Date.now() + 10000), fresh2 => failed(complaint, fresh2, done),
                            error2 => failed(complaint, null, done));
                    }, error => failed(error, null, done));
                }
                message = "Hotspot active; Internet access is not verified";
            } else message = "Connection active (NetworkManager)";
        }
        model.notice = message;
        install(model, "", hintFor(action, request));
        settleDone(activation, true, message);
    }

    // scripts/network_profiles.py::stop_attempt — bring down only the activations this flow
    // created (not siblings, not pre-existing ones).
    function stopAttempt(model, profile, device, before, deadline, ok, fail) {
        const targets = NetworkPlans.activeFor(model, profile, device)
            .filter(active => before.indexOf(active.path) < 0
                && model.active.filter(entry => entry.path === active.path).length === 1);
        function step(index) {
            if (index >= targets.length) return ok();
            command(deadline, ["nmcli", "--wait", "5", "connection", "down", "apath", targets[index].path], true,
                () => step(index + 1), fail);
        }
        step(0);
    }

    // scripts/wifi_actions.py::provide_connections::cancel — only a live activation of the
    // two cancellable actions; the finished guard mirrors the backend's worker-done window.
    function cancel(done) {
        if (!activation || ["networkConnect", "networkHotspotStart"].indexOf(activation.action) < 0)
            return done(false, "No network activation is running");
        if (activation.finished) return done(true, "Activation already finished; check observed connections");
        activation.cancelling = true;
        const record = activation;
        if (record.mutating) runner.stopCurrent(() => { record.mutating = false; cancelled(true); });
        done(true, "Cancellation requested; waiting for the observed outcome");
    }

    // The Cancelled arm: observe, stop what this flow created, confirm it is gone.
    function cancelled(attempted) {
        const record = activation;
        if (!record) return;
        read(Date.now() + 10000, model => {
            if (!attempted) return finishCancelled(record, attempted, model);
            if (model.serverId !== record.request.serverId)
                return failed("NetworkManager changed during cancellation; check actual connections", model, record.done, true);
            stopAttempt(model, record.profile, record.device, record.before, Date.now() + 8000, () => {
                read(Date.now() + 10000, fresh => {
                    const actual = NetworkPlans.activeFor(fresh, record.profile, record.device);
                    if (actual.some(entry => record.before.indexOf(entry.path) < 0))
                        return failed("Cancellation could not confirm disconnection; use Advanced network settings", fresh, record.done, true);
                    finishCancelled(record, attempted, fresh);
                }, error => failed(error, null, record.done, true));
            }, error => failed(error, null, record.done, true));
        }, error => failed(error, null, record.done, true));
    }

    function finishCancelled(record, attempted, model) {
        const message = "Activation cancelled." + (attempted && record.action === "networkHotspotStart" ? " Previous Wi-Fi may need reconnecting." : "");
        model.notice = message;
        install(model, "", hintFor(record.action, record.request));
        settleDone(record, true, message);
    }

    // The backend's except arm: after a mutation was attempted, refresh the observed state
    // best-effort (same deadline) before surfacing; the cancel cleanup surfaces directly.
    function failed(error, model, done, direct) {
        if (!direct && activation && activation.attempted) {
            read(Math.min(activation.deadline, Date.now() + 10000),
                fresh => surface(error, fresh, done), () => surface(error, model, done));
        } else surface(error, model, done);
    }

    function surface(error, model, done) {
        const message = String(error).slice(0, 400);
        install(model, message, null);
        if (activation) settleDone(activation, false, message); else done(false, message);
    }

    // scripts/wifi_actions.py::provide_connections::install — the observed model (or the
    // unavailable fallback) with the error attached; mutations leave the selection hint.
    function install(model, error, hint) {
        const previous = section && section.lastRequest ? section.lastRequest : null;
        const base = model ? Object.assign({}, model) : {available: false, devices: [], profiles: [], active: [], hotspotPlan: null};
        if (error) base.error = String(error).slice(0, 400);
        const chosen = hint || previous;
        if (chosen && chosen.serverId !== undefined && chosen.serverId === base.serverId) base.lastRequest = chosen;
        section = base;
    }

    function hintFor(action, request) {
        return {serverId: request.serverId, action: action, uuid: request.uuid, deviceId: String(request.deviceId || "")};
    }

    // Terminal publication: finished flips first (a synchronous dispatch inside done() still
    // sees the finished record, like the backend's worker-done window), then the record clears.
    function settleDone(record, ok, message) {
        if (record) { record.finished = true; record.done(ok, message); }
        if (activation === record) activation = null;
    }
}
