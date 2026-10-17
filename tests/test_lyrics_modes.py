"""Lyrics modes, shared Island playback and cue-boundary lifecycle checks."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_backend import backend, Fixture
from settings_transfer import document, validate_document
import test_local_qml as qml_tests


class LyricsModePreferencesCase(Fixture, unittest.TestCase):
    def test_modes_follow_and_island_defaults_are_validated_saved_and_portable(self):
        self.assertEqual({k:self.preferences.values[k] for k in ('lyricsMode','lyricsFollow','activityLyrics')},
                         dict(lyricsMode='scroll', lyricsFollow=True, activityLyrics=True))
        values = dict(lyricsMode='line', lyricsFollow=False, activityLyrics=False)
        self.preferences.update(values)
        restored = backend.Preferences(self.preferences.path)
        for kind in ('preset', 'backup'):
            imported = validate_document(document(restored.values, kind), backend.validate_preference, backend.DEFAULT_PREFERENCES)
            self.assertEqual({k:imported[k] for k in values}, values)
        for key, value in [('lyricsMode','karaoke'), ('lyricsMode',[]), ('lyricsFollow',1), ('activityLyrics','yes')]:
            with self.assertRaises(ValueError): backend.validate_preference(key,value)


@unittest.skipUnless(os.environ.get('LME_TEST_LYRICS_UI') == '1', 'requires private MPRIS/D-Bus session')
class LyricsModesQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_cue_boundary_follows_double_speed_without_a_visible_media_timeline(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryFile(mode='w+') as log:
            player = subprocess.Popen(['/usr/bin/python3',str(repo/'tests/mpris_fixture.py'),'--lyrics','--double-rate'],stdout=log,stderr=log)
            try:
                result = self.run_qml('import "qml/services"', '''
    property int ticks: 0
    Timer { interval: 30; running: true; repeat: true; onTriggered: {
        const engine=ActivityState.lyrics;
        if (++fixture.ticks>160) { fixture.finish({timeout:true}); return; }
        if(engine.currentLine===2) fixture.finish({title:ActivityState.title,position:ActivityState.player.position});
    } }
''', {'LME_SHELL_DEMO':'0','LME_SHELL_BACKEND_DEMO':'1'})
                self.assertEqual(result.get('title'),'Last line')
                self.assertGreaterEqual(result['position'],35)
                self.assertLess(result['position'],35.5,'A cue must follow playback speed, without waiting for the drift timer')
            finally:
                player.terminate(); player.wait(timeout=5)

    def test_player_disconnect_and_reconnect_clear_then_reload_the_shared_session(self):
        script = str(Path(__file__).resolve().parent/'mpris_fixture.py')
        result = self.run_qml('import Quickshell.Io\nimport "qml/components"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property bool cleared: false
    Process { id: playerProcess; command: ["/usr/bin/python3", "SCRIPT", "--lyrics"]; running: true }
    FloatingWindow { implicitWidth: 500; implicitHeight: 500; LyricsView { id: view; width: 460; player: ActivityState.player; expanded: true } }
    Timer { interval: 60; running: true; repeat: true; onTriggered: {
        const engine=ActivityState.lyrics;
        if (++fixture.ticks>150) { fixture.finish({timeout:fixture.phase}); return; }
        if (fixture.phase===0 && engine.lyricData.status==="ready") { playerProcess.running=false; fixture.phase++; }
        else if (fixture.phase===1 && !ActivityState.player && engine.lyricData.status==="idle") {
            fixture.cleared=engine.currentText==="" && !engine.ticking && !engine.lookup.active && !engine.drift.running && engine.readers===0;
            playerProcess.running=true; fixture.phase++;
        } else if (fixture.phase===2 && ActivityState.player && engine.lyricData.status==="ready" && engine.readers===1) {
            fixture.finish({cleared:fixture.cleared,reloaded:ActivityState.title==="Current line" && view.session===engine});
        }
    } }
'''.replace('SCRIPT',script), {'LME_SHELL_DEMO':'0','LME_SHELL_BACKEND_DEMO':'1'})
        self.assertEqual(result, dict(cleared=True,reloaded=True))

    def test_shared_island_modes_follow_boundary_pause_seek_and_disable(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryFile(mode='w+') as log:
            player = subprocess.Popen(['/usr/bin/python3',str(repo/'tests/mpris_fixture.py'),'--lyrics'],stdout=log,stderr=log)
            try:
                result = self.run_qml('import "qml/components"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property var checks: ({})
    function find(item, name) { if (item.objectName === name) return item; for (const child of item.children || []) { const found=find(child,name); if (found) return found; } return null; }
    function setting(key,value) { ShellState.run("setting",{key,value}); }
    FloatingWindow { implicitWidth: 500; implicitHeight: 700
        Column { width: 460
            LyricsView { id: first; width: parent.width; player: ActivityState.player }
            LyricsView { id: second; width: parent.width; player: ActivityState.player }
        }
    }
    Timer { interval: 60; running: true; repeat: true; onTriggered: {
        const engine=ActivityState.lyrics, player=ActivityState.player;
        if (++fixture.ticks>180) { fixture.finish({timeout:fixture.phase,data:engine.lyricData,readers:engine.readers}); return; }
        if (!ShellState.backendReady || !player) return;
        if (fixture.phase===0 && engine.lyricData.status==="ready") {
            fixture.checks.automatic=ActivityState.title==="Current line" && engine.readers===0 && engine.wanted;
            first.expanded=true; second.expanded=true; fixture.phase++;
        } else if (fixture.phase===1 && engine.readers===2) {
            fixture.checks.shared=first.session===second.session && first.session===engine;
            fixture.checks.defaults=!first.singleLine && first.following;
            fixture.find(first,"lyricsTranscript").movementStarted();
            fixture.checks.manual=!first.following;
            first.expanded=false; first.expanded=true;
            fixture.checks.reopened=first.following;
            fixture.setting("lyricsMode","line"); fixture.setting("lyricsFollow",false); fixture.phase++;
        } else if (fixture.phase===2 && first.singleLine && ShellState.preferences.lyricsFollow===false) {
            fixture.checks.line=fixture.find(first,"lyricsCurrentLine").visible && !fixture.find(first,"lyricsTranscript").visible && !first.following;
            fixture.setting("lyricsMode","scroll"); fixture.setting("lyricsFollow",true); fixture.phase++;
        } else if (fixture.phase===3 && !first.singleLine && first.following) {
            fixture.checks.scroll=fixture.find(first,"lyricsTranscript").visible && !fixture.find(first,"lyricsCurrentLine").visible;
            player.position=34.6; fixture.phase++;
        } else if (fixture.phase===4 && engine.currentLine===2) {
            fixture.checks.boundary=ActivityState.title==="Last line";
            player.pause(); fixture.phase++;
        } else if (fixture.phase===5 && !player.isPlaying) {
            fixture.checks.paused=!engine.ticking && !engine.boundary.running && ActivityState.title==="Native track";
            player.position=1; fixture.phase++;
        } else if (fixture.phase===6 && engine.currentLine===0) {
            fixture.checks.seek=engine.currentText==="Opening line";
            first.expanded=false; second.expanded=false; fixture.phase++;
        } else if (fixture.phase===7 && engine.readers===0 && !engine.wanted) {
            fixture.checks.idle=!engine.lookup.active && !engine.drift.running && !engine.boundary.running;
            player.play(); fixture.phase++;
        } else if (fixture.phase===8 && player.isPlaying && engine.wanted) {
            fixture.checks.resumed=ActivityState.title==="Opening line";
            fixture.setting("activityLyrics",false); fixture.phase++;
        } else if (fixture.phase===9 && ShellState.preferences.activityLyrics===false) {
            fixture.checks.disabled=!engine.wanted && ActivityState.title==="Native track";
            player.next(); fixture.setting("activityLyrics",true); fixture.phase++;
        } else if (fixture.phase===10 && engine.lyricData.status==="offline") {
            fixture.checks.fallback=ActivityState.title==="Next track" && engine.lines.length===0;
            fixture.setting("lyricsEnabled",false); fixture.phase++;
        } else if (fixture.phase===11 && ShellState.preferences.lyricsEnabled===false) {
            fixture.checks.off=!engine.wanted && !engine.drift.running;
            fixture.finish(fixture.checks);
        }
    } }
''', {'LME_SHELL_DEMO':'0','LME_SHELL_BACKEND_DEMO':'1'})
                self.assertEqual(result, {key:True for key in ('automatic','shared','defaults','manual','reopened','line','scroll','boundary','paused','seek','idle','resumed','disabled','fallback','off')})
            finally:
                player.terminate(); player.wait(timeout=5)

    def test_plain_lyrics_and_players_without_timing_stay_readable(self):
        repo = Path(__file__).resolve().parents[1]
        for flag in ('--plain-lyrics','--no-position'):
            with self.subTest(flag=flag), tempfile.TemporaryFile(mode='w+') as log:
                player = subprocess.Popen(['/usr/bin/python3',str(repo/'tests/mpris_fixture.py'),'--lyrics',flag],stdout=log,stderr=log)
                try:
                    result = self.run_qml('import "qml/components"\nimport "qml/services"', '''
    property int ticks: 0
    function find(item,name) { if(item.objectName===name) return item; for(const child of item.children || []) { const found=find(child,name); if(found) return found; } return null; }
    FloatingWindow { implicitWidth: 500; implicitHeight: 500; LyricsView { id: lyrics; width: 460; expanded: true; player: ActivityState.player } }
    Timer { interval: 60; running: true; repeat: true; onTriggered: {
        if (++fixture.ticks>100) { fixture.finish({timeout:true}); return; }
        if (!ShellState.backendReady) return;
        if (ShellState.preferences.lyricsMode!=="line") { if (!ShellState.pendingActions.setting) ShellState.run("setting",{key:"lyricsMode",value:"line"}); return; }
        const engine=lyrics.session;
        if(engine.lyricData.status!=="ready") return;
        fixture.finish({title:ActivityState.title, current:engine.currentText, ticking:engine.ticking,
            plain:fixture.find(lyrics,"lyricsPlain").visible, transcript:fixture.find(lyrics,"lyricsTranscript").visible});
    } }
''', {'LME_SHELL_DEMO':'0','LME_SHELL_BACKEND_DEMO':'1'})
                    self.assertEqual(result, dict(title='Native track', current='', ticking=False,
                                                  plain=flag=='--plain-lyrics', transcript=flag=='--no-position'))
                finally:
                    player.terminate(); player.wait(timeout=5)
