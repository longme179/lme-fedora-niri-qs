"""Charge request admission; the existing charge executor and completion stay owned."""
from dataclasses import dataclass
from typing import Callable
from backend_actions import ActionSpec


@dataclass(frozen=True)
class ChargeCapabilities:
    state: Callable
    pending: Callable
    submit: Callable
    invalidate: Callable
    demo_state: Callable


def provide(cap):
    def value(request):
        limit=request.get('value')
        if type(limit) is not int or limit not in (85,100):
            raise ValueError('Choose conservation (85) or maximum charge (100).')
        return limit
    def live(request):
        limit=value(request)
        state=cap.state()
        if not state['canSet']: raise ValueError(state['reason'])
        if cap.pending(): raise ValueError('A charge-mode change is already running.')
        cap.submit(limit)
        cap.invalidate()
        return 'Changing charge mode; administrator authentication may be required'
    def demo(request):
        limit=value(request)
        cap.demo_state().update(mode='conservation' if limit==85 else 'max',limitPercent=limit)
    return ((ActionSpec('chargeMode',{'shell'},live,demo),),lambda:{})
