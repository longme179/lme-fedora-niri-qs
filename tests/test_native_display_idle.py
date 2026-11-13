"""Q4 legs 2-3: the display/mirror and night-light/idle family ports to QML.
Contract: test_native_display_idle.py covers native_display_idle behavior/contracts; check imports for fixtures/helpers under test.
"""
import importlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

import test_local_qml as qml_tests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

REPO = Path(__file__).resolve().parents[1]
SERVICES = REPO / "qml" / "services"
DISPLAY_MODEL, DISPLAY_STATE = SERVICES / "DisplayModel.js", SERVICES / "DisplayState.qml"
MIRROR_STATE = SERVICES / "MirrorState.qml"
NIGHT_MODEL, NIGHT_STATE = SERVICES / "NightLightModel.js", SERVICES / "NightLightState.qml"
IDLE_STATE = SERVICES / "IdleState.qml"
NATIVE_STATE, SHELL_STATE = SERVICES / "NativeState.qml", SERVICES / "ShellState.qml"
QMIDS = SERVICES / "qmldir"
SHELL_ENTRY = REPO / "shell.qml"
BACKEND = REPO / "scripts" / "desktop_backend.py"
IDLE_HELPER = REPO / "scripts" / "idle_control.py"
MIRROR_CONTROLS = REPO / "qml" / "components" / "MirrorControls.qml"
DISPLAY_PAGE, SETTINGS_VIEW = REPO / "qml" / "settings" / "DisplayPage.qml", REPO / "qml" / "settings" / "SettingsView.qml"
NIGHT_PAGE, IDLE_PAGE = REPO / "qml" / "settings" / "NightLightPage.qml", REPO / "qml" / "settings" / "IdlePage.qml"
PORT_FILES = [DISPLAY_STATE, MIRROR_STATE, NIGHT_STATE, IDLE_STATE]

PINNED_MESSAGES = [
    "Displays refreshed",
    "Display mirroring is disabled",
    "Stop the current mirror before starting another.",
    "Install wl-mirror to mirror onto a connected display.",
    "Choose two different, active niri displays.",
    "Mirror started on ",
    "Mirror stopped",
    "Mirror refreshed",
    "A mirrored display was disconnected or disabled.",
    "Night Light refreshed",
    "Night Light retry must be boolean",
    "Install wlsunset, then restart the shell to enable Night Light.",
    "wlsunset stopped. Gamma control may be unavailable or owned by another app.",
    "Gamma control failed. Check compositor/driver support and stop any other gamma controller. ",
    "Waiting for location. Choose a location in Weather or use a time schedule.",
    "Use a time in HH:MM format",
    "Invalid sunset coordinates",
    "Sunset scheduling is unavailable at this latitude; choose a time schedule",
    "No sunrise or sunset today; choose a time schedule",
    "Idle profile refreshed",
    "Idle paused",
    "Idle resumed",
    "Idle inhibit must be boolean",
    " to enable this idle profile.",
    "swayidle stopped: ",
]


def nonblank(path):
    return sum(1 for line in Path(path).read_text().splitlines() if line.strip())


class StubRunner:
    """Plain-name executables so the Python argv builder compares against the QML builder."""

    def executable(self, name):
        return name


def normalized_idle_argv(argv, helper):
    """Mask the interpreter and helper paths the two builders legitimately choose differently."""
    masked = []
    for word in argv:
        text = word
        for absolute, token in ((str(helper), "<helper>"), (sys.executable, "python3")):
            text = text.replace(absolute, token)
        masked.append(text)
    return masked


def wait_for_exit(pid, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        time.sleep(0.05)
    return False


class DisplayIdleContractsCase(unittest.TestCase):
    def test_display_state_ports_the_family(self):
        # displayRefresh stays infallible like scripts/display_actions.py::refresh — a failed
        # read degrades to the empty outputs list with the same acknowledgement — and the
        # section carries display_control.py's snapshot shape (outputs + socket-scoped preview).
        model = DISPLAY_MODEL.read_text()
        self.assertIn(".pragma library", model)
        self.assertIn("function normalizedOutputs", model)
        self.assertIn(" × ", model)
        self.assertIn(" Hz", model)
        self.assertIn("toPrecision", model)  # Python f'{x:g}' — 6 significant digits
        code = DISPLAY_STATE.read_text()
        self.assertIn('"niri", "msg", "--json", "outputs"', code)
        self.assertIn("16777216", code)  # command_output.LIMITS['niri']
        self.assertIn("FileView", code)
        self.assertIn("watchChanges", code)
        self.assertIn("display-preview.json", code)
        self.assertIn("NIRI_SOCKET", code)  # preview state is scoped to the session
        self.assertIn("Displays refreshed", code)
        self.assertIn("outputs: [], preview: {}", code)

    def test_mirror_state_ports_the_family(self):
        # display_mirror.py's ownership: the wl-mirror child, the stop/exit error tails, the
        # disconnect re-check and the exact argv (fullscreen output, fit scaling, title).
        code = MIRROR_STATE.read_text()
        self.assertIn("--fullscreen-output", code)
        self.assertIn("--scaling", code)
        self.assertIn('"fit"', code)
        self.assertIn('"LME Display Mirror"', code)
        self.assertIn("Stop the current mirror before starting another.", code)
        self.assertIn("Install wl-mirror to mirror onto a connected display.", code)
        self.assertIn("Choose two different, active niri displays.", code)
        self.assertIn("Mirror started on ", code)
        self.assertIn("Mirror stopped", code)
        self.assertIn("Mirror refreshed", code)
        self.assertIn("A mirrored display was disconnected or disabled.", code)
        self.assertIn("128", code)  # output-name length bound
        self.assertIn("Process", code)
        self.assertIn("SplitParser", code)

    def test_night_light_ports_the_family(self):
        # night_light.py: the Almanac solar math verbatim, the schedule modes, and the
        # wlsunset child with the backend's exact argv and error surfaces.
        model = NIGHT_MODEL.read_text()
        self.assertIn(".pragma library", model)
        for constant in ("0.9856", "3.289", "1.916", "0.020", "282.634", "0.91764", "0.39782", "90.833", "0.06571", "6.622"):
            self.assertIn(constant, model)
        self.assertIn("function clockMinutes", model)
        self.assertIn("function solarTimes", model)
        self.assertIn("function desiredState", model)
        code = NIGHT_STATE.read_text()
        self.assertIn('"-T"', code)
        self.assertIn('"-t"', code)
        self.assertIn('"06:00"', code)
        self.assertIn('"18:00"', code)
        self.assertIn("--parent", code)  # idle_control.py client sets PDEATHSIG against the shell
        self.assertIn('"client"', code)
        self.assertIn("Install wlsunset, then restart the shell to enable Night Light.", code)
        self.assertIn("wlsunset stopped. Gamma control may be unavailable or owned by another app.", code)
        self.assertIn("Gamma control failed. Check compositor/driver support and stop any other gamma controller. ", code)
        self.assertIn("Night Light refreshed", code)
        self.assertIn("Night Light retry must be boolean", code)
        self.assertIn("no gamma", code)  # the stderr failure pattern

    def test_idle_state_ports_the_family(self):
        # idle_control.py::idle_command's swayidle argv (shlex-joined command strings for the
        # sh -c daemon), the AC/battery profiles, the availability gate and the inhibit pause.
        code = IDLE_STATE.read_text()
        self.assertIn('"swayidle"', code)
        self.assertIn('"-w"', code)
        self.assertIn('"timeout"', code)
        self.assertIn('"resume"', code)
        self.assertIn('"before-sleep"', code)
        self.assertIn('"after-resume"', code)
        self.assertIn("power-off-monitors", code)
        self.assertIn("power-on-monitors", code)
        self.assertIn('"sleep"', code)
        self.assertIn('"--lock"', code)
        self.assertIn('"lock"', code)
        self.assertIn("Install ", code)
        self.assertIn(" to enable this idle profile.", code)
        self.assertIn("Idle paused", code)
        self.assertIn("Idle resumed", code)
        self.assertIn("Idle inhibit must be boolean", code)
        self.assertIn("Idle profile refreshed", code)
        self.assertIn("swayidle stopped: ", code)
        self.assertIn("--parent", code)
        self.assertIn("shellQuote", code)

    def test_shellstate_routes_and_drives_the_session_families(self):
        # The router fans out to the four services; the sections publish through NativeState;
        # the backend poll hook re-syncs the daemons at the backend's 2 s cadence and the shell
        # process stops the backend from owning wlsunset/swayidle (--no-session-daemons).
        code = SHELL_STATE.read_text()
        for name in ("DisplayState", "MirrorState", "NightLightState", "IdleState"):
            self.assertIn(name + ".handles(action)", code)
        for section in ("displays", "mirror", "nightLight", "idle"):
            self.assertIn("NativeState." + section + "(snapshot." + section + ")", code)
        self.assertIn("NightLightState.sync(", code)
        self.assertIn("IdleState.sync(", code)
        self.assertIn("MirrorState.recheck(preferences)", code)  # the hook passes preferences — recheck takes (preferences, done)
        self.assertIn('"--no-session-daemons"', code)

    def test_sections_gate_through_nativestate(self):
        code = NATIVE_STATE.read_text()
        for name, owner in (("displays", "DisplayState"), ("mirror", "MirrorState"),
                            ("nightLight", "NightLightState"), ("idle", "IdleState")):
            self.assertIn("function " + name + "(", code)
            self.assertIn(owner + ".section", code)

    def test_the_ipc_surface_serves_the_native_sections(self):
        # shell.qml's mirrorStatus/nightLightStatus/idleStatus feed the Settings forwarding
        # path (scripts/mirror_actions.py, night_light_actions.py, idle_actions.py) — they
        # must read the native-served properties, not the backend's stale copies.
        code = SHELL_ENTRY.read_text()
        self.assertIn("JSON.stringify(ShellState.mirror", code)
        self.assertIn("JSON.stringify(ShellState.nightLight", code)
        self.assertIn("JSON.stringify(ShellState.idle", code)

    def test_consumers_read_the_published_sections(self):
        for path, needle in ((MIRROR_CONTROLS, "ShellState.mirror"), (MIRROR_CONTROLS, "ShellState.displays"),
                             (DISPLAY_PAGE, "ShellState.displays"), (SETTINGS_VIEW, "ShellState.displays"),
                             (NIGHT_PAGE, "ShellState.nightLight"), (IDLE_PAGE, "ShellState.idle")):
            self.assertIn(needle, path.read_text(), str(path))
        for path in (MIRROR_CONTROLS, DISPLAY_PAGE, SETTINGS_VIEW, NIGHT_PAGE, IDLE_PAGE):
            self.assertNotIn("snapshot.mirror", path.read_text(), str(path))
            self.assertNotIn("snapshot.nightLight", path.read_text(), str(path))
            self.assertNotIn("snapshot.idle", path.read_text(), str(path))

    def test_qml_documents_only_use_declared_types_from_qmldir_directories(self):
        declared = {}
        for line in QMIDS.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "singleton":
                declared[parts[1]] = parts[3]
        for name in ("DisplayState", "MirrorState", "NightLightState", "IdleState"):
            self.assertEqual(declared.get(name), name + ".qml")

    def test_backend_keeps_the_families_as_the_documented_fallback(self):
        # The Settings preview flow (displayApply/Confirm/Revert) and the demo registry keep
        # the backend path; the shell stops owning the daemons through the new flag. The
        # families are marked for the Q6 retirement sweep like the earlier phases.
        code = BACKEND.read_text()
        self.assertIn("--no-session-daemons", code)
        self.assertIn("no_session_daemons", code)
        for script, note in (("display_control.py", "DEPRECATED(Q4->Q6)"), ("display_actions.py", "DEPRECATED(Q4->Q6)"),
                             ("display_mirror.py", "DEPRECATED(Q4->Q6)"), ("display_layout.py", "DEPRECATED(Q4->Q6)"),
                             ("night_light.py", "DEPRECATED(Q4->Q6)"), ("night_light_actions.py", "DEPRECATED(Q4->Q6)"),
                             ("idle_actions.py", "DEPRECATED(Q4->Q6)")):
            text = (REPO / "scripts" / script).read_text()
            self.assertIn(note, text, script)
        helper = IDLE_HELPER.read_text()
        self.assertIn("'probe'", helper)   # the availability probe the native services use
        self.assertIn("execvp", helper)     # PATH-resolved client exec (the plain-name argv)

    def test_messages_match_the_backend_contract(self):
        sources = "\n".join(path.read_text() for path in PORT_FILES + [NIGHT_MODEL, DISPLAY_MODEL])
        for message in PINNED_MESSAGES:
            self.assertIn(message, sources)

    def test_service_files_stay_within_the_size_cap(self):
        for path in PORT_FILES:
            self.assertLessEqual(nonblank(path), 250, path.name)
        self.assertLessEqual(nonblank(NIGHT_MODEL), 250)
        self.assertLessEqual(nonblank(DISPLAY_MODEL), 250)
        self.assertLessEqual(nonblank(SHELL_STATE), 368)  # Q5 weather+wallpaper routing ratchet
        self.assertLessEqual(nonblank(NATIVE_STATE), 253)  # Q4 closeout + Q5 weather composer ratchet

    def test_es2019plus_apis_stay_banned(self):
        for path in PORT_FILES + [NIGHT_MODEL, DISPLAY_MODEL]:
            self.assertNotIn("Object.fromEntries", path.read_text())


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class DisplayIdleQmlCase(unittest.TestCase):
    # Borrow the runner without subclassing LocalQmlCase — its own test methods would be
    # collected twice through this module (the sibling files' convention).
    run_qml = qml_tests.LocalQmlCase.run_qml

    OUTPUTS = {
        "HDMI-A-1": {"make": "Lenovo", "model": "ThinkVision", "modes": [
            {"width": 1920, "height": 1080, "refresh_rate": 60000},
            {"width": 1920, "height": 1080, "refresh_rate": 144002},
            {"width": 1280, "height": 720, "refresh_rate": 59999}],
            "current_mode": 1, "logical": {"scale": 2, "x": 1920, "y": 0, "width": 960, "height": 540}},
        "eDP-1": {"make": "BOE", "model": "0x095D", "modes": [
            {"width": 1920, "height": 1080, "refresh_rate": 120000},
            {"width": 1920, "height": 1080, "refresh_rate": 59997}],
            "current_mode": 0, "logical": {"scale": 1, "x": 0, "y": 0, "width": 1920, "height": 1080}},
        "DP-1": {"make": "", "model": "", "modes": [], "current_mode": None},
        "bad": "not-a-dict",
    }

    def test_display_model_matches_the_python_normalizer(self):
        # Parity: display_control.py::normalized_outputs over the corpus — mode labels (the
        # %g formatting of refresh/1000), the current-mode gating, logical defaults, the
        # disabled output and the name sort.
        module = importlib.import_module("display_control")
        corpus = [self.OUTPUTS, {}, {"only": "string"}, {"x": {"modes": "not-a-list", "logical": None}},
                  {"z": {"modes": [{"width": 0, "height": 1080, "refresh_rate": 60000},
                                   {"width": 1920, "height": 1080, "refresh_rate": True}],
                         "current_mode": "1", "logical": {"scale": 1.5, "x": -5, "y": 32767, "width": 1, "height": 2}},
                   "a": {"modes": [{"width": 3840, "height": 2160, "refresh_rate": 29997}],
                         "current_mode": 0}}]
        expected = []
        for raw in corpus:
            try:
                expected.append(module.normalized_outputs(raw))
            except (ValueError, TypeError):
                expected.append(None)
        body = '''
    property var cases: []
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            for (const raw of %(corpus)s) {
                try { cases.push(DisplayModel.normalizedOutputs(raw)); }
                catch (error) { cases.push(null); }
            }
            fixture.finish({cases: cases});
        }
    }''' % {"corpus": json.dumps(corpus)}
        result = self.run_qml('import "qml/services/DisplayModel.js" as DisplayModel', body)
        for index, (actual, want) in enumerate(zip(result["cases"], expected)):
            with self.subTest(corpus=index):
                self.assertEqual(actual, want)

    def test_night_light_model_matches_the_python_scheduler(self):
        # Parity: night_light.py::desired_state and solar_times over modes, schedule windows
        # (including the midnight wrap), sunset places, and the error corpus.
        module = importlib.import_module("night_light")
        from datetime import datetime
        hanoi = {"latitude": 21.0278, "longitude": 105.8342}
        tromso = {"latitude": 69.6492, "longitude": 18.9553}
        cases = []
        for epoch, mode, start, end, enabled, place in [
                (1769834400000, "manual", "20:00", "06:00", True, None),
                (1769834400000, "manual", "20:00", "06:00", False, None),
                (1769834400000, "schedule", "20:00", "06:00", True, None),
                (1769784000000, "schedule", "20:00", "06:00", True, None),
                (1769810400000, "schedule", "08:00", "18:00", True, None),
                (1769847600000, "schedule", "08:00", "18:00", True, None),
                (1769834400000, "sunset", "20:00", "06:00", True, hanoi),
                (1764986400000, "sunset", "20:00", "06:00", True, hanoi),
                (1769834400000, "sunset", "20:00", "06:00", True, None),
                (1769834400000, "sunset", "20:00", "06:00", True, {"latitude": 95, "longitude": 0}),
                (1764986400000, "sunset", "20:00", "06:00", True, tromso),
                (1769834400000, "schedule", "7:00", "06:00", True, None),
                (1769834400000, "schedule", "24:00", "06:00", True, None)]:
            preferences = {"nightLightMode": mode, "nightLightStart": start, "nightLightEnd": end,
                           "nightLightEnabled": enabled}
            try:
                wanted, begins, finish = module.desired_state(preferences, place, datetime.fromtimestamp(epoch / 1000).astimezone())
                cases.append({"epoch": epoch, "preferences": preferences, "place": place,
                              "wanted": wanted, "start": begins, "end": finish})
            except (ValueError, KeyError) as error:
                message = "Waiting for location. Choose a location in Weather or use a time schedule." if isinstance(error, KeyError) else str(error)
                cases.append({"epoch": epoch, "preferences": preferences, "place": place, "error": message})
        body = '''
    property var cases: []
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            for (const item of %(cases)s) {
                try {
                    const result = NightLightModel.desiredState(item.preferences, item.place, new Date(item.epoch));
                    cases.push({epoch: item.epoch, wanted: result[0], start: result[1], end: result[2]});
                } catch (error) { cases.push({epoch: item.epoch, error: String(error)}); }
            }
            fixture.finish({cases: cases});
        }
    }''' % {"cases": json.dumps(cases)}
        result = self.run_qml('import "qml/services/NightLightModel.js" as NightLightModel', body)
        for actual, want in zip(result["cases"], cases):
            with self.subTest(epoch=want["epoch"], mode=want["preferences"]["nightLightMode"]):
                if "error" in want:
                    self.assertEqual(actual.get("error"), want["error"])
                else:
                    self.assertEqual(actual["wanted"], want["wanted"])
                    self.assertEqual(actual["start"], want["start"])
                    self.assertEqual(actual["end"], want["end"])

    def test_idle_command_matches_the_python_builder(self):
        # Parity: idle_control.py::idle_command over the profile matrix (display/lock/suspend
        # combinations and lock-before-sleep) — the shlex-joined command strings and the
        # timeout ordering, with the interpreter/helper paths masked to the common tokens.
        module = importlib.import_module("idle_control")
        profiles = [{"display": 10, "lock": 15, "suspend": 0}, {"display": 3, "lock": 5, "suspend": 15},
                    {"display": 0, "lock": 0, "suspend": 30}, {"display": 7, "lock": 0, "suspend": 0}]
        expected = []
        for profile in profiles:
            for lock_before_sleep in (False, True):
                argv = module.idle_command(profile, lock_before_sleep, StubRunner())
                expected.append({"profile": profile, "lockBeforeSleep": lock_before_sleep,
                                 "argv": normalized_idle_argv(argv, IDLE_HELPER)})
        body = '''
    property var cases: []
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            for (const item of %(cases)s) {
                cases.push({profile: item.profile, lockBeforeSleep: item.lockBeforeSleep,
                    argv: IdleState.idleCommand(item.profile, item.lockBeforeSleep)});
            }
            fixture.finish({cases: cases, helper: Quickshell.shellPath("scripts/idle_control.py")});
        }
    }''' % {"cases": json.dumps([{"profile": item["profile"], "lockBeforeSleep": item["lockBeforeSleep"]} for item in expected])}
        result = self.run_qml('import "qml/services"', body)
        helper = Path(result["helper"])
        for actual, want in zip(result["cases"], expected):
            with self.subTest(profile=want["profile"], lockBeforeSleep=want["lockBeforeSleep"]):
                self.assertEqual(normalized_idle_argv(actual["argv"], helper), want["argv"])

    def write_fake_tools(self, names, blocked=()):
        """A PATH dir with fake CLI tools that record their argv and idle; names in
        `blocked` become directories, which PATH resolution (shutil.which, execvp)
        skips — hiding a really-installed binary for the missing-tool cases."""
        directory = tempfile.mkdtemp(prefix="lme-q4-fakes-")
        markers = {}
        for name in names:
            marker = Path(directory) / (name + ".mark")
            markers[name] = str(marker)
            (Path(directory) / name).write_text(textwrap.dedent('''\
                #!/bin/sh
                { echo $$; for arg in "$@"; do echo "$arg"; done; } > "$MARK"
                exec sleep 300
                ''').replace("$MARK", markers[name]))
            os.chmod(Path(directory) / name, 0o755)
        for name in blocked:
            (Path(directory) / name).mkdir()
        return directory, markers

    def gate_environment(self, **overrides):
        """os.environ plus the harness's offscreen defaults — the migration gates export
        QT_QPA_PLATFORM=wayland, and the display cases override XDG_RUNTIME_DIR (the
        preview journal), which cuts the fixture off from the gate's private Sway socket."""
        environment = dict(os.environ)
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment["QT_QUICK_BACKEND"] = "software"
        environment.update(overrides)
        return environment

    def fake_niri_script(self, directory):
        payload = json.dumps(self.OUTPUTS)
        path = Path(directory) / "niri"
        path.write_text("#!/bin/sh\nprintf '%%s\\n' %s\n" % shlex.quote(payload))
        os.chmod(path, 0o755)

    def read_marker(self, marker):
        lines = Path(marker).read_text().splitlines()
        return int(lines[0]), lines[1:]

    def test_display_refresh_reads_outputs_and_the_journal(self):
        # End to end: displayRefresh reads the outputs (through a PATH-injected fake niri
        # CLI — the real one's Version handshake needs the live compositor), normalizes it
        # like display_control.py, and merges the socket-scoped preview journal. The live
        # socket parity is a separate real-machine probe, not an engine case.
        module = importlib.import_module("display_control")
        directory, _ = self.write_fake_tools([])
        self.fake_niri_script(directory)
        environment = self.gate_environment(PATH=directory + ":" + os.environ["PATH"],
                                            NIRI_SOCKET="/tmp/q4-fake-session.sock", LME_SHELL_DEMO="0")
        with tempfile.TemporaryDirectory() as runtime:
            environment["XDG_RUNTIME_DIR"] = runtime
            (Path(runtime) / "lme-shell").mkdir()
            (Path(runtime) / "lme-shell" / "display-preview.json").write_text(json.dumps(
                {"token": "abc123", "status": "pending", "deadline": 1799999999.5, "error": "",
                 "socket": environment["NIRI_SOCKET"], "original": [{"name": "eDP-1"}], "layout": [{"name": "eDP-1"}]}))
            body = '''
    property var answer: null
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            DisplayState.perform("displayRefresh", {}, (ok, message) => {
                fixture.finish({ok: ok, message: message, section: DisplayState.section});
            });
        }
    }'''
            result = self.run_qml('import "qml/services"', body, environment=environment)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["message"], "Displays refreshed")
            self.assertEqual(result["section"]["outputs"], module.normalized_outputs(self.OUTPUTS))
            self.assertEqual(result["section"]["preview"], {"token": "abc123", "status": "pending",
                                                            "deadline": 1799999999.5, "error": ""})

    def test_display_refresh_scopes_the_journal_to_the_session(self):
        # A journal written by another compositor session (socket mismatch) must publish an
        # empty preview — display_control.py::snapshot's stale-session guard.
        directory, _ = self.write_fake_tools([])
        self.fake_niri_script(directory)
        environment = self.gate_environment(PATH=directory + ":" + os.environ["PATH"],
                                            NIRI_SOCKET="/tmp/q4-fake-session.sock", LME_SHELL_DEMO="0")
        with tempfile.TemporaryDirectory() as runtime:
            environment["XDG_RUNTIME_DIR"] = runtime
            (Path(runtime) / "lme-shell").mkdir()
            (Path(runtime) / "lme-shell" / "display-preview.json").write_text(json.dumps(
                {"token": "stale", "status": "pending", "deadline": 1799999999.5, "socket": "/elsewhere/niri.sock"}))
            body = '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: DisplayState.perform("displayRefresh", {}, (ok, message) =>
            fixture.finish({section: DisplayState.section}));
    }'''
            result = self.run_qml('import "qml/services"', body, environment=environment)
            self.assertEqual(result["section"]["preview"], {})
            self.assertTrue(result["section"]["outputs"])

    def test_mirror_round_trip_with_a_fake_wl_mirror(self):
        # The wl-mirror child ownership: mirrorStart spawns the recorded argv, a concurrent
        # second start is busy, stop reaps the child, and a restart after the stop is never
        # busy (the synchronous command clear). The stop step settles first so the fake's
        # marker lands before the SIGTERM.
        directory, markers = self.write_fake_tools(["wl-mirror"])
        self.fake_niri_script(directory)
        environment = dict(os.environ)
        environment["PATH"] = directory + ":" + environment["PATH"]
        environment["LME_SHELL_DEMO"] = "0"
        body = '''
    property var results: []
    property Timer settle: Timer {
        interval: 600
        onTriggered: {
            if (fixture.results.length === 2) fixture.step("mirrorStop", {});
            else if (fixture.results.length === 3) fixture.step("mirrorStart", {source: "eDP-1", target: "eDP-1"});
        }
    }
    function step(action, request) {
        MirrorState.perform(action, request, (ok, message) => {
            results.push({action: action, ok: ok, message: message, section: JSON.parse(JSON.stringify(MirrorState.section))});
            if (results.length >= 4) fixture.finish({results: results});
            else if (results.length === 1) fixture.step("mirrorStart", {source: "eDP-1", target: "DP-2"});
            else settle.restart();
        }, {preferences: {mirroringEnabled: true}});
    }
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: fixture.step("mirrorStart", {source: "eDP-1", target: "HDMI-A-1"})
    }
    Timer { interval: 12000; running: true; repeat: false; onTriggered: fixture.finish({results: results}) }'''
        result = self.run_qml('import "qml/services"', body, environment=environment)
        by_action = {}
        for row in result["results"]:
            by_action.setdefault(row["action"], []).append(row)
        started = by_action["mirrorStart"][0]
        self.assertTrue(started["ok"], started)
        self.assertEqual(started["message"], "Mirror started on HDMI-A-1")
        self.assertTrue(started["section"]["active"])
        self.assertEqual(started["section"]["source"], "eDP-1")
        self.assertEqual(started["section"]["target"], "HDMI-A-1")
        pid, argv = self.read_marker(markers["wl-mirror"])
        self.assertEqual(argv, ["--fullscreen-output", "HDMI-A-1", "--scaling", "fit",
                                "--title", "LME Display Mirror", "eDP-1"])
        busy = by_action["mirrorStart"][1]
        self.assertFalse(busy["ok"])
        self.assertEqual(busy["message"], "Stop the current mirror before starting another.")
        stopped = by_action["mirrorStop"][0]
        self.assertTrue(stopped["ok"])
        self.assertEqual(stopped["message"], "Mirror stopped")
        self.assertFalse(stopped["section"]["active"])
        rejected = by_action["mirrorStart"][2]
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["message"], "Choose two different, active niri displays.")
        self.assertTrue(wait_for_exit(pid), "the fake wl-mirror must be reaped by mirrorStop")

    @unittest.skipIf(shutil.which("wl-mirror"), "the missing-tool path needs a machine without wl-mirror (a PATH block cannot hide an installed binary — which/execvp continue past it)")
    def test_mirror_reports_a_missing_wl_mirror(self):
        # The FailedToStart discovery stands in for the backend's runner.available() pre-check:
        # the start settles with the install message and the section marks the tool missing.
        directory, _ = self.write_fake_tools([], blocked=("wl-mirror",))
        self.fake_niri_script(directory)
        environment = dict(os.environ)
        environment["PATH"] = directory + ":" + environment["PATH"]
        environment["LME_SHELL_DEMO"] = "0"
        body = '''
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            MirrorState.perform("mirrorStart", {source: "eDP-1", target: "HDMI-A-1"}, (ok, message) => {
                const section = MirrorState.section;
                if (!ok && !section.available) fixture.finish({ok: ok, message: message, section: section});
            }, {preferences: {mirroringEnabled: true}});
        }
    }
    Timer { interval: 12000; running: true; repeat: false; onTriggered: fixture.finish({ok: true, message: "", section: MirrorState.section}) }'''
        result = self.run_qml('import "qml/services"', body, environment=environment)
        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "Install wl-mirror to mirror onto a connected display.")
        self.assertFalse(result["section"]["available"])

    def test_night_light_spawns_and_stops_wlsunset(self):
        # The wlsunset child through the PDEATHSIG helper: the recorded argv is the backend's
        # (-T temperature+1, -t temperature, fixed 06:00/18:00), and disabling stops it.
        directory, markers = self.write_fake_tools(["wlsunset"])
        python = shutil.which("python3")
        os.symlink(python, Path(directory) / "python3")
        environment = dict(os.environ)
        environment["PATH"] = directory + ":" + environment["PATH"]
        environment["LME_SHELL_DEMO"] = "0"
        preferences = {"nightLightEnabled": True, "nightLightMode": "manual",
                       "nightLightStart": "20:00", "nightLightEnd": "06:00", "nightLightTemperature": 4000}
        body = '''
    property int phase: 0
    property var states: []
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            if (phase === 0) {
                NightLightState.sync(%(preferences)s, null);
                if (NightLightState.section.running) {
                    states.push(JSON.parse(JSON.stringify(NightLightState.section)));
                    phase = 1;  // settle: let the helper exec and the marker land
                }
            } else if (phase === 2) {
                NightLightState.sync(Object.assign({}, %(preferences)s, {nightLightEnabled: false}), null);
                states.push(JSON.parse(JSON.stringify(NightLightState.section)));
                fixture.finish({states: states});
            }
        }
    }
    Timer { interval: 3000; running: true; repeat: false; onTriggered: if (fixture.phase === 1) fixture.phase = 2 }
    Timer { interval: 12000; running: true; repeat: false; onTriggered: fixture.finish({states: states}) }''' % {"preferences": json.dumps(preferences)}
        result = self.run_qml('import "qml/services"', body, environment=environment)
        active, disabled = result["states"]
        self.assertTrue(active["available"], active)
        self.assertTrue(active["active"])
        self.assertTrue(active["running"])
        self.assertEqual(active["temperature"], 4000)
        self.assertEqual(active["mode"], "manual")
        self.assertEqual(active["error"], "")
        pid, argv = self.read_marker(markers["wlsunset"])
        self.assertEqual(argv, ["-T", "4001", "-t", "4000", "-S", "06:00", "-s", "18:00"])
        self.assertFalse(disabled["running"])
        self.assertFalse(disabled["active"])
        self.assertTrue(wait_for_exit(pid), "disabling Night Light must stop the wlsunset child")

    @unittest.skipIf(shutil.which("wlsunset"), "the missing-tool path needs a machine without wlsunset (a PATH block cannot hide an installed binary)")
    def test_night_light_reports_a_missing_wlsunset(self):
        directory, _ = self.write_fake_tools([], blocked=("wlsunset",))
        os.symlink(shutil.which("python3"), Path(directory) / "python3")
        environment = dict(os.environ)
        environment["PATH"] = directory + ":" + environment["PATH"]  # python3 for the probe, wlsunset blocked
        environment["LME_SHELL_DEMO"] = "0"
        preferences = {"nightLightEnabled": True, "nightLightMode": "manual",
                       "nightLightStart": "20:00", "nightLightEnd": "06:00", "nightLightTemperature": 4000}
        body = '''
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            NightLightState.sync(%(preferences)s, null);
            const section = NightLightState.section;
            if (!section.available && section.error) fixture.finish({section: section});
        }
    }
    Timer { interval: 12000; running: true; repeat: false; onTriggered: fixture.finish({section: NightLightState.section}) }''' % {"preferences": json.dumps(preferences)}
        result = self.run_qml('import "qml/services"', body, environment=environment)
        self.assertFalse(result["section"]["available"])
        self.assertEqual(result["section"]["error"],
                         "Install wlsunset, then restart the shell to enable Night Light.")

    def test_idle_spawns_swayidle_with_the_backend_argv(self):
        # The swayidle child: the recorded argv equals idle_control.py::idle_command's port
        # (timeout ordering, resume/before-sleep/after-resume), and inhibit stops it.
        directory, markers = self.write_fake_tools(["swayidle"])
        os.symlink(shutil.which("python3"), Path(directory) / "python3")
        environment = dict(os.environ)
        environment["PATH"] = directory + ":" + environment["PATH"]
        environment["LME_SHELL_DEMO"] = "0"
        preferences = {"idleEnabled": True, "idleLockBeforeSleep": False,
                       "idleProfiles": {"ac": {"display": 1, "lock": 2, "suspend": 0},
                                        "battery": {"display": 3, "lock": 5, "suspend": 15}}}
        body = '''
    property int phase: 0
    property var states: []
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            if (phase === 0) {
                IdleState.sync(%(preferences)s, true);
                if (IdleState.section.running) {
                    states.push(JSON.parse(JSON.stringify(IdleState.section)));
                    phase = 1;  // settle: let the helper exec and the marker land
                }
            } else if (phase === 2) {
                IdleState.perform("idleInhibit", {value: true}, (ok, message) => {
                    states.push({ok: ok, message: message, section: JSON.parse(JSON.stringify(IdleState.section))});
                    fixture.finish({states: states, helper: Quickshell.shellPath("scripts/idle_control.py")});
                });
            }
        }
    }
    Timer { interval: 3000; running: true; repeat: false; onTriggered: if (fixture.phase === 1) fixture.phase = 2 }
    Timer { interval: 12000; running: true; repeat: false; onTriggered: fixture.finish({states: states, helper: Quickshell.shellPath("scripts/idle_control.py")}) }''' % {"preferences": json.dumps(preferences)}
        result = self.run_qml('import "qml/services"', body, environment=environment)
        running, paused = result["states"]
        self.assertTrue(running["running"], running)
        self.assertEqual(running["source"], "ac")
        self.assertEqual(running["profile"], {"display": 1, "lock": 2, "suspend": 0})
        self.assertEqual(running["error"], "")
        pid, argv = self.read_marker(markers["swayidle"])
        helper = Path(result["helper"])
        module = importlib.import_module("idle_control")
        expected = module.idle_command({"display": 1, "lock": 2, "suspend": 0}, False, StubRunner())
        self.assertEqual(normalized_idle_argv(["swayidle"] + argv, helper), normalized_idle_argv(expected, IDLE_HELPER))
        self.assertTrue(paused["ok"])
        self.assertEqual(paused["message"], "Idle paused")
        self.assertTrue(paused["section"]["paused"])
        self.assertFalse(paused["section"]["running"])
        self.assertTrue(wait_for_exit(pid), "inhibiting idle must stop the swayidle child")

    @unittest.skipIf(shutil.which("swayidle"), "the missing-tool path needs a machine without swayidle (a PATH block cannot hide an installed binary)")
    def test_idle_reports_missing_binaries(self):
        directory, _ = self.write_fake_tools([], blocked=("swayidle", "niri", "swaylock"))
        os.symlink(shutil.which("python3"), Path(directory) / "python3")
        environment = dict(os.environ)
        environment["PATH"] = directory + ":" + environment["PATH"]  # python3 only — swayidle/niri/swaylock blocked
        environment["LME_SHELL_DEMO"] = "0"
        preferences = {"idleEnabled": True, "idleLockBeforeSleep": False,
                       "idleProfiles": {"ac": {"display": 1, "lock": 2, "suspend": 0},
                                        "battery": {"display": 3, "lock": 5, "suspend": 15}}}
        body = '''
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            IdleState.sync(%(preferences)s, true);
            const section = IdleState.section;
            if (!section.available && section.error) fixture.finish({section: section});
        }
    }
    Timer { interval: 12000; running: true; repeat: false; onTriggered: fixture.finish({section: IdleState.section}) }''' % {"preferences": json.dumps(preferences)}
        result = self.run_qml('import "qml/services"', body, environment=environment)
        self.assertFalse(result["section"]["available"])
        self.assertEqual(result["section"]["error"],
                         "Install swayidle, niri, swaylock to enable this idle profile.")


if __name__ == "__main__":
    unittest.main()
