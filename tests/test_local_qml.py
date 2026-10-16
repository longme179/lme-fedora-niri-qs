"""Local QML regressions, using Quickshell without a desktop session."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class LocalQmlCase(unittest.TestCase):
    def run_qml(self, imports, body):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("qml", "scripts", "config", "assets"):
                (root / name).symlink_to(repo / name, target_is_directory=True)
            entry = root / "shell.qml"
            entry.write_text('''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import Quickshell
''' + imports + '''
ShellRoot {
    id: fixture
    function finish(value) {
        console.log("LOCAL_QML_RESULT " + JSON.stringify(value));
        Qt.quit();
    }
''' + body + '\n}')
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", LME_SHELL_DEMO="1",
                       XDG_CONFIG_HOME=str(root / "home"), XDG_STATE_HOME=str(root / "state"),
                       XDG_DATA_HOME=str(root / "data"), DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(root / "no-system-bus"))
            try:
                result = subprocess.run(["quickshell", "-p", str(entry)], env=env, capture_output=True, text=True, timeout=15)
            except subprocess.TimeoutExpired as error:
                self.fail(f"QML fixture timed out: {error.stdout!r}\n{error.stderr!r}")
            log = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, log)
            self.assertNotIn("TypeError", log)
            self.assertNotIn("ReferenceError", log)
            lines = [line.split("LOCAL_QML_RESULT ", 1)[1] for line in log.splitlines() if "LOCAL_QML_RESULT " in line]
            self.assertEqual(len(lines), 1, log)
            return json.loads(lines[0])

    def test_empty_clipboard_navigation_and_filtered_recovery(self):
        result = self.run_qml('import "qml/panels"\nimport "qml/services"', '''
    FloatingWindow {
        visible: false; implicitWidth: 620; implicitHeight: 710
        ClipboardPanel { id: panel; anchors.fill: parent }
    }
    Component.onCompleted: Qt.callLater(() => {
        const original = ClipboardState.demoEntries;
        const states = [];
        ClipboardState.demoEntries = [];
        for (const delta of [1, -1]) {
            panel.moveSelection(delta);
            panel.activateSelected();
            states.push(panel.selectedId);
        }
        ClipboardState.demoEntries = original;
        panel.moveSelection(1);
        const selected = panel.selectedId;
        ClipboardState.search("no-such-clipboard-entry", "all");
        for (const delta of [-1, 1]) {
            panel.moveSelection(delta);
            panel.activateSelected();
            states.push(panel.selectedId);
        }
        ClipboardState.search("", "all");
        panel.moveSelection(1);
        const recovered = panel.selectedId;
        panel.moveSelection(100);
        const last = panel.selectedId;
        panel.moveSelection(-100);
        fixture.finish({states, selected, recovered, last, first: panel.selectedId,
            expectedLast: original[original.length - 1].id, expectedFirst: original[0].id});
    })
''')
        self.assertEqual(result["states"], ["", "", "", ""])
        self.assertTrue(result["selected"])
        self.assertTrue(result["recovered"])
        self.assertEqual(result["last"], result["expectedLast"])
        self.assertEqual(result["first"], result["expectedFirst"])

    def test_minute_clocks_keep_formats_and_follow_visibility(self):
        result = self.run_qml('import "qml/bar"\nimport "qml/panels"', '''
    FloatingWindow {
        implicitWidth: 900; implicitHeight: 760
        BarModule { id: bar; moduleId: "clock" }
        ControlDashboard { id: dashboard; y: 40; width: 880; height: 700 }
    }
    function clockOf(item) { return item.resources.find(o => o.precision !== undefined && o.date !== undefined); }
    Component.onCompleted: Qt.callLater(() => {
        const barClock = clockOf(bar.item), panelClock = clockOf(dashboard);
        const full = bar.item.caption;
        const expected = Qt.locale("en_US").toString(new Date(), "ddd, MMM d  ·  HH:mm");
        const precision = [barClock.precision, panelClock.precision];
        const initial = [barClock.enabled, panelClock.enabled];
        bar.compact = true;
        const compact = bar.item.caption;
        const expectedCompact = Qt.locale("en_US").toString(new Date(), "HH:mm");
        bar.moduleId = "audio"; dashboard.visible = false;
        const disabled = [clockOf(bar.item).enabled, panelClock.enabled];
        bar.moduleId = "clock"; dashboard.visible = true;
        fixture.finish({full, expected, compact, expectedCompact, precision, minute: SystemClock.Minutes,
            initial, disabled, resumed: [clockOf(bar.item).enabled, panelClock.enabled],
            panelDate: Qt.formatDateTime(dashboard.now, "yyyy-MM-dd hh:mm"),
            expectedDate: Qt.formatDateTime(new Date(), "yyyy-MM-dd hh:mm")});
    })
''')
        self.assertEqual(result["precision"], [result["minute"]] * 2)
        self.assertEqual(result["full"], result["expected"])
        self.assertEqual(result["compact"], result["expectedCompact"])
        self.assertEqual(result["panelDate"], result["expectedDate"])
        self.assertEqual(result["initial"], [True, True])
        self.assertEqual(result["disabled"], [False, False])
        self.assertEqual(result["resumed"], [True, True])

    def test_local_notification_expiry_changes_history_only_when_due(self):
        result = self.run_qml('import "qml/services"', '''
    property int changes: 0
    property int stage: 0
    property var original: null
    property var observations: ({})
    Connections { target: Notifications; function onHistoryChanged() { fixture.changes++; } }
    Component.onCompleted: Qt.callLater(() => {
        Notifications.historyLoaded = true;
        Notifications.history = [
            {id: "old", local: true, active: false, popup: false, timestamp: Date.now() - 10000},
            {id: "fresh", local: true, active: true, popup: true, timestamp: Date.now(), actions: [{text: "Keep"}]},
            {id: "native", local: false, active: true, popup: true, timestamp: Date.now() - 10000}
        ];
        fixture.original = Notifications.history;
        fixture.changes = 0;
        check.start();
    })
    Timer {
        id: check; interval: 1200; repeat: true
        onTriggered: {
            fixture.stage++;
            if (fixture.stage === 1) {
                fixture.observations.unchanged = Notifications.history === fixture.original && fixture.changes === 0;
                Notifications.history[1].timestamp = Date.now() - 8000;
            } else if (fixture.stage === 2) {
                fixture.observations.expired = !Notifications.history[1].active && !Notifications.history[1].popup;
                fixture.observations.actions = Notifications.history[1].actions;
                fixture.observations.nativeActive = Notifications.history[2].active && Notifications.history[2].popup;
                fixture.observations.oldUntouched = Notifications.history[0] === fixture.original[0];
                fixture.original = Notifications.history;
            } else {
                fixture.observations.changes = fixture.changes;
                fixture.observations.stopped = Notifications.history === fixture.original;
                fixture.finish(fixture.observations);
            }
        }
    }
''')
        self.assertTrue(result["unchanged"], result)
        self.assertTrue(result["expired"], result)
        self.assertEqual(result["changes"], 1)
        self.assertTrue(result["nativeActive"])
        self.assertTrue(result["oldUntouched"])
        self.assertTrue(result["stopped"])
        self.assertEqual(result["actions"], [{"text": "Keep"}])

    def test_process_filter_sort_and_source_order_are_preserved(self):
        result = self.run_qml('import "qml/panels"\nimport "qml/services"', '''
    FloatingWindow {
        visible: false; implicitWidth: 700; implicitHeight: 800
        SystemMonitor { id: monitor; anchors.fill: parent }
    }
    function ids() { return monitor.processes.map(p => p.pid); }
    Component.onCompleted: Qt.callLater(() => {
        const source = [
            {pid: 30, name: "Zeta", user: "roo", cpu: 1, memoryBytes: 20},
            {pid: 20, name: "Alpha", user: "ada", cpu: 5, memoryBytes: 10},
            {pid: 10, name: "Beta", user: "ada", cpu: 5, memoryBytes: 30},
            {pid: 40, name: "Delta", user: "roo", cpu: 0, memoryBytes: 40}
        ];
        ShellState.snapshot = Object.assign({}, ShellState.snapshot, {monitor: {processes: source}});
        const cpu = ids();
        monitor.order = 1; const memory = ids();
        monitor.order = 2; const name = ids();
        monitor.query = "ALP"; const app = ids();
        monitor.query = "10"; const pid = ids();
        monitor.query = "ROO"; const user = ids();
        monitor.query = "absent"; const empty = ids();
        monitor.query = ""; monitor.order = 0;
        fixture.finish({cpu, memory, name, app, pid, user, empty, recovered: ids(), source: source.map(p => p.pid)});
    })
''')
        self.assertEqual(result, {"cpu": [10, 20, 30, 40], "memory": [40, 10, 30, 20],
                                  "name": [20, 10, 40, 30], "app": [20], "pid": [10], "user": [40, 30],
                                  "empty": [], "recovered": [10, 20, 30, 40], "source": [30, 20, 10, 40]})
