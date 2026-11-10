"""Read-only keybinding refresh, with the original bundled demo input. DEPRECATED(Q4->Q6): native KeybindsState serves; fallback + demo provider through the A/B window.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: keybinds; Phase 3 graph).
"""
# REL: qml/settings/KeybindsPage.qml – ActionSpec dispatch via scripts/backend_actions.py::ActionRegistry; scripts/desktop_backend.py host.
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
