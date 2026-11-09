"""ShellState surfaces failures, keeps demo panels and rejects malformed snapshots.
Contract: test_shell_state_errors.py covers shell_state_errors behavior/contracts; check imports for fixtures/helpers under test.
"""
import shutil
import unittest

import test_local_qml as qml_tests


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class ShellStateStatusCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_demo_annotate_keeps_panels_and_failures_reach_the_banner(self):
        result = self.run_qml('import "qml/services"', '''
    property int phase: 0
    property var observations: ({})
    Timer {
        interval: 50; repeat: true; running: true
        onTriggered: {
            if (phase !== 0 || !ShellState.backendReady) return;
            phase = 1;
            ShellState.togglePanel("control");
            observations.open = ShellState.panelOpen;
            ShellState.run("imageAnnotate", {path: "/tmp/not-real.png"});
            observations.afterAnnotate = ShellState.panelOpen;
            ShellState.accept(JSON.stringify(Object.assign({}, ShellState.snapshot,
                {lastResult: {ok: false, action: "notificationSave", message: "Save failed", sequence: 1}})));
            observations.errorStatus = ShellState.statusMessage;
            observations.errorFlag = ShellState.statusError;
            ShellState.accept('{"apps":[]}');
            observations.malformedStatus = ShellState.statusMessage;
            observations.malformedFlag = ShellState.statusError;
            fixture.finish(observations);
        }
    }
    Timer { interval: 8000; running: true; onTriggered: fixture.finish({phase: phase}) }
''')
        self.assertTrue(result["open"], result)
        self.assertTrue(result["afterAnnotate"], result)
        self.assertEqual(result["errorStatus"], "Save failed", result)
        self.assertTrue(result["errorFlag"], result)
        self.assertIn("incomplete snapshot", result["malformedStatus"], result)
        self.assertTrue(result["malformedFlag"], result)
