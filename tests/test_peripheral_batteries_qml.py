"""Peripheral alert transitions and responsive device battery rows."""
import shutil
import unittest
import test_local_qml as qml_tests


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required")
class PeripheralBatteryQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_low_alert_latches_missing_samples_reconnect_and_hysteresis(self):
        result = self.run_qml('import "qml/services"', '''
    Component.onCompleted: Qt.callLater(() => {
        function check(percent, extra, enabled = true, threshold = 20) {
            return PeripheralBatteries.check([Object.assign({id:"bt:one", name:"Headphones", percentage:percent, connected:true}, extra || {})], enabled, threshold).length;
        }
        const counts = [check(null), check(50), check(20), check(19), check(null), check(0, {connected:false}), check(0)];
        counts.push(check(25), check(19), check(26), check(20));
        counts.push(check(10, {charging:true}), check(10));
        PeripheralBatteries.alerts = ({});
        counts.push(check(10, {}, false), check(10));
        counts.push(check(10, {id:"bt:two"}), check(NaN, {id:"bad"}), check(-1, {id:"bad"}), check(101, {id:"bad"}));
        PeripheralBatteries.alerts = ({});
        counts.push(check(0));
        PeripheralBatteries.check(Array.from({length:140}, (_, i) => ({id:"device-"+i, percentage:80, connected:true})), true, 20);
        fixture.finish({counts, bounded:Object.keys(PeripheralBatteries.alerts).length});
    })
''')
        self.assertEqual(result["counts"], [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 1, 1, 0, 0, 0, 1])
        self.assertEqual(result["bounded"], 128)

    def test_snapshot_alerts_batch_respect_dnd_and_skip_demo_and_settings(self):
        for mode, expected in (({}, 1), ({"LME_SHELL_SETTINGS":"1"}, 0), ({"LME_SHELL_DEMO":"1"}, 0)):
            with self.subTest(mode=mode):
                result = self.run_qml('import "qml/services"', '''
    Timer { interval:80; running:true; repeat:true; onTriggered: {
        if (!ShellState.backendReady) return;
        stop();
        Notifications.history = [];
        PeripheralBatteries.alerts = ({});
        const next = Object.assign({}, ShellState.snapshot, {
            preferences:Object.assign({}, ShellState.preferences, {peripheralBatteryAlerts:true, peripheralBatteryThreshold:20, dndUntil:Date.now()+60000}),
            system:Object.assign({}, ShellState.system, {peripheralBatteries:[
                {id:"bt:one",name:"Headphones",percentage:15,connected:true,charging:false},
                {id:"bt:two",name:"Mouse",percentage:0,connected:true,charging:false}
            ]})
        });
        ShellState.accept(JSON.stringify(next));
        ShellState.accept(JSON.stringify(next));
        fixture.finish({count:Notifications.history.length, popups:Notifications.popups.length,
            body:Notifications.history[0]?.body || ""});
    } }
''', {"LME_SHELL_DEMO":"0", "LME_SHELL_BACKEND_DEMO":"1", **mode})
                self.assertEqual(result["count"], expected)
                self.assertEqual(result["popups"], 0)
                self.assertEqual(result["body"], "Headphones · 15%\nMouse · 0%" if expected else "")

    def test_battery_rows_wrap_names_and_distinguish_zero_from_unknown(self):
        result = self.run_qml('import QtTest\nimport "qml/panels"\nimport "qml/services"', '''
    FloatingWindow {
        implicitWidth:320; implicitHeight:700
        PeripheralBatteryList { id:list; width:280 }
        TestCase { id:probe; when:false }
    }
    property int ticks:0
    Timer { interval:80; repeat:true; running:true; onTriggered: {
        if (!ShellState.backendReady) return;
        if (fixture.ticks++ === 0) {
            ShellState.snapshot = Object.assign({}, ShellState.snapshot, {system:Object.assign({}, ShellState.system, {peripheralBatteries:[
                {id:"zero",name:"Wireless keyboard with a deliberately long device name",percentage:0,connected:true,charging:false},
                {id:"unknown",name:"Headphones",percentage:null,connected:true,charging:null}
            ]})});
            return;
        }
        const zero = probe.findChild(list,"peripheralBattery-zero"), unknown = probe.findChild(list,"peripheralBattery-unknown");
        fixture.finish({count:list.devices.length,zeroReported:zero.reported,zeroLow:zero.low,unknownReported:unknown.reported,
            wrapped:zero.height > unknown.height, fits:zero.width <= list.width,visible:list.visible});
    } }
''')
        self.assertEqual(result, dict(count=2, zeroReported=True, zeroLow=True, unknownReported=False, wrapped=True, fits=True, visible=True))
