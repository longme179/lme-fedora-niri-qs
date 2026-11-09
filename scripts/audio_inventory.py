"""Bounded pactl JSON and fresh, server-scoped audio identities; no system I/O.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: audio; Phase 3 graph).
"""
import hashlib
import json
import re


def integer(value, maximum=2**32-1):
    if type(value) is not int or not 0<=value<=maximum: raise ValueError('Invalid audio object index')
    return value


def name(value):
    if not isinstance(value,str) or not 0<len(value)<=256 or any(ord(c)<32 or 0xd800<=ord(c)<=0xdfff for c in value):
        raise ValueError('Invalid audio option name')
    return value


def label(value, fallback):
    if not isinstance(value,str): value=fallback
    return ' '.join(''.join(' ' if ord(c)<32 or 0xd800<=ord(c)<=0xdfff else c for c in value).split())[:160] or fallback


def server_id(info):
    if not isinstance(info,dict): raise ValueError('Invalid audio server information')
    parts=[info.get(k) for k in ('server_string','cookie','server_name')]
    if not all(isinstance(v,str) and 0<len(v)<=4096 for v in parts): raise ValueError('Audio server identity is unavailable')
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()


def identity(kind, row):
    index=integer(row.get('index'))
    props=row.get('properties')
    serial=props.get('object.serial') if isinstance(props,dict) else None
    if type(serial) is int: serial=str(serial)
    if not isinstance(serial,str) or not re.fullmatch(r'[0-9]{1,20}',serial) or int(serial)>2**64-1:
        raise ValueError('PipeWire object identity is unavailable; use Advanced audio settings')
    serial=str(int(serial))
    return dict(id=f'{kind}/{index}/{serial}',index=index,serial=serial)


def selected(value):
    return name(value.get('name')) if isinstance(value,dict) else name(value) if value not in (None,'') else ''


def options(values):
    if isinstance(values,dict):
        if not all(isinstance(v,dict) for v in values.values()): raise ValueError('Invalid audio option')
        values=[dict(v,name=k) for k,v in values.items()]
    if not isinstance(values,list) or len(values)>64: raise ValueError('Audio options exceed the supported inventory')
    result=[]
    for item in values:
        if not isinstance(item,dict): raise ValueError('Invalid audio option')
        key=name(item.get('name'));available=item.get('availability',item.get('available','unknown'))
        if type(available) is str:
            available={'available':'yes','not available':'no','availability unknown':'unknown'}.get(available,available)
        if not (available is None or type(available) is bool or type(available) is str and available in ('yes','no','unknown')):
            raise ValueError('Invalid audio availability')
        result.append(dict(name=key,title=label(item.get('description'),key),available=available not in ('no',False)))
    if len({x['name'] for x in result})!=len(result): raise ValueError('Ambiguous audio options')
    return result


def rows(values,kind):
    if not isinstance(values,list): raise ValueError('Invalid audio inventory')
    result=[]
    for row in values:
        if not isinstance(row,dict): raise ValueError('Invalid audio object')
        result.append((identity(kind,row),row))
    if (len({r['index'] for r,_ in result})!=len(result) or len({r['serial'] for r,_ in result})!=len(result)):
        raise ValueError('Ambiguous audio identities; refresh devices')
    return result


def normalize(info,cards,sinks,sources,streams):
    collections=(cards,sinks,sources,streams)
    if not all(isinstance(v,list) for v in collections) or sum(map(len,collections))>128:
        raise ValueError('Audio inventory exceeds 128 objects or is malformed')
    model=dict(available=True,serverId=server_id(info),server=label(info['server_name'],'Audio server'),
               cards=[],sinks=[],sources=[],streams=[],error='',stale=False)
    for ref,row in rows(cards,'card'):
        key=name(row.get('name'));props=row['properties']
        model['cards'].append(dict(ref,name=key,title=label(props.get('device.description'),key),
            profiles=options(row.get('profiles',{})),activeProfile=selected(row.get('active_profile'))))
    card_ids={r['index']:r['id'] for r in model['cards']}
    for group,kind in (('sinks','sink'),('sources','source')):
        for ref,row in rows(sinks if kind=='sink' else sources,kind):
            key=name(row.get('name'))
            card=integer(row['card']) if row.get('card') is not None else None
            model[group].append(dict(ref,name=key,title=label(row.get('description'),key),kind=kind,
                cardId=card_ids.get(card,''),ports=options(row.get('ports',[])),activePort=selected(row.get('active_port'))))
    sink_ids={r['index']:r['id'] for r in model['sinks']}
    for ref,row in rows(streams,'stream'):
        props=row['properties'];title=label(props.get('application.name'),'Audio application')
        model['streams'].append(dict(ref,title=title,detail=label(props.get('media.name'),title),
                                    sinkId=sink_ids.get(integer(row.get('sink')),'')))
    for group in ('cards','sinks','sources','streams'):model[group].sort(key=lambda item:item['index'])
    if len(json.dumps(model,ensure_ascii=True).encode())>256*1024: raise ValueError('Audio inventory exceeds 256 KiB')
    return model


def validate_request(action,request):
    if action=='audioDevicesRefresh': return
    fields={'audioProfile':('cardId','profile'),'audioPort':('deviceId','port'),'audioRoute':('streamId','sinkId')}
    if action not in fields: raise ValueError('Unknown audio device action')
    if not isinstance(request.get('serverId'),str) or not re.fullmatch(r'[0-9a-f]{64}',request['serverId']):
        raise ValueError('Invalid audio device request; refresh devices')
    for field in fields[action]:
        value=request.get(field)
        if field.endswith('Id'):
            if not isinstance(value,str) or not re.fullmatch(r'(?:card|sink|source|stream)/[0-9]{1,10}/[0-9]{1,20}',value):
                raise ValueError('Invalid audio device identity')
        else: name(value)


def selection(model,action,request):
    validate_request(action,request)
    if request['serverId']!=model['serverId']: raise ValueError('Audio server changed; refresh devices before retrying')
    def find(groups,ident):
        found=[(group,row) for group in groups for row in model[group] if row['id']==ident]
        if len(found)!=1: raise ValueError('Audio object changed or disappeared; refresh devices')
        return found[0]
    if action=='audioRoute':
        group,row=find(('streams',),request['streamId']);_,target=find(('sinks',),request['sinkId'])
        return dict(argv=('move-sink-input',str(row['index']),str(target['index'])),group=group,id=row['id'],
                    field='sinkId',value=target['id'],message='Application output confirmed')
    key='cardId' if action=='audioProfile' else 'deviceId'
    group,row=find(('cards',) if action=='audioProfile' else ('sinks','sources'),request[key])
    choice=request['profile' if action=='audioProfile' else 'port']
    choices=row['profiles' if action=='audioProfile' else 'ports']
    if not any(item['name']==choice and item['available'] for item in choices): raise ValueError('This audio option is unavailable')
    profile=action=='audioProfile'
    return dict(argv=('set-card-profile' if profile else 'set-sink-port' if group=='sinks' else 'set-source-port',str(row['index']),choice),
        group=group,id=row['id'],field='activeProfile' if profile else 'activePort',value=choice,
        message='Audio profile confirmed' if profile else 'Audio port confirmed')


def demo_inventory():
    info=dict(server_string='demo',cookie='demo',server_name='Demo PipeWire Pulse')
    card=dict(index=1,name='demo_headset',properties={'object.serial':'101','device.description':'Demo headset'},
        profiles={'stereo':dict(description='High quality playback',available='yes'),
                  'headset':dict(description='Call audio with microphone',available='yes')},active_profile='stereo')
    def endpoint(index,title,port):
        return dict(index=index,name='demo_'+str(index),description=title,card=1,properties={'object.serial':str(index+100)},
            ports=[dict(name=port,description=title,available='yes')],active_port=port)
    sinks=[endpoint(10,'Speakers','speakers'),endpoint(11,'Headphones','headphones')]
    streams=[dict(index=i,sink=10,properties={'object.serial':str(i+100),'application.name':title,'media.name':title})
             for i,title in ((20,'Music'),(21,'Call'))]
    return normalize(info,[card],sinks,[endpoint(12,'Microphone','microphone')],streams)
