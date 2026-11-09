"""Audio composition: existing controls plus bounded device workers and one projection.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: audio; Phase 3 graph).
"""
# REL: qml/panels/AudioHardware.qml – ActionSpec dispatch via scripts/backend_actions.py::ActionRegistry; scripts/desktop_backend.py host.
import copy
from dataclasses import dataclass
import time
from typing import Callable

from audio_actions import AudioCapabilities, provide as provide_controls
from audio_devices import AudioDevices
from audio_inventory import demo_inventory, selection, validate_request
from backend_actions import ActionSpec, PreparedWork

ACTIONS=('audioDevicesRefresh','audioPort','audioProfile','audioRoute')  # DEPRECATED(Q3->Q6): audio device actions route natively in real sessions (qml/services/AudioDeviceState.qml); this registry stays as the fallback and demo provider through the A/B window


@dataclass(frozen=True)
class DeviceCapabilities:
    controls: AudioCapabilities
    available: Callable
    pending: Callable


def provide(capabilities):
    legacy,project=provide_controls(capabilities.controls)
    devices=AudioDevices(capabilities.controls.run,capabilities.available)
    state={}
    def install(value):
        if isinstance(value,Exception):
            known=getattr(value,'state',None)
            model=copy.deepcopy(known) if known else dict(available=False,cards=[],sinks=[],sources=[],streams=[],stale=True)
            model['error']=str(value)[:400]
        else:model=value['state']
        state['value']=model

    def prepare(action,request):
        validate_request(action,request)
        if any(name in capabilities.pending() for name in (*ACTIONS,'bluetoothDevice')):
            raise ValueError('An audio device operation is already running')
        return PreparedWork(devices.refresh if action=='audioDevicesRefresh' else lambda:devices.change(action,request))

    def demo(action,request):
        validate_request(action,request)
        model=copy.deepcopy(state.get('value') or demo_inventory())
        if action!='audioDevicesRefresh':
            change=selection(model,action,request)
            next(r for r in model[change['group']] if r['id']==change['id'])[change['field']]=change['value']
        model.update(error='',stale=False,checkedAt=int(time.time()*1000))
        install(dict(state=model))

    specs=tuple(ActionSpec(action,{'shell'},lambda request:None,
        lambda request,action=action:demo(action,request),execution='worker',complete=install,
        presentation=lambda value:value['message'],prepare=lambda request,action=action:prepare(action,request)) for action in ACTIONS)
    return (*legacy,*specs),lambda:{**project(),**({'audioDevices':state['value']} if state else {})}
