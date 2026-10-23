"""History persistence recovery through the real UI/backend in a copied checkout."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from clipboard_slice_fixture import World

OBSERVE = '''
    property int recoverySaveCount: 0
    Connections {
        target: ShellState
        function onLastResultChanged() {
            const r = ShellState.lastResult;
            if (r && r.action === "notificationSave" && !r.pending) root.recoverySaveCount++;
        }
    }
    IpcHandler {
        target: "notificationRecovery"
        function state(): string {
            return JSON.stringify({loaded:Notifications.historyLoaded,history:Notifications.history,
                dirty:Notifications.historyDirty === true,saving:Notifications.saving === true,
                error:String(Notifications.saveError || ""),count:root.recoverySaveCount,
                result:ShellState.lastResult,status:ShellState.statusMessage,
                retry:!!root.sliceFind(root.sliceSurface,"notificationSaveRetry")});
        }
        function add(summary: string): void {
            Notifications.history = [{id:"recovery-"+summary,appName:"RecoveryApp",summary,body:"Body",
                timestamp:Date.now(),urgency:1,actions:[],active:false,popup:false,transient:false},...Notifications.history];
        }
        function restartBackend(): void { ShellState.backend.running = false; }
    }
'''


@unittest.skipUnless(os.environ.get('LME_TEST_CONTENT_RECOVERY') == '1', 'private Wayland notification recovery')
class NotificationRecoveryUiCase(unittest.TestCase):
    def world(self):
        temp = tempfile.TemporaryDirectory(prefix='notif-recovery-');self.addCleanup(temp.cleanup)
        world = World(Path(temp.name))
        shell = world.root/'shell.qml'
        shell.write_text(shell.read_text().replace('    id: root\n','    id: root\n'+OBSERVE,1))
        hold, started = world.home/'hold-save', world.home/'save-started'
        # Instrument only the copy: hold a real atomic write without a production hook.
        actions = world.root/'scripts/local_content_actions.py'
        text = actions.read_text().replace('from storage import write_json', 'from storage import write_json as original_write_json')
        text += '\nfrom pathlib import Path\nimport time\ndef write_json(path, value):\n'
        text += f'    if Path({str(hold)!r}).exists():\n        Path({str(started)!r}).touch()\n'
        text += f'        while Path({str(hold)!r}).exists(): time.sleep(.01)\n'
        text += '    return original_write_json(path, value)\n';actions.write_text(text)
        world.hold, world.started = hold, started
        return world

    def state(self, probe):
        return json.loads(probe.call('state',target='notificationRecovery'))

    def wait(self, probe, predicate):
        probe.wait(lambda _:predicate(self.state(probe)))
        return self.state(probe)

    def ready(self, probe):
        return self.wait(probe,lambda s:s['loaded'] and s['count'] > 0 and s['result']['ok'])

    def test_save_failure_is_visible_retryable_and_does_not_loop(self):
        world = self.world();history = world.settings.parent/'notification-history.json'
        with world.launch() as probe:
            self.ready(probe)
            original = history.read_bytes();backup = history.with_suffix('.saved')
            history.rename(backup);history.mkdir()
            probe.call('toggle','notifications',target='shell');probe.wait(lambda s:s['panelKind']=='notifications' and s['progress']==1)
            probe.call('add','Unsaved',target='notificationRecovery')
            failed = self.wait(probe,lambda s:s['result']['action']=='notificationSave' and not s['result']['ok'])
            self.assertTrue(failed['error']);self.assertTrue(failed['dirty']);self.assertTrue(failed['retry'])
            self.assertFalse(failed['saving']);self.assertEqual(failed['status'],'')
            before = time.monotonic();self.wait(probe,lambda s:time.monotonic()-before > 1.1)
            self.assertEqual(self.state(probe)['count'],failed['count'])
            self.assertEqual(backup.read_bytes(),original)
            self.assertEqual([e['summary'] for e in failed['history']],['Unsaved'])
            history.rmdir();backup.rename(history)
            probe.click('notificationSaveRetry')
            saved = self.wait(probe,lambda s:s['count'] > failed['count'] and not s['dirty'])
            self.assertEqual(saved['error'],'');self.assertFalse(saved['saving'])
            self.assertEqual(json.loads(history.read_text())[0]['summary'],'Unsaved')
            self.assertEqual(history.stat().st_mode & 0o777,0o600)
        with world.launch() as probe:
            restored = self.wait(probe,lambda s:s['loaded'] and len(s['history'])==1)
            self.assertEqual(restored['history'][0]['summary'],'Unsaved')
            self.assertFalse(restored['history'][0]['active'])

    def test_changes_during_save_are_coalesced_and_only_latest_revision_clears_dirty(self):
        world = self.world();history = world.settings.parent/'notification-history.json'
        with world.launch() as probe:
            initial = self.ready(probe);world.hold.touch()
            try:
                probe.call('add','First',target='notificationRecovery')
                during = self.wait(probe,lambda s:world.started.exists())
                self.assertTrue(during['saving']);self.assertTrue(during['dirty'])
                probe.call('add','Second',target='notificationRecovery')
                probe.call('add','Third',target='notificationRecovery')
                self.assertTrue(self.state(probe)['dirty'])
            finally:world.hold.unlink(missing_ok=True)
            final = self.wait(probe,lambda s:s['count']>=initial['count']+2 and not s['dirty'])
            self.assertEqual(final['count'],initial['count']+2)
            self.assertEqual([e['summary'] for e in json.loads(history.read_text())],['Third','Second','First'])
            self.assertFalse(final['saving']);self.assertEqual(final['error'],'')

    def test_backend_restart_recovers_dirty_history_after_a_failed_write(self):
        world = self.world();history = world.settings.parent/'notification-history.json'
        with world.launch() as probe:
            self.ready(probe);history.unlink();history.mkdir()
            probe.call('add','Reconnect',target='notificationRecovery')
            failed = self.wait(probe,lambda s:s['result']['action']=='notificationSave' and not s['result']['ok'])
            self.assertTrue(failed['dirty'])
            history.rmdir()
            probe.call('restartBackend',target='notificationRecovery')
            restored = self.wait(probe,lambda s:history.is_file() and not s['dirty'] and s['count']>failed['count'])
            self.assertFalse(restored['saving']);self.assertEqual(restored['error'],'')
            self.assertEqual(json.loads(history.read_text())[0]['summary'],'Reconnect')

