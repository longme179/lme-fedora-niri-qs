"""Only fields written by notificationSave may advance the save revision."""
import shutil
import unittest

import test_local_qml as qml_tests


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class NotificationPersistedFieldsCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_popup_and_transient_changes_do_not_resubmit_unchanged_history(self):
        result = self.run_qml('import "qml/services"', '''
    Component.onCompleted: Qt.callLater(() => {
        Notifications.historyLoaded = true;
        const base = Notifications.historyRevision;
        const entry = {id:"one",appName:"App",appIcon:"",imagePath:"",summary:"hello",body:"body",
            timestamp:1,urgency:1,actions:[],active:true,popup:true,transient:false};
        Notifications.history = [entry];
        const added = Notifications.historyRevision;
        Notifications.history = Notifications.history.map(item => Object.assign({}, item, {active:false,popup:false,actions:[{identifier:"x",text:"X"}]}));
        const toggled = Notifications.historyRevision;
        Notifications.history = [{id:"transient",appName:"App",appIcon:"",imagePath:"",summary:"ephemeral",body:"",
            timestamp:2,urgency:1,actions:[],active:true,popup:true,transient:true}, ...Notifications.history];
        const transient = Notifications.historyRevision;
        Notifications.history = Notifications.history.map(item => item.id === "one" ? Object.assign({}, item, {summary:"changed"}) : item);
        const edited = Notifications.historyRevision;
        Notifications.history = Notifications.history.filter(item => item.id !== "one");
        const removed = Notifications.historyRevision;
        fixture.finish({base, added, toggled, transient, edited, removed});
    });
''', {"LME_SHELL_DEMO": "0", "LME_SHELL_BACKEND_DEMO": "1"})
        self.assertEqual(result["added"], result["base"] + 1)
        self.assertEqual(result["toggled"], result["added"])
        self.assertEqual(result["transient"], result["toggled"])
        self.assertEqual(result["edited"], result["transient"] + 1)
        self.assertEqual(result["removed"], result["edited"] + 1)
