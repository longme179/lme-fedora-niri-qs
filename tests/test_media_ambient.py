"""Ambient shape lifecycle and reduced-motion checks."""
import shutil
import unittest
import test_local_qml as qml_tests
from test_backend import backend
from settings_transfer import document, validate_document


class MediaAmbientPreferenceCase(unittest.TestCase):
    def test_shapes_are_boolean_portable_and_in_appearance_profiles(self):
        self.assertIn('mediaShapes', backend.APPEARANCE_KEYS)
        values = dict(backend.DEFAULT_PREFERENCES, mediaShapes=False)
        self.assertFalse(validate_document(document(values, 'preset'), backend.validate_preference, backend.DEFAULT_PREFERENCES)['mediaShapes'])
        for value in (None, 'false', 0):
            with self.assertRaises(ValueError): backend.validate_preference('mediaShapes', value)


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is required')
class MediaAmbientCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_frames_stop_when_paused_hidden_or_motion_disabled(self):
        result = self.run_qml('import "qml/components"\nimport "qml/services"', '''
    property int phase: 0
    property real initial: 0
    property var observations: ({})
    FloatingWindow {
        id: window; implicitWidth: 500; implicitHeight: 260
        MediaAmbient { id: ambient; anchors.fill: parent; playing: true }
    }
    function firstShape(item) {
        if (item.progressX !== undefined) return item;
        for (const child of item.children || []) { const shape = firstShape(child); if (shape) return shape; }
        return null;
    }
    Timer {
        interval: 150; running: true; repeat: true
        onTriggered: {
            const shape = fixture.firstShape(ambient);
            if (fixture.phase === 0) { fixture.initial = shape.progressX; fixture.phase++; }
            else if (fixture.phase === 1) {
                fixture.observations.moving = ambient.animating && shape.progressX !== fixture.initial;
                ambient.playing = false; fixture.initial = shape.progressX; fixture.phase++;
            } else if (fixture.phase === 2) {
                fixture.observations.paused = !ambient.animating && shape.progressX === fixture.initial;
                ambient.playing = true; ambient.visible = false; fixture.phase++;
            } else if (fixture.phase === 3) {
                fixture.observations.hidden = !ambient.animating && fixture.firstShape(ambient) === null;
                ambient.visible = true;
                ShellState.snapshot = Object.assign({}, ShellState.snapshot, {preferences: Object.assign({}, ShellState.preferences, {animations: false})});
                fixture.phase++;
            } else if (fixture.phase === 4) {
                fixture.observations.reduced = !ambient.animating;
                ShellState.snapshot = Object.assign({}, ShellState.snapshot, {preferences: Object.assign({}, ShellState.preferences, {animations: true, mediaShapes: false})});
                fixture.phase++;
            } else {
                fixture.observations.disabled = !ambient.animating && fixture.firstShape(ambient) === null;
                fixture.finish(fixture.observations);
            }
        }
    }
''')
        self.assertEqual(result, dict(moving=True, paused=True, hidden=True, reduced=True, disabled=True))
