"""Bounded metadata retention without stale player capabilities."""
import shutil
import unittest
import test_local_qml as qml_tests
from test_backend import backend
from settings_transfer import document, validate_document


class MediaStabilityPreferenceCase(unittest.TestCase):
    def test_toggle_is_boolean_and_portable(self):
        values = dict(backend.DEFAULT_PREFERENCES, mediaStability=False)
        self.assertFalse(validate_document(document(values, 'preset'), backend.validate_preference, backend.DEFAULT_PREFERENCES)['mediaStability'])
        for value in (None, 'false', 0):
            with self.assertRaises(ValueError): backend.validate_preference('mediaStability', value)


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is required')
class MediaPresentationCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_partial_metadata_grace_loss_switch_and_disabled_mode(self):
        result = self.run_qml('import "qml/components"', '''
    property var source: first
    property int phase: 0
    property var observations: ({})
    QtObject { id: first; property string dbusName: "one"; property string identity: "First player";
        property string trackTitle: "First track"; property string trackArtist: "First artist"; property string trackArtUrl: "first.png" }
    QtObject { id: second; property string dbusName: "two"; property string identity: "Second player";
        property string trackTitle: "Other track"; property string trackArtist: "Other artist"; property string trackArtUrl: "" }
    MediaPresentation { id: presentation; player: fixture.source }
    Timer {
        interval: 80; running: true; repeat: true
        onTriggered: {
            if (fixture.phase === 0) {
                first.trackTitle = ""; first.trackArtist = ""; first.trackArtUrl = "";
                fixture.observations.retained = presentation.current.title === "First track" && presentation.current.artUrl === "first.png";
                fixture.phase++;
            } else if (fixture.phase === 1) {
                first.trackTitle = "Next track"; first.trackArtist = "Next artist";
                fixture.observations.coherent = presentation.current.title === "First track";
                first.trackArtUrl = "next.png";
                fixture.observations.complete = presentation.current.title === "Next track" && presentation.current.artUrl === "next.png" && !presentation.settling;
                first.trackArtUrl = ""; fixture.phase++;
            } else if (fixture.phase === 2 && !presentation.settling) {
                fixture.observations.expired = presentation.current.artUrl === "";
                fixture.source = null;
                fixture.observations.lossGrace = presentation.current !== null;
                fixture.phase++;
            } else if (fixture.phase === 3 && !presentation.settling) {
                fixture.observations.cleared = presentation.current === null;
                fixture.source = first;
                first.trackTitle = "";
                fixture.source = second;
                fixture.observations.switch = presentation.current.key === "two" && presentation.current.title === "Other track" && presentation.current.artUrl === "";
                presentation.enabled = false;
                second.trackTitle = "";
                fixture.observations.disabled = presentation.current.title === "" && !presentation.settling;
                fixture.finish(fixture.observations);
            }
        }
    }
''')
        self.assertEqual(result, dict(retained=True, coherent=True, complete=True, expired=True,
                                     lossGrace=True, cleared=True, switch=True, disabled=True))
