"""Q4 session families: the compositor/session family ports to QML.
Contract: test_native_session.py covers native_session behavior/contracts; check imports for fixtures/helpers under test.
"""
import importlib  # Contract: test_native_session.py (Q4 session families; headroom 0, trailing note)
import json
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import test_local_qml as qml_tests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

NIRI_STATE = ROOT / "qml/services/NiriState.qml"
NIRI_IPC = ROOT / "qml/services/NiriIpc.qml"
NIRI_MODEL = ROOT / "qml/services/NiriModel.js"
WINDOW_STATE = ROOT / "qml/services/WindowState.qml"
KEYBINDS_STATE = ROOT / "qml/services/KeybindsState.qml"
KEYBINDS_MODEL = ROOT / "qml/services/KeybindsModel.js"
KEYBINDS_KDL = ROOT / "qml/services/KeybindsKdl.js"
IME_STATE = ROOT / "qml/services/ImeState.qml"
SHELL_STATE = ROOT / "qml/services/ShellState.qml"
NATIVE_STATE = ROOT / "qml/services/NativeState.qml"
QMLDIR = ROOT / "qml/services/qmldir"
IME_ACTIONS = ROOT / "scripts/ime_actions.py"
KEYBIND_ACTIONS = ROOT / "scripts/keybind_actions.py"
WINDOW_ACTIONS = ROOT / "scripts/window_actions.py"
NIRI_EVENTS = ROOT / "scripts/niri_events.py"
DESKTOP_BACKEND = ROOT / "scripts/desktop_backend.py"
KEYBINDS_PAGE = ROOT / "qml/settings/KeybindsPage.qml"

# The user-facing messages the backend contract established (scripts/window_actions.py,
# scripts/desktop_backend.py::niri_action, scripts/keybind_actions.py + niri_keybinds.py,
# scripts/ime_actions.py through command_runner.py's error strings); the native port must
# produce the same strings so toast/dialog UX is identical.
PINNED_MESSAGES = [
    "Window focused",
    "Window moved to workspace",
    "Native overview toggled",
    "Workspace focused",
    "A non-negative numeric ID is required",
    "Window or workspace is no longer available",
    "Workspace is no longer available",
    "NIRI_SOCKET is unavailable. Run the shell inside the niri session.",
    "The niri reply was too large",
    "Invalid niri reply",
    "The niri action failed",
    "timed out",
    "Keybindings refreshed",
    "Niri config not found. Set its path below if you use --config.",
    "Include limit reached (32 files / 12 levels).",
    "Config exceeds 512 KiB",
    "Included configs exceed 2 MiB",
]

PORT_FILES = [NIRI_STATE, NIRI_IPC, NIRI_MODEL, WINDOW_STATE, KEYBINDS_STATE, KEYBINDS_MODEL, KEYBINDS_KDL, IME_STATE]


def nonblank(path):
    return sum(1 for line in path.read_text().splitlines() if line.strip())


class NativeSessionContractCase(unittest.TestCase):
    def test_window_state_ports_the_family(self):
        # scripts/window_actions.py's four compositor actions route natively: the two argv
        # one-shots (focus/overview) and the two socket actions (move/workspace) with the
        # backend's validation order — moveWindow refreshes before checking, workspace checks
        # the cached lists first. launch stays with LauncherState (Q2) and fileOpen with the
        # backend (the Q5 search entries own its validation).
        code = WINDOW_STATE.read_text()
        self.assertIn('["focusWindow", "moveWindow", "nativeOverview", "workspace"]', code)
        self.assertIn('"niri", "msg", "action", "focus-window", "--id"', code)
        self.assertIn('"niri", "msg", "action", "toggle-overview"', code)
        self.assertIn("MoveWindowToWorkspace", code)
        self.assertIn("FocusWorkspace", code)
        self.assertIn("reference", code)
        self.assertIn("focus: false", code)
        # launch/fileOpen stay with their owning phases — the pinned handledActions list
        # above is the contract.
        self.assertIn("Window or workspace is no longer available", code)
        self.assertIn("Workspace is no longer available", code)

    def test_niri_ipc_ports_the_backend_action_protocol(self):
        # desktop_backend.py::niri_action is the contract: a fresh connection per request,
        # {"Action": ...} + newline (compact JSON), one reply line capped at 1 MiB, the 3 s
        # timeout surfacing as the TimeoutError string. Requests queue one deep (the backend
        # serialized them through its single-threaded loop).
        code = NIRI_IPC.read_text()
        self.assertIn('JSON.stringify({Action: action}) + "\\n"', code)
        # The Q4 real-machine lesson: every request builds its own Socket (createObject) —
        # a reused connection's false→true `connected` toggle loses the queued write while
        # the previous teardown is still settling, and the abandoned teardown segfaults
        # quickshell 0.3.2 (first engine run of the round-trip case).
        self.assertIn("createObject", code)
        self.assertIn("destroy", code)
        self.assertIn("3000", code)
        self.assertIn("1048576", code)
        self.assertIn("The niri reply was too large", code)
        self.assertIn("Invalid niri reply", code)
        self.assertIn("The niri action failed", code)
        self.assertIn('"timed out"', code)
        self.assertIn("NIRI_SOCKET is unavailable. Run the shell inside the niri session.", code)
        self.assertIn("queue", code)

    def test_niri_state_ports_the_event_stream(self):
        # The niri IPC event stream (plan §5 Q4: "niri IPC moves to Socket"): one long-lived
        # socket subscribes with the bare "EventStream" request, the ack line is skipped and
        # the event lines feed NiriModel's cache. The stream retries after 5 s (the backend's
        # next_event_retry); while it is not serving, Workspaces/Windows requests reseed the
        # cache at the backend's 2 s cadence. The published section keeps the backend shape.
        code = NIRI_STATE.read_text()
        self.assertIn('"EventStream"', code)
        # The subscription must be a real write from connectedChanged(true), not the
        # REL comment's prose (the second-engine-run lesson: the line existed only in
        # the header while the section silently degraded to the 2 s polled reads).
        self.assertIn("write('\"EventStream\"\\n')", code)
        self.assertIn("flush()", code)
        self.assertIn("NiriModel", code)
        self.assertIn("5000", code)
        self.assertIn("2000", code)
        self.assertIn("available", code)
        self.assertIn("workspaces", code)
        self.assertIn("windows", code)
        model = NIRI_MODEL.read_text()
        self.assertIn("IGNORED", model)
        self.assertIn("WorkspacesChanged", model)
        self.assertIn("WorkspaceActivated", model)
        self.assertIn("WindowOpenedOrChanged", model)
        self.assertIn("WindowLayoutsChanged", model)
        self.assertIn("8 * 1024 * 1024", model)
        # The reseed read pair lives in the IPC client (one connection per request, like
        # the backend's two `niri msg` invocations).
        ipc = NIRI_IPC.read_text()
        self.assertIn('"Workspaces"', ipc)
        self.assertIn('"Windows"', ipc)

    def test_keybinds_family_ports_the_parser(self):
        # scripts/niri_keybinds.py::read_keybinds ports to JS (the KDL tokenizer with raw
        # strings and block comments, disabled nodes, include chains at the documented
        # bounds); KeybindsState drives a FileView over the chain and installs the exact
        # backend section shape. keybindRefresh keeps its message.
        kdl = KEYBINDS_KDL.read_text()
        self.assertIn("tokens", kdl)
        self.assertIn("nodes", kdl)
        model = KEYBINDS_MODEL.read_text()
        for message in ("Niri config not found. Set its path below if you use --config.",
                        "Include limit reached (32 files / 12 levels).",
                        "Config exceeds 512 KiB", "Included configs exceed 2 MiB"):
            self.assertIn(message, model)
        self.assertIn("hotkey-overlay-title", model)
        self.assertIn("512 * 1024", model)
        self.assertIn("2 * 1024 * 1024", model)
        state = KEYBINDS_STATE.read_text()
        self.assertIn("FileView", state)
        self.assertIn("Keybindings refreshed", state)
        self.assertIn('["keybindRefresh"]', state)

    def test_ime_state_ports_the_input_method_action(self):
        # scripts/ime_actions.py: fcitx5-remote -n one-shot whose result message IS the
        # method name (ImeState consumes it through lastResult). CommandRunner reproduces
        # command_runner.py's error strings for a missing binary.
        code = IME_STATE.read_text()
        self.assertIn('["fcitx5-remote", "-n"]', code)
        self.assertIn("CommandRunner", code)
        self.assertIn('["inputMethod"]', code)

    def test_shellstate_router_fans_out_to_the_session_services(self):
        # The router (plan §5 Q3 mechanism, extended per family) fans out to the three new
        # action services; the niri section gates through NativeState like apps/usage do.
        # The busy gate is scoped to the incoming action (the backend's busy() contract —
        # a pending wifi mutation must not block the volume slider or workspace switches).
        code = SHELL_STATE.read_text()
        self.assertIn("WindowState.handles(action)", code)
        self.assertIn("KeybindsState.handles(action)", code)
        self.assertIn("ImeState.handles(action)", code)
        self.assertIn("NativeState.niri(snapshot.niri, draggingWindow)", code)
        self.assertIn("nativeMutationActions.includes(action)", code)

    def test_sections_gate_through_nativestate_and_the_page_reads_them(self):
        # NativeState.niri mirrors the apps gating: fixture modes pass the backend section
        # through, real sessions prefer the native section once it serves, and the drag pin
        # holds the previous reference exactly like Identity.keep did for the backend value.
        # compareSections gains the niri count pair (the event-driven native side leads the
        # backend's 2 s poll copy; counts are the day-long signal).
        code = NATIVE_STATE.read_text()
        self.assertIn("function niri(", code)
        self.assertIn("dragging", code)
        self.assertIn("niriWindows", code)
        self.assertIn("niriWorkspaces", code)
        page = KEYBINDS_PAGE.read_text()
        self.assertIn("ShellState.keybinds", page)
        shell = SHELL_STATE.read_text()
        self.assertIn("NativeState.keybinds(snapshot.keybinds)", shell)

    def test_qml_documents_only_use_declared_types_from_qmldir_directories(self):
        # The 43806ea lesson: a qmldir'd directory exports only its declared types, so every
        # type-referenced .qml must be declared. The new singletons join the qmldir.
        declared = set()
        for line in QMLDIR.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[0] == "singleton" and parts[2] == "1.0":
                declared.add(parts[1])
            elif len(parts) >= 3 and parts[1] == "1.0":
                declared.add(parts[0])
        for name in ("NiriState", "NiriIpc", "WindowState", "KeybindsState"):
            self.assertIn(name, declared)
        for path in PORT_FILES:
            if path.suffix != ".qml":
                continue
            self.assertTrue(any(line.strip() == "pragma Singleton" for line in path.read_text().splitlines()), path.name)

    def test_backend_families_stay_registered_as_the_fallback(self):
        # The A/B window keeps the backend round-trip: the families stay registered and
        # their modules carry the deprecation marker like the Q1-Q3 families did.
        backend = DESKTOP_BACKEND.read_text()
        for module in ("ime_actions", "keybind_actions", "window_actions", "niri_events", "niri_keybinds"):
            self.assertIn(module, backend)
        for path in (IME_ACTIONS, KEYBIND_ACTIONS, WINDOW_ACTIONS, NIRI_EVENTS):
            self.assertEqual(path.read_text().count("DEPRECATED(Q4->Q6)"), 1, path.name)
        self.assertGreaterEqual(backend.count("DEPRECATED(Q4->Q6)"), 4)

    def test_session_messages_match_the_backend_contract(self):
        corpus = "\n".join(path.read_text() for path in PORT_FILES)
        for message in PINNED_MESSAGES:
            self.assertIn(message, corpus)

    def test_service_files_stay_within_the_size_cap(self):
        for path in PORT_FILES:
            self.assertLessEqual(nonblank(path), 250, path.name)
        self.assertLessEqual(nonblank(SHELL_STATE), 371)  # Q5 weather+wallpaper routing  # Q4 legs 2-3 ratchet
        self.assertLessEqual(nonblank(NATIVE_STATE), 257)  # Q4 closeout + Q5 weather/search composer ratchet

    def test_es2019plus_apis_stay_banned(self):
        # The Q2 real-machine lesson: quickshell 0.3.2's V4 engine lacks Object.fromEntries;
        # the established contract bans it across qml/services.
        for path in PORT_FILES:
            self.assertNotIn("Object.fromEntries", path.read_text())


class FakeNiriSocket:
    """A unix-socket server speaking the niri IPC line protocol for engine probes."""

    def __init__(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / "niri.sock")
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.path)
        self.server.listen(8)
        self.server.settimeout(10)
        self.requests = []
        self.lock = threading.Lock()
        self.stream_holds = []

    def start(self):
        thread = threading.Thread(target=self._accept, daemon=True)
        thread.start()
        return self

    def _accept(self):
        while True:
            try:
                connection, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(connection,), daemon=True).start()

    def _handle(self, connection):
        connection.settimeout(10)
        try:
            line = b""
            while b"\n" not in line:
                chunk = connection.recv(65536)
                if not chunk:
                    return
                line += chunk
            request = line.decode().strip()
            with self.lock:
                self.requests.append(request)
            if request == '"EventStream"':
                connection.sendall(b'{"Ok":"Handled"}\n')
                connection.sendall(b'{"WorkspacesChanged":{"workspaces":[{"id":3,"idx":1,"output":"DP-1","is_active":true,"is_focused":true}]}}\n')
                connection.sendall(b'{"WindowsChanged":{"windows":[{"id":25,"app_id":"app","workspace_id":3}]}}\n')
                hold = threading.Event()
                self.stream_holds.append(hold)
                hold.wait(20)  # keep the stream open for the fixture's lifetime
            elif request == '"Workspaces"':
                connection.sendall(b'{"Ok":[{"id":3,"idx":1,"output":"DP-1"}]}\n')
            elif request == '"Windows"':
                connection.sendall(b'{"Ok":[{"id":25,"app_id":"a","workspace_id":3}]}\n')
            elif request.startswith('{"Action"'):
                action = json.loads(request)["Action"]
                if "MoveWindowToWorkspace" in action:
                    connection.sendall(b'{"Err":"no such window"}\n')
                else:
                    connection.sendall(b'{"Ok":"Handled"}\n')
            else:
                connection.sendall(b'{"Ok":"Handled"}\n')
        except OSError:
            pass
        finally:
            try:
                connection.close()
            except OSError:
                pass

    def close(self):
        for hold in self.stream_holds:
            hold.set()
        try:
            self.server.close()
        except OSError:
            pass
        self.directory.cleanup()


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class NativeSessionQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_keybinds_model_matches_the_python_parser(self):
        # Parity: the same KDL corpus (nested includes, disabled nodes, raw strings, block
        # comments, a missing include and an unterminated string) driven through the JS
        # traversal state machine must equal niri_keybinds.read_keybinds' section.
        module = importlib.import_module("niri_keybinds")
        corpus = {
            "root.kdl": (
                'include "part.kdl"\n'
                'include "absent.kdl"\n'
                'binds { Mod+T { hotkey-overlay-title="Terminal"; spawn "kitty"; } }\n'
                '/- binds { Mod+X { spawn "xterm"; } }\n'
                'binds { Mod+Q { close-window; } include "missing.kdl" }\n'
            ),
            "part.kdl": (
                'include "deep/second.kdl"\n'
                'binds { Mod+D {\n'
                '  spawn "alacritty" "--class" r#"term"inal"#;\n'
                '  // comment with "quotes"\n'
                '  /* block */ quit;\n'
                '} }\n'
            ),
            "deep/second.kdl": 'binds { Super+Left { focus-column-left; } }\nbinds { Super+Right { focus-workspace (null)? right; } }\n',
            "bad.kdl": 'binds { Mod+B { spawn "unterminated\n',
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, text in corpus.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(text)
            expected = module.read_keybinds(str(root / "root.kdl"))
            bad = module.read_keybinds(str(root / "bad.kdl"))
            files = json.dumps({str(root / name): text for name, text in corpus.items() if name != "bad.kdl"})
        body = '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const files = %s;
            const bad = %s;
            const cases = [];
            for (const corpus of [files, {"bad.kdl": bad}]) {
                const paths = Object.keys(corpus);
                let state = KeybindsModel.start(paths[0]);
                let guard = 0;
                while (guard++ < 64) {
                    const path = KeybindsModel.nextRead(state);
                    if (path === null) break;
                    if (corpus[path] === undefined) state = KeybindsModel.ingestError(state, "FileNotFound");
                    else state = KeybindsModel.ingest(state, corpus[path]);
                }
                cases.push(KeybindsModel.finish(state));
            }
            fixture.finish({cases: cases});
        }
    }''' % (files, json.dumps(corpus["bad.kdl"]))
        result = self.run_qml('import "qml/services/KeybindsModel.js" as KeybindsModel', body)
        # The missing top-level include is the one documented deviation: the native line is
        # "File could not be read" where the backend echoes the OS errno text. Everything
        # else — binding order, titles, commands, sources, lines, parse errors — is exact.
        def native_error(error):
            return error.split(":")[0] + ": File could not be read" if "No such file or directory" in error else error
        self.assertEqual(result["cases"][0]["bindings"], expected["bindings"])
        self.assertEqual([native_error(error) for error in result["cases"][0]["errors"]],
                         [native_error(error) for error in expected["errors"]])
        self.assertEqual(result["cases"][1]["bindings"], bad["bindings"])
        self.assertEqual(result["cases"][1]["errors"], bad["errors"])

    def test_niri_model_matches_the_python_event_cache(self):
        # Parity: the same event sequence (seed/connect cycles, valid updates, ignored
        # events, an unknown event, close) fed through NiriModel and niri_events'
        # NiriStateCache must agree on every snapshot, revision and invalidation.
        events_module = importlib.import_module("niri_events")
        sequence = [
            {"WorkspacesChanged": {"workspaces": [
                {"id": 1, "idx": 1, "output": "DP-1", "is_active": True, "is_focused": True},
                {"id": 2, "idx": 2, "output": "DP-1"}, {"id": 3, "idx": 1, "output": "eDP-1"}]}},
            {"KeyboardLayoutsChanged": {"layouts": ["us"]}},
            {"WorkspaceActivated": {"id": 2, "focused": True}},
            {"WindowsChanged": {"windows": [{"id": 11, "app_id": "a", "workspace_id": 1, "is_focused": True}]}},
            {"WindowOpenedOrChanged": {"window": {"id": 12, "app_id": "b", "workspace_id": 2, "is_urgent": True}}},
            {"WindowFocusChanged": {"id": 12}},
            {"WindowFocusTimestampChanged": {"id": 12, "focus_timestamp": 77}},
            {"WorkspaceActiveWindowChanged": {"workspace_id": 2, "active_window_id": 12}},
            {"WorkspaceUrgencyChanged": {"id": 3, "urgent": True}},
            {"WindowLayoutsChanged": {"changes": [[11, {"kind": "tile"}]]}},
            {"TotallyUnknownEvent": {"x": 1}},
            {"WindowClosed": {"id": 11}},
        ]
        model = {"available": True, "workspaces": [{"id": 1, "idx": 1, "output": "DP-1"}], "windows": []}
        cache = events_module.NiriStateCache()
        expected_states = []
        cache.seed(model)
        expected_states.append({"snapshot": cache.snapshot(), "valid": cache.valid, "revision": cache.revision})
        cache.connect()
        expected_states.append({"snapshot": cache.snapshot(), "valid": cache.valid, "revision": cache.revision})
        cache.seed(model)
        for event in sequence:
            cache.feed((json.dumps(event) + "\n").encode())  # the backend feeds pipe bytes
            expected_states.append({"snapshot": cache.snapshot(), "valid": cache.valid, "revision": cache.revision})
        cache.close()
        expected_states.append({"snapshot": cache.snapshot(), "valid": cache.valid, "revision": cache.revision})
        body = '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const events = %s;
            const model = %s;
            const cases = [];
            let cache = NiriModel.initial();
            cache = NiriModel.seed(cache, model);
            cases.push({snapshot: NiriModel.snapshot(cache), valid: cache.valid, revision: cache.revision});
            cache = NiriModel.connect(cache);
            cases.push({snapshot: NiriModel.snapshot(cache), valid: cache.valid, revision: cache.revision});
            cache = NiriModel.seed(cache, model);
            for (const event of events) {
                cache = NiriModel.feed(cache, JSON.stringify(event) + "\\n");
                cases.push({snapshot: NiriModel.snapshot(cache), valid: cache.valid, revision: cache.revision});
            }
            cache = NiriModel.close(cache);
            cases.push({snapshot: NiriModel.snapshot(cache), valid: cache.valid, revision: cache.revision});
            fixture.finish({cases: cases});
        }
    }''' % (json.dumps(sequence), json.dumps(model))
        result = self.run_qml('import "qml/services/NiriModel.js" as NiriModel', body)
        for index, (actual, expected) in enumerate(zip(result["cases"], expected_states)):
            with self.subTest(step=index):
                self.assertEqual(actual["valid"], expected["valid"])
                self.assertEqual(actual["revision"], expected["revision"])
                self.assertEqual(actual["snapshot"], expected["snapshot"])

    def test_window_actions_round_trip_through_a_fake_niri_socket(self):
        # End to end over a real unix socket serving the niri IPC protocol: the workspace
        # and moveWindow actions must send the backend's exact request JSON, settle with
        # the pinned messages, and surface the identifier/Err reply failure paths.
        fake = FakeNiriSocket().start()
        try:
            body = '''
    property var results: []
    function step(action, request) {
        WindowState.perform(action, request, (ok, message) => {
            results.push({action: action, ok: ok, message: message});
            if (results.length >= 4) fixture.finish({results: results});
        }, {niri: {available: true, workspaces: [{id: 3, idx: 1, output: "DP-1"}], windows: [{id: 25}]}});
    }
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            fixture.step("workspace", {id: 3});
            fixture.step("moveWindow", {id: 25, workspaceId: 3});
            fixture.step("focusWindow", {id: -2});
            fixture.step("workspace", {id: 99});
        }
    }'''
            result = self.run_qml('import "qml/services"', body,
                                  environment={"NIRI_SOCKET": fake.path, "LME_SHELL_DEMO": "0"})
            by_action = {}
            for row in result["results"]:
                by_action.setdefault(row["action"], []).append(row)
            self.assertEqual(by_action["workspace"][0], {"action": "workspace", "ok": True, "message": "Workspace focused"})
            self.assertEqual(by_action["moveWindow"][0], {"action": "moveWindow", "ok": False, "message": "no such window"})
            self.assertEqual(by_action["focusWindow"][0], {"action": "focusWindow", "ok": False,
                                                           "message": "A non-negative numeric ID is required"})
            self.assertEqual(by_action["workspace"][1], {"action": "workspace", "ok": False,
                                                         "message": "Workspace is no longer available"})
            with fake.lock:
                requests = list(fake.requests)
            self.assertIn('{"Action":{"FocusWorkspace":{"reference":{"Id":3}}}}', requests)
            self.assertIn('{"Action":{"MoveWindowToWorkspace":{"window_id":25,"reference":{"Id":3},"focus":false}}}', requests)
        finally:
            fake.close()

    def test_event_stream_updates_the_native_section(self):
        # The subscription line, the ack and the read-pair reseed populate NiriState's
        # section with the backend shape (available/workspaces/windows). Events that land
        # before the first seed are superseded by it — the backend's own ordering
        # (niri_events: feed() never flips valid; seed() overwrites the event-derived rows),
        # pinned by replaying NiriStateCache against this fake on the real machine.
        fake = FakeNiriSocket().start()
        try:
            body = '''
    property int ticks: 0
    Timer {
        interval: 250; running: true; repeat: true
        onTriggered: {
            fixture.ticks++;
            const section = NiriState.section;
            if (section.available === true && section.workspaces.length === 1 && section.windows.length === 1)
                fixture.finish({ready: true, section: section});
            else if (fixture.ticks > 40) fixture.finish({ready: false, section: section});
        }
    }'''
            result = self.run_qml('import "qml/services"', body,
                                  environment={"NIRI_SOCKET": fake.path, "LME_SHELL_DEMO": "0"})
            self.assertTrue(result["ready"], result)
            self.assertEqual(result["section"]["workspaces"][0]["id"], 3)
            # The read pair's "a", not the event's "app": the fake's events arrive before
            # the first seed, and the backend's seed() overwrites them (parity above).
            self.assertEqual(result["section"]["windows"][0]["app_id"], "a")
            with fake.lock:
                requests = list(fake.requests)
            self.assertIn('"EventStream"', requests)
        finally:
            fake.close()


if __name__ == "__main__":
    unittest.main()
