"""Launchpad action provider; capabilities refer to the existing controller and current preferences."""
from dataclasses import dataclass
from typing import Callable

from backend_actions import ActionSpec


@dataclass(frozen=True)
class LaunchpadCapabilities:
    preferences: Callable
    run: Callable
    snapshot: Callable


def provide(capabilities):
    def run(request):
        preferences = capabilities.preferences()
        if not preferences['launchpadEnabled']: raise ValueError('Launchpad is disabled')
        return capabilities.run(request.get('id'), preferences['launchpadEntries'],
                                preferences['terminal'], request.get('mode'))

    return ((ActionSpec('launchpadRun', {'shell', 'settings'}, run, lambda request: None),),
            lambda: {'launchpadJobs': capabilities.snapshot()})
