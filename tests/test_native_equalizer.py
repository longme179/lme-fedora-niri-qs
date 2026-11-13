"""Q5 leg 3b native tests: the equalizer staging machine, daemon runner and store.

Contract: test_native_equalizer.py (pins the Q5 equalizer port; source strings and engine
flows freeze the shapes both sides keep).
REL: scripts/equalizer_actions.py – DEPRECATED(Q5->Q6) source; qml/services/EqualizerModel.js
+ EqualizerState.qml + scripts/json_store.py + assets/equalizer-test.wav.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DAEMON_REPORT = "set 1 2 3 4 5 6 7 8 9 10 0.25 1 0 off 0 0"


class EqualizerContractCase(unittest.TestCase):
    def read(self, name):
        return (REPO / name).read_text()

    def test_routing_and_store_registration(self):
        text = self.read("qml/services/ShellState.qml")
        self.assertIn("if (EqualizerState.handles(action)) return EqualizerState; // Q5 leg 3b", text)
        state = self.read("qml/services/EqualizerState.qml")
        self.assertIn('"eqStart", "eqStop", "eqStatus", "eqGet", "eqSetBand", "eqApply"', state)
        self.assertIn("Equalizer.daemonSetArgs(state)", state)
        self.assertIn("Equalizer.savedView(committed, state)", state)
        self.assertIn("assets/equalizer-test.wav", state)
        self.assertIn('["pw-play"]', state)
        self.assertIn("DEPRECATED(Q5->Q6)", self.read("scripts/equalizer_actions.py"))
        architecture = self.read("config/architecture.json")
        self.assertIn('"equalizer": ["scripts/equalizer_actions.py", "scripts/json_store.py", "scripts/regen_equalizer_test_tone.py"]', architecture)
        self.assertTrue((REPO / "assets/equalizer-test.wav").stat().st_size > 500000)
        self.assertIn("os.replace(temporary, target)", self.read("scripts/json_store.py"))

    def test_store_helper_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "equalizer.json"
            reply = subprocess.run([sys.executable, str(REPO / "scripts/json_store.py"), "--path", str(target)],
                                   input=json.dumps({"b1": -1.5, "pending": True, "mono": False}),
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(reply.returncode, 0, reply.stderr)
            self.assertEqual(json.loads(target.read_text()), {"b1": -1.5, "pending": True, "mono": False})
            self.assertEqual(oct(target.stat().st_mode)[-3:], "600")


try:
    sys.path.insert(0, str(REPO / "tests"))
    from test_local_qml import LocalQmlCase  # noqa: E402
except ImportError:  # pragma: no cover - the engine cases need the local harness
    LocalQmlCase = None


@unittest.skipIf(LocalQmlCase is None or not Path("/usr/bin/quickshell").exists(), "Quickshell is required for native QML checks")
class EqualizerModelCase(LocalQmlCase):
    def test_model_corpus(self):
        result = self.run_qml('import "qml/services/EqualizerModel.js" as Equalizer', '''
    property var checks: ({})
    Component.onCompleted: {
        const checks = fixture.checks;
        const flat = Equalizer.defaultState();
        checks.defaultState = flat.preset === "Flat" && flat.b10 === 0 && flat.dynamics === "off" && !flat.dyneq;
        const seeded = Equalizer.stateFromDaemonLine(fixture.report);
        checks.daemonLine = seeded !== null && seeded.b1 === 1 && seeded.b10 === 10
            && seeded.balance === 0.25 && seeded.mono === true && seeded.swap === false
            && seeded.dynamics === "off" && seeded.dyneq === false && seeded.preset === "Custom";
        checks.badLines = Equalizer.stateFromDaemonLine("set 1 2 3") === null
            && Equalizer.stateFromDaemonLine("get 1 2 3 4 5 6 7 8 9 10 0.25 1 0 off 0 0") === null
            && Equalizer.stateFromDaemonLine("set 1 2 3 4 5 6 7 8 9 99 0.25 1 0 off 0 0") === null
            && Equalizer.stateFromDaemonLine("set 1 2 3 4 5 6 7 8 9 10 9 1 0 fast 0 0") === null
            && Equalizer.stateFromDaemonLine("set 1 2 3 4 5 6 7 8 9 10 0.25 yes 0 off 0 0") === null;
        const bass = Equalizer.defaultState();
        for (let index = 0; index < 10; index++) bass["b" + (index + 1)] = Equalizer.PRESETS["Bass"][index];
        checks.presetForGains = Equalizer.presetForGains(bass) === "Bass"
            && Equalizer.presetForGains(Equalizer.defaultState()) === "Flat"
            && Equalizer.presetForGains(Object.assign({}, bass, {b1: 4})).preset === undefined
            && Equalizer.presetForGains(Object.assign({}, bass, {b1: 4})) === "Custom";
        const argv = Equalizer.daemonSetArgs(Object.assign({}, Equalizer.defaultState(), {b1: 2.5, balance: -0.5, mono: true, dynamics: "night", dyneq: true}));
        checks.setArgs = JSON.stringify(argv) === JSON.stringify(["serpantinum-audio", "ctl", "set",
            "2.5", "0", "0", "0", "0", "0", "0", "0", "0", "0", "-0.5", "1", "0", "night", "0", "1"]);
        const committed = Object.assign({}, Equalizer.defaultState(), {b1: 5, balance: 0, dynamics: "off"});
        const live = Object.assign({}, Equalizer.defaultState(), {b1: -3, balance: 0.75, mono: true, dynamics: "night", dyneq: true, pending: true});
        const view = Equalizer.savedView(committed, live);
        checks.savedView = view.b1 === 5 && view.balance === 0.75 && view.mono === true
            && view.dynamics === "night" && view.dyneq === true && view.pending === false;
        checks.normalize = Equalizer.normalize({b1: 1, b2: 2, b3: 3, b4: 4, b5: 5, b6: 6, b7: 7, b8: 8, b9: 9, b10: 10,
                balance: 0.5, mono: false, swap: false, dyneq: false, dynamics: "balanced", pending: true}).dynamics === "balanced"
            && Equalizer.normalize({b1: "x", b2: 2, b3: 3, b4: 4, b5: 5, b6: 6, b7: 7, b8: 8, b9: 9, b10: 10}) === null
            && Equalizer.normalize({b1: 1, b2: 2, b3: 3, b4: 4, b5: 5, b6: 6, b7: 7, b8: 8, b9: 9, b10: 10, balance: 0, mono: "yes"}) === null;
        checks.validators = Equalizer.bandError(0) === "Band must be an integer between 1 and 10"
            && Equalizer.bandError(2.5) === "Band must be an integer between 1 and 10" && Equalizer.bandError(11) !== ""
            && Equalizer.bandError(3) === "" && Equalizer.gainError(12.5) === "Equalizer gain is out of range"
            && Equalizer.gainError(-12) === "" && Equalizer.balanceError(1.5) === "Balance must be between -1 and 1"
            && Equalizer.flagError(1) === "Equalizer switches must be boolean" && Equalizer.flagError(true) === ""
            && Equalizer.dynamicsError("loud") === "Unknown dynamics mode" && Equalizer.dynamicsError("night") === "";
        done.start();
    }
    Timer { id: done; interval: 100; onTriggered: fixture.finish(checks) }
    property string report: "set 1 2 3 4 5 6 7 8 9 10 0.25 1 0 off 0 0"
''')
        self.assertEqual(result, dict(defaultState=True, daemonLine=True, badLines=True, presetForGains=True,
                                      setArgs=True, savedView=True, normalize=True, validators=True))

    def test_action_flows_with_fake_transport(self):
        result = self.run_qml('import "qml/services"', '''
    property var checks: ({})
    property var daemonCalls: []
    property var saved: []
    property var replies: []
    Timer { interval: 100; running: true; onTriggered: {
        EqualizerState.runner = (argv, seconds, done) => {
            const command = argv.join(" ");
            fixture.daemonCalls.push(command);
            if (argv[2] === "get") return done(true, "set 1 2 3 4 5 6 7 8 9 10 0.25 1 0 off 0 0");
            if (argv[argv.length - 1] === "quit") return done(false, "");
            return done(true, "");
        };
        EqualizerState.storeWriter = (document, done) => { fixture.saved.push(JSON.stringify(document)); done(true); };
        EqualizerState.documentSeen = false;
        EqualizerState.committed = null;
        const collect = (name) => (ok, message) => fixture.replies.push([name, ok, message]);
        // First read seeds from the daemon report and persists it.
        EqualizerState.perform("eqGet", {}, collect("get"));
        const seeded = JSON.parse(fixture.saved[0]);
        checks.seed = fixture.replies[0][0] === "get" && fixture.replies[0][1] === true
            && seeded.b1 === 1 && seeded.b10 === 10 && seeded.balance === 0.25 && seeded.mono === true
            && seeded.preset === "Custom" && fixture.daemonCalls[0] === "serpantinum-audio ctl get";
        // Band staging persists without a daemon push.
        EqualizerState.perform("eqSetBand", {band: 2, value: -3.5}, collect("band"));
        const staged = JSON.parse(fixture.saved[1]);
        checks.staging = fixture.replies[1][1] === true && fixture.replies[1][2] === ""
            && staged.b2 === -3.5 && staged.preset === "Custom" && staged.pending === true
            && fixture.daemonCalls.length === 1;
        // Apply pushes the full state and commits the bands.
        EqualizerState.perform("eqApply", {}, collect("apply"));
        checks.apply = fixture.replies[2][1] === true && fixture.daemonCalls[1].startsWith("serpantinum-audio ctl set 1 -3.5 3 ")
            && fixture.daemonCalls[1].endsWith("0.25 1 0 off 0 0")
            && EqualizerState.committed.b2 === -3.5 && EqualizerState.committed.pending === false;
        // Live balance keeps the committed bands.
        EqualizerState.perform("eqBalance", {value: 0.456}, collect("balance"));
        checks.liveBalance = fixture.replies[3][1] === true
            && fixture.daemonCalls[2].indexOf("0.46") >= 0 && EqualizerState.committed.b2 === -3.5
            && EqualizerState.committed.balance === 0.46;
        // Revert restores the committed bands with the live values.
        EqualizerState.perform("eqRevert", {}, collect("revert"));
        checks.revert = fixture.daemonCalls[3].startsWith("serpantinum-audio ctl set 1 -3.5 3 ")
            && fixture.daemonCalls[3].indexOf("0.46") >= 0;
        // Presets push their gains.
        EqualizerState.perform("eqPreset", {name: "Bass"}, collect("preset"));
        checks.preset = fixture.daemonCalls[4] === "serpantinum-audio ctl set 5 7 5 2 1 0 0 0 1 2 0.46 1 0 off 0 0";
        // Validation and error surfaces keep the Python messages.
        EqualizerState.perform("eqSetBand", {band: 11, value: 1}, collect("badBand"));
        EqualizerState.perform("eqSetBand", {band: 3, value: 13}, collect("badGain"));
        EqualizerState.perform("eqMono", {value: 1}, collect("badFlag"));
        EqualizerState.perform("eqDynamics", {value: "loud"}, collect("badMode"));
        EqualizerState.perform("eqPreset", {name: "Loud"}, collect("badPreset"));
        checks.errors = fixture.replies[5][2] === "Band must be an integer between 1 and 10"
            && fixture.replies[6][2] === "Equalizer gain is out of range"
            && fixture.replies[7][2] === "Equalizer switches must be boolean"
            && fixture.replies[8][2] === "Unknown dynamics mode"
            && fixture.replies[9][2] === "Unknown equalizer preset"
            && fixture.daemonCalls.length === 5;
        // A quit that fails is still a stop; a timeout is the only error.
        EqualizerState.perform("eqStop", {}, collect("stop"));
        checks.stop = fixture.replies[10][1] === true && fixture.replies[10][2] === "Equalizer stopped";
        fixture.finish(fixture.checks);
    } }
''', {"LME_SHELL_DEMO": "0", "NIRI_SOCKET": "/nonexistent-lme-q5-test"})
        self.assertEqual(result, dict(seed=True, staging=True, apply=True, liveBalance=True,
                                      revert=True, preset=True, errors=True, stop=True))


if __name__ == "__main__":
    unittest.main()
