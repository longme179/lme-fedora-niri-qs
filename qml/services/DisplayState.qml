// Role: DisplayState.qml (shared layer) — native display refresh + the displays section
// (Q4 display/mirror families; plan §5 Q4). The preview flow itself (apply/confirm/revert
// with the independent watchdog) stays on the Settings backend path that owns it.
// REL: scripts/display_actions.py::refresh – the infallible acknowledgement; the outputs
// read is scripts/display_control.py::outputs (`niri msg --json outputs` through the argv
// runner) and the preview merge is DisplayControl.snapshot() — the journal is read (and
// watched) from the same runtime path, scoped to this compositor session's NIRI_SOCKET so
// a stale session's preview never applies here.
// INVARIANT: the section keeps the backend shape {outputs, preview} where preview carries
// only {token, status, deadline, error} from the journal; a failed outputs read degrades
// to the empty list with the same ok acknowledgement (the backend's catch). GOTCHA: the
// deadline is seconds-since-epoch like the journal writes it (the Settings countdown
// divides Date.now() by 1000); the backend byte cap for niri is 16 MiB (characters here).
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "DisplayModel.js" as DisplayModel

QtObject {
    id: root

    readonly property bool settingsApp: Quickshell.env("LME_SHELL_SETTINGS") === "1"
    readonly property bool backendDemo: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
        || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1"
    readonly property bool live: !backendDemo && !settingsApp

    // display_control.py's directory: runtime, else state, else the home fallback.
    readonly property string journalDirectory: {
        const runtime = Quickshell.env("XDG_RUNTIME_DIR"), state = Quickshell.env("XDG_STATE_HOME");
        return (runtime || state || (Quickshell.env("HOME") || "") + "/.local/state") + "/lme-shell";
    }

    property var section: ({outputs: [], preview: {}})
    property var outputs: []

    property CommandRunner tools: CommandRunner { id: runner }

    // The preview journal is written by the Settings backend's preview watchdog; watching
    // keeps the shell's copy current without a dispatch (the backend re-read it per poll).
    // blockLoading makes text() a synchronous read, like the backend's read_json.
    property FileView journal: FileView {
        path: root.live ? root.journalDirectory + "/display-preview.json" : ""
        watchChanges: true; blockLoading: true; blockWrites: true; printErrors: false
        onFileChanged: reload()
        onLoaded: root.publish(root.outputs)
    }

    readonly property var handledActions: ["displayRefresh"]
    function handles(action) { return handledActions.includes(action); }
    // The service produces the backend's canonical degradation itself (a failed read is
    // the empty list with the same acknowledgement), so real sessions always route here;
    // fixture modes never reach the router.
    function canRoute(action, payload, context) { return true; }

    function perform(action, request, done, context) {
        runner.dispatch("niri", ["niri", "msg", "--json", "outputs"], 3000, 16777216, (ok, text, error) => {
            let outputs = [];
            if (ok) {
                try {
                    const normalized = DisplayModel.normalizedOutputs(JSON.parse(text));
                    if (normalized) outputs = normalized;
                } catch (parseError) {}
            }
            root.outputs = outputs;
            publish(outputs);
            done(true, "Displays refreshed");
        });
    }

    // DisplayControl.snapshot()'s preview projection: only the four keys, and only when
    // the journal belongs to this compositor session.
    function previewFrom(text) {
        let state = null;
        try { state = JSON.parse(text); } catch (error) { state = null; }
        if (!state || typeof state !== "object" || state.socket !== (Quickshell.env("NIRI_SOCKET") || "")) return {};
        const preview = {};
        for (const key of ["token", "status", "deadline", "error"])
            if (key in state) preview[key] = state[key];
        return preview;
    }

    function publish(outputs) {
        section = {outputs: outputs, preview: previewFrom(journal.text())};
    }
}
