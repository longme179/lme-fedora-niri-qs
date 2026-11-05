"""Snapshot identity reuse by backend revisions and the stringify fallback."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class SnapshotIdentityCase(unittest.TestCase):
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
        console.log("SNAPSHOT_RESULT " + JSON.stringify(value));
        Qt.quit();
    }
''' + body + '''
}''')
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QT_LOGGING_RULES="qml.debug=true",
                       LME_SHELL_DEMO="1", XDG_CONFIG_HOME=str(root / "home"), XDG_STATE_HOME=str(root / "state"),
                       XDG_DATA_HOME=str(root / "data"), DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(root / "no-system-bus"))
            try:
                result = subprocess.run(["quickshell", "-p", str(entry)], env=env, capture_output=True, text=True, timeout=15)
            except subprocess.TimeoutExpired as error:
                self.fail(f"QML fixture timed out: {error.stdout!r}\n{error.stderr!r}")
            log = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, log)
            self.assertNotIn("TypeError", log)
            self.assertNotIn("ReferenceError", log)
            lines = [line.split("SNAPSHOT_RESULT ", 1)[1] for line in log.splitlines() if "SNAPSHOT_RESULT " in line]
            self.assertEqual(len(lines), 1, log)
            return json.loads(lines[0])

    def test_keep_uses_revisions_then_stringify_and_drag_pin(self):
        result = self.run_qml('import "qml/services/SnapshotIdentity.js" as Identity', '''
    Component.onCompleted: Qt.callLater(() => {
        const old = {revisions: {apps: 1, niri: 1, preferences: 1, launcherUsage: 1}};
        fixture.finish({
            same: Identity.keep({revisions: {apps: 1, niri: 1, preferences: 1, launcherUsage: 1}}, old, "niri", {}, false),
            changed: Identity.keep({revisions: {apps: 2, niri: 2, preferences: 2, launcherUsage: 2}}, old, "niri", {}, false),
            dragging: Identity.keep({revisions: {apps: 2, niri: 2, preferences: 2, launcherUsage: 2}}, old, "niri", {}, true),
            fallbackSame: Identity.keep({niri: {a: 1}}, old, "niri", {a: 1}, false),
            fallbackChanged: Identity.keep({niri: {a: 2}}, old, "niri", {a: 1}, false),
            launcherMissing: Identity.keep({}, old, "launcherUsage", {}, false)
        });
    });
''')
        self.assertEqual(result, {"same": True, "changed": False, "dragging": True,
                                  "fallbackSame": True, "fallbackChanged": False, "launcherMissing": True})

    def test_shell_state_keeps_identity_by_revision_and_during_drag(self):
        result = self.run_qml('import "qml/services"', '''
    Component.onCompleted: Qt.callLater(() => {
        ShellState.backend.running = false;
        const base = {apps: [{id: "a"}], system: {}, niri: {available: true, workspaces: [], windows: []},
            preferences: {language: "en"}, launcherUsage: {a: 1}, actionPending: {},
            revisions: {apps: 1, niri: 1, preferences: 1, launcherUsage: 1}};
        ShellState.accept(JSON.stringify(base));
        const niri = ShellState.niri, apps = ShellState.apps, preferences = ShellState.preferences, usage = ShellState.launcherUsage;
        ShellState.accept(JSON.stringify(base));
        const same = ShellState.niri === niri && ShellState.apps === apps
            && ShellState.preferences === preferences && ShellState.launcherUsage === usage;
        ShellState.accept(JSON.stringify(Object.assign({}, base,
            {revisions: {apps: 2, niri: 2, preferences: 2, launcherUsage: 2}})));
        const changed = ShellState.niri !== niri && ShellState.apps !== apps
            && ShellState.preferences !== preferences && ShellState.launcherUsage !== usage;
        const pinned = ShellState.niri;
        ShellState.draggingWindow = true;
        ShellState.accept(JSON.stringify(Object.assign({}, base, {niri: {available: true, workspaces: [{id: 2}], windows: []},
            revisions: {apps: 2, niri: 3, preferences: 2, launcherUsage: 2}})));
        fixture.finish({same, changed, dragging: ShellState.niri === pinned});
    });
''')
        self.assertEqual(result, {"same": True, "changed": True, "dragging": True})
