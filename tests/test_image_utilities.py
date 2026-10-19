"""Gowall adapter contracts and safe preview/export/apply lifecycle."""
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
from image_utilities import ImageUtilities, command, OPERATIONS
from test_backend import Fixture, FakeRunner, backend

class ImageUtilitiesCase(Fixture,unittest.TestCase):
    def tool(self):
        class Images(FakeRunner):
            def run(self,name,*args,**kwargs):
                result=super().run(name,*args,**kwargs)
                if '--output' in args: Path(args[args.index('--output')+1]).write_bytes(b'\x89PNG\r\n\x1a\nprocessed image')
                return result
        runner=Images({('gowall','list'):'\x1b[31mdracula\x1b[0m\nrose-pine\nnord\n'},available={'gowall'})
        live=self.make_backend(runner)
        self.addCleanup(live.feature_executor.shutdown,wait=True,cancel_futures=True)
        self.addCleanup(live.image_utilities.close)
        return live,live.image_utilities

    def test_options_build_real_cli_flags_without_shell_expansion(self):
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                args=command(operation,'/a b.png','/new.png',{})
                self.assertIn('/a b.png',args)
                self.assertNotIn('--yes',args)
                if operation!='extract': self.assertEqual(args[-4:],['--output','/new.png','--preview','false'])
        self.assertEqual(command('upscale','/a.png','/out.png',{'scale':4})[:4],['upscale','/a.png','--scale','4'])
        self.assertEqual(command('saturation','/a.png','/out.png',{'amount':20})[:5],['effects','saturation','/a.png','--percentage','20'])
        for operation,options in [('palette',{'theme':'--help'}),('upscale',{'scale':True}),('resize',{'dimensions':'0x0'}),('brightness',{'amount':float('nan')}),('extract',{'colors':200})]:
            with self.subTest(operation=operation),self.assertRaises(ValueError):command(operation,'/a','/b',options)

    def test_batch_preview_original_export_exclusive_and_failed_preview_retained(self):
        live,tool=self.tool();a=self.put('a.png','original');b=self.put('b.png','other')
        with patch.dict(os.environ,XDG_CACHE_HOME=str(self.root/'cache')):
            tool.state=tool.generate(dict(paths=[str(a),str(b)],operation='palette',options={'theme':'nord'}))
            self.assertEqual(len(tool.state['images']),2);self.assertEqual(a.read_text(),'original')
            image=tool.state['images'][0]['path'];destination=self.root/'saved.png'
            tool.save(image,str(destination));self.assertEqual(destination.read_bytes(),b'\x89PNG\r\n\x1a\nprocessed image')
            with self.assertRaises(FileExistsError): tool.save(image,str(destination))
            partial=self.root/'partial.png'
            with patch('image_utilities.shutil.copyfileobj',side_effect=OSError('disk full')):
                with self.assertRaises(OSError): tool.save(image,str(partial))
            self.assertFalse(partial.exists());self.assertTrue(destination.is_file())
            with self.assertRaises(ValueError): tool.save(image,str(self.root/'wrong.jpg'))
            old=dict(tool.state)
            with self.assertRaises(ValueError):tool.generate(dict(paths=[str(a)],operation='upscale',options={'scale':10}))
            self.assertEqual(tool.state,old);self.assertTrue(Path(image).is_file())
            self.assertEqual(tool.themes(),['dracula','nord','rose-pine'])
            self.assertEqual(a.read_text(),'original')

    def test_apply_persists_image_before_awww_and_export_rejects_foreign_paths(self):
        live,tool=self.tool();a=self.put('a.png','original')
        with patch.dict(os.environ,XDG_CACHE_HOME=str(self.root/'cache'),XDG_DATA_HOME=str(self.root/'data')):
            tool.state=tool.generate(dict(paths=[str(a)],operation='invert'))
            path=tool.state['images'][0]['path']
            with patch.object(live.wallpapers,'apply',return_value='Applied') as apply:
                self.assertEqual(tool.apply(path,'eDP-1'),'Applied')
                saved=Path(apply.call_args.args[0]);self.assertTrue(saved.is_file());self.assertNotEqual(saved,Path(path))
                self.assertEqual(apply.call_args.args[1],'eDP-1')
            with self.assertRaises(ValueError):tool.save(str(a),str(self.root/'bad.png'))
            with patch.object(live.wallpapers,'apply',side_effect=ValueError('failed')):
                with self.assertRaises(ValueError):tool.apply(path,'eDP-1')
            self.assertEqual(len(list(saved.parent.glob('*.png'))),1)

    def test_backend_jobs_publish_structured_results_and_demo_stays_inert(self):
        live,tool=self.tool()
        result=live.handle(dict(action='gowallThemes'));self.assertTrue(result['pending'])
        live.feature_jobs['gowallThemes'].result(timeout=2);live.finish_features()
        self.assertTrue(live.last_result['ok']);self.assertIn('nord',live.feature_snapshot()['imageUtilities']['themes'])
        with patch.object(tool.launchpad,'run',return_value='terminal opened') as launch:
            image=self.put('a.png','a');tool.setup(str(image),'kitty')
            command_text=launch.call_args.args[1]['gowall-setup']['command']
            self.assertIn('upscale',command_text);self.assertNotIn('--yes',command_text)
        demo=backend.DesktopBackend(demo=True,preferences=self.preferences)
        with patch('subprocess.Popen') as spawn:
            self.assertTrue(demo.handle(dict(action='gowallGenerate',paths=['/no.png']))['ok']);spawn.assert_not_called()

    def test_close_removes_owned_previews_and_preserves_exports_and_applied_wallpaper(self):
        live,tool=self.tool();source=self.put('original.png','original')
        request=dict(paths=[str(source)],operation='palette')
        with patch.dict(os.environ,XDG_CACHE_HOME=str(self.root/'cache'),XDG_DATA_HOME=str(self.root/'data')):
            tool.state=tool.generate(request)
            preview=Path(tool.state['images'][0]['path']);session=tool.session
            exported=self.root/'export.png';tool.save(str(preview),str(exported))
            with patch.object(live.wallpapers,'apply',return_value='Applied') as apply:
                tool.apply(str(preview),'eDP-1');applied=Path(apply.call_args.args[0])
            tool.close();tool.close()
            self.assertFalse(session.exists());self.assertFalse(preview.exists())
            self.assertTrue(exported.is_file());self.assertTrue(applied.is_file());self.assertTrue(source.is_file())
            with self.assertRaisesRegex(ValueError,'closing'):tool.generate(request)

    def test_active_instances_keep_separate_previews_and_reclaim_crashed_session(self):
        live,tool=self.tool();other_live,other=self.tool();source=self.put('original.png','original')
        request=dict(paths=[str(source)],operation='invert')
        with patch.dict(os.environ,XDG_CACHE_HOME=str(self.root/'cache')):
            tool.state=tool.generate(request);first=Path(tool.state['images'][0]['path'])
            other.state=other.generate(request);second=Path(other.state['images'][0]['path'])
            self.assertTrue(first.is_file());self.assertTrue(second.is_file());self.assertNotEqual(tool.session,other.session)
            code='from image_utilities import ImageUtilities; from pathlib import Path; import os; tool=ImageUtilities(None,None,None); cache=tool.cache(); (cache/"orphan.png").write_bytes(b"preview"); print(cache,flush=True); os._exit(0)'
            crashed=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=3,
                                   env={**os.environ,'PYTHONPATH':str(Path(backend.__file__).parent)})
            self.assertEqual(crashed.returncode,0,crashed.stderr)
            orphan=Path(crashed.stdout.strip());self.assertTrue((orphan/'orphan.png').exists())
            fresh_live,fresh=self.tool();fresh.state=fresh.generate(request)
            self.assertFalse(orphan.exists());self.assertTrue(first.is_file());self.assertTrue(second.is_file())
            tool.close();self.assertFalse(first.exists());self.assertTrue(second.is_file())

    def test_legacy_cache_cleanup_is_conservative_and_does_not_follow_symlinks(self):
        live,tool=self.tool();source=self.put('original.png','original')
        cache=self.root/'cache/lme-shell/gowall';cache.mkdir(parents=True)
        old=cache/'job-old';old.mkdir();(old/'preview.png').write_bytes(b'old preview')
        os.utime(old,(time.time()-90000,time.time()-90000))
        recent=cache/'job-recent';recent.mkdir();(recent/'preview.png').write_bytes(b'recent preview')
        outside=self.root/'outside';outside.mkdir();(outside/'keep.png').write_bytes(b'keep')
        (cache/'session-link').symlink_to(outside,target_is_directory=True)
        partial=cache/'session-interrupted';partial.mkdir();os.utime(partial,(time.time()-90000,time.time()-90000))
        fresh_partial=cache/'session-fresh';fresh_partial.mkdir()
        with patch.dict(os.environ,XDG_CACHE_HOME=str(self.root/'cache')):
            tool.state=tool.generate(dict(paths=[str(source)],operation='invert'))
        self.assertFalse(old.exists());self.assertFalse(partial.exists())
        self.assertTrue(recent.is_dir());self.assertTrue(fresh_partial.is_dir())
        self.assertTrue((outside/'keep.png').is_file());self.assertTrue((cache/'session-link').is_symlink())

    def test_held_cache_guard_does_not_block_shutdown(self):
        live,tool=self.tool();source=self.put('original.png','original')
        cache=self.root/'cache/lme-shell/gowall';cache.mkdir(parents=True)
        errors=[];entered=threading.Event();prepare=tool.cache
        def blocked_cache(): entered.set();return prepare()
        def generate():
            try:tool.generate(dict(paths=[str(source)],operation='invert'))
            except ValueError as error:errors.append(str(error))
        with patch.dict(os.environ,XDG_CACHE_HOME=str(self.root/'cache')),(cache/'.lock').open('a+b') as guard,patch.object(tool,'cache',side_effect=blocked_cache):
            fcntl.flock(guard,fcntl.LOCK_EX)
            worker=threading.Thread(target=generate);worker.start()
            try:
                self.assertTrue(entered.wait(timeout=2))
                started=time.monotonic();tool.close();worker.join(timeout=2)
                self.assertFalse(worker.is_alive());self.assertLess(time.monotonic()-started,1.5)
                self.assertEqual(len(errors),1);self.assertIn('busy',errors[0])
            finally:worker.join(timeout=2)

    def test_close_waits_for_generate_before_removing_its_cache(self):
        live,tool=self.tool();source=self.put('original.png','original')
        started=threading.Event();release=threading.Event();results=[]
        original=tool.runner.run
        def run(*args,**kwargs):
            started.set();release.wait(timeout=3)
            return original(*args,**kwargs)
        with patch.dict(os.environ,XDG_CACHE_HOME=str(self.root/'cache')),patch.object(tool.runner,'run',side_effect=run):
            worker=threading.Thread(target=lambda:results.append(tool.generate(dict(paths=[str(source)],operation='invert'))))
            worker.start()
            try:
                self.assertTrue(started.wait(timeout=2))
                close=threading.Thread(target=tool.close);close.start()
                release.set();worker.join(timeout=2);close.join(timeout=2)
                self.assertFalse(worker.is_alive());self.assertFalse(close.is_alive())
                self.assertEqual(len(results),1)
                self.assertFalse(Path(results[0]['images'][0]['path']).exists())
            finally:release.set();worker.join(timeout=3)
