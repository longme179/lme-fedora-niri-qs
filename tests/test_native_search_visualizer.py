"""Q5 leg 3 native tests: file search/fileOpen and the direct cava visualizer.

Contract: test_native_search_visualizer.py (pins the Q5 search/visualizer port; source
strings and engine flows freeze the shapes both sides keep).
REL: scripts/file_search.py + file_search_actions.py + window_actions.py::file_open +
scripts/audio_visualizer.py – DEPRECATED(Q5->Q6) sources; qml/services/FileSearchState.qml
+ VisualizerState.qml + config/cava-visualizer.config.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class SearchVisualizerContractCase(unittest.TestCase):
    def read(self, name):
        return (REPO / name).read_text()

    def test_routing_and_composers(self):
        text = self.read("qml/services/ShellState.qml")
        self.assertIn("if (FileSearchState.handles(action)) return FileSearchState; // Q5 leg 3", text)
        self.assertIn("readonly property var fileSearch: NativeState.fileSearch(snapshot.fileSearch)", text)
        self.assertIn("function fileSearch(backendSection)", self.read("qml/services/NativeState.qml"))
        self.assertIn("singleton FileSearchState 1.0 FileSearchState.qml", self.read("qml/services/qmldir"))
        self.assertIn("ShellState.fileSearch || {query:\"\",entries:[]}", self.read("qml/panels/Launcher.qml"))

    def test_worker_mode_and_retired_bridge(self):
        worker = self.read("scripts/file_search.py")
        self.assertIn("'--worker' in sys.argv", worker)
        self.assertIn("DEPRECATED(Q5->Q6)", worker)
        self.assertIn("DEPRECATED(Q5->Q6)", self.read("scripts/audio_visualizer.py"))
        self.assertIn("[general]", (REPO / "config/cava-visualizer.config").read_text())
        visualizer = self.read("qml/services/VisualizerState.qml")
        self.assertIn('command: ["cava", "-p", Quickshell.shellPath("config/cava-visualizer.config")]', visualizer)
        self.assertNotIn('Quickshell.shellPath("scripts/audio_visualizer.py")', visualizer)
        self.assertIn("Install cava to enable the audio visualizer", visualizer)
        state = self.read("qml/services/FileSearchState.qml")
        self.assertIn('"File search needs 2\\u2013160 characters"', state)
        self.assertIn("Search again before opening this file", state)
        self.assertIn('"gio", "open", "file://" + path', state)


class SearchWorkerCase(unittest.TestCase):
    def test_worker_round_trip_over_a_temp_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "alpha-note.txt").write_text("x")
            (root / "beta.md").write_text("x")
            (root / ".alpha-hidden").write_text("x")
            (root / "nested").mkdir()
            (root / "nested" / "gamma-alpha.txt").write_text("x")
            reply = subprocess.run([sys.executable, "-u", str(REPO / "scripts/file_search.py"), "--worker"],
                                   input=json.dumps({"query": " alpha ", "folders": [str(root)]}) + "\n",
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(reply.returncode, 0, reply.stderr)
            result = json.loads(reply.stdout.strip())
            self.assertEqual(result["query"], "alpha")
            self.assertFalse(result["truncated"])
            self.assertEqual([entry["name"] for entry in result["entries"]],
                             ["alpha-note.txt", "gamma-alpha.txt"])
            self.assertTrue(all(entry["kind"] == "file" for entry in result["entries"]))


try:
    sys.path.insert(0, str(REPO / "tests"))
    from test_local_qml import LocalQmlCase  # noqa: E402
except ImportError:  # pragma: no cover - the engine cases need the local harness
    LocalQmlCase = None


@unittest.skipIf(LocalQmlCase is None or not Path("/usr/bin/quickshell").exists(), "Quickshell is required for native QML checks")
class SearchVisualizerEngineCase(LocalQmlCase):
    def test_search_flow_open_validation_and_frame_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "alpha-note.txt").write_text("x")
            (root / "nested").mkdir()
            (root / "nested" / "gamma-alpha.txt").write_text("x")
            result = self.run_qml('import "qml/services"', '''
    property var checks: ({})
    property int phase: 0
    property var replies: []
    Timer { interval: 120; running: true; repeat: true; onTriggered: {
        switch (fixture.phase) {
        case 0:
            FileSearchState.perform("fileSearch", {query: "al"},
                (ok, message) => fixture.replies.push([ok, message]),
                {preferences: {fileSearchEnabled: true, fileSearchRoots: [ROOT]}});
            fixture.phase = 1; break;
        case 1:
            const section = FileSearchState.section;
            if (section.entries.length === 2 || section.truncated) {
                fixture.checks.searched = section.entries.length === 2 && !section.truncated
                    && section.entries[0].name === "alpha-note.txt"
                    && section.entries.some(entry => entry.name === "gamma-alpha.txt" && entry.directory === false);
                FileSearchState.perform("fileSearch", {query: "x"},
                    (ok, message) => fixture.replies.push([ok, message]),
                    {preferences: {fileSearchEnabled: true, fileSearchRoots: [ROOT]}});
                fixture.phase = 2; break;
            }
            break;  // wait for the worker line
        case 2:
            fixture.checks.badQuery = fixture.replies.length === 2 && fixture.replies[1][0] === false
                && fixture.replies[1][1] === "File search needs 2\\u2013160 characters";
            FileSearchState.perform("fileSearch", {query: "alpha"},
                (ok, message) => fixture.replies.push([ok, message]),
                {preferences: {fileSearchEnabled: false, fileSearchRoots: [ROOT]}});
            fixture.phase = 3; break;
        case 3:
            fixture.checks.disabled = fixture.replies[2][0] === false && fixture.replies[2][1] === "File search is disabled";
            FileSearchState.perform("fileOpen", {path: "/not/in/entries.txt"},
                (ok, message) => fixture.replies.push([ok, message]));
            fixture.phase = 4; break;
        case 4:
            fixture.checks.openGuard = fixture.replies[3][0] === false
                && fixture.replies[3][1] === "Search again before opening this file";
            fixture.checks.frames = JSON.stringify(VisualizerState.frame("0;10;20.5;30;40;50;60;70;80;90;100;0;1;2;3;4;"))
                === JSON.stringify([0, .1, .205, .3, .4, .5, .6, .7, .8, .9, 1, 0, .01, .02, .03, .04])
                && VisualizerState.frame("1;2;3") === null && VisualizerState.frame("a;1;2;3;4;5;6;7;8;9;10;11;12;13;14;15;16") === null
                && VisualizerState.frame("150;-5;1;2;3;4;5;6;7;8;9;10;11;12;13;14;15")[0] === 1
                && VisualizerState.frame("150;-5;1;2;3;4;5;6;7;8;9;10;11;12;13;14;15")[1] === 0;
            fixture.phase = 5; break;
        case 5:
            fixture.finish(fixture.checks); break;
        }
    } }
'''.replace("ROOT", json.dumps(str(root))), {"LME_SHELL_DEMO": "0", "NIRI_SOCKET": "/nonexistent-lme-q5-test"})
            self.assertEqual(result, dict(searched=True, badQuery=True, disabled=True, openGuard=True, frames=True))


if __name__ == "__main__":
    unittest.main()
