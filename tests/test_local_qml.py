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
