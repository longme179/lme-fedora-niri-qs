"""Native MPRIS capability guards and pointer/keyboard media controls."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import test_local_qml as qml_tests
from test_backend import backend
from settings_transfer import document, validate_document


class MediaPreferenceCase(unittest.TestCase):
    def test_extended_controls_are_boolean_and_portable(self):
        values = dict(backend.DEFAULT_PREFERENCES, mediaControls=False)
        result = validate_document(document(values, 'preset'), backend.validate_preference, backend.DEFAULT_PREFERENCES)
        self.assertFalse(result['mediaControls'])
        for value in [None, 'true', 1, []]:
            with self.assertRaises(ValueError): backend.validate_preference('mediaControls', value)


@unittest.skipUnless(os.environ.get('LME_TEST_MEDIA_UI') == '1', 'requires private D-Bus/Wayland session')
class MediaControlQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def player(self, extra=()):
        root = Path(__file__).resolve().parents[1]
        log = tempfile.TemporaryFile(mode='w+')
        self.addCleanup(log.close)
        process = subprocess.Popen(['/usr/bin/python3', str(root / 'tests/mpris_fixture.py'), *extra], stdout=log, stderr=log)
        self.addCleanup(lambda: (process.terminate(), process.wait(timeout=5)))
        return process

    def test_seek_shuffle_repeat_through_real_mpris(self):
        with tempfile.TemporaryDirectory() as directory:
            events = Path(directory) / 'events.jsonl'
            with unittest.mock.patch.dict(os.environ, LME_MPRIS_EVENTS=str(events)):
                self.player()
            result = self.run_qml('import QtTest\nimport Quickshell.Services.Mpris\nimport "qml/components"\nimport "qml/services"', '''
    property var player: Mpris.players.values[0] || null
    property int phase: 0
    property int ticks: 0
    property var observations: ({})
    FloatingWindow {
        implicitWidth: 500; implicitHeight: 260
        MediaProgress { id: progress; width: 460; player: fixture.player }
        MediaActions { id: actions; y: 80; width: 460; player: fixture.player }
    }
    TestCase { id: pointer; when: false }
    function find(item, name) {
        if (item.objectName === name) return item;
        for (const child of item.children || []) { const found = find(child, name); if (found) return found; }
        return null;
    }
    Timer {
        interval: 100; repeat: true; running: true
        onTriggered: {
            if (++fixture.ticks > 100) { fixture.finish({timeout: fixture.phase}); return; }
            if (!fixture.player || !progress.canSeek || !actions.canShuffle || !actions.canRepeat) return;
            const slider = fixture.find(progress, "mediaSeek");
            if (fixture.phase === 0) { fixture.player.pause(); fixture.phase++; }
            else if (fixture.phase === 1 && !fixture.player.isPlaying) {
                pointer.mouseClick(slider, slider.width / 2, 16); fixture.phase++;
            } else if (fixture.phase === 2 && Math.abs(progress.position - 60) < 1) {
                fixture.observations.click = true; slider.forceActiveFocus(); pointer.keyClick(Qt.Key_Right); fixture.phase++;
            } else if (fixture.phase === 3 && Math.abs(progress.position - 65) < 1) {
                fixture.observations.keyboard = true;
                pointer.mousePress(slider, slider.width * .6, 16);
                pointer.mouseMove(slider, slider.width * .8, 16);
                fixture.observations.deferred = Math.abs(fixture.player.position - 65) < 1;
                pointer.mouseRelease(slider, slider.width * .8, 16); fixture.phase++;
            } else if (fixture.phase === 4 && progress.position > 90) {
                fixture.observations.drag = true;
                const button = fixture.find(actions, "mediaShuffle"); pointer.mouseClick(button, 30, 20); fixture.phase++;
            } else if (fixture.phase === 5 && actions.shuffled) {
                fixture.observations.shuffle = true;
                const button = fixture.find(actions, "mediaRepeat"); pointer.mouseClick(button, 30, 20); fixture.phase++;
            } else if (fixture.phase === 6 && actions.loop === MprisLoopState.Playlist) {
                fixture.observations.all = true;
                const button = fixture.find(actions, "mediaRepeat"); pointer.mouseClick(button, 30, 20); fixture.phase++;
            } else if (fixture.phase === 7 && actions.loop === MprisLoopState.Track) {
                fixture.observations.one = true;
                const button = fixture.find(actions, "mediaRepeat"); pointer.mouseClick(button, 30, 20); fixture.phase++;
            } else if (fixture.phase === 8 && actions.loop === MprisLoopState.None) {
                fixture.observations.off = true; fixture.finish(fixture.observations);
            }
        }
    }
''', {'LME_SHELL_DEMO': '0', 'LME_SHELL_BACKEND_DEMO': '1'})
            self.assertEqual(result, dict(click=True, keyboard=True, deferred=True, drag=True, shuffle=True, all=True, one=True, off=True))
            calls = [json.loads(line) for line in events.read_text().splitlines()]
            self.assertEqual([args for method, args in calls if method == 'LoopStatus'], ['Playlist', 'Track', 'None'])
            self.assertEqual([args for method, args in calls if method == 'Shuffle'], [True])
            self.assertGreaterEqual(sum(method == 'SetPosition' for method, args in calls), 3)

    def test_unsupported_player_disables_extended_actions(self):
        self.player(['--no-controls'])
        result = self.run_qml('import Quickshell.Services.Mpris\nimport "qml/components"\nimport "qml/services"', '''
    property var player: Mpris.players.values[0] || null
    MediaProgress { id: progress; player: fixture.player }
    MediaActions { id: actions; player: fixture.player }
    Timer { interval: 100; repeat: true; running: true; onTriggered: {
        if (!fixture.player) return;
        progress.seek(42); actions.toggleShuffle(); actions.cycleRepeat();
        fixture.finish({seek: progress.canSeek, shuffle: actions.canShuffle, repeat: actions.canRepeat});
    } }
''', {'LME_SHELL_DEMO': '0', 'LME_SHELL_BACKEND_DEMO': '1'})
        self.assertEqual(result, dict(seek=False, shuffle=False, repeat=False))
