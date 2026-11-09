"""Launchpad action provider; capabilities refer to the existing controller and current preferences.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: launchpad; Phase 3 graph).
"""
# REL: qml/panels/Launcher.qml – ActionSpec dispatch via scripts/backend_actions.py::ActionRegistry; scripts/desktop_backend.py host.
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
