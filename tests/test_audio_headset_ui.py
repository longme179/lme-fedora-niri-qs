"""Audio UI characterization and later controls run only in private sessions."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from audio_ui_fixture import AudioWorld


@unittest.skipUnless(os.environ.get('LME_TEST_AUDIO_UI') == '1', 'private Wayland audio/headset UI')
class NativeAudioBaselineCase(unittest.TestCase):
    def test_existing_mixer_opens_closes_and_reopens_in_the_actual_shell(self):
        with tempfile.TemporaryDirectory(prefix='audio-ui-') as directory:
            world=AudioWorld(Path(directory))
            with world.launch('demo') as probe:
                for _ in range(2):
                    probe.call('open',target='audioHeadset')
                    probe.wait(lambda _:json.loads(probe.call('state',target='audioHeadset'))['heading'])
                    state=json.loads(probe.call('state',target='audioHeadset'))
                    self.assertEqual(state['labels'],['Audio devices & mixer','Output device','Input device','Applications'])
                    self.assertTrue(state['open'])
                    probe.call('close',target='shell')
                    probe.wait(lambda s:not s['panelOpen'])
