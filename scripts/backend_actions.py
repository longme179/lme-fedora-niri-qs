"""Synchronous action ownership; the host retains protocol, acknowledgements and legacy routing."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ActionSpec:
    name: str
    contexts: frozenset[str]
    live: Callable
    demo: Callable
    execution: str = 'sync'
    complete: Callable | None = None
    presentation: object = None

    def __post_init__(self):
        object.__setattr__(self, 'contexts', frozenset(self.contexts))


class ActionRegistry:
    def __init__(self, specs=()):
        self._specs = {}
        self.register(specs)

    def register(self, specs):
        pending = {}
        for spec in specs:
            if spec.name in self._specs or spec.name in pending:
                raise ValueError('Duplicate action owner: '+spec.name)
            if spec.execution != 'sync':
                raise ValueError('Only synchronous actions are supported')
            pending[spec.name] = spec
        self._specs.update(pending)

    def get(self, name):
        return self._specs.get(name)

    def provide(self, providers):
        projections = []
        for factory, capabilities in providers:
            specs, project = factory(capabilities)
            self.register(specs)
            projections.append(project)
        return lambda: {key: value for project in projections for key, value in project().items()}

    def check_context(self, name, context):
        if context not in self._specs[name].contexts:
            raise ValueError('This action is unavailable in the settings app')

    def dispatch(self, name, request, *, context, demo):
        self.check_context(name, context)
        spec = self._specs[name]
        return (spec.demo if demo else spec.live)(request)
