"""Battery-saver admission delegates to its existing journal/restore controller.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: batterySaver; Phase 3 graph).
"""
# REL: qml/settings/BehaviorPage.qml – ActionSpec dispatch via scripts/backend_actions.py::ActionRegistry; scripts/desktop_backend.py host.
from dataclasses import dataclass
from typing import Callable
from backend_actions import ActionSpec, PreparedWork


@dataclass(frozen=True)
class SaverCapabilities:
    state: Callable
    preflight: Callable
    toggle: Callable
    demo_install: Callable


def provide(cap):
    def enabled(request):
        value=request.get('enabled')
        if type(value) is not bool: raise ValueError('Battery saver must be enabled or disabled')
        return value
    def prepare(request):
        value=enabled(request)
        cap.preflight(value,cap.state())
        return PreparedWork(lambda:cap.toggle(value))
    def demo(request):
        cap.demo_install({'active':enabled(request),'busy':False,'error':'','warnings':[]})
    return ((ActionSpec('batterySaver',{'shell','settings'},lambda request:None,demo,
        execution='worker',complete=lambda value:None,prepare=prepare),),lambda:{})
