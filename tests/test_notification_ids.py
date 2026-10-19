"""Local notification IDs remain independent when the clock does not advance."""
import shutil
import unittest

import test_local_qml as qml_tests


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class LocalNotificationIdsCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_same_timestamp_popups_can_be_hidden_and_dismissed_independently(self):
        result = self.run_qml('import "qml/services"', '''
    Component.onCompleted: Qt.callLater(() => {
        Notifications.history = [];
        let previous = null, entries = null;
        for (let i = 0; i < 128 && !entries; i++) {
            Notifications.local("Notification " + i, "Body " + i);
            const current = Notifications.history[0];
            if (previous && previous.timestamp === current.timestamp) entries = [current, previous];
            previous = current;
        }
        if (!entries) { fixture.finish({sameTimestampPair:false}); return; }
        Notifications.history = entries;
        const popups = Notifications.popups.length;
        Notifications.hidePopup(entries[0].id);
        const afterHide = Notifications.history.map(entry => entry.popup);
        Notifications.dismiss(entries[0].id);
        fixture.finish({sameTimestampPair:true, ids: entries.map(entry => entry.id), timestamps: entries.map(entry => entry.timestamp),
            popups, afterHide, remaining: Notifications.history.map(entry => entry.summary), expectedRemaining:entries[1].summary,
            remainingActive: Notifications.history[0]?.active, remainingPopup: Notifications.popups.length});
    })
''')
        self.assertTrue(result["sameTimestampPair"], result)
        self.assertEqual(result["timestamps"][0], result["timestamps"][1])
        self.assertEqual(len(set(result["ids"])), 2)
        self.assertEqual(result["popups"], 2)
        self.assertEqual(result["afterHide"], [False, True])
        self.assertEqual(result["remaining"], [result["expectedRemaining"]])
        self.assertTrue(result["remainingActive"])
        self.assertEqual(result["remainingPopup"], 1)
