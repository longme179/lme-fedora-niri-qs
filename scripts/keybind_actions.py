"""Read-only keybinding refresh, with the original bundled demo input."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backend_actions import ActionSpec
from niri_keybinds import read_keybinds


@dataclass(frozen=True)
class KeybindCapabilities:
    path: Callable
    install: Callable


def provide(capabilities):
    def live(request):
        capabilities.install(read_keybinds(capabilities.path()))
        return 'Keybindings refreshed'

    def demo(request):
        capabilities.install(read_keybinds(str(Path(__file__).resolve().parents[1]/'config/niri/lme-shell.kdl')))

    return ((ActionSpec('keybindRefresh', {'shell', 'settings'}, live, demo),), lambda: {})
