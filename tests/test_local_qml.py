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
