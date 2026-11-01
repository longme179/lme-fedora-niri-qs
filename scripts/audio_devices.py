"""On-demand audio changes and bounded observed read-back; no watcher or policy."""
import json
import time

from audio_inventory import identity, integer, normalize, selected, selection, server_id
from audio_pipewire import route_plan, apply_route
from command_runner import CommandError


class AudioFailure(CommandError):
    def __init__(self,message,state=None):
        super().__init__(message);self.state=state


class AudioDevices:
    def __init__(self,run,available):
        self.run,self.available=run,available

    def tool(self,deadline,tool,*args):
        remaining=deadline-time.monotonic()
        if remaining<=0: raise CommandError('Audio operation timed out; refresh to check the actual state')
        return self.run(tool,*args,timeout=min(2.0,remaining),max_output=2*1024*1024 if tool=='pw-dump' else 1024*1024)

    def command(self,deadline,*args):return self.tool(deadline,'pactl',*args)

    def query(self,deadline,*args):
        try:return json.loads(self.command(deadline,'--format=json',*args))
        except (json.JSONDecodeError,RecursionError) as error:raise ValueError('Audio server returned invalid JSON') from error

    def read(self,deadline):
        if not self.available('pactl'): raise CommandError('Install pulseaudio-utils (pactl) to use ports, profiles and app outputs')
        info=self.query(deadline,'info')
        values=[self.query(deadline,'list',kind) for kind in ('cards','sinks','sources','sink-inputs')]
        if server_id(info)!=server_id(self.query(deadline,'info')): raise ValueError('Audio server changed while reading devices; refresh')
        model=normalize(info,*values);model['checkedAt']=int(time.time()*1000)
        return model

    def refresh(self):
        return dict(state=self.read(time.monotonic()+6),message='Audio devices refreshed')

    def observed(self,deadline,change):
        group=change['group'];kind={'cards':'card','sinks':'sink','sources':'source','streams':'stream'}[group]
        data=self.query(deadline,'list','sink-inputs' if group=='streams' else group)
        if not isinstance(data,list) or len(data)>128:raise ValueError('Invalid audio read-back')
        for row in data:
            if not isinstance(row,dict):raise ValueError('Invalid audio read-back')
            if identity(kind,row)['id']!=change['id']:continue
            return (integer(row.get('sink'))==int(change['argv'][2]) if group=='streams' else
                    selected(row.get('active_profile' if group=='cards' else 'active_port'))==change['value'])
        return False

    def change(self,action,request):
        deadline=time.monotonic()+8;current=None;attempted=False
        try:
            current=self.read(deadline);change=selection(current,action,request)
            if action=='audioRoute' and self.available('pw-dump') and self.available('pw-metadata'):
                info=self.query(deadline,'info')
                if server_id(info)!=request['serverId']:raise ValueError('Audio server changed; refresh devices')
                try:objects=json.loads(self.tool(deadline,'pw-dump'))
                except (json.JSONDecodeError,RecursionError) as error:raise ValueError('Invalid PipeWire inventory') from error
                route=route_plan(info,objects,request['streamId'].split('/')[-1],request['sinkId'].split('/')[-1])
                attempted=True;apply_route(lambda *args:self.tool(deadline,*args),route)
            else:
                attempted=True;self.command(deadline,'--',*change['argv'])
            # Pulse acknowledges before WirePlumber may finish linking/recreating nodes.
            # Only this explicit operation retries its affected list, not the full inventory.
            for attempt in range(8):
                if self.observed(deadline,change):break
                if attempt<7:time.sleep(.15)
            current=self.read(deadline)
            if current['serverId']!=request['serverId']: raise AudioFailure('Audio server changed before confirmation; refresh',current)
            row=next((r for r in current[change['group']] if r['id']==change['id']),None)
            if row and row[change['field']]==change['value']:
                return dict(state=current,message=change['message'])
            raise AudioFailure('Unable to confirm the requested audio change; showing the observed state',current)
        except AudioFailure:raise
        except (CommandError,ValueError,OSError) as error:
            if attempted:
                try:current=self.read(deadline)
                except (CommandError,ValueError,OSError):current=None
            raise AudioFailure(str(error),current) from error
