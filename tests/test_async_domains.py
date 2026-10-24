"""Golden dispatch/staging contracts for the authorized asynchronous families."""
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from async_domain_fixture import ACTIONS, configured, trace
from backend_actions import ActionSpec, ActionRegistry
from test_backend import Fixture, backend

PREPARED = 'prepare' in inspect.signature(ActionSpec).parameters
GOLDEN = Path(__file__).with_name('fixtures')/'async-domains.json'


class AsyncDomainsCase(Fixture, unittest.TestCase):
    def test_all_context_demo_ack_completion_calls_and_projection_match_baseline(self):
        golden=json.loads(GOLDEN.read_text())
        for demo in (False,True):
            for settings in (False,True):
                for action in ACTIONS:
                    with self.subTest(action=action,demo=demo,settings=settings):
                        self.assertEqual(trace(self,action,demo,settings),golden[f'{action}/{int(demo)}/{int(settings)}'])

    def test_preflight_errors_do_not_claim_ownership_and_keep_messages(self):
        for action, request, message in (
            ('fileSearch',dict(query='x'),'File search needs 2–160 characters'),
            ('batterySaver',dict(enabled=1),'Battery saver must be enabled or disabled'),
            ('recordStart',dict(output='gone'),'Choose a connected niri output'),
            ('captureAnnotate',dict(token='old'),'This screenshot session has ended'),
            ('captureExport',{},'Missing screenshot session'),
            ('chargeMode',dict(value=True),'Choose conservation (85) or maximum charge (100).')):
            live,_,_ = configured(self)
            with self.subTest(action=action):
                self.assertEqual(live.handle(dict(action=action,**request)),
                    dict(ok=False,action=action,message=message,sequence=1))
                self.assertFalse(live.feature_jobs);self.assertIsNone(live.charge_job)

    def test_request_time_options_remain_frozen_while_worker_is_queued(self):
        live,events,requests = configured(self)
        self.assertTrue(live.handle(dict(action='imageAnnotate',**requests['imageAnnotate']))['pending'])
        live.preferences.values['captureEditor']='swappy'
        live.feature_executor.complete();live.finish_features()
        self.assertEqual(events[-1][0],'image_annotate');self.assertEqual(events[-1][1][1],'satty')
        live,events,requests = configured(self)
        live.preferences.values['recordingFps']=60
        self.assertTrue(live.handle(dict(action='recordStart',**requests['recordStart']))['pending'])
        live.preferences.values['recordingFps']=24
        live.feature_executor.complete();live.finish_features()
        record=next(event for event in events if event[0]=='record_start')
        self.assertEqual(record[1][-2],60)

    def test_prefix_guards_precede_ownership_and_keep_duplicate_messages(self):
        from concurrent.futures import Future
        for action,existing,message in (('wallpaperNext','wallpaperScan','A wallpaper change is already running'),
            ('gowallGenerate','gowallSave','A gowall operation is already running')):
            live,_,requests=configured(self);owner=Future();live.feature_jobs[existing]=owner
            self.assertEqual(live.handle(dict(action=action,**requests[action])),
                dict(ok=False,action=action,message=message,sequence=1))
            self.assertEqual(live.feature_jobs,{existing:owner})

    def test_file_replacement_and_capture_token_discard_keep_existing_owners(self):
        live,_,requests=configured(self)
        live.handle(dict(action='fileSearch',**requests['fileSearch']))
        previous=live.feature_jobs['fileSearch'];cancel=live.file_search_cancel
        live.handle(dict(action='fileSearch',query='other'))
        self.assertTrue(previous.cancelled());self.assertTrue(cancel.is_set())
        self.assertIsNot(live.feature_jobs['fileSearch'],previous)
        live,_,requests=configured(self)
        live.handle(dict(action='captureOcr',**requests['captureOcr']))
        self.assertEqual(live.feature_jobs['captureOcr'].capture_token,'lease')
        live.capture.state['token']='new'
        live.feature_executor.complete();live.finish_features()
        self.assertEqual(live.last_result,dict(ok=True,action='captureOcr',message='',sequence=2))
        self.assertFalse(live.feature_jobs)

    @unittest.skipUnless(PREPARED,'prepared-worker seam unavailable on baseline')
    def test_prepare_is_after_context_before_queue_and_demo_never_prepares(self):
        from backend_actions import PreparedWork
        work=Mock();prepare=Mock(return_value=PreparedWork(work,{'capture_token':'lease'}));queue=Mock(return_value='Working…')
        spec=ActionSpec('capture',{'shell'},Mock(),Mock(),execution='worker',complete=Mock(),prepare=prepare)
        registry=ActionRegistry([spec],start_feature=queue)
        with self.assertRaisesRegex(ValueError,'unavailable'):
            registry.dispatch('capture',{},context='settings',demo=True)
        prepare.assert_not_called();queue.assert_not_called()
        registry.dispatch('capture',{},context='shell',demo=True);prepare.assert_not_called()
        self.assertEqual(registry.dispatch('capture',{'token':'lease'},context='shell',demo=False),'Working…')
        queue.assert_called_once_with('capture',work,metadata={'capture_token':'lease'});work.assert_not_called()


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--write-golden']:
        case=AsyncDomainsCase();case.setUp()
        try:
            records={f'{a}/{int(d)}/{int(s)}':trace(case,a,d,s) for d in (False,True) for s in (False,True) for a in ACTIONS}
            GOLDEN.write_text('{\n'+',\n'.join(json.dumps(k)+':'+json.dumps(v,ensure_ascii=False,separators=(',',':')) for k,v in records.items())+'\n}\n')
        finally:case.doCleanups()
    else:unittest.main()
