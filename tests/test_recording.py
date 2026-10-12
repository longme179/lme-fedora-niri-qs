"""Recorder discovery, hybrid fallback and real container finalization."""
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from test_backend import backend, Fixture, FakeRunner
from screen_recording import Recorder


class RecordingCase(Fixture, unittest.TestCase):
    def test_missing_command_is_rediscovered_and_minimal_path_has_system_fallback(self):
        with patch.object(backend.shutil, 'which', return_value=None): runner=backend.CommandRunner()
        with patch.object(backend.shutil, 'which', return_value='/usr/bin/wf-recorder') as lookup, patch.dict(os.environ, PATH='/missing'):
            self.assertEqual(runner.executable('wf-recorder'),'/usr/bin/wf-recorder')
            self.assertIn('/usr/bin',lookup.call_args.kwargs['path'].split(os.pathsep))
            self.assertFalse(runner.available('arbitrary-command'))
        binary=self.put('wf-recorder','#!/bin/sh\n');binary.chmod(0o755)
        runner.commands['wf-recorder']=str(binary);binary.unlink()
        with patch.object(backend.shutil,'which',return_value=None):
            with self.assertRaises(backend.CommandError): runner.executable('wf-recorder')

    def test_candidates_prioritize_nvidia_then_integrated_then_software_without_probes(self):
        self.put('sys/bus/pci/devices/0000:01:00.0/vendor','0x10de')
        self.put('sys/bus/pci/devices/0000:01:00.0/class','0x030200')
        self.put('sys/class/drm/renderD128/device/vendor','0x1002')
        runner=FakeRunner();recorder=Recorder(runner,self.root/'sys')
        names={'h264_nvenc','h264_vaapi','libx264','vp9_vaapi','libvpx-vp9'}
        self.assertEqual([c[2] for c in recorder.candidates(names,'auto','mp4','h264')],['NVIDIA','AMD','CPU'])
        self.assertEqual(recorder.candidates(names,'nvidia','webm','vp9'),[])
        self.assertEqual(recorder.candidates(names,'cpu','webm','vp9'),[('libvpx-vp9',None,'CPU')])
        self.assertEqual(runner.calls,[])

    def test_failed_nvenc_probe_falls_back_to_amd_with_explicit_hybrid_arguments(self):
        self.put('sys/class/drm/renderD129/device/vendor','0x10de')
        self.put('sys/class/drm/renderD128/device/vendor','0x1002')
        class Runner(FakeRunner):
            def run(self,name,*args,**kwargs):
                self.calls.append((name,*args))
                if '-encoders' in args: return ' V..... h264_nvenc\n V..... h264_vaapi\n V..... libx264\n A..... aac'
                if name=='pactl': return 'speaker'
                if 'h264_nvenc' in args: raise backend.CommandError('NVENC driver unavailable')
                return ''
        runner=Runner(available={'wf-recorder','ffmpeg','pactl'});recorder=Recorder(runner,self.root/'sys')
        child=Mock();child.poll.return_value=None
        with patch('screen_recording.subprocess.Popen',return_value=child) as spawn, patch('screen_recording.time.sleep'):
            recorder.start(str(self.root/'videos'),'output','eDP-1','system','auto','mp4','h264',60,16000)
        args=spawn.call_args.args[0]
        for arg in ['-y','h264_vaapi','/dev/dri/renderD128','--no-dmabuf','60','b=16000k','--audio=speaker.monitor','aac','matroska']: self.assertIn(arg,args)
        self.assertIn('pad=ceil(iw/2)*2:ceil(ih/2)*2,format=nv12,hwupload',args)
        self.assertEqual(recorder.state()['gpu'],'AMD');self.assertIn('NVENC driver unavailable',recorder.state()['fallback'])
        self.assertEqual(recorder.path.stat().st_mode & 0o777,0o600)
        recorder.child=None;recorder.log.close()

    def test_failed_startup_retries_cpu_without_deleting_partial_gpu_video(self):
        self.put('sys/class/drm/renderD128/device/vendor','0x1002')
        runner=FakeRunner({('ffmpeg','-hide_banner','-encoders'):' V..... h264_vaapi\n V..... libx264'},available={'wf-recorder'})
        recorder=Recorder(runner,self.root/'sys');failed=Mock();failed.poll.return_value=1;failed.returncode=1
        active=Mock();active.poll.return_value=None
        def spawn(args,**kwargs):
            if 'h264_vaapi' in args:
                Path(args[args.index('-f')+1]).write_bytes(b'partial footage')
                kwargs['stderr'].write('Device failed');kwargs['stderr'].flush();return failed
            return active
        with patch('screen_recording.subprocess.Popen',side_effect=spawn),patch('screen_recording.time.sleep'):
            recorder.start(str(self.root/'videos'),'output','eDP-1','none','auto','mkv','h264')
        self.assertEqual(recorder.state()['gpu'],'CPU');self.assertIn('Device failed',recorder.state()['fallback'])
        self.assertEqual(len(list((self.root/'videos').glob('*.mkv'))),2)
        recorder.child=None;recorder.log.close()

    def test_validation_rejects_incompatible_and_unbounded_options_before_spawn(self):
        recorder=Recorder(FakeRunner(),self.root/'sys')
        for container,codec,fps,bitrate in [('webm','h264',30,12000),('mov','vp9',30,12000),('mkv','auto',True,12000),('mp4','auto',121,12000),('mp4','auto',30,999)]:
            with self.assertRaises(ValueError): recorder.start(str(self.root/'videos'),'output','eDP-1','none','auto',container,codec,fps,bitrate)
        self.assertFalse((self.root/'videos').exists());self.assertFalse(recorder.state()['preparing'])
        for key,value in [('recordingFormat','avi'),('recordingCodec','bad'),('recordingFps',True),('recordingBitrate',100001),('recordingEncoder','bad')]:
            with self.assertRaises(ValueError): backend.validate_preference(key,value)

    def test_old_cpu_default_migrates_but_new_explicit_cpu_is_preserved(self):
        self.preferences.path.parent.mkdir(parents=True,exist_ok=True)
        self.preferences.path.write_text('{"recordingEncoder":"cpu"}')
        self.preferences.reload(force=True);self.assertEqual(self.preferences.values['recordingEncoder'],'auto')
        self.preferences.set('recordingEncoder','cpu');self.preferences.reload(force=True)
        self.assertEqual(self.preferences.values['recordingEncoder'],'cpu')

    def stopped_fixture(self, runner, path, target):
        recorder=Recorder(runner,self.root/'sys');child=Mock();child.poll.return_value=None;child.returncode=0
        def wait(**_): child.poll.return_value=0;return 0
        child.wait.side_effect=wait
        recorder.child=child;recorder.path=path;recorder.started=time.monotonic();recorder.log=tempfile.TemporaryFile(mode='w+')
        recorder.info={'active':True,'owned':True,'path':str(path),'target':str(target),'error':''}
        return recorder,child

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg unavailable for actual container checks')
    def test_real_ffmpeg_remuxes_private_mp4_mov_webm_and_decodes_results(self):
        runner=backend.CommandRunner()
        for container,codec in [('mp4','libx264'),('mov','libx264'),('webm','libvpx-vp9')]:
            with self.subTest(container=container):
                source=self.root/(container+'.mkv');target=source.with_suffix('.'+container)
                runner.run('ffmpeg','-v','error','-f','lavfi','-i','color=size=128x128:rate=30','-t','0.2','-c:v',codec,'-threads','1',str(source),timeout=15)
                source.chmod(0o600);recorder,child=self.stopped_fixture(runner,source,target)
                self.assertIn(str(target),recorder.stop());child.send_signal.assert_called_once_with(signal.SIGINT)
                self.assertFalse(source.exists());self.assertGreater(target.stat().st_size,0)
                self.assertEqual(target.stat().st_mode & 0o777,0o600);self.assertFalse(recorder.state()['finishing'])

    def test_remux_failure_or_existing_destination_retains_original(self):
        source=self.put('record.mkv','original');target=self.put('record.mp4','existing')
        runner=FakeRunner(available={'ffmpeg'});recorder,_=self.stopped_fixture(runner,source,target)
        with self.assertRaisesRegex(ValueError,'Original MKV retained'): recorder.stop()
        self.assertEqual(source.read_text(),'original');self.assertEqual(target.read_text(),'existing')
        self.assertFalse(list(self.root.glob('.lme-remux-*')))
        runner.run=Mock(side_effect=backend.CommandError('Bad container'));recorder,_=self.stopped_fixture(runner,source,target)
        with self.assertRaises(ValueError):recorder.stop()
        self.assertTrue(source.exists())
