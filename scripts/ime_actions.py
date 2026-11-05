"""Input-method action; backend resolves the active fcitx5 method."""
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