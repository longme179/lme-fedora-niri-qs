"""Bluetooth connection results do not duplicate native device notifications."""
import shutil
import unittest

import test_local_qml as qml_tests


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class BluetoothStatusQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_connection_success_is_quiet_without_hiding_errors_or_notifications(self):
        result = self.run_qml('import "qml/services"', '''
    Timer { interval:80; running:true; repeat:true; onTriggered: {
        if (!ShellState.backendReady) return;
        stop();
        const blueman = {id:"blueman-connected", appName:"blueman", summary:"Connected", body:"Headphones · 100%",
            active:true, popup:true, actions:[], timestamp:Date.now()};
        Notifications.history = [blueman];
        const muted = JSON.stringify(Notifications.mutedApps);
        const observations = {};
        let sequence = 100;
        function accept(action, ok, message) {
            ShellState.statusMessage = "";
            ShellState.accept(JSON.stringify(Object.assign({}, ShellState.snapshot, {
                lastResult:{action, ok, message, sequence:++sequence}
            })));
        }
        ShellState.pendingActions = {bluetoothDevice:true, powerProfile:true};
        accept("bluetoothDevice", true, "Bluetooth device connected");
        observations.connectedQuiet = ShellState.statusMessage === "";
        observations.resultKept = ShellState.lastResult.message === "Bluetooth device connected";
        observations.pendingCleared = !ShellState.pendingActions.bluetoothDevice && !!ShellState.pendingActions.powerProfile;
        accept("bluetoothDevice", true, "Bluetooth device disconnected");
        observations.disconnectedQuiet = ShellState.statusMessage === "";
        accept("bluetoothDevice", false, "Connection failed: device unavailable");
        observations.failureVisible = ShellState.statusMessage === "Connection failed: device unavailable" && ShellState.statusError;
        accept("powerProfile", true, "Power profile changed");
        observations.otherSuccessVisible = ShellState.statusMessage === "Power profile changed" && !ShellState.statusError;
        observations.notificationKept = Notifications.history.length === 1 && Notifications.history[0] === blueman
            && Notifications.popups.length === 1;
        observations.mutedUnchanged = JSON.stringify(Notifications.mutedApps) === muted;
        fixture.finish(observations);
    } }
''')
        self.assertEqual(result, dict(connectedQuiet=True, resultKept=True, pendingCleared=True,
            disconnectedQuiet=True, failureVisible=True, otherSuccessVisible=True,
            notificationKept=True, mutedUnchanged=True))
