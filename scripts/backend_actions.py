"""Action ownership; the host retains scheduling, protocol and completion publication."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class PreparedWork:
    operation: Callable
    metadata: dict | None = None


@dataclass(frozen=True)
class ActionSpec:
    name: str
    contexts: frozenset[str]
    live: Callable
    demo: Callable
    execution: str = 'sync'
    complete: Callable | None = None
    presentation: object = None
    prepare: Callable | None = None

    def __post_init__(self):
        object.__setattr__(self, 'contexts', frozenset(self.contexts))


class ActionRegistry:
    def __init__(self, specs=(), *, start_feature=None):
        self._start_feature = start_feature
        self._specs = {}
        self.register(specs)

    def register(self, specs):
        pending = {}
        for spec in specs:
            if spec.name in self._specs or spec.name in pending:
                raise ValueError('Duplicate action owner: '+spec.name)
            if spec.execution != 'sync' and not (spec.execution == 'worker' and callable(spec.complete)):
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
        return spec.demo(request) if demo else self.invoke_live(name, request)

    def invoke_live(self, name, request):
        spec = self._specs[name]
        if spec.execution == 'worker':
            if self._start_feature is None: raise ValueError('Worker dispatcher is unavailable')
            if spec.prepare is not None:
                prepared = spec.prepare(request)
                if not isinstance(prepared, PreparedWork) or not callable(prepared.operation):
                    raise ValueError('Prepared worker must provide an operation')
                if prepared.metadata:
                    return self._start_feature(name, prepared.operation, metadata=prepared.metadata)
                return self._start_feature(name, prepared.operation)
            return self._start_feature(name, lambda: spec.live(request))
        return spec.live(request)
