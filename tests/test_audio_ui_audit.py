"""Copied-checkout observer must retain audio results across unrelated acknowledgements.
Contract: test_audio_ui_audit.py covers audio_ui_audit behavior/contracts; check imports for fixtures/helpers under test.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest

from audio_ui_fixture import AudioWorld


@unittest.skipUnless(os.environ.get('LME_TEST_AUDIO_UI') == '1', 'private Wayland audio observer audit')
class NativeAudioObserverCase(unittest.TestCase):
    def test_notification_ack_cannot_hide_the_completed_audio_result_from_the_probe(self):
        with tempfile.TemporaryDirectory(prefix='audio-observer-') as directory:
            world = AudioWorld(Path(directory))
            path = world.root/'shell.qml'
            path.write_text(path.read_text().replace('        function cloneAudio(): void {', '''
        function simulateAcknowledgements(): void {
            ShellState.lastResult = {action:"audioRoute",ok:true,message:"Audited route",sequence:40};
            ShellState.lastResult = {action:"notificationSave",ok:true,message:"",sequence:41};
        }
        function cloneAudio(): void {'''))
            with world.launch('demo') as probe:
                probe.call('simulateAcknowledgements', target='audioHeadset')
                state = json.loads(probe.call('state', target='audioHeadset'))
                self.assertEqual(state['result'], dict(action='audioRoute', ok=True, message='Audited route', sequence=40))
