"""Q5 leg 2 native tests: the wallpaper daemon owner and playlist scheduler.

Contract: test_native_wallpaper.py (pins the Q5 wallpaper port; source strings and engine
flows freeze the shapes both sides keep).
REL: scripts/wallpaper.py + wallpaper_actions.py – DEPRECATED(Q5->Q6) sources;
qml/services/WallpaperModel.js + WallpaperState.qml.
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class WallpaperContractCase(unittest.TestCase):
    def read(self, name):
        return (REPO / name).read_text()

    def test_shell_state_routes_the_native_scheduler(self):
        text = self.read("qml/services/ShellState.qml")
        self.assertIn("if (WallpaperState.handles(action)) return WallpaperState; // Q5 leg 2", text)
        self.assertIn("WallpaperState.sync(preferences,", text)
        self.assertIn('send("setting", {key: key, value: value, token: token})', text)
        self.assertIn('["--no-wallpaper"]', text)
        self.assertEqual(text.count('"--no-wallpaper"'), 1)

    def test_backend_stays_the_user_save_path(self):
        text = self.read("scripts/desktop_backend.py")
        self.assertIn('--no-wallpaper", action="store_true"', text)
        self.assertIn("not self.no_wallpaper and os.environ.get('LME_NO_WALLPAPER')", text)
        self.assertIn("DEPRECATED(Q5->Q6)", self.read("scripts/wallpaper.py"))

    def test_state_files_keep_the_injection_seams(self):
        qmldir = self.read("qml/services/qmldir")
        self.assertIn("singleton WallpaperState 1.0 WallpaperState.qml", qmldir)
        state = self.read("qml/services/WallpaperState.qml")
        for seam in ("property var runner", "property var spawner", "property var clock",
                     "property var writeSetting", "property var runAction"):
            self.assertIn(seam, state)
        self.assertIn('["wallpaperStatus", "wallpaperEnsure", "wallpaperNext"]', state)
        self.assertIn("A wallpaper change is already running", state)  # the in-process flock half


try:
    sys.path.insert(0, str(REPO / "tests"))
    from test_local_qml import LocalQmlCase  # noqa: E402
except ImportError:  # pragma: no cover - the engine cases need the local harness
    LocalQmlCase = None


@unittest.skipIf(LocalQmlCase is None or not Path("/usr/bin/quickshell").exists(), "Quickshell is required for native QML checks")
class WallpaperModelCase(LocalQmlCase):
    def test_parsers_names_and_arguments(self):
        result = self.run_qml('import "qml/services/WallpaperModel.js" as Wallpaper', '''
    property var checks: ({})
    Component.onCompleted: {
        let thrown = "";
        try { Wallpaper.outputName("bad name"); } catch (error) { thrown = error.message; }
        checks.outputName = thrown === "Choose a valid display name" && Wallpaper.outputName("", true) === ""
            && Wallpaper.outputName("DP-1.a_2") === "DP-1.a_2";
        const query = "eDP-1: 1920x1080, scale: 1, currently displaying: image: /home/z/w1.png\\n" +
            "some-namespace: DP-1: 2560x1440, scale: 1, currently displaying: image: /home/z/w2.png\\n" +
            "HDMI-A-1: 1920x1080, scale: 1, currently displaying: color: 000000\\n" +
            "ignored line";
        const outputs = Wallpaper.queryOutputs(query);
        checks.queryOutputs = outputs.has("eDP-1") && outputs.has("DP-1") && outputs.has("HDMI-A-1") && outputs.size === 3;
        const images = Wallpaper.queryImages(query);
        checks.queryImages = images["eDP-1"] === "/home/z/w1.png" && images["DP-1"] === "/home/z/w2.png";
        const animate = Wallpaper.imageArguments("/w.png", {animations: true, wallpaperTransition: "wave",
            wallpaperResize: "crop", wallpaperFilter: "Lanczos3", wallpaperFillColor: "#101010",
            wallpaperTransitionFps: 60, wallpaperTransitionStep: 2, wallpaperTransitionDuration: 3.5,
            wallpaperTransitionAngle: 45, wallpaperTransitionPosition: "center", wallpaperTransitionBezier: "0.54,0,0.34,0.99",
            wallpaperTransitionWave: "20,20"}, true);
        checks.arguments = animate[0] === "img" && animate.indexOf("--transition-type") > 0
            && animate[animate.indexOf("--transition-type") + 1] === "wave"
            && animate[animate.indexOf("--transition-step") + 1] === "90"
            && animate[animate.indexOf("--fill-color") + 1] === "101010";
        const still = Wallpaper.imageArguments("/w.png", {animations: true, wallpaperTransition: "fade",
            wallpaperResize: "crop", wallpaperFilter: "Lanczos3", wallpaperFillColor: "#000000",
            wallpaperTransitionFps: 60, wallpaperTransitionStep: 2, wallpaperTransitionDuration: 3,
            wallpaperTransitionAngle: 45, wallpaperTransitionPosition: "center", wallpaperTransitionBezier: "0.54,0",
            wallpaperTransitionWave: "20,20"}, false);
        checks.still = still[still.indexOf("--transition-type") + 1] === "none" && still.indexOf("--transition-duration") < 0;
        done.start();
    }
    Timer { id: done; interval: 100; onTriggered: fixture.finish(checks) }
''')
        self.assertEqual(result, dict(outputName=True, queryOutputs=True, queryImages=True,
                                      arguments=True, still=True))

    def test_plan_deadline_pause_signature_and_restore_priority(self):
        result = self.run_qml('import "qml/services/WallpaperModel.js" as Wallpaper', '''
    property var checks: ({})
    property var prefs: ({wallpaperPlaylist: ["/a.png", "/b.png"], wallpaperPlaylistEnabled: true,
        wallpaperPlaylistPaused: false, wallpaperPlaylistShuffle: false, wallpaperPlaylistInterval: 300,
        wallpaperPlaylistOutput: "eDP-1", wallpaper: "/shared.png", wallpaperOutputs: {"DP-1": "/fixed.png"}})
    property var state: ({connected: null, applied: {}, signature: null, cursor: null, deadline: null,
        remaining: null, wasPaused: false, retryAt: 0})
    function step(outputs, now, saving, paused, enabled) {
        fixture.prefs.wallpaperPlaylistPaused = paused === true;
        fixture.prefs.wallpaperPlaylistEnabled = enabled !== false;
        const plan = Wallpaper.plan(fixture.state, fixture.prefs, outputs, now, saving === true);
        fixture.state = plan.state;
        return plan.job || {};  // null jobs read as kind undefined
    }
    Component.onCompleted: {
        const checks = fixture.checks;
        // First connect seeds the shared image on non-overridden outputs; the overridden display
        // has not been applied by this instance yet, so the first job is its restore.
        checks.seed = fixture.step(["eDP-1", "DP-1"], 0).kind === "restore"
            && fixture.state.applied["eDP-1"] === "/shared.png" && !fixture.state.applied["DP-1"];
        fixture.state.applied["DP-1"] = "/fixed.png";  // the restore job executed
        // The deadline arrives → advance for the playlist output.
        checks.advance = fixture.step(["eDP-1", "DP-1"], 300).kind === "advance"
            && fixture.state.deadline === 600;
        // Pause keeps the remaining time; resume restores it.
        fixture.step(["eDP-1", "DP-1"], 400, false, true);
        checks.paused = fixture.state.deadline === null && fixture.state.remaining === 200 && fixture.state.wasPaused;
        checks.resume = fixture.step(["eDP-1", "DP-1"], 900, false, false).kind === undefined
            && fixture.state.deadline === 1100;  // 900 + remaining 200, not a fresh interval
        // A preference change resets the signature (cursor/deadline cleared, fresh interval).
        fixture.prefs.wallpaperPlaylist = ["/c.png", "/a.png", "/b.png"];
        checks.signature = fixture.step(["eDP-1", "DP-1"], 1000).kind === undefined
            && fixture.state.deadline === 1300 && fixture.state.cursor === null;
        // A changed display (applied vs desired) restores before advancing, with a 30 s retry.
        fixture.state.applied["eDP-1"] = "/stale.png";
        const job = fixture.step(["eDP-1", "DP-1"], 1300);
        checks.restore = job.kind === "restore" && job.outputs.length === 1 && job.outputs[0] === "eDP-1"
            && fixture.state.retryAt === 1330;
        checks.retryBackoff = fixture.step(["eDP-1", "DP-1"], 1320).kind === undefined
            && fixture.step(["eDP-1", "DP-1"], 1330).kind === "restore";
        // A disconnect holds the bookkeeping (no job) and the deadline still ticks.
        checks.disconnect = fixture.step([], 1330).kind === undefined && fixture.state.connected.length === 0;
        // The playlist output leaving the displays cancels the automatic advance (the matching
        // display holds its image, so no restore fires first).
        fixture.state.applied["DP-1"] = "/fixed.png";
        checks.outputGone = fixture.step(["DP-1"], 1600).kind === undefined;
        // Disabled or empty playlists clear the deadline entirely.
        fixture.prefs.wallpaperPlaylistEnabled = false;
        checks.disabled = fixture.step(["DP-1"], 1700).kind === undefined && fixture.state.deadline === null;
        // Sequential rotation follows the cursor and skips the current image.
        fixture.prefs.wallpaperPlaylistEnabled = true;
        fixture.state.cursor = null; fixture.state.deadline = 2000; fixture.state.applied = {};
        checks.choices = JSON.stringify(Wallpaper.advanceChoices(fixture.prefs, "eDP-1", null, "/b.png", false).choices)
            === JSON.stringify(["/c.png", "/a.png"]);
        checks.cursor = JSON.stringify(Wallpaper.advanceChoices(fixture.prefs, "eDP-1", ["eDP-1", "/c.png", "/b.png"], "/b.png", false).choices)
            === JSON.stringify(["/a.png", "/c.png"]);
        checks.shuffleSkipsCurrent = Wallpaper.advanceChoices(fixture.prefs, "eDP-1", null, "/b.png", true).choices.indexOf("/b.png") < 0
            && Wallpaper.advanceChoices(fixture.prefs, "eDP-1", null, "/b.png", true).choices.length === 2;
        fixture.prefs.wallpaperPlaylist = ["/only.png"];
        checks.single = Wallpaper.advanceChoices(fixture.prefs, "eDP-1", null, "/only.png", false).note
            === "The only playlist image is already active";
        try { Wallpaper.advanceChoices({wallpaperPlaylist: []}, "eDP-1", null, "", false); checks.empty = false; }
        catch (failure) { checks.empty = failure.message === "The playlist has no available images"; }
        done.start();
    }
    Timer { id: done; interval: 100; onTriggered: fixture.finish(checks) }
''')
        self.assertEqual(result, dict(seed=True, advance=True, paused=True, resume=True, signature=True,
                                      restore=True, retryBackoff=True, disconnect=True, outputGone=True,
                                      disabled=True, choices=True, cursor=True, shuffleSkipsCurrent=True,
                                      single=True, empty=True))

    def test_state_advance_status_and_restore_with_fake_transport(self):
        result = self.run_qml('import "qml/services"', '''
    property var checks: ({})
    property var applied: []
    property var writes: []
    property var actions: []
    property var queryText: "eDP-1: 1920x1080, scale: 1, currently displaying: image: /stale.png\\nDP-1: 2560x1440, scale: 1, currently displaying: image: /fixed.png"
    property var statusDone: null
    Component.onCompleted: {
        WallpaperState.clock = () => 5000;
        WallpaperState.spawner = () => { fixture.checks.spawned = true; };  // must stay unset: the query answers
        WallpaperState.runner = (args, seconds, done) => {
            if (args[0] === "query") return done(true, fixture.queryText);
            fixture.applied.push(args.join(" "));
            done(true, "");
        };
        WallpaperState.writeSetting = (key, value, token) => fixture.writes.push([key, value, token]);
        WallpaperState.runAction = (action, payload) => fixture.actions.push([action, payload.path, payload.output]);
        const prefs = {animations: true, wallpaperTransition: "fade", wallpaperResize: "crop", wallpaperFilter: "Lanczos3",
            wallpaperFillColor: "#000000", wallpaperTransitionFps: 60, wallpaperTransitionStep: 2, wallpaperTransitionDuration: 3,
            wallpaperTransitionAngle: 45, wallpaperTransitionPosition: "center", wallpaperTransitionBezier: "0.54,0,0.34,0.99",
            wallpaperTransitionWave: "20,20", wallpaperPlaylist: ["/a.png", "/b.png"], wallpaperPlaylistEnabled: true,
            wallpaperPlaylistPaused: false, wallpaperPlaylistShuffle: false, wallpaperPlaylistInterval: 300,
            wallpaperPlaylistOutput: "eDP-1", wallpaper: "/shared.png", wallpaperOutputs: {}};
        // A due advance: applies the next image natively and persists the per-output token.
        WallpaperState.lastPreferences = prefs;
        WallpaperState.machine = {connected: ["eDP-1", "DP-1"], applied: {"eDP-1": "/shared.png", "DP-1": "/fixed.png"},
            signature: null, cursor: null, deadline: 5000, remaining: null, wasPaused: false, retryAt: 0};
        let manual = null;
        WallpaperState.perform("wallpaperNext", {}, (ok, message) => { manual = {ok: ok, message: message}; });
        checks.advance = manual.ok === true && manual.message === "Wallpaper updated"
            && fixture.applied.length === 1 && fixture.applied[0].indexOf("/a.png") >= 0
            && fixture.applied[0].indexOf("--outputs eDP-1") >= 0
            && fixture.writes.length === 1 && fixture.writes[0][0] === "wallpaperOutputs" && fixture.writes[0][2] === "eDP-1"
            && WallpaperState.machine.cursor[1] === "/a.png";
        // Status surfaces the daemon query; the shared rotation delegates to the backend action.
        WallpaperState.perform("wallpaperStatus", {}, (ok, message) => { fixture.statusDone = {ok: ok, message: message}; });
        checks.status = fixture.statusDone.ok === true && fixture.statusDone.message === "Wallpaper daemon checked"
            && WallpaperState.statusResult.running === true && WallpaperState.statusResult.query === fixture.queryText;
        WallpaperState.machine.deadline = 6000;
        WallpaperState.machine.applied = {"eDP-1": "/shared.png"};
        prefs.wallpaperPlaylistOutput = "";
        WallpaperState.lastPreferences = prefs;
        WallpaperState.perform("wallpaperNext", {}, (ok, message) => { manual = {ok: ok, message: message}; });
        checks.sharedDelegates = manual.ok === true && fixture.actions.length === 1
            && fixture.actions[0][0] === "wallpaper" && fixture.actions[0][1] === "/a.png" && fixture.actions[0][2] === ""
            && fixture.applied.length === 1;  // no native awww apply for the shared path
        // Restore re-applies only displays whose image drifted, without persisting.
        fixture.applied = [];
        WallpaperState.machine.applied = {"eDP-1": "/shared.png", "DP-1": "/fixed.png"};
        WallpaperState.lastPreferences = Object.assign({}, prefs, {wallpaperOutputs: {"eDP-1": "/wanted.png", "DP-1": "/fixed.png"}, wallpaper: "/shared.png"});
        WallpaperState.executeRestore(["eDP-1", "DP-1"]);
        checks.noSpawn = fixture.checks.spawned === undefined;
        checks.restore = fixture.applied.length === 1 && fixture.applied[0].indexOf("/wanted.png") >= 0
            && fixture.applied[0].indexOf("--transition-type none") >= 0 && fixture.writes.length === 1
            && WallpaperState.machine.applied["DP-1"] === "/fixed.png";  // matched display kept, not re-applied
        done.start();
    }
    Timer { id: done; interval: 100; onTriggered: fixture.finish(checks) }
''', {"LME_SHELL_DEMO": "0", "NIRI_SOCKET": "/nonexistent-lme-q5-test"})
        self.assertEqual(result, dict(advance=True, status=True, sharedDelegates=True, restore=True, noSpawn=True))


if __name__ == "__main__":
    unittest.main()
