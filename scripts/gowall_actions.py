"""Gowall prefix admission is coordinator work; image utilities own the operations."""
from dataclasses import dataclass
from typing import Callable
from backend_actions import ActionSpec, PreparedWork


@dataclass(frozen=True)
class GowallCapabilities:
    pending: Callable
    themes: Callable
    generate: Callable
    save: Callable
    apply: Callable
    current: Callable
    install: Callable


def provide(cap):
    def prepare(action, request):
        if any(key.startswith('gowall') for key in cap.pending()):
            raise ValueError('A gowall operation is already running')
        if action=='gowallThemes': operation=cap.themes
        elif action=='gowallGenerate': operation=lambda:cap.generate(request)
        elif action=='gowallSave': operation=lambda:cap.save(request.get('path'),request.get('destination'))
        else: operation=lambda:cap.apply(request.get('path'),request.get('output',''))
        return PreparedWork(operation)
    def complete(action, value):
        if isinstance(value,Exception): return
        if action=='gowallThemes': cap.install({**cap.current(),'themes':value})
        elif action=='gowallGenerate': cap.install(value)
    def demo(action, request):
        if action=='gowallThemes': cap.install({**cap.current(),'themes':['dracula','nord','gruvbox','rose-pine']})
    names=('gowallThemes','gowallGenerate','gowallSave','gowallApply')
    messages={'gowallThemes':'Gowall themes loaded','gowallGenerate':'Gowall preview ready'}
    specs=tuple(ActionSpec(name,{'shell','settings'},lambda request:None,
        lambda request,name=name:demo(name,request),execution='worker',
        complete=lambda value,name=name:complete(name,value),presentation=messages.get(name),
        prepare=lambda request,name=name:prepare(name,request)) for name in names)
    return specs,lambda:{}
