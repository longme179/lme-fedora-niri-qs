"""Theme load guards and OSD output fallback without a desktop session.
Contract: test_theme_osd_guards.py covers theme_osd_guards behavior/contracts; check imports for fixtures/helpers under test.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class ThemeOsdGuardCase(unittest.TestCase):
    def run_qml(self, imports, body, prepare=None):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("qml", "scripts", "assets"):
                (root / name).symlink_to(repo / name, target_is_directory=True)
            shutil.copytree(repo / "config", root / "config")
            if prepare: prepare(root)
            entry = root / "shell.qml"
            entry.write_text('''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import Quickshell
''' + imports + '''
ShellRoot {
    id: fixture
    function finish(value) {
        console.log("THEME_OSD_RESULT " + JSON.stringify(value));
        Qt.quit();
    }
''' + body + '''
    Timer {
        interval: 2000; running: true; repeat: true
        onTriggered: console.log("THEME_OSD_HEALTH " + JSON.stringify({ticks:fixture.ticks}))
    }
}''')
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QT_LOGGING_RULES="qml.debug=true", LME_SHELL_DEMO="1",
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
            self.assertNotIn("Unable to assign", log)
            lines = [line.split("THEME_OSD_RESULT ", 1)[1] for line in log.splitlines() if "THEME_OSD_RESULT " in line]
            self.assertEqual(len(lines), 1, log)
            return json.loads(lines[0])

    def test_theme_guards_keep_defaults_and_report_diagnostics(self):
        def prepare(root):
            (root / "config/liquid-glass.json").write_text('{"tint": 3}')
            (root / "config/palettes.json").write_text('{"palettes": "bad", "schemes": {}}')
            (root / "config/theme-tokens.json").write_text('{"colors": "bad", "fonts": "bad"}')

        result = self.run_qml('import "qml/theme"\nimport "qml/services"', '''
    property int ticks: 0
    Timer {
        interval: 50; running: true; repeat: true
        onTriggered: {
            if (++fixture.ticks > 80) { fixture.finish({timeout: true, ready: Theme.ready, diagnostics: Theme.themeDiagnosticsText}); return; }
            if (!Theme.ready) return;
            fixture.finish({ready: Theme.ready, palettes: Array.isArray(Theme.paletteCatalog), schemes: Array.isArray(Theme.paletteSchemes),
                preset: JSON.stringify(Theme.activePreset), glass: Object.keys(Theme.glassControls).length,
                catalog: Array.isArray(Theme.catalog.colors) && Array.isArray(Theme.catalog.fonts), diagnostics: Theme.themeDiagnosticsText});
        }
    }
''', prepare)
        self.assertNotIn("timeout", result)
        self.assertTrue(result["ready"])
        self.assertTrue(result["palettes"])
        self.assertTrue(result["schemes"])
        self.assertEqual(result["preset"], "{}")
        self.assertEqual(result["glass"], 0)
        self.assertTrue(result["catalog"])
        for message in ("Glass controls", "Palette catalog", "Theme catalog"):
            self.assertIn(message, result["diagnostics"])

    def test_osd_output_fallback_prefers_focused_then_first_screen(self):
        result = self.run_qml('import "qml/services"', '''
    Component.onCompleted: Qt.callLater(() => fixture.finish({
        missing: OSDManager.outputName("HDMI-A-1", [{name:"eDP-1"},{name:"DP-1"}], {output:"DP-1"}, {name:"eDP-1"}),
        focusedFallback: OSDManager.outputName("focused", [{name:"eDP-1"},{name:"DP-1"}], {output:"HDMI-A-1"}, {name:"eDP-1"}),
        panelFallback: OSDManager.outputName("HDMI-A-1", [{name:"eDP-1"}], {}, {name:"eDP-1"}),
        first: OSDManager.outputName("HDMI-A-1", [{name:"DP-1"}], {}, {}),
        all: OSDManager.outputName("all", [{name:"eDP-1"}], {}, {}),
        emptyAll: OSDManager.outputName("all", [], {}, {}),
        valid: OSDManager.outputName("DP-1", [{name:"eDP-1"},{name:"DP-1"}], {output:"eDP-1"}, {})
    }));
''')
        self.assertEqual(result, {"missing": "DP-1", "focusedFallback": "eDP-1", "panelFallback": "eDP-1",
                                  "first": "DP-1", "all": "all", "emptyAll": "", "valid": "DP-1"})
