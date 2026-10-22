"""Synchronous idle actions; existing host fields and worker lifecycle remain authoritative."""
from dataclasses import dataclass
import json
from typing import Callable

from backend_actions import ActionSpec


@dataclass(frozen=True)
class IdleCapabilities:
    preferences: Callable
    settings_only: Callable
    shell_entry: Callable
    ac_online: Callable
    available: Callable
    try_run: Callable
    install: Callable
    pause: Callable


def provide(capabilities):
    def live(request):
        capabilities.install({'source': 'ac' if capabilities.ac_online() else 'battery',
            'available': all(capabilities.available(name) for name in ('swayidle', 'swaylock', 'niri')), 'error': ''})
        if capabilities.settings_only():
            reply = capabilities.try_run('quickshell', '-p', capabilities.shell_entry(), 'ipc', 'call', 'shell', 'idleStatus')
            try:
                state = json.loads(reply or '{}')
                if isinstance(state, dict) and state.get('source') in {'ac', 'battery'}: capabilities.install(state)
            except ValueError: pass
        return 'Idle profile refreshed'

    def demo(request):
        capabilities.install({'source': 'battery', 'available': True, 'running': False, 'error': '',
                              'profile': capabilities.preferences()['idleProfiles']['battery']})

    def inhibit(request):
        if type(request.get('value')) is not bool: raise ValueError('Idle inhibit must be boolean')
        capabilities.pause(request['value'])
        return 'Idle paused' if request['value'] else 'Idle resumed'

    return ((ActionSpec('idleRefresh', {'shell', 'settings'}, live, demo),
             ActionSpec('idleInhibit', {'shell'}, inhibit, inhibit)), lambda: {})
