"""Ephemeral per-stream route: prove the Pulse/native core before metadata writes."""
import re

from audio_inventory import integer


def route_plan(info,objects,stream_serial,sink_serial):
    if not isinstance(info,dict):raise ValueError('Invalid audio server information')
    cookie=info.get('cookie')
    if not isinstance(cookie,str) or not re.fullmatch(r'[0-9a-fA-F]{4}:[0-9a-fA-F]{4}',cookie):
        raise ValueError('Cannot verify the local PipeWire core for this audio server')
    if not isinstance(objects,list) or len(objects)>2048: raise ValueError('Invalid PipeWire inventory')
    cores=[o for o in objects if isinstance(o,dict) and o.get('type')=='PipeWire:Interface:Core']
    core=cores[0].get('info') if len(cores)==1 else None
    if not isinstance(core,dict) or type(core.get('cookie')) is not int or core['cookie']!=int(cookie.replace(':',''),16):
        raise ValueError('Audio server does not match the local PipeWire core; use Advanced audio settings')
    def node(serial,kind):
        found=[]
        for obj in objects:
            if not isinstance(obj,dict) or obj.get('type')!='PipeWire:Interface:Node':continue
            details=obj.get('info')
            props=details.get('props') if isinstance(details,dict) else None
            if not isinstance(props,dict):continue
            if str(props.get('object.serial'))==serial and props.get('media.class')==kind:
                found.append(integer(obj.get('id')))
        if len(found)!=1:raise ValueError('Audio node changed or is ambiguous; refresh devices')
        return found[0]
    source=node(stream_serial,'Stream/Output/Audio');node(sink_serial,'Audio/Sink')
    return source,sink_serial


def apply_route(run,route):
    node,serial=route
    run('pw-metadata','-n','default',str(node),'target.object',serial,'Spa:Id')
    # PipeWire Pulse may also leave this deprecated object.id target behind.
    run('pw-metadata','-n','default',str(node),'target.node')
