"""Lock preflight stays on the coordinator; the lock service keeps its lifecycle."""
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
