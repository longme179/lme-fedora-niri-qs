"""Owned recording; GPU encoding is probed only when a user starts capture."""
# NVIDIA-first / VAAPI / software fallback adapted from iNiR record.sh (48cdcecb).
# Copyright (C) 2025-2026 snowarch; modified for LME ownership and validated settings.
# See third_party/iNiR-NOTICE and THIRD_PARTY.md.
# SPDX-License-Identifier: GPL-3.0-only
# Retains iNiR's additional GPLv3 section 7 terms in third_party/iNiR-NOTICE.
from pathlib import Path
import os
import json
import re

FORMATS = {'mkv': {'auto','h264','hevc','av1','vp9'}, 'mp4': {'auto','h264','hevc','av1','vp9'},
           'mov': {'auto','h264','hevc'}, 'webm': {'auto','av1','vp9'}}
ENCODERS = {'h264': ('h264_nvenc','h264_vaapi','libx264','libopenh264'),
            'hevc': ('hevc_nvenc','hevc_vaapi','libx265'), 'av1': ('av1_nvenc','av1_vaapi','libsvtav1','libaom-av1'),
            'vp9': ('vp9_vaapi','libvpx-vp9')}
import signal
import subprocess
import tempfile
import threading
import time


class Recorder:
    @staticmethod
    def provide_stop(stop):
        from backend_actions import ActionSpec
        return ((ActionSpec('recordStop', {'shell'}, lambda request: stop(), lambda request: None,
                            execution='worker', complete=lambda value: None),), lambda: {})

    def __init__(self, runner, sysfs=Path('/sys')):
        self.runner,self.sysfs=runner,sysfs
        self.child=None;self.selector=None;self.closed=False;self.preparing=False;self.log=None;self.path=None;self.started=0;self.lock=threading.RLock()
        self.info={'active':False,'owned':False,'error':''}
        self.finishing=False

    def state(self):
        with self.lock:
            if self.child and self.child.poll() is not None:
                code=self.child.returncode
                self.info.update(active=False,owned=False,elapsed=max(0,int(time.monotonic()-self.started)))
                if code:
                    self.log.seek(0,2);size=self.log.tell();self.log.seek(max(0,size-2000))
                    self.info['error']='Recorder stopped ('+str(code)+'): '+self.log.read().strip()[:1000]
                elif not self.path or not self.path.exists() or not self.path.stat().st_size:
                    self.info['error']='Recorder produced no video'
                self.child=None;self.log.close();self.log=None
            if self.child: self.info.update(active=True,owned=True,elapsed=max(0,int(time.monotonic()-self.started)))
            return {**self.info, "preparing": self.preparing, "finishing": self.finishing}

    def candidates(self, names, encoder, container, codec):
        families = [codec] if codec != 'auto' else [c for c in ('h264','av1','hevc','vp9') if c in FORMATS[container]]
        nodes=[]; nvidia=False
        for node in sorted((self.sysfs/'class/drm').glob('renderD*')):
            try: vendor=(node/'device/vendor').read_text().strip()
            except OSError: continue
            nvidia = nvidia or vendor == '0x10de'
            if vendor in ('0x1002','0x8086'): nodes.append(('/dev/dri/'+node.name, 'AMD' if vendor=='0x1002' else 'Intel'))
        if not nvidia:
            for node in (self.sysfs/'bus/pci/devices').glob('*'):
                try:
                    if (node/'vendor').read_text().strip()=='0x10de' and (node/'class').read_text().strip().startswith('0x03'): nvidia=True; break
                except OSError: continue
        result=[]
        if encoder in ('auto','nvidia') and nvidia:
            for family in families:
                result += [(c,None,'NVIDIA') for c in ENCODERS[family] if c.endswith('_nvenc') and c in names]
        if encoder in ('auto','radeon'):
            for device, gpu in nodes:
                if encoder=='radeon' and gpu!='AMD': continue
                for family in families:
                    result += [(c,device,gpu) for c in ENCODERS[family] if c.endswith('_vaapi') and c in names]
        if encoder in ('auto','cpu'):
            for family in families:
                result += [(c,None,'CPU') for c in ENCODERS[family] if not c.endswith(('_nvenc','_vaapi')) and c in names]
        return result

    def probe(self, codec, device, fps, bitrate):
        args=['-hide_banner','-loglevel','error']
        if device: args+=['-vaapi_device',device]
        # Desktop-sized frames avoid rejecting NVENC's minimum-dimension constraints.
        # shortcut: probe geometry is fixed, match capture dimensions if small regions need preflight.
        args+=['-f','lavfi','-i','color=size=1920x1080:rate='+str(fps),'-frames:v','1','-an']
        if device: args+=['-vf','format=nv12,hwupload']
        else: args+=['-pix_fmt','yuv420p']
        self.runner.run('ffmpeg',*args,'-c:v',codec,'-b:v',str(bitrate)+'k','-f','null','-',timeout=8)

    def start(self, folder, mode, output, audio, encoder, container='mkv', video_codec='auto', fps=30, bitrate=12000):
        with self.lock:
            if self.closed: raise ValueError('Recording service is closing')
            if self.preparing or self.finishing or self.state()['active']: raise ValueError('A shell recording is already preparing or running')
            self.preparing=True
            self.info={'active':False,'owned':False,'error':'','fallback':''}
        try:
            if mode not in ('output','region') or audio not in ('none','system','microphone') or encoder not in ('auto','nvidia','cpu','radeon'):
                raise ValueError('Invalid recording mode, audio or encoder')
            if container not in FORMATS or video_codec not in FORMATS[container]: raise ValueError('Choose a compatible video codec and container')
            if type(fps) is not int or fps not in (24,30,60,120) or type(bitrate) is not int or not 1000<=bitrate<=100000: raise ValueError('Invalid recording frame rate or bitrate')
            if not isinstance(output,str) or not 1<=len(output)<=128 or any(ord(c)<32 for c in output): raise ValueError('Choose a connected output')
            binary=self.runner.executable('wf-recorder')
            codecs=self.runner.run('ffmpeg','-hide_banner','-encoders')
            names={line.split()[1] for line in codecs.splitlines() if len(line.split())>=2}
            candidates=self.candidates(names,encoder,container,video_codec)
            if not candidates: raise ValueError('No compatible encoder for '+container+'/'+video_codec+'. Check FFmpeg codec support or choose Auto/MKV.')
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
                self.runner.executable('ffprobe')
                source=self.runner.run('pactl','get-default-sink' if audio=='system' else 'get-default-source').strip()
                if not source or len(source)>512 or any(ord(c)<32 for c in source): raise ValueError('No audio source available')
                if audio=='system': source+='.monitor'
                audio_codec = 'aac' if container in ('mp4','mov') else 'libopus'
                if audio_codec not in names: raise ValueError('Audio recording needs FFmpeg '+audio_codec+' support')
            if self.closed: raise ValueError('Recording cancelled during shell shutdown')
            if not isinstance(folder,str) or not folder or len(folder)>4096 or any(ord(c)<32 for c in folder): raise ValueError('Choose a recording folder')
            directory=Path(folder).expanduser().resolve();directory.mkdir(parents=True,exist_ok=True)
            failures=[]
            for codec, device, gpu in candidates:
                if self.closed: raise ValueError('Recording cancelled during shell shutdown')
                with self.lock: self.info.update(encoder=codec,gpu=gpu)
                try: self.probe(codec,device,fps,bitrate)
                except RuntimeError as error:
                    failures.append(codec+': '+str(error)[:350]); continue
                with tempfile.NamedTemporaryFile(prefix='Recording-'+time.strftime('%Y%m%d-%H%M%S')+'-',suffix='.mkv',dir=directory,delete=False) as reserved: path=Path(reserved.name)
                target=path.with_suffix('.'+container)
                pad='pad=ceil(iw/2)*2:ceil(ih/2)*2'
                args=[binary,'-y','-f',str(path),'-m','matroska','-o',output,'-r',str(fps),'-c',codec,'--no-dmabuf','-p','b='+str(bitrate)+'k']
                if geometry: args+=['--geometry',geometry]
                if device: args+=['-d',device,'-F',pad+',format=nv12,hwupload']
                else: args+=['-x','yuv420p','-F',pad+',format=yuv420p']
                if codec in ('libvpx','libvpx-vp9'): args+=['-p','deadline=realtime','-p','cpu-used=6']
                elif codec in ('libx264','libx265'): args+=['-p','preset=veryfast']
                if source: args+=['--audio='+source,'-C',audio_codec,'-P','b=192k']
                with self.lock:
                    if self.closed: path.unlink(missing_ok=True); raise ValueError('Recording service is closing')
                    self.path=path;self.log=tempfile.TemporaryFile(mode='w+',encoding='utf-8',errors='replace')
                    try: self.child=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=self.log,start_new_session=True)
                    except OSError:
                        self.log.close();self.log=None;path.unlink(missing_ok=True);raise
                    self.started=time.monotonic();self.info={'active':True,'owned':True,'name':'wf-recorder','path':str(path),'target':str(target),'format':container,'fps':fps,'bitrate':bitrate,'elapsed':0,'encoder':codec,'gpu':gpu,'audio':audio,'audioSource':source or '', 'fallback':'; '.join(failures)[-1200:],'error':''}
                time.sleep(.35)
                state=self.state()
                if state['active']: return 'Recording requested: '+str(target)
                failures.append(codec+': '+(state['error'] or 'Recorder exited before capture began'))
                # Keep any partial video for recovery; only empty failed attempts are removed.
                if path.exists() and not path.stat().st_size: path.unlink()
            raise ValueError('Recording could not start. '+ '; '.join(failures)[-1500:])
        except (RuntimeError,ValueError,OSError) as error:
            with self.lock: self.info['error']=str(error)
            raise
        finally:
            with self.lock: self.preparing=False

    def stop(self):
        with self.lock:
            if self.finishing: raise ValueError('Recorder is already finishing')
            if not self.child or self.child.poll() is not None: raise ValueError('No recording owned by this shell is running')
            child=self.child;child.send_signal(signal.SIGINT)
            self.finishing=True
        try: return self.finish(child)
        finally:
            with self.lock: self.finishing=False

    def finish(self, child):
        try: child.wait(timeout=12)
        except subprocess.TimeoutExpired: raise ValueError('Recorder is still finishing; retry Stop')
        state=self.state()
        if state['error']: raise ValueError(state['error'])
        try: self.runner.run('ffmpeg','-v','error','-i',state['path'],'-t','0.1','-f','null','-',timeout=12)
        except RuntimeError as error:
            with self.lock: self.info['error']='Recording retained but decode check failed: '+str(error)
            raise ValueError(self.info['error']) from error
        if state.get('audio', 'none')!='none':
            try:
                streams=json.loads(self.runner.run('ffprobe','-v','error','-select_streams','a','-show_entries','stream=codec_type','-of','json',state['path'],timeout=12)).get('streams',[])
                if not streams: raise ValueError('No audio track was captured')
            except (ValueError,RuntimeError,AttributeError) as error:
                with self.lock: self.info['error']='Recording retained; audio verification failed: '+str(error)+'. Check the audio source and wf-recorder audio backend.'
                raise ValueError(self.info['error']) from error
            with self.lock: self.info['audioVerified']=True
        target=Path(state.get('target',state['path']))
        if str(target)!=state['path']:
            converted=None
            try:
                # Only overwrite our private temporary file; publish without replacing user files.
                with tempfile.NamedTemporaryFile(prefix='.lme-remux-',suffix=target.suffix,dir=target.parent,delete=False) as reserved: converted=Path(reserved.name)
                args=['-v','error','-y','-i',state['path'],'-c','copy']
                if target.suffix in ('.mp4','.mov'): args+=['-movflags','+faststart']
                self.runner.run('ffmpeg',*args,str(converted),timeout=60)
                self.runner.run('ffmpeg','-v','error','-i',str(converted),'-t','0.1','-f','null','-',timeout=12)
                os.link(converted,target)
            except (RuntimeError,OSError) as error:
                with self.lock: self.info['error']='Original MKV retained; video conversion failed: '+str(error)
                raise ValueError(self.info['error']) from error
            finally:
                if converted: converted.unlink(missing_ok=True)
            self.path.unlink(); self.path=target
            with self.lock: self.info['path']=str(target)
        return 'Saved recording: '+str(target)

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
