"""Synthetic pactl JSON matches the private PipeWire-Pulse capability probe."""
import copy
import json
from test_backend import FakeRunner


def documents():
    def device(index, name, title, port):
        return dict(index=index, name=name, description=title, card=1,
            properties={'object.serial': str(index+100)}, active_port=port,
            ports=[dict(name=port, description=title, available='yes'),
                   dict(name=port+'-absent', description='Unplugged', available='no')])
    return dict(info=dict(server_string='unix:/private/pulse/native', cookie='1234:abcd',
        server_name='PulseAudio (on PipeWire 1.4.2)'), cards=[dict(index=1, name='test_card',
        properties={'object.serial':'101','device.description':'Private headset'},
        active_profile='output:stereo', profiles={
            'output:stereo':dict(description='High quality playback',available='yes'),
            'output:headset+input:headset':dict(description='Call audio',available='unknown'),
            'output:absent':dict(description='Unavailable',available='no')})],
        sinks=[device(10,'speakers','Speakers','speaker'),device(11,'headset','Headset','headphones')],
        sources=[device(12,'microphone','Microphone','mic')],
        **{'sink-inputs':[dict(index=20, sink=10, properties={'object.serial':'120',
            'application.name':'Music','media.name':'Song'}), dict(index=21,sink=10,
            properties={'object.serial':'121','application.name':'Call','media.name':'Meeting'})]})


class PulseRunner(FakeRunner):
    def __init__(self):
        super().__init__(available={'pactl'})
        self.docs=documents(); self.mutations=[]; self.options=[]
        self.error=None; self.apply=True

    def run(self, name, *args, **kwargs):
        self.calls.append((name,*args)); self.options.append(kwargs)
        if self.error: raise self.error
        if name!='pactl': return ''
        if args[0]=='--format=json':
            return json.dumps(self.docs['info' if args[1]=='info' else args[2]])
        self.mutations.append((name,*args))
        if self.apply:
            command,index,value=args[1:]; index=int(index)
            if command=='set-card-profile':
                next(x for x in self.docs['cards'] if x['index']==index)['active_profile']=value
            elif command in ('set-sink-port','set-source-port'):
                next(x for x in self.docs['sinks' if command=='set-sink-port' else 'sources'] if x['index']==index)['active_port']=value
            elif command=='move-sink-input':
                next(x for x in self.docs['sink-inputs'] if x['index']==index)['sink']=int(value)
        return ''

    def clone(self): return copy.deepcopy(self.docs)
