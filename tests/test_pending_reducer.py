"""Pure transport reduction through Qt's actual JavaScript engine."""
from pathlib import Path
import unittest

import test_local_qml

REDUCER = Path(__file__).resolve().parents[1]/'qml/services/ActionPending.js'


@unittest.skipUnless(REDUCER.exists(), 'F3 reducer contract not implemented on baseline')
class PendingReducerCase(unittest.TestCase):
    def test_delayed_ack_duplicate_legacy_fault_and_safe_serial_contracts(self):
        result = test_local_qml.LocalQmlCase.run_qml(self, 'import "qml/services/ActionPending.js" as Pending', '''
    Component.onCompleted: {
        const checks = {};
        let s = Pending.initial();
        s = Pending.sent(s,"volume"); s = Pending.sent(s,"volume");
        let r = Pending.received(s,{acknowledged:1,active:[]},null);
        checks.late = !!r.state.pending.volume && r.state.local.volume === 2;
        r = Pending.received(r.state,{acknowledged:2,active:[]},null);
        checks.burst = !r.state.pending.volume && Object.keys(r.state.local).length === 0;
        s = Pending.sent(r.state,"bluetoothDevice");
        r = Pending.received(s,{acknowledged:3,active:["bluetoothDevice"]},{action:"bluetoothDevice",pending:true});
        s = Pending.sent(r.state,"bluetoothDevice");
        r = Pending.received(s,{acknowledged:4,active:["bluetoothDevice"]},{action:"bluetoothDevice",ok:false});
        checks.duplicate = !!r.state.pending.bluetoothDevice;
        s = Pending.sent(r.state,"calculate");
        r = Pending.received(s,{acknowledged:4,active:[]},{action:"bluetoothDevice",ok:true});
        checks.independent = !r.state.pending.bluetoothDevice && !!r.state.pending.calculate;
        s = r.state;
        for (const metadata of [undefined,null,{}, {acknowledged:true,active:[]},
                {acknowledged:NaN,active:[]}, {acknowledged:Infinity,active:[]},
                {acknowledged:9007199254740992,active:[]}, {acknowledged:3,active:[]},
                {acknowledged:5,active:["x","x"]}, {acknowledged:5,active:[3]},
                {acknowledged:5,active:[""]}, {acknowledged:5,active:"x"}]) {
            const bad = Pending.received(s,metadata,{action:"calculate",ok:true});
            checks.faults = checks.faults !== false && bad.invalid && bad.state === s;
        }
        r = Pending.received(s,{acknowledged:5,active:[]},null);
        checks.recover = !r.invalid && Object.keys(r.state.pending).length === 0;
        s = Pending.sent(Pending.initial(),"setting");
        r = Pending.received(s,undefined,{action:"setting",ok:true});
        checks.legacy = !r.invalid && !r.state.pending.setting && !r.state.negotiated;
        s = Pending.sent(Pending.initial(),"fileSearch");
        r = Pending.received(s,{acknowledged:1,active:["fileSearch"]},{action:"fileSearch",pending:true});
        s = Pending.sent(r.state,"fileSearch");
        r = Pending.received(s,{acknowledged:1,active:[]},{action:"fileSearch",ok:true});
        checks.replace = !!r.state.pending.fileSearch;
        s = Pending.initial(); s.serial = 9007199254740990;
        s = Pending.sent(s,"setting");
        checks.boundary = s.serial === 9007199254740991;
        try { Pending.sent(s,"setting"); checks.overflow = false; }
        catch (e) { checks.overflow = true; }
        checks.reset = Pending.initial().serial === 0 && !Pending.initial().negotiated;
        Qt.callLater(() => fixture.finish(checks));
    }
''')
        self.assertEqual(set(result), {'late','burst','duplicate','independent','faults','recover',
                                      'legacy','replace','boundary','overflow','reset'})
        for name, passed in result.items():
            with self.subTest(name=name): self.assertTrue(passed)
