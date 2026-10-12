"""Owned wf-recorder lifecycle. Never scans/kills other recorders or probes NVIDIA."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import threading
import time


class Recorder:
    def __init__(self, runner, sysfs=Path('/sys')):
        self.runner,self.sysfs=runner,sysfs
        self.child=None;self.selector=None;self.closed=False;self.preparing=False;self.log=None;self.path=None;self.started=0;self.lock=threading.RLock()
        self.info={'active':False,'owned':False,'error':''}

    def state(self):
        with self.lock:
            if self.child and self.child.poll() is not None:
                code=self.child.returncode
                self.info.update(active=False,owned=False,elapsed=max(0,int(time.monotonic()-self.started)))
                if code:
                    self.log.seek(0,2);size=self.log.tell();self.log.seek(max(0,size-2000))
                    self.info['error']='Recorder stopped ('+str(code)+'): '+self.log.read().strip()[-350:]
                elif not self.path or not self.path.exists() or not self.path.stat().st_size:
                    self.info['error']='Recorder produced no video'
                self.child=None;self.log.close();self.log=None
            if self.child: self.info.update(active=True,owned=True,elapsed=max(0,int(time.monotonic()-self.started)))
            return {**self.info, "preparing": self.preparing}

    def start(self, folder, mode, output, audio, encoder):
        with self.lock:
            if self.closed: raise ValueError('Recording service is closing')
            if self.preparing or self.state()['active']: raise ValueError('A shell recording is already preparing or running')
            self.preparing=True
        try:
            if mode not in ('output','region') or audio not in ('none','system','microphone') or encoder not in ('cpu','radeon'):
                raise ValueError('Invalid recording mode, audio or encoder')
            if not isinstance(output,str) or not 1<=len(output)<=128 or any(ord(c)<32 for c in output): raise ValueError('Choose a connected output')
            binary=self.runner.executable('wf-recorder')
            codecs=self.runner.run('ffmpeg','-hide_banner','-encoders')
            names={line.split()[1] for line in codecs.splitlines() if len(line.split())>=2}
            codec=next((c for c in ('libvpx-vp9','libvpx') if c in names),None)
            device=None
            if encoder=='radeon':
                for node in sorted((self.sysfs/'class/drm').glob('renderD*')):
                    try:
                        if (node/'device/vendor').read_text().strip()=='0x1002': device='/dev/dri/'+node.name;break
                    except OSError: continue
                if not device or 'h264_vaapi' not in names: raise ValueError('Radeon VAAPI encoder is unavailable; choose CPU')
                codec='h264_vaapi'
            if not codec: raise ValueError('No CPU VP8/VP9 encoder; install ffmpeg-free with libvpx support')
            geometry=None
            if mode=='region':
                with self.lock:
                    if self.closed: raise ValueError('Recording service is closing')
                    self.selector=subprocess.Popen([self.runner.executable('slurp'),'-f','%x,%y %wx%h'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
                try:
                    geometry=self.selector.communicate(timeout=60)[0].strip()
                    if self.selector.returncode: raise ValueError('Area selection cancelled')
                except subprocess.TimeoutExpired:
                    self.selector.kill();self.selector.wait();raise ValueError('Area selection timed out')
                finally: self.selector=None
                if not re.fullmatch(r'-?\d+,-?\d+ [1-9]\d*x[1-9]\d*',geometry): raise ValueError('Area selection was cancelled or invalid')
            source=None
            if audio!='none':
                source=self.runner.run('pactl','get-default-sink' if audio=='system' else 'get-default-source').strip()
                if not source or len(source)>512 or any(ord(c)<32 for c in source): raise ValueError('No audio source available')
                if audio=='system': source+='.monitor'
                if 'libopus' not in names: raise ValueError('Audio recording needs FFmpeg libopus support')
            if self.closed: raise ValueError('Recording cancelled during shell shutdown')
            if not isinstance(folder,str) or not folder or len(folder)>4096 or any(ord(c)<32 for c in folder): raise ValueError('Choose a recording folder')
            directory=Path(folder).expanduser().resolve();directory.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix='Recording-'+time.strftime('%Y%m%d-%H%M%S')+'-',suffix='.mkv',dir=directory,delete=False) as reserved: path=Path(reserved.name)
            args=[binary,'-f',str(path),'-o',output,'-r','30','-c',codec]
            if geometry: args+=['--geometry',geometry]
            if device: args+=['-d',device,'-F','format=nv12,hwupload']
            else: args+=['-p','deadline=realtime','-p','cpu-used=6']
            if source: args+=['--audio='+source,'-C','libopus']
            with self.lock:
                if self.closed: path.unlink(missing_ok=True); raise ValueError('Recording service is closing')
                self.path=path;self.log=tempfile.TemporaryFile(mode='w+',encoding='utf-8',errors='replace')
                try: self.child=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=self.log,start_new_session=True)
                except OSError:
                    self.log.close();self.log=None;path.unlink(missing_ok=True);raise
                self.started=time.monotonic();self.info={'active':True,'owned':True,'name':'wf-recorder','path':str(path),'elapsed':0,'encoder':codec,'audio':audio,'error':''}
            time.sleep(.15)
            state=self.state()
            if not state['active']: raise ValueError(state['error'] or 'Recorder exited before capture began')
            return 'Recording requested: '+str(path)
        finally:
            with self.lock: self.preparing=False

    def stop(self):
        with self.lock:
            if not self.child or self.child.poll() is not None: raise ValueError('No recording owned by this shell is running')
            child=self.child;child.send_signal(signal.SIGINT)
        try: child.wait(timeout=12)
        except subprocess.TimeoutExpired: raise ValueError('Recorder is still finishing; retry Stop')
        state=self.state()
        if state['error']: raise ValueError(state['error'])
        try: self.runner.run('ffmpeg','-v','error','-i',state['path'],'-t','0.1','-f','null','-',timeout=12)
        except RuntimeError as error:
            with self.lock: self.info['error']='Recording retained but decode check failed: '+str(error)
            raise ValueError(self.info['error']) from error
        return 'Saved recording: '+state['path']

    def close(self):
        with self.lock:
            self.closed=True
            selector=self.selector;child=self.child
        if selector and selector.poll() is None: selector.terminate()
        if child and child.poll() is None:
            try: self.stop()
            except (OSError,ValueError,RuntimeError):
                if child.poll() is None:
                    child.terminate()
                    try:child.wait(timeout=2)
                    except subprocess.TimeoutExpired:child.kill();child.wait()
        self.state()
