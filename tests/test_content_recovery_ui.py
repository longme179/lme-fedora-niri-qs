"""Copied-checkout native probes for burst results and durable history recovery."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from clipboard_slice_fixture import World

OBSERVE = '''
    property var recoveryCopies: []
    property var recoverySearches: []
    Connections {
        target: ClipboardState
        function onCopied() { root.recoveryCopies = root.recoveryCopies.concat(ClipboardState.lastResult.sequence); }
        function onSearched(success) { if (success) root.recoverySearches = root.recoverySearches.concat([ClipboardState.entries.map(e => e.preview)]); }
    }
    IpcHandler {
        target: "contentRecovery"
        function state(): string {
            return JSON.stringify({ready:ClipboardState.ready,copyPending:ClipboardState.copyPending,
                searching:ClipboardState.searching,copies:root.recoveryCopies,searches:root.recoverySearches,
                result:ClipboardState.lastResult,open:ShellState.clipboardOpen});
        }
        function burst(): void {
            const id = ClipboardState.entries.find(e => e.kind === "text").id;
            ClipboardState.copyPending = true;
            ClipboardState.searching = true;
            ClipboardState.backend.write(JSON.stringify({action:"copy",id})+"\\n"+
                JSON.stringify({action:"search",query:"persisted",kind:"all"})+"\\n");
        }
        function searches(): void {
            ClipboardState.search("absent","all"); ClipboardState.search("persisted","all");
        }
        function enterSearch(): void {
            ClipboardState.search("absent","all");
            const field = root.sliceFind(root.sliceSurface,"Search clipboard history");
            field.text = "persisted"; field.accepted();
        }
    }
'''


@unittest.skipUnless(os.environ.get('LME_TEST_CONTENT_RECOVERY') == '1', 'private Wayland content recovery')
class ClipboardRecoveryUiCase(unittest.TestCase):
    def test_burst_copy_search_closes_and_reopens_without_stuck_pending(self):
        with tempfile.TemporaryDirectory(prefix='content-ui-') as directory:
            world = World(Path(directory))
            shell = world.root/'shell.qml'
            shell.write_text(shell.read_text().replace('    id: root\n', '    id: root\n'+OBSERVE, 1))
            with world.launch() as probe:
                probe.wait(lambda s:s['workerReady'] and s['count'] == 2)
                probe.call('toggle','clipboard',target='shell');probe.wait(lambda s:s['open'] and s['history'])
                probe.call('burst',target='contentRecovery')
                probe.wait(lambda s:not s['open'])
                state = json.loads(probe.call('state',target='contentRecovery'))
                self.assertFalse(state['copyPending']);self.assertEqual(len(state['copies']),1)
                probe.call('toggle','clipboard',target='shell');probe.wait(lambda s:s['open'] and s['history'])
                before = json.loads(probe.call('state',target='contentRecovery'))
                probe.call('searches',target='contentRecovery')
                probe.wait(lambda s:(json.loads(probe.call('state',target='contentRecovery'))['result'] or {}).get('sequence',0) >= before['result']['sequence']+2)
                state = json.loads(probe.call('state',target='contentRecovery'))
                self.assertFalse(state['searching'])
                self.assertEqual(len(state['searches']), len(before['searches'])+1)
                self.assertTrue(state['searches'][-1])
                probe.call('enterSearch',target='contentRecovery')
                probe.wait(lambda s:not s['open'])
                state = json.loads(probe.call('state',target='contentRecovery'))
                self.assertEqual(len(state['copies']),2)
                self.assertEqual(len(world.workers()),1)

