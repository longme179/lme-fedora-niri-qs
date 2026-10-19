"""Playlists use one awww owner and retain known-good per-display preferences."""
import copy
import unittest
from unittest.mock import patch
from test_backend import Fixture, FakeRunner, backend
from wallpaper import query_outputs
from settings_transfer import document

QUERY='awww-daemon: eDP-1: 1920x1080, scale: 1, currently displaying: image: /old.png\nHDMI-A-1: 1920x1080, scale: 1, currently displaying: color: 000000'


class WallpaperPlaybackCase(Fixture, unittest.TestCase):
    def controller(self):
        live=self.make_backend(FakeRunner({('awww','query'):QUERY},available={'awww'}))
        self.addCleanup(live.feature_executor.shutdown,wait=True,cancel_futures=True)
        self.addCleanup(live.wallpapers.close)
        return live

    def complete(self,live,request):
        first=live.handle(request)
        if first.get('pending'):
            live.feature_jobs[request['action']].exception(timeout=2)
            live.finish_features()
        return live.last_result

    def test_preferences_merge_and_backup_excludes_private_paths_from_presets(self):
        a=str(self.put('images/one.png','image'))
        self.preferences.set('wallpaperPlaylist',[a,a,str(self.root/'missing.png')])
        self.assertEqual(len(self.preferences.values['wallpaperPlaylist']),2)
        other=backend.Preferences(self.preferences.path)
        self.preferences.set('wallpaperOutputs',a,token='eDP-1')
        other.set('wallpaperOutputs',a,token='HDMI-A-1')
        self.preferences.reload()
        self.assertEqual(set(self.preferences.values['wallpaperOutputs']),{'eDP-1','HDMI-A-1'})
        self.preferences.set('wallpaperOutputs',None,token='eDP-1')
        self.assertEqual(self.preferences.values['wallpaperOutputs'],{'HDMI-A-1':a})
        saved=self.preferences.path.read_bytes()
        for key,value in [('wallpaperPlaylist',[a]*501),('wallpaperPlaylist',['relative.png']),('wallpaperPlaylist',['/bad\0.png']),('wallpaperPlaylistInterval',True),('wallpaperPlaylistInterval',29),('wallpaperPlaylistInterval',86401),('wallpaperOutputs',{'--help':a}),('wallpaperTransition','invalid'),('wallpaperTransition',[]),('wallpaperTransitionDuration',float('nan')),('wallpaperTransitionDuration',float('inf')),('wallpaperTransitionDuration',10**1000)]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError): self.preferences.set(key,value)
        self.assertEqual(self.preferences.path.read_bytes(),saved)
        preset=document(self.preferences.values,'preset')['settings']
        self.assertNotIn('wallpaperPlaylist',preset);self.assertNotIn('wallpaperOutputs',preset);self.assertNotIn('wallpaperPlaylistOutput',preset)
        self.assertIn('wallpaperTransition',preset)
        self.assertIn(a,document(self.preferences.values,'backup')['settings']['wallpaperPlaylist'])

    def test_query_formats_targeting_shared_overrides_and_disconnected_restore(self):
        self.assertEqual(query_outputs(QUERY),{'eDP-1','HDMI-A-1'})
        live=self.controller();a=str(self.put('a.png','a'));b=str(self.put('b.png','b'))
        self.preferences.set('wallpaperOutputs',b,token='HDMI-A-1')
        result=self.complete(live,dict(action='wallpaper',path=a))
        self.assertTrue(result['ok'],result)
        self.assertEqual(live.runner.calls[-1],('awww','img',a,'--transition-type','fade','--outputs','eDP-1'))
        result=self.complete(live,dict(action='wallpaper',path=a,output='DP-3'))
        self.assertTrue(result['ok'],result)
        self.assertIn('disconnected',result['message'])
        self.assertEqual(self.preferences.values['wallpaperOutputs']['DP-3'],a)
        self.assertFalse(any(call[1]=='img' and call[-1]=='DP-3' for call in live.runner.calls))
        # A reconnected output is restored once, without replaying transitions.
        self.assertIsNone(live.wallpapers.due({'eDP-1'},now=0))
        live.runner.responses[('awww','query')]=QUERY+'\nDP-3: 800x600, scale: 1, currently displaying: color: 000000'
        job=live.wallpapers.due({'eDP-1','DP-3'},now=1);self.assertIsNotNone(job);job()
        self.assertIn(('awww','img',a,'--transition-type','none','--outputs','DP-3'),live.runner.calls)
        self.assertIsNone(live.wallpapers.due({'eDP-1','DP-3'},now=2))
        self.assertTrue(self.complete(live,dict(action='wallpaperResetOutput',output='HDMI-A-1'))['ok'])
        self.assertNotIn('HDMI-A-1',self.preferences.values['wallpaperOutputs'])

    def test_order_shuffle_missing_single_and_decode_failure_keep_good_image(self):
        live=self.controller();a=str(self.put('a.png','a'));b=str(self.put('b.png','b'));c=str(self.put('c.png','c'))
        self.preferences.update({'wallpaper':a,'wallpaperPlaylist':[a,str(self.root/'missing.png'),b,c]})
        live.runner.responses[('awww','img',b,'--transition-type','fade','--outputs','HDMI-A-1,eDP-1')]=backend.CommandError('Bad image')
        self.assertTrue(self.complete(live,dict(action='wallpaperNext'))['ok'])
        self.assertEqual(self.preferences.values['wallpaper'],c)
        self.preferences.set('wallpaperPlaylistShuffle',True)
        self.assertTrue(self.complete(live,dict(action='wallpaperNext'))['ok'])
        self.assertNotEqual(self.preferences.values['wallpaper'],c)
        active=self.preferences.values['wallpaper'];self.preferences.set('wallpaperPlaylist',[active]);live.runner.calls.clear()
        live.wallpapers.advance()
        self.assertEqual(live.runner.calls,[])
        self.preferences.update({'wallpaperPlaylist':[active,b],'wallpaperPlaylistShuffle':False})
        self.assertFalse(self.complete(live,dict(action='wallpaperNext'))['ok'])
        self.assertEqual(self.preferences.values['wallpaper'],active)
        self.preferences.set('wallpaperPlaylist',[str(self.root/'gone.png')])
        self.assertFalse(self.complete(live,dict(action='wallpaperNext'))['ok'])
        self.assertEqual(self.preferences.values['wallpaper'],active)

    def test_pause_resume_suspend_and_disabled_do_not_catch_up_or_poll_awww(self):
        live=self.controller();a=str(self.put('a.png','a'));b=str(self.put('b.png','b'))
        self.preferences.update({'wallpaper':a,'wallpaperPlaylist':[a,b],'wallpaperPlaylistInterval':30})
        self.assertIsNone(live.wallpapers.due({'eDP-1'},now=0));self.assertIsNone(live.wallpapers.deadline)
        self.preferences.set('wallpaperPlaylistEnabled',True)
        self.assertIsNone(live.wallpapers.due({'eDP-1'},now=5));self.assertEqual(live.wallpapers.deadline,35)
        self.preferences.set('wallpaperPlaylistPaused',True)
        live.wallpapers.due({'eDP-1'},now=15);self.assertIsNone(live.wallpapers.deadline)
        self.preferences.set('wallpaperPlaylistPaused',False)
        live.wallpapers.due({'eDP-1'},now=100);self.assertEqual(live.wallpapers.deadline,120)
        job=live.wallpapers.due({'eDP-1'},now=10000);self.assertIsNotNone(job)
        self.assertEqual(live.wallpapers.deadline,10030)
        self.assertEqual(live.runner.calls,[])
        job();self.assertEqual(self.preferences.values['wallpaper'],b)

    def test_transition_reduced_motion_failure_lock_and_shutdown(self):
        live=self.controller();a=str(self.put('a.png','a'));b=str(self.put('b.png','b'))
        self.preferences.update({'wallpaperTransition':'wave','wallpaperTransitionDuration':1.2})
        live.wallpapers.apply(a,output='eDP-1')
        self.assertEqual(live.runner.calls[-1][-2:],('--transition-duration','1.2'))
        self.preferences.set('animations',False);live.wallpapers.apply(a)
        self.assertIn('none',live.runner.calls[-1])
        with live.wallpapers.operation():
            other=self.controller()
            with self.assertRaisesRegex(ValueError,'Another wallpaper'): other.wallpapers.apply(b)
        self.assertEqual(self.preferences.values['wallpaper'],a)
        before=copy.deepcopy(self.preferences.values)
        live.runner.responses[('awww','img',b,'--transition-type','none','--outputs','eDP-1')]=backend.CommandError('Failed')
        self.assertFalse(self.complete(live,dict(action='wallpaper',path=b,output='eDP-1'))['ok'])
        self.assertEqual(self.preferences.values,before)
        live.wallpapers.close();calls=list(live.runner.calls)
        with self.assertRaises(ValueError): live.wallpapers.apply(b)
        self.assertEqual(live.runner.calls,calls)

    def test_pending_operations_do_not_block_other_actions_or_write_after_shutdown(self):
        from test_features import ManualExecutor
        live=self.controller();live.feature_executor.shutdown(wait=True);live.feature_executor=ManualExecutor()
        image=str(self.put('wallpaper.png','image'))
        result=live.handle(dict(action='wallpaper',path=image))
        self.assertTrue(result['pending']);self.assertEqual(live.runner.calls,[])
        self.assertFalse(live.handle(dict(action='wallpaperNext'))['ok'])
        self.assertEqual(live.handle(dict(action='calculate',query='6*7'))['message'],'42')
        live.wallpapers.close();live.feature_executor.complete();live.finish_features()
        self.assertFalse(live.last_result['ok'])
        self.assertFalse(self.preferences.path.exists());self.assertEqual(live.runner.calls,[])

    def test_queued_cycle_rechecks_pause_disable_and_output_before_starting(self):
        for change in ({'wallpaperPlaylistPaused':True},{'wallpaperPlaylistEnabled':False},{'wallpaperPlaylistOutput':'HDMI-A-1'}):
            with self.subTest(change=change):
                live=self.controller();a=str(self.put('a.png','a'));b=str(self.put('b.png','b'))
                self.preferences.update({'wallpaper':a,'wallpaperOutputs':{},'wallpaperPlaylist':[a,b],'wallpaperPlaylistEnabled':True,'wallpaperPlaylistPaused':False,'wallpaperPlaylistOutput':'','wallpaperPlaylistInterval':30})
                self.assertIsNone(live.wallpapers.due({'eDP-1'},now=0))
                job=live.wallpapers.due({'eDP-1'},now=31);self.assertIsNotNone(job)
                self.preferences.update(change);self.assertEqual(job(),'')
                self.assertEqual(live.runner.calls,[]);self.assertEqual(self.preferences.values['wallpaper'],a)
                # Explicit Next is independent of the automatic playback switch.
                live.wallpapers.advance('');self.assertEqual(self.preferences.values['wallpaper'],b)

    def test_symlinks_are_validated_after_resolution_and_reload_without_losing_playlist(self):
        image=self.put('actual.jpg','image');link=self.root/'link.png';link.symlink_to(image)
        self.preferences.set('wallpaperPlaylist',[str(link)])
        self.assertEqual(backend.Preferences(self.preferences.path).values['wallpaperPlaylist'],[str(image)])
        bad=self.put('not-image.txt','text');link.unlink();link.symlink_to(bad)
        before=self.preferences.path.read_bytes()
        with self.assertRaises(ValueError): self.preferences.set('wallpaperPlaylist',[str(link)])
        self.assertEqual(self.preferences.path.read_bytes(),before)
