"""Input-method action; backend resolves the active fcitx5 method.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: ime; Phase 3 graph).
"""
# REL: qml/bar/ImeModule.qml – ActionSpec dispatch via scripts/backend_actions.py::ActionRegistry; scripts/desktop_backend.py host.
from dataclasses import dataclass
from typing import Callable

from backend_actions import ActionSpec


@dataclass(frozen=True)
class ImeCapabilities:
    run: Callable
    available: Callable


def provide(capabilities):
    def live(request):
        name = capabilities.run("fcitx5-remote", "-n")
        return str(name).strip() if isinstance(name, str) else str(name).strip()

    def demo(request):
        return "lotus"

    return ((ActionSpec("inputMethod", {"shell"}, live, demo),), lambda: {})