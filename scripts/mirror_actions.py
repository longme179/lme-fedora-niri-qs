"""Mirror routing; the main shell retains the child and Settings uses its IPC."""
import copy
from dataclasses import dataclass
import json
from typing import Callable

from backend_actions import ActionSpec


@dataclass(frozen=True)
class MirrorCapabilities:
    settings_only: Callable
    preferences: Callable
    shell_entry: Callable
    available: Callable
    run: Callable
    try_run: Callable
    start: Callable
    stop: Callable
    state: Callable
    outputs: Callable
    current: Callable
    install: Callable
    refresh_displays: Callable
    displays: Callable


def provide(cap):
    def proxy(action, request):
        if action != 'mirrorRefresh':
            args = [request.get('source'), request.get('target')] if action == 'mirrorStart' else []
            if any(not isinstance(arg, str) for arg in args): raise ValueError('Choose source and target displays')
            reply = cap.run('quickshell', '-p', cap.shell_entry(), 'ipc', 'call', 'shell', action, *args)
            if reply.strip() != 'true':
                raise ValueError(f"Start {cap.preferences()['shellName']} before controlling display mirroring.")
        reply = cap.try_run('quickshell', '-p', cap.shell_entry(), 'ipc', 'call', 'shell', 'mirrorStatus')
        cap.install({'active': False, 'available': cap.available(),
            'error': f"Start {cap.preferences()['shellName']} before controlling display mirroring."})
        try:
            value = json.loads(reply or '{}')
            if isinstance(value, dict) and type(value.get('active')) is bool: cap.install(value)
        except ValueError: pass
        return 'Mirror refreshed' if action == 'mirrorRefresh' else 'Mirror request sent'

    def live(action, request):
        if cap.settings_only(): return proxy(action, request)
        if action == 'mirrorStart':
            if not cap.preferences()['mirroringEnabled']: raise ValueError('Display mirroring is disabled')
            return cap.start(request.get('source'), request.get('target'), cap.outputs())
        if action == 'mirrorStop': return cap.stop()
        cap.install(cap.state())
        return 'Mirror refreshed'

    def demo(action, request):
        if action == 'mirrorRefresh':
            cap.refresh_displays()
            if len(cap.displays()) == 1:
                external = copy.deepcopy(cap.displays()[0])
                external.update(name='HDMI-A-1', description='Demo projector', x=1920)
                cap.displays().append(external)
        if action == 'mirrorStart':
            names = {output['name'] for output in cap.displays() if output['enabled']}
            if request.get('source') not in names or request.get('target') not in names or request.get('source') == request.get('target'):
                raise ValueError('Choose two different, active niri displays.')
            if not cap.preferences()['mirroringEnabled']: raise ValueError('Display mirroring is disabled')
            cap.install({'active': True, 'available': True, 'source': request.get('source'), 'target': request.get('target'), 'error': ''})
        elif action == 'mirrorStop': cap.install({**cap.current(), 'active': False})

    return tuple(ActionSpec(name, {'shell', 'settings'},
        lambda request, name=name: live(name, request), lambda request, name=name: demo(name, request))
        for name in ('mirrorRefresh', 'mirrorStart', 'mirrorStop')), lambda: {}
