"""Lyric parsing, offline lookup, bounded cache and optional MPRIS UI checks."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock
from test_backend import backend
import lyrics
import test_local_qml as qml_tests


class LyricsCase(unittest.TestCase):
    def test_lrc_offsets_fractional_multiple_stamps_and_duplicate_lines(self):
        parsed = lyrics.parse('[ar:Test]\n[offset:100]\n[00:01.50][01:02.123] Hello\n[00:01.50] Translation\n[00:03]')
        self.assertTrue(parsed['synced'])
        self.assertEqual(parsed['lines'], [{'time':1.4,'text':'Hello\nTranslation'}, {'time':2.9,'text':''}, {'time':62.023,'text':'Hello'}])
        self.assertEqual(lyrics.parse('A plain line\nAnother')['plain'], 'A plain line\nAnother')
        with self.assertRaises(ValueError): lyrics.parse('x'*(lyrics.MAX_BYTES+1))
        with self.assertRaises(ValueError): lyrics.parse('[00:01]'*3000+'x'*1000)

    def test_embedded_sidecar_and_cache_precede_network(self):
        opener = Mock(return_value={'syncedLyrics':'[00:01] Network lyric'})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); cache = root/'cache'
            base = dict(title='Track',artist='Artist',duration=120,online=True)
            self.assertEqual(lyrics.lookup(dict(base,embedded='[00:00] Embedded'),cache,opener)['source'],'Player metadata')
            audio = root/'track name.ogg'; audio.touch(); audio.with_suffix('.lrc').write_text('[00:00] Local')
            self.assertEqual(lyrics.lookup(dict(base,url=audio.as_uri()),cache,opener)['source'],'Local LRC')
            opener.assert_not_called()
            self.assertEqual(lyrics.lookup(base,cache,opener)['status'],'ready')
            self.assertEqual(lyrics.lookup(dict(base,online=False),cache,opener)['source'],'LRCLIB · cached')
            opener.assert_called_once()
            self.assertEqual(lyrics.lookup(dict(base,title='Other',online=False),cache,opener)['status'],'offline')
            self.assertEqual(lyrics.lookup(dict(base,artist=''),cache,opener)['status'],'metadata')

    def test_instrumental_negative_cache_validation_and_corrupt_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            cache=Path(directory); request=dict(title='Track',artist='Artist',online=True)
            opener=Mock(return_value={'instrumental':True})
            self.assertEqual(lyrics.lookup(request,cache,opener)['status'],'instrumental')
            self.assertEqual(lyrics.lookup(request,cache,opener)['status'],'instrumental')
            opener.assert_called_once()
            next(cache.glob('*.json')).write_text('{bad')
            self.assertEqual(lyrics.lookup(request,cache,lambda p:{})['status'],'none')
            for field,value in [('duration',float('nan')),('duration',True),('title',[]),('online',1)]:
                with self.assertRaises(ValueError): lyrics.lookup(dict(request,**{field:value}),cache,opener)
        for key in ('lyricsEnabled','lyricsOnline'):
            self.assertIs(backend.validate_preference(key,False),False)


@unittest.skipUnless(os.environ.get('LME_TEST_LYRICS_UI') == '1', 'requires private MPRIS/D-Bus session')
class LyricsQmlCase(unittest.TestCase):
    run_qml=qml_tests.LocalQmlCase.run_qml

    def test_embedded_lyrics_follow_seek_pause_track_and_visibility(self):
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryFile(mode='w+') as log:
            player=subprocess.Popen(['/usr/bin/python3',str(repo/'tests/mpris_fixture.py'),'--lyrics'],stdout=log,stderr=log)
            try:
                result=self.run_qml('import Quickshell.Services.Mpris\nimport "qml/components"', '''
    property var player: Mpris.players.values[0] || null
    property int phase: 0
    property int ticks: 0
    property var checks: ({})
    FloatingWindow { implicitWidth: 500; implicitHeight: 500; LyricsView { id: lyrics; width: 460; expanded: true; player: fixture.player } }
    Timer { interval: 100; running: true; repeat: true; onTriggered: {
        if (++fixture.ticks > 100) { fixture.finish({timeout:fixture.phase,data:lyrics.lyricData}); return; }
        if (!fixture.player) return;
        if (fixture.phase === 0 && lyrics.lyricData.status === "ready") { fixture.player.pause(); fixture.phase++; }
        else if (fixture.phase === 1 && !fixture.player.isPlaying) { fixture.player.position=36; fixture.phase++; }
        else if (fixture.phase === 2 && lyrics.currentLine===2) {
            fixture.checks.follow=true; lyrics.visible=false; fixture.checks.hidden=!lyrics.active; lyrics.visible=true; fixture.phase++;
        } else if (fixture.phase === 3 && lyrics.active && lyrics.lyricData.status === "ready") {
            fixture.checks.reopened=true; fixture.player.next(); fixture.phase++;
        } else if (fixture.phase === 4 && lyrics.lyricData.status === "offline") {
            fixture.checks.cleared=lyrics.lines.length===0; fixture.finish(fixture.checks);
        }
    } }
''',{'LME_SHELL_DEMO':'0','LME_SHELL_BACKEND_DEMO':'1'})
                self.assertEqual(result,dict(follow=True,hidden=True,reopened=True,cleared=True))
            finally:
                player.terminate();player.wait(timeout=5)
