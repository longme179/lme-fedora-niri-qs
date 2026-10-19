"""Gowall adapter contracts and safe preview/export/apply lifecycle."""
import os
from pathlib import Path
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
