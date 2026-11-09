"""Q2 native-file contracts: launcher apps/history, cpu-memory monitor, wiring.
Contract: test_native_files.py covers native_files behavior/contracts; check imports for fixtures/helpers under test.
"""
import json  # Contract: test_native_files.py (Q2 native file families; headroom 0, trailing note)
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import test_local_qml as qml_tests

ROOT = Path(__file__).resolve().parents[1]

# The backend demo snapshot freezes the sections this phase migrates (plan §5 Q2):
# the apps list, the launcher usage store and the file-sourced system fields.
DEMO_APPS = [
    {"id": "org.mozilla.firefox.desktop", "name": "Firefox", "icon": "firefox", "path": "", "terminal": False},
    {"id": "kitty.desktop", "name": "Kitty", "icon": "kitty", "path": "", "terminal": False},
    {"id": "org.gnome.Nautilus.desktop", "name": "Files", "icon": "org.gnome.Nautilus", "path": "", "terminal": False},
]
DEMO_SYSTEM_FILES = {"cpu": 12.4, "memoryPercent": 34.2, "memoryUsedGiB": 5.47, "memoryTotalGiB": 16,
                     "tempC": 47, "brightness": {"available": True, "percent": 65}}

SERVICES = ("qml/services/LauncherState.qml", "qml/services/MonitorState.qml")


def nonblank(path):
    return sum(bool(line.strip()) for line in (ROOT / path).read_text().splitlines())


def backend_demo_snapshot():
    environment = dict(os.environ, PYTHONPATH=str(ROOT / "scripts"))
    result = subprocess.run(["python3", "scripts/desktop_backend.py", "--demo", "--once"],
                            capture_output=True, text=True, timeout=60, cwd=ROOT, env=environment, check=True)
    return json.loads(result.stdout)


class NativeFilesContractCase(unittest.TestCase):
    def test_backend_demo_file_sections_are_frozen(self):
        state = backend_demo_snapshot()
        self.assertEqual(state.get("apps"), DEMO_APPS)
        self.assertEqual(state.get("monitor"), {})
        self.assertIsNone(state.get("launcherUsage"))
        for key, expected in DEMO_SYSTEM_FILES.items():
            self.assertEqual(state["system"].get(key), expected, key)

    def test_new_service_files_exist_within_the_size_cap(self):
        for path in SERVICES:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file(), path)
                self.assertLessEqual(nonblank(path), 250)

    def test_services_avoid_apis_missing_from_quickshells_v4_engine(self):
        # Real-machine Q2 verification: quickshell 0.3.2's engine has no Object.fromEntries
        # (TypeError at load) and rejects ES3 future-reserved words like 'native' as property
        # names (parse error). Node-based sandbox checks cannot catch either.
        for path in sorted((ROOT / "qml/services").glob("*.qml")):
            source = path.read_text()
            code = "\n".join(line for line in source.splitlines() if not line.strip().startswith("//"))
            with self.subTest(path=path.name):
                self.assertNotIn("Object.fromEntries", code)
                for match in re.finditer(r"^\s*(?:readonly\s+)?property\s+\w+\s+(native)\s*:", source, re.M):
                    self.fail(f"{path.name}: reserved keyword {match.group(1)!r} used as a property name")

    def test_launcher_state_pairs_helper_replaces_fromentries(self):
        source = (ROOT / "qml/services/LauncherState.qml").read_text()
        self.assertIn("function fromPairs(pairs)", source)
        self.assertGreaterEqual(source.count("fromPairs("), 4)  # definition + three call sites

    def test_qmldir_registers_the_new_singletons(self):
        qmldir = (ROOT / "qml/services/qmldir").read_text()
        for name in ("LauncherState", "MonitorState"):
            self.assertIn(f"singleton {name} 1.0", qmldir)

    def test_shellstate_routes_apps_and_usage_through_the_native_gate(self):
        source = (ROOT / "qml/services/ShellState.qml").read_text()
        self.assertIn("readonly property var apps: NativeState.apps(snapshot.apps)", source)
        self.assertIn("readonly property var launcherUsage: NativeState.usage(snapshot.launcherUsage,", source)
        self.assertNotIn("readonly property var apps: snapshot.apps || []", source)
        self.assertNotIn("readonly property var launcherUsage: snapshot.launcherUsage || ({})", source)

    def test_launcher_activation_routes_through_launcherstate(self):
        source = (ROOT / "qml/panels/Launcher.qml").read_text()
        self.assertIn('if (item.kind === "app") LauncherState.launch(item.id);', source)
        self.assertNotIn('ShellState.run("launch", {id: item.id})', source)

    def test_system_monitor_panel_reads_the_native_gate(self):
        source = (ROOT / "qml/panels/SystemMonitor.qml").read_text()
        self.assertIn("NativeState.monitor(ShellState.snapshot.monitor)", source)
        self.assertNotIn("readonly property var state: ShellState.snapshot.monitor || {}", source)

    def test_launcher_state_uses_desktop_entries_and_the_native_launch_path(self):
        source = (ROOT / "qml/services/LauncherState.qml").read_text()
        self.assertIn("DesktopEntries.applications.values", source)
        self.assertIn('id: entry.id + ".desktop"', source)
        self.assertIn("DesktopEntries.byId(", source)
        self.assertIn(".execute()", source)
        self.assertIn("startDetached()", source)
        # Fixture modes must keep the backend round-trip (demo preview, standalone Settings).
        self.assertIn('ShellState.run("launch", {id: id})', source)

    def test_launcher_history_store_ports_the_python_semantics(self):
        source = (ROOT / "qml/services/LauncherState.qml").read_text()
        # launcher_history.py constants: 7-day half-life, 90 s per event, 60-day retention, 256-app cap.
        for token in ("halfLifeDays: 7", "launchSecondsPerEvent: 90", "retentionDays: 60", "maxApps: 256"):
            self.assertIn(token, source)
        self.assertIn("atomicWrites: true", source)
        self.assertIn("watchChanges: true", source)
        self.assertIn('lme-shell/launcher.json', source)
        self.assertIn('"schema":1', source)

    def test_monitor_state_polls_the_same_proc_files_at_the_same_cadence(self):
        source = (ROOT / "qml/services/MonitorState.qml").read_text()
        for path in ('"/proc/stat"', '"/proc/meminfo"', '"/proc/net/dev"'):
            self.assertIn(path, source)
        self.assertIn("interval: 2000", source)  # the backend --interval default (no A6 change)
        # procfs has no inotify; the poll drives reload() explicitly.
        self.assertIn(".reload()", source)
        self.assertNotIn("watchChanges: true", source)

    def test_native_state_documents_the_transitional_backend_fed_keys(self):
        source = (ROOT / "qml/services/NativeState.qml").read_text()
        self.assertIn("tempC", source)
        self.assertIn("brightness", source)
        self.assertIn("processes", source)
        self.assertIn("DEPRECATED(Q2->Q6)", source)

    def test_backend_file_sections_are_marked_deprecated(self):
        source = (ROOT / "scripts/desktop_backend.py").read_text()
        self.assertGreaterEqual(source.count("DEPRECATED(Q2->Q6)"), 4)


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class NativeFilesQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_demo_apps_flow_through_unchanged(self):
        # Readiness-poll like the Q1 demo test: the backend snapshot and the shell's
        # spin-up take longer than any fixed wait on the real machine (round 3 raced at 1.2 s).
        result = self.run_qml('import "qml/services"', '''
    property int ticks: 0
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            fixture.ticks++;
            const ready = ShellState.backendReady && ShellState.apps && ShellState.apps.length > 0;
            if (ready || fixture.ticks >= 40) fixture.finish({apps: ShellState.apps || [], usage: ShellState.launcherUsage});
        }
    }''')
        self.assertEqual(result["apps"], DEMO_APPS)
        self.assertEqual(result["usage"], {})

    def test_native_apps_have_the_backend_shape_and_ordering(self):
        # DesktopEntries scans asynchronously — poll until the list lands (deadline 8 s,
        # comfortably inside run_qml's 15 s subprocess timeout) instead of a fixed 1.2 s
        # wait that raced the scan on the real machine (round 2: count 0 at 1.2 s).
        result = self.run_qml('import "qml/services"', '''
    property int ticks: 0
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            fixture.ticks++;
            const apps = LauncherState.apps;
            if ((apps && apps.length > 0) || fixture.ticks >= 40) fixture.finish({apps: apps || []});
        }
    }''', environment={"LME_SHELL_DEMO": "0"})
        apps = result["apps"]
        self.assertIsInstance(apps, list)
        self.assertGreater(len(apps), 0)
        for app in apps:
            for key in ("id", "name", "icon", "terminal", "genericName", "comment", "keywords"):
                self.assertIn(key, app)
            self.assertTrue(app["id"].endswith(".desktop"), app["id"])
        ordered = sorted(apps, key=lambda app: (app["name"].casefold(), app["id"]))
        self.assertEqual([app["id"] for app in apps], [app["id"] for app in ordered])

    def test_history_store_reads_scores_and_decay_like_the_python_module(self):
        # 3 launches today score 3*90; a single launch 8 days ago decayed one half-life window.
        # Poll until the FileView store lands — the fixture file load raced the fixed
        # 1.2 s wait on the real machine (round 3: usage still empty).
        result = self.run_qml('import "qml/services"', '''
    property int ticks: 0
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            fixture.ticks++;
            const usage = LauncherState.usage(true);
            if (Object.keys(usage).length > 0 || fixture.ticks >= 40) {
                const a = usage["app-a.desktop"], b = usage["app-b.desktop"];
                fixture.finish({keys: Object.keys(usage).sort(),
                                aScore: a ? Math.round(a.score) : null,
                                bScore: b ? Math.round(b.score) : null,
                                aLastIsNumber: a ? (typeof a.last === "number" && a.last <= Date.now()/1000) : null});
            }
        }
    }''', environment={
            "LME_SHELL_DEMO": "0",  # the store is fixture-gated; native mode points it at XDG_STATE_HOME
            "XDG_STATE_HOME": str(self.fixture_state_home()),
        })
        self.assertEqual(result["keys"], ["app-a.desktop", "app-b.desktop"])
        self.assertEqual(result["aScore"], 270)
        self.assertAlmostEqual(result["bScore"], 90 * 0.5 ** (8 / 7), delta=1)
        self.assertIs(result["aLastIsNumber"], True)

    def test_record_round_trips_into_the_store(self):
        state_home = self.fixture_state_home()
        result = self.run_qml('import "qml/services"', '''
    property int phase: 0
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            fixture.phase++;
            if (fixture.phase === 6) LauncherState.record("app-a.desktop");
            if (fixture.phase > 16) {
                const usage = LauncherState.usage(true);
                fixture.finish({score: usage["app-a.desktop"] ? usage["app-a.desktop"].score : null});
            }
        }
    }''', environment={"LME_SHELL_DEMO": "0", "XDG_STATE_HOME": str(state_home)})
        self.assertGreaterEqual(result["score"], 90)
        raw = json.loads((state_home / "lme-shell/launcher.json").read_text())
        self.assertEqual(raw["schema"], 1)
        self.assertIn("app-a.desktop", raw["apps"])

    def test_monitor_parsers_port_the_python_math(self):
        # finish() fires from a one-shot Timer, never from Component.onCompleted — Qt.quit()
        # without a receiver hangs until the 15 s timeout on the real machine (the Q1
        # hotfix lesson, commit eb5f2db).
        result = self.run_qml('import "qml/services"', '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const stat1 = "cpu  100 0 100 100 0 0 0 0 0 0\\ncpu0 60 0 20 20 0 0 0 0 0 0\\ncpu1 30 0 10 0 0 0 0 0 0 0\\n";
            const stat2 = "cpu  200 0 100 100 0 0 0 0 0 0\\ncpu0 120 0 40 20 0 0 0 0 0 0\\ncpu1 30 0 10 0 0 0 0 0 0 0\\n";
            const first = MonitorState.parseStat(stat1, null);
            const second = MonitorState.parseStat(stat2, first.totals);
            const mem = MonitorState.parseMeminfo("MemTotal:       16384000 kB\\nMemAvailable:    8192000 kB\\n");
            const net = MonitorState.parseNetDev("  wlo1: 1000 0 0 0 0 0 0 0 500 0 0 0 0 0 0 0\\n  lo: 1 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0\\n", {wlo1: [0, 0]}, 2);
            fixture.finish({cpu: second.cpu, core0: second.cores[0].percent, coreName: second.cores[0].name,
                            core1: second.cores[1].percent, cores: second.cores.length,
                            memPercent: mem.memoryPercent, memUsed: mem.memoryUsedGiB, memTotal: mem.memoryTotalGiB,
                            iface: net.interfaces[0].name, ifaceCount: net.interfaces.length,
                            download: net.interfaces[0].download, upload: net.interfaces[0].upload});
        }
    }''')
        # Totals delta: aggregate +100 total/+0 idle and cpu0 +80/+0 -> 100% busy; cpu1 unchanged -> null.
        self.assertEqual(result["cpu"], 100.0)
        self.assertEqual(result["core0"], 100.0)
        self.assertIsNone(result["core1"])
        self.assertEqual(result["coreName"], "CPU0")
        self.assertEqual(result["cores"], 2)
        # 16384000-8192000 = 8192000 of 16384000 -> 50.0%; 8192000/1024^2 = 7.81; 16384000/1024^2 = 15.63
        self.assertEqual(result["memPercent"], 50.0)
        self.assertEqual(result["memUsed"], 7.81)
        self.assertEqual(result["memTotal"], 15.63)
        self.assertEqual(result["iface"], "wlo1")
        self.assertEqual(result["ifaceCount"], 1)
        self.assertEqual(result["download"], 500)
        self.assertEqual(result["upload"], 250)

    def fixture_state_home(self):
        import tempfile
        directory = Path(tempfile.mkdtemp(prefix="lme-q2-"))
        self.addCleanup(shutil.rmtree, directory, True)
        store = directory / "lme-shell/launcher.json"
        store.parent.mkdir(parents=True)
        today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).date()
        old = (today - __import__("datetime").timedelta(days=8)).isoformat()
        store.write_text(json.dumps({"schema": 1, "apps": {
            "app-a.desktop": {"last": 1000000000, "days": {today.isoformat(): 3}},
            "app-b.desktop": {"last": 1000000000, "days": {old: 1}},
        }}))
        return directory
