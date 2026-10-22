"""Synchronous Night Light refresh; the host retains its periodic state/worker facade."""
from dataclasses import dataclass
import json
from typing import Callable

from backend_actions import ActionSpec


@dataclass(frozen=True)
class NightLightCapabilities:
    preferences: Callable
    settings_only: Callable
    shell_entry: Callable
    available: Callable
    run: Callable
    try_run: Callable
    install: Callable
    invalidate: Callable


def provide(capabilities):
    def live(request):
        if type(request.get('retry', False)) is not bool: raise ValueError('Night Light retry must be boolean')
        if capabilities.settings_only():
            capabilities.install({'available': capabilities.available('wlsunset'), 'active': False,
                'error': f"Start {capabilities.preferences()['shellName']} to control Night Light."})
            if request.get('retry'):
                capabilities.run('quickshell', '-p', capabilities.shell_entry(), 'ipc', 'call', 'shell', 'retryNightLight')
            reply = capabilities.try_run('quickshell', '-p', capabilities.shell_entry(), 'ipc', 'call', 'shell', 'nightLightStatus')
            try:
                state = json.loads(reply or '{}')
                if isinstance(state, dict) and 'active' in state: capabilities.install(state)
            except ValueError: pass
        else: capabilities.invalidate()
        return 'Night Light refreshed'

    def demo(request):
        prefs = capabilities.preferences()
        capabilities.install(dict(available=True, enabled=prefs['nightLightEnabled'], active=prefs['nightLightEnabled'],
            temperature=prefs['nightLightTemperature'], mode=prefs['nightLightMode'], start=prefs['nightLightStart'], end=prefs['nightLightEnd'], error=''))

    # State projection remains at the host's original slot; periodic sync still owns that facade.
    return ((ActionSpec('nightLightRefresh', {'shell', 'settings'}, live, demo),), lambda: {})
