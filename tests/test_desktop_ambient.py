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

    def test_visual_options_are_bounded_persistent_and_portable(self):
        options = {'desktopShapeCount': 12, 'desktopShapeScale': 2, 'desktopShapeOpacity': .6,
                   'desktopShapeSpeed': 3, 'desktopShapeStyle': 'flower', 'desktopShapeRotation': False}
        self.preferences.update(options)
        saved = backend.Preferences(self.preferences.path).values
        preset = validate_document(document(saved, 'preset'), backend.validate_preference, backend.DEFAULT_PREFERENCES)
        self.assertEqual({key: saved[key] for key in options}, options)
        self.assertEqual({key: preset[key] for key in options}, options)
        for key, low in [('desktopShapeCount', 1), ('desktopShapeScale', .5),
                         ('desktopShapeOpacity', .02), ('desktopShapeSpeed', .1)]:
            self.assertEqual(backend.validate_preference(key, low), low)
        invalid = {'desktopShapeCount': [0, 13, 4.0, True, '4'],
                   'desktopShapeScale': [.49, 2.01, float('inf'), True, '1'],
                   'desktopShapeOpacity': [.01, .61, float('nan'), False],
                   'desktopShapeSpeed': [0, 3.01, float('inf'), True],
                   'desktopShapeStyle': ['triangle', '', None, []],
                   'desktopShapeRotation': [0, 1, 'false', None]}
        for key, values in invalid.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.preferences.set(key, value)


@unittest.skipUnless(os.environ.get('LME_TEST_DESKTOP_UI') == '1', 'requires private Wayland')
class DesktopAmbientQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_visual_controls_update_live_shapes_without_replacing_the_surface(self):
        result = self.run_qml('import QtTest\nimport "qml/settings"\nimport "qml/panels"\nimport "qml/services"', '''
    DesktopAmbient { id: desktop }
    FloatingWindow {
        implicitWidth: 900; implicitHeight: 1050
        DesktopPage { id: page; anchors { top: parent.top; left: parent.left; right: parent.right; margins: 16 } }
        TestCase { id: pointer; when: false }
    }
    property int phase: 0
    property int ticks: 0
    property var original: null
    property real angle: 0
    property real position: 0
    property var checks: ({})
    function shapes(item) {
        if (item.progressX !== undefined) return [item];
        const found = [];
        for (const child of item.children || []) found.push(...shapes(child));
        return found;
    }
    function change(key) {
        const slider = pointer.findChild(page, key);
        pointer.mouseClick(slider, slider.width - 1, slider.height / 2);
    }
    Timer { interval: 150; running: true; repeat: true; onTriggered: {
        if (++fixture.ticks > 65) { fixture.finish({timeout: fixture.phase, checks: fixture.checks, count: ShellState.preferences.desktopShapeCount, slider: pointer.findChild(page, "desktopShapeCount").value, result: ShellState.lastResult}); return; }
        if (!ShellState.backendReady || ShellState.pendingActions.setting) return;
        const ambient = desktop.instances.length ? desktop.instances[0].contentItem.children[0] : null;
        if (fixture.phase === 0) {
            fixture.checks.disabledControls = !pointer.findChild(page, "desktopShapeScale").enabled;
            ShellState.run("setting", {key:"desktopShapes", value:true}); fixture.phase++;
        } else if (fixture.phase === 1 && ambient) {
            fixture.original = desktop.instances[0];
            fixture.change("desktopShapeCount"); fixture.phase++;
        } else if (fixture.phase === 2 && ShellState.preferences.desktopShapeCount === 12) {
            fixture.change("desktopShapeScale"); fixture.phase++;
        } else if (fixture.phase === 3 && ShellState.preferences.desktopShapeScale === 2) {
            fixture.change("desktopShapeOpacity"); fixture.phase++;
        } else if (fixture.phase === 4 && ShellState.preferences.desktopShapeOpacity === .6) {
            fixture.change("desktopShapeSpeed"); fixture.phase++;
        } else if (fixture.phase === 5 && ShellState.preferences.desktopShapeSpeed === 3) {
            const style = pointer.findChild(page, "desktopShapeStyle");
            pointer.mouseClick(style, style.width / 2, style.height / 2);
            pointer.keyClick(Qt.Key_End); pointer.keyClick(Qt.Key_Return); fixture.phase++;
        } else if (fixture.phase === 6 && ShellState.preferences.desktopShapeStyle === "square") {
            ShellState.run("setting", {key:"desktopShapeRotation", value:false}); fixture.phase++;
        } else if (fixture.phase === 7 && ShellState.preferences.desktopShapeRotation === false) {
            const shapes = fixture.shapes(ambient);
            fixture.checks.count = shapes.length === 12;
            fixture.checks.style = shapes.every(s => s.shape === "square");
            fixture.checks.opacity = shapes.every(s => s.opacity === .6);
            fixture.checks.size = shapes.every(s => s.width === (48 + s.index % 4 * 14) * ambient.shapeScale);
            fixture.checks.speed = ambient.motionSpeed === 3;
            fixture.angle = shapes[0].rotation; fixture.position = shapes[0].progressX; fixture.phase++;
        } else if (fixture.phase === 8) {
            const shape = fixture.shapes(ambient)[0];
            fixture.checks.noSpin = shape.rotation === fixture.angle;
            fixture.checks.stillDrifting = shape.progressX !== fixture.position;
            fixture.checks.sameSurface = desktop.instances[0] === fixture.original;
            ShellState.run("setting", {key:"desktopShapeCount", value:1}); fixture.phase++;
        } else if (fixture.phase === 9 && ShellState.preferences.desktopShapeCount === 1) {
            fixture.checks.shrank = fixture.shapes(ambient).length === 1;
            fixture.finish(fixture.checks);
        }
    } }
''', {'QT_QPA_PLATFORM': 'wayland'})
        self.assertEqual(result, dict(disabledControls=True, count=True, style=True, opacity=True,
                                     size=True, speed=True, noSpin=True, stillDrifting=True, sameSurface=True, shrank=True))

    def test_shapes_keep_moving_without_media_during_pause_and_player_reconnect(self):
        result = self.run_qml('import Quickshell.Io\nimport "qml/panels"\nimport "qml/services"', '''
    DesktopAmbient { id: desktop }
    Process { id: player; command: ["/usr/bin/python3", Quickshell.env("LME_TEST_MPRIS_FIXTURE"), "--browser"] }
    property int phase: 0
    property int ticks: 0
    property var checks: ({})
    property var original: null
    property real position: 0
    function find(item, property) {
        if (item[property] !== undefined) return item;
        for (const child of item.children || []) { const found = find(child, property); if (found) return found; }
        return null;
    }
    Timer { interval: 120; running: true; repeat: true; onTriggered: {
        if (++fixture.ticks > 80) { fixture.finish({timeout: fixture.phase, checks: fixture.checks}); return; }
        if (!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if (fixture.phase === 0) {
            ShellState.run("setting", {key:"desktopShapes", value:true}); fixture.phase++;
        } else if (fixture.phase === 1 && desktop.instances.length === Quickshell.screens.length) {
            fixture.original = desktop.instances[0];
            fixture.position = fixture.find(fixture.original.contentItem, "progressX").progressX;
            fixture.checks.noPlayer = !ActivityState.hasMedia && fixture.find(fixture.original.contentItem, "animating").animating;
            player.running = true; fixture.phase++;
        } else if (fixture.phase === 2 && ActivityState.playing && desktop.instances.length === Quickshell.screens.length) {
            fixture.checks.connected = ActivityState.player.dbusName.includes("chromium") && fixture.find(fixture.original.contentItem, "progressX").progressX !== fixture.position;
            ActivityState.player.pause(); fixture.phase++;
        } else if (fixture.phase === 3 && !ActivityState.playing && ActivityState.hasMedia) {
            fixture.checks.pausedMoving = fixture.find(fixture.original.contentItem, "animating").animating;
            fixture.position = fixture.find(fixture.original.contentItem, "progressX").progressX;
            player.running = false; fixture.phase++;
        } else if (fixture.phase === 4 && !ActivityState.hasMedia) {
            fixture.checks.disconnectedMoving = desktop.instances[0] === fixture.original && fixture.find(fixture.original.contentItem, "animating").animating && fixture.find(fixture.original.contentItem, "progressX").progressX !== fixture.position;
            player.running = true; fixture.phase++;
        } else if (fixture.phase === 5 && ActivityState.playing && desktop.instances.length === Quickshell.screens.length) {
            fixture.checks.reconnected = desktop.instances[0] === fixture.original;
            player.running = false; fixture.phase++;
        } else if (fixture.phase === 6 && !player.running && !ActivityState.hasMedia) fixture.finish(fixture.checks);
    } }
''', {'QT_QPA_PLATFORM': 'wayland', 'LME_SHELL_DEMO': '0', 'LME_SHELL_BACKEND_DEMO': '1',
      'LME_TEST_MPRIS_FIXTURE': str(Path(__file__).with_name('mpris_fixture.py').resolve())})
        self.assertEqual(result, dict(noPlayer=True, connected=True, pausedMoving=True, disconnectedMoving=True, reconnected=True))

    def test_native_surfaces_ignore_playback_respect_reduced_motion_and_release(self):
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
            fixture.checks.independentPlayback = ambient.animating && fixture.find(ambient, "progressX").progressX !== fixture.position;
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
                                     noFocusOrSpace=True, independentWidgets=True, moving=True, independentPlayback=True,
                                     independentCards=True, reduced=True, released=True, restoredStill=True))
