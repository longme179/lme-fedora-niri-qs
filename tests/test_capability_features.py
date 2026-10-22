"""Stateful-feature characterization before catalog conversion; withdrawal afterward."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from capability_feature_fixture import FeatureWorld, ROOT, converted

@unittest.skipUnless(os.environ.get('LME_TEST_CAPABILITY_UI')=='1','private stateful capability checks')
class NativeStatefulCapabilityCase(unittest.TestCase):
    def world(self):
        directory=tempfile.TemporaryDirectory(prefix='cap-feature-');self.addCleanup(directory.cleanup)
        return FeatureWorld(Path(directory.name))
    def test_live_server_history_mute_dnd_center_suppression_and_reload(self):
        world=self.world()
        with world.launch('shell') as probe:
            probe.wait(lambda s:probe.owns_server())
            first=probe.notify('First native title');probe.wait(lambda s:any(e['id']==first and e['popup'] for e in s['history']))
            probe.call('mute','ContractApp','true');probe.wait(lambda s:'ContractApp' in s['preferences']['notificationMutedApps'])
            second=probe.notify('Muted native title')
            state=probe.wait(lambda s:any(e['id']==second for e in s['history']))
            self.assertFalse(next(e for e in state['history'] if e['id']==second)['popup'])
            probe.call('mute','ContractApp','false');probe.wait(lambda s:not s['preferences']['notificationMutedApps'])
            probe.call('dnd','-1');probe.wait(lambda s:s['preferences']['dndUntil']==-1)
            third=probe.notify('DND native title');state=probe.wait(lambda s:any(e['id']==third for e in s['history']))
            self.assertFalse(next(e for e in state['history'] if e['id']==third)['popup'])
            probe.call('dnd','0');probe.wait(lambda s:s['preferences']['dndUntil']==0)
            probe.call('toggle','notifications',target='shell');probe.wait(lambda s:s['notificationsOpen'] and s['unread']==0)
            fourth=probe.notify('Center native title');state=probe.wait(lambda s:any(e['id']==fourth for e in s['history']))
            self.assertFalse(next(e for e in state['history'] if e['id']==fourth)['popup'])
            self.assertEqual(next(e for e in state['history'] if e['id']==first)['body'],'Literal <body>')
            history=world.settings.parent/'notification-history.json'
            probe.wait(lambda s:history.exists() and len(json.loads(history.read_text()))==4)
        with world.launch('shell') as probe:
            state=probe.wait(lambda s:len(s['history'])==4)
            self.assertEqual({e['summary'] for e in state['history']},{'First native title','Muted native title','DND native title','Center native title'})
            self.assertTrue(all(not e['active'] and not e['popup'] for e in state['history']))

    def test_desktop_contexts_and_about_cli_preserve_current_lifecycle(self):
        world=self.world();saved=json.loads(world.settings.read_text())
        saved.update(desktopEnabled=True,desktopShapes=True,desktopWidgets={'one':dict(type='clock',output='primary',x=.2,y=.2,width=320,height=200,enabled=True,interactive=False)})
        world.settings.write_text(json.dumps(saved))
        for mode in ('shell','demo','preview','settings'):
            with self.subTest(mode=mode),world.launch(mode) as probe:
                expected=int(mode in ('shell','demo'))
                state=probe.wait(lambda s:s['windows']==expected and s['ambient']==expected)
                self.assertEqual(state['windows'],expected)
                if mode!='shell':self.assertFalse(probe.owns_server())
        with world.launch('settings',page='about') as probe:
            state=probe.wait(lambda s:s['about']);self.assertEqual(state['page'],'about')
            self.assertEqual(probe.call('startupPending',target='settings'),'false')

    def test_notification_withdrawal_has_no_server_ui_or_history_writes_and_reenables(self):
        if not converted('notifications'):self.skipTest('Notifications unconverted on baseline; withdrawal N/A')
        world=self.world();world.toggle('notifications',False)
        original=world.settings.read_bytes();history=world.settings.parent/'notification-history.json';history.write_bytes(b'[]')
        with world.launch('shell') as probe:
            state=probe.wait(lambda s:s['ready'])
            self.assertFalse(probe.owns_server());self.assertNotIn('notifications',state['pages']);self.assertNotIn('notifications',state['bars'])
            self.assertNotIn('notifications',[t['id'] for t in state['tabs']])
            probe.call('local');probe.call('mute','ContractApp','true');probe.call('dnd','-1')
            probe.call('toggle','notifications',target='shell')
            state=probe.wait(lambda s:True);self.assertFalse(state['panelOpen']);self.assertFalse(state['notificationsOpen'])
            # Wait through the existing persistence debounce without changing a timeout.
            started=time.monotonic();probe.wait(lambda s:time.monotonic()-started>1)
        self.assertEqual(world.settings.read_bytes(),original);self.assertEqual(history.read_bytes(),b'[]')
        world.toggle('notifications',True)
        with world.launch('shell') as probe:probe.wait(lambda s:probe.owns_server())
