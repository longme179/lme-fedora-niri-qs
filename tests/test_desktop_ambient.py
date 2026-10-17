"""Desktop ambient preference round-trip and native motion/input lifecycle."""
import os
from pathlib import Path
import unittest
from test_backend import backend, Fixture
import test_local_qml as qml_tests
from settings_transfer import document, validate_document


class DesktopAmbientPreferenceCase(Fixture, unittest.TestCase):
    def test_disabled_by_default_validated_saved_and_portable(self):
        self.assertFalse(self.preferences.values['desktopShapes'])
        for value in (True, False):
            self.preferences.set('desktopShapes', value)
            saved = backend.Preferences(self.preferences.path).values
            self.assertIs(saved['desktopShapes'], value)
            preset = validate_document(document(saved, 'preset'), backend.validate_preference, backend.DEFAULT_PREFERENCES)
            self.assertIs(preset['desktopShapes'], value)
        for value in (None, 'true', 1, [], {}):
            with self.assertRaises(ValueError):
                self.preferences.set('desktopShapes', value)


@unittest.skipUnless(os.environ.get('LME_TEST_DESKTOP_UI') == '1', 'requires private Wayland')
class DesktopAmbientQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_browser_player_disconnect_and_reconnect_remove_and_restore_surfaces(self):
        result = self.run_qml('import Quickshell.Io\nimport "qml/panels"\nimport "qml/services"', '''
    DesktopAmbient { id: desktop }
    Process { id: player; command: ["/usr/bin/python3", Quickshell.env("LME_TEST_MPRIS_FIXTURE"), "--browser"] }
    property int phase: 0
    property int ticks: 0
    property var checks: ({})
    Timer { interval: 120; running: true; repeat: true; onTriggered: {
        if (++fixture.ticks > 80) { fixture.finish({timeout: fixture.phase, checks: fixture.checks}); return; }
        if (!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if (fixture.phase === 0) {
            ShellState.run("setting", {key:"desktopShapes", value:true}); fixture.phase++;
        } else if (fixture.phase === 1) {
            fixture.checks.noPlayer = !ActivityState.hasMedia && desktop.instances.length === 0;
            player.running = true; fixture.phase++;
        } else if (fixture.phase === 2 && ActivityState.playing && desktop.instances.length === Quickshell.screens.length) {
            fixture.checks.connected = ActivityState.player.dbusName.includes("chromium");
            ActivityState.player.pause(); fixture.phase++;
        } else if (fixture.phase === 3 && !ActivityState.playing && ActivityState.hasMedia) {
            fixture.checks.pausedRetained = desktop.instances.length === Quickshell.screens.length;
            player.running = false; fixture.phase++;
        } else if (fixture.phase === 4 && !ActivityState.hasMedia && !desktop.instances.length) {
            fixture.checks.removed = true;
            player.running = true; fixture.phase++;
        } else if (fixture.phase === 5 && ActivityState.playing && desktop.instances.length === Quickshell.screens.length) {
            fixture.checks.reconnected = true;
            player.running = false; fixture.phase++;
        } else if (fixture.phase === 6 && !player.running && !desktop.instances.length) fixture.finish(fixture.checks);
    } }
''', {'QT_QPA_PLATFORM': 'wayland', 'LME_SHELL_DEMO': '0', 'LME_SHELL_BACKEND_DEMO': '1',
      'LME_TEST_MPRIS_FIXTURE': str(Path(__file__).with_name('mpris_fixture.py').resolve())})
        self.assertEqual(result, dict(noPlayer=True, connected=True, pausedRetained=True, removed=True, reconnected=True))

    def test_native_surfaces_move_pause_ignore_input_and_release(self):
        result = self.run_qml('import Quickshell.Wayland\nimport "qml/panels"\nimport "qml/services"', '''
    DesktopAmbient { id: desktop }
    property int phase: 0
    property int ticks: 0
    property real position: 0
    property var checks: ({})
    function surfaces() {
        return desktop.instances;
    }
    function find(item, property) {
        if (item[property] !== undefined) return item;
        for (const child of item.children || []) { const found = find(child, property); if (found) return found; }
        return null;
    }
    Timer { interval: 150; running: true; repeat: true; onTriggered: {
        if (++fixture.ticks > 65) { fixture.finish({timeout: fixture.phase, checks: fixture.checks}); return; }
        if (!ShellState.backendReady || ShellState.pendingActions.setting) return;
        const windows = fixture.surfaces();
        if (fixture.phase === 0) {
            fixture.checks.defaultOff = windows.length === 0;
            ShellState.run("setting", {key:"desktopShapes", value:true}); fixture.phase++;
        } else if (fixture.phase === 1 && windows.length === Quickshell.screens.length) {
            const window = windows[0];
            fixture.checks.outputs = windows.every(w => w.screen && w.width === w.screen.width && w.height === w.screen.height);
            fixture.checks.below = windows.every(w => w.WlrLayershell.layer === WlrLayer.Bottom);
            fixture.checks.clickthrough = windows.every(w => w.mask.item === null && w.mask.width === 0 && w.mask.height === 0);
            fixture.checks.noFocusOrSpace = windows.every(w => w.WlrLayershell.keyboardFocus === WlrKeyboardFocus.None && w.exclusiveZone === 0);
            fixture.checks.independentWidgets = !ShellState.preferences.desktopEnabled;
            fixture.position = fixture.find(window.contentItem, "progressX").progressX;
            fixture.phase++;
        } else if (fixture.phase === 2) {
            const ambient = fixture.find(windows[0].contentItem, "animating");
            const shape = fixture.find(ambient, "progressX");
            fixture.checks.moving = ambient.animating && shape.progressX !== fixture.position && shape.width >= 48;
            ActivityState.demoPlaying = false; fixture.position = shape.progressX; fixture.phase++;
        } else if (fixture.phase === 3) {
            const ambient = fixture.find(windows[0].contentItem, "animating");
            fixture.checks.paused = !ambient.animating && fixture.find(ambient, "progressX").progressX === fixture.position;
            ActivityState.demoPlaying = true;
            ShellState.run("setting", {key:"mediaShapes", value:false}); fixture.phase++;
        } else if (fixture.phase === 4) {
            fixture.checks.independentCards = fixture.find(windows[0].contentItem, "animating").animating;
            ShellState.run("setting", {key:"animations", value:false}); fixture.phase++;
        } else if (fixture.phase === 5) {
            fixture.checks.reduced = !fixture.find(windows[0].contentItem, "animating").animating;
            ShellState.run("setting", {key:"desktopShapes", value:false}); fixture.phase++;
        } else if (fixture.phase === 6 && !windows.length) {
            fixture.checks.released = true;
            ShellState.run("setting", {key:"desktopShapes", value:true}); fixture.phase++;
        } else if (fixture.phase === 7 && windows.length === Quickshell.screens.length) {
            fixture.checks.restoredStill = !fixture.find(windows[0].contentItem, "animating").animating;
            fixture.finish(fixture.checks);
        }
    } }
''', {'QT_QPA_PLATFORM': 'wayland'})
        self.assertEqual(result, dict(defaultOff=True, outputs=True, below=True, clickthrough=True,
                                     noFocusOrSpace=True, independentWidgets=True, moving=True, paused=True,
                                     independentCards=True, reduced=True, released=True, restoredStill=True))
