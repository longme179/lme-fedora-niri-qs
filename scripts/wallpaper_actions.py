"""The wallpaper scan pilot owns domain state, never scheduling or result publication."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backend_actions import ActionSpec
from command_runner import CommandError


@dataclass(frozen=True)
class WallpaperScanCapabilities:
    scan: Callable
    current: Callable
    install: Callable


def provide(capabilities):
    def scan(request):
        return capabilities.scan(request.get('folder'))

    def demo(request):
        bundled = Path(__file__).resolve().parents[1] / 'assets/wallpapers'
        capabilities.install(capabilities.scan(str(bundled)))

    def complete(value):
        if isinstance(value, (CommandError, ValueError, OSError)):
            capabilities.install({**capabilities.current(), 'error': str(value)[:400]})
        else:
            capabilities.install(value)

    spec = ActionSpec('wallpaperScan', {'shell', 'settings'}, scan, demo,
                      execution='worker', complete=complete, presentation='Wallpaper library refreshed')
    return (spec,), lambda: {}
