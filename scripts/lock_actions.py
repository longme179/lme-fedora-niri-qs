"""Lock preflight stays on the coordinator; the lock service keeps its lifecycle.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: power; Phase 3 graph).
"""
# REL: qml/panels/PowerMenu.qml – ActionSpec dispatch via scripts/backend_actions.py::ActionRegistry; scripts/desktop_backend.py host.
from dataclasses import dataclass
from typing import Callable
from backend_actions import ActionSpec, PreparedWork


@dataclass(frozen=True)
class LockCapabilities:
    executable: Callable
    operation: Callable


def provide(cap):
    def prepare(request):
        cap.executable('swaylock')
        return PreparedWork(cap.operation())
    return ((ActionSpec('lock',{'shell'},lambda request:None,lambda request:None,
        execution='worker',complete=lambda value:None,prepare=prepare),),lambda:{})
