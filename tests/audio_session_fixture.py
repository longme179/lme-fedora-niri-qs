"""Private virtual PipeWire/Pulse: no hardware monitors, real-session sockets or agents."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest


class AudioSession:
    def __enter__(self):
        self.tools={name:shutil.which(name) for name in ('pipewire','wireplumber','pactl','pacat','pw-dump')}
        if not all(self.tools.values()): raise unittest.SkipTest('private audio requires PipeWire, WirePlumber and pulseaudio-utils test tools')
        self.temp=tempfile.TemporaryDirectory(prefix='audio-session-');self.root=Path(self.temp.name)
        self.env=dict(os.environ);self.processes=[];self.logs=[]
        for key in ('CONFIG','STATE','CACHE','DATA'):
            path=self.root/key.lower();path.mkdir();self.env['XDG_'+key+'_HOME']=str(path)
        runtime=self.root/'run';runtime.mkdir(mode=0o700);(runtime/'pulse').mkdir(mode=0o700)
        prefix=Path(self.tools['pipewire']).resolve().parents[1]
        def library(name):
            return str(next(p for p in [*prefix.glob('lib/*/'+name),prefix/'lib'/name] if p.is_dir()))
        self.env.update(XDG_RUNTIME_DIR=str(runtime),PIPEWIRE_RUNTIME_DIR=str(runtime),PIPEWIRE_REMOTE='pipewire-0',
            PULSE_SERVER='unix:'+str(runtime/'pulse/native'),PULSE_COOKIE=str(self.root/'cookie'),
            PULSE_RUNTIME_PATH=str(runtime/'pulse'),PIPEWIRE_CONFIG_DIR=str(prefix/'share/pipewire'),
            PIPEWIRE_MODULE_DIR=library('pipewire-0.3'),SPA_PLUGIN_DIR=library('spa-0.2'),
            WIREPLUMBER_MODULE_DIR=library('wireplumber-0.5'),WIREPLUMBER_DATA_DIR=str(prefix/'share/wireplumber'),
            DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(self.root/'no-system-bus'))
        config=self.root/'pipewire.conf'
        config.write_text('''context.properties = { core.daemon = true core.name = pipewire-0 }
context.spa-libs = { audio.convert.* = audioconvert/libspa-audioconvert support.* = support/libspa-support }
context.modules = [
 { name = libpipewire-module-protocol-native }
 { name = libpipewire-module-client-node }
 { name = libpipewire-module-spa-node-factory }
 { name = libpipewire-module-adapter }
 { name = libpipewire-module-link-factory }
 { name = libpipewire-module-metadata }
 { name = libpipewire-module-access args = { access.force = unrestricted } }
 { name = libpipewire-module-protocol-pulse args = { server.address = [ "unix:'''+str(runtime/'pulse/native')+'''" ] } }
]
context.objects = [
 { factory = spa-node-factory args = { factory.name = support.node.driver node.name = Dummy-Driver priority.driver = 20000 } }
 { factory = adapter args = { factory.name = support.null-audio-sink node.name = TestSpeaker node.description = "Private speakers" media.class = Audio/Sink object.linger = true audio.position = [ FL FR ] } }
 { factory = adapter args = { factory.name = support.null-audio-sink node.name = TestHeadset node.description = "Private headset" media.class = Audio/Sink object.linger = true audio.position = [ FL FR ] } }
]
''')
        wp=self.root/'wp';wp.mkdir();(wp/'wireplumber.conf').write_text((prefix/'share/wireplumber/wireplumber.conf').read_text())
        (wp/'wireplumber.conf.d').mkdir()
        (wp/'wireplumber.conf.d/90-private.conf').write_text('wireplumber.profiles = { main = { monitor.alsa = disabled monitor.bluez = disabled monitor.bluez-midi = disabled monitor.v4l2 = disabled monitor.libcamera = disabled } }')
        self.env['WIREPLUMBER_CONFIG_DIR']=str(wp)
        try:
            self.start([self.tools['pipewire'],'-c',str(config)])
            self.wait(lambda:(runtime/'pipewire-0').exists())
            self.start([self.tools['wireplumber']])
            self.wait(lambda:len(self.json('list','sinks'))==2)
            self.wait(lambda:self.json('info')['default_sink_name'] in ('TestSpeaker','TestHeadset'))
            return self
        except BaseException:
            self.__exit__(None,None,None);raise

    def start(self,argv,stdin=None):
        log=tempfile.TemporaryFile(mode='w+');self.logs.append(log)
        process=subprocess.Popen(argv,env=self.env,stdin=stdin,stdout=log,stderr=log,start_new_session=True)
        self.processes.append(process);return process

    def pulse(self,*args):
        return subprocess.check_output([self.tools['pactl'],*args],env=self.env,text=True,stderr=subprocess.PIPE,timeout=3)

    def json(self,*args):return json.loads(self.pulse('--format=json',*args))

    def wait(self,predicate,timeout=6):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                if predicate():return
            except (subprocess.CalledProcessError,json.JSONDecodeError):pass
            time.sleep(.04)
        for log in self.logs:log.seek(0)
        raise AssertionError('Private audio condition timed out\n'+'\n'.join(log.read()[-1500:] for log in self.logs))

    def streams(self):
        for name in ('Music','Call'):
            with open('/dev/zero','rb') as zero:
                self.start([self.tools['pacat'],'--playback','--raw','--device=TestSpeaker',
                    '--client-name=LME '+name,'--stream-name='+name],stdin=zero)
        target=next(s['index'] for s in self.json('list','sinks') if s['name']=='TestSpeaker')
        def linked():
            current=self.json('list','sink-inputs')
            return len(current)==2 and all(s['sink']==target for s in current)
        self.wait(linked)
        return self.json('list','sink-inputs')

    def __exit__(self,*_):
        for p in reversed(self.processes):
            if p.poll() is None:
                try:os.killpg(p.pid,signal.SIGTERM)
                except ProcessLookupError:pass
        for p in reversed(self.processes):
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        for log in self.logs:log.close()
        self.temp.cleanup()
