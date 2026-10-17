"""Validated, portable module gestures and their QML dispatch."""
import shutil
import unittest
from test_backend import backend, Fixture, FakeRunner
import test_local_qml as qml_tests
from settings_transfer import document, validate_document


class BarGestureCase(Fixture, unittest.TestCase):
    def test_bindings_are_validated_isolated_persistent_and_portable(self):
        mapping = {'audio': {'left': 'audio', 'right': 'mute', 'scrollUp': 'volumeUp'},
                   'notifications': {'right': 'dnd'}, 'workspaces': {'scrollDown': 'none'}}
        self.preferences.set('barGestures', mapping)
        mapping['audio']['right'] = 'none'
        saved = backend.Preferences(self.preferences.path).values
        self.assertEqual(saved['barGestures']['audio']['right'], 'mute')
        portable = validate_document(document(saved, 'preset'), backend.validate_preference, backend.DEFAULT_PREFERENCES)
        self.assertEqual(portable['barGestures'], saved['barGestures'])
        for bad in [None, [], {'unknown': {}}, {'audio': []}, {'audio': {'double': 'mute'}},
                    {'audio': {'right': []}}, {'audio': {'right': 'sh -c anything'}}]:
            with self.subTest(value=bad), self.assertRaises(ValueError): backend.validate_preference('barGestures', bad)

    def test_relative_volume_uses_wpctl_relative_updates_and_validates_delta(self):
        runner = FakeRunner(available=["wpctl"]); live = self.make_backend(runner)
        for delta in [5, 10, -5]:
            self.assertTrue(live.handle({'action': 'volume', 'delta': delta})['ok'])
            self.assertIn(('wpctl', 'set-volume', '--limit', '1.0', '@DEFAULT_AUDIO_SINK@', f"{abs(delta)}%{'+' if delta >= 0 else '-'}"), runner.calls)
        for delta in [True, '5', [], float('nan'), -101, 101]:
            with self.subTest(delta=delta): self.assertFalse(live.handle({'action': 'volume', 'delta': delta})['ok'])


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is required')
class BarGestureQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_defaults_overrides_none_and_primary_fallback(self):
        result = self.run_qml('import "qml/bar"\nimport "qml/services"', '''
    FloatingWindow {
        visible: false; implicitWidth: 800; implicitHeight: 40
        BarModule { id: module; moduleId: "audio" }
    }
    Component.onCompleted: Qt.callLater(() => {
        const defaults = [BarGestures.action("audio", "right"), BarGestures.action("audio", "scrollUp"),
            BarGestures.action("notifications", "right"), BarGestures.action("workspaces", "scrollDown"),
            BarGestures.action("clock", "left"), BarGestures.action("clock", "scrollUp")];
        const fallback = BarGestures.perform("audio", "left", null);
        ShellState.snapshot = Object.assign({}, ShellState.snapshot, {preferences: Object.assign({}, ShellState.preferences,
            {barGestures: {audio: {left: "none", right: "activity", scrollUp: "none"}}})});
        const selected = [BarGestures.action("audio", "left"), BarGestures.action("audio", "right"), BarGestures.action("audio", "scrollUp")];
        const suppressed = BarGestures.perform("audio", "left", null);
        BarGestures.perform("audio", "right", null);
        fixture.finish({defaults, fallback, selected, suppressed, activity: ShellState.activityOpen, loaded: !!module.item});
    })
''')
        self.assertEqual(result, dict(defaults=['mute', 'volumeUp', 'dnd', 'workspaceNext', 'default', 'none'],
                                     fallback=False, selected=['none', 'activity', 'none'], suppressed=True, activity=True, loaded=True))

    def test_real_mouse_buttons_and_wheel_do_not_trigger_primary_action(self):
        result = self.run_qml('import QtTest\nimport "qml/bar"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property var observations: ({})
    FloatingWindow {
        implicitWidth: 700; implicitHeight: 200
        Row {
            BarModule { id: audio; moduleId: "audio" }
            BarModule { id: notifications; moduleId: "notifications" }
        }
    }
    TestCase { id: pointer; when: false }
    Timer {
        interval: 80; repeat: true; running: true
        onTriggered: {
            if (++fixture.ticks > 100) { fixture.finish({timeout: fixture.phase, observations: fixture.observations}); return; }
            if (!ShellState.backendReady || Object.keys(ShellState.pendingActions).some(k => ShellState.pendingActions[k])) return;
            if (fixture.phase === 0) {
                fixture.observations.volume = ShellState.system.audio.volume;
                pointer.mouseClick(audio.item, 10, 15, Qt.RightButton);
                fixture.phase++;
            } else if (fixture.phase === 1 && ShellState.system.audio.muted) {
                fixture.observations.secondaryOnly = !ShellState.controlOpen;
                pointer.mouseWheel(audio.item, 10, 15, 0, 240);
                fixture.phase++;
            } else if (fixture.phase === 2 && ShellState.system.audio.volume === fixture.observations.volume + 10) {
                fixture.observations.wheel = true;
                pointer.mouseClick(notifications.item, 15, 15, Qt.RightButton);
                fixture.phase++;
            } else if (fixture.phase === 3 && Notifications.dnd) {
                fixture.observations.dnd = !ShellState.notificationsOpen;
                pointer.mouseClick(audio.item, 10, 15, Qt.LeftButton);
                fixture.phase++;
            } else if (fixture.phase === 4 && ShellState.controlOpen) {
                fixture.observations.primary = true;
                pointer.mouseClick(audio.item, 10, 15, Qt.MiddleButton);
                fixture.phase++;
            } else if (fixture.phase === 5 && ShellState.settingsOpen) {
                fixture.observations.middle = true;
                ShellState.run("setting", {key: "barGestures", value: {audio: {left: "none"}}});
                fixture.phase++;
            } else if (fixture.phase === 6 && ShellState.preferences.barGestures.audio?.left === "none") {
                ShellState.closePanels(); pointer.mouseClick(audio.item, 10, 15, Qt.LeftButton); fixture.phase++;
            } else if (fixture.phase === 7) {
                fixture.observations.disabledLeft = !ShellState.controlOpen;
                fixture.finish(fixture.observations);
            }
        }
    }
''')
        self.assertEqual(result, dict(volume=42, secondaryOnly=True, wheel=True, dnd=True, primary=True, middle=True, disabledLeft=True))
