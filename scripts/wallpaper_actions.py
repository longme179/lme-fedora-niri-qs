"""Wallpaper actions own domain state, never scheduling or result publication."""
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


@dataclass(frozen=True)
class WallpaperDaemonCapabilities:
    available: Callable
    run: Callable
    ready: Callable
    install: Callable


def provide_daemon(capabilities):
    def status(request):
        try:
            return {'available': capabilities.available('awww'), 'running': True,
                    'query': capabilities.run('awww', 'query', timeout=2), 'error': ''}
        except RuntimeError as error:
            return {'available': capabilities.available('awww'), 'running': False,
                    'query': '', 'error': str(error)}

    def demo_status(request):
        capabilities.install({'available': True, 'running': True,
                              'query': 'eDP-1: 1920x1080 · demo wallpaper', 'error': ''})

    def complete_status(value):
        if not isinstance(value, (CommandError, ValueError, OSError)):
            capabilities.install(value)

    def ensure(request):
        capabilities.ready()
        return 'Wallpaper daemon ready'

    specs = (
        ActionSpec('wallpaperStatus', {'shell', 'settings'}, status, demo_status,
                   execution='worker', complete=complete_status, presentation='Wallpaper daemon checked'),
        ActionSpec('wallpaperEnsure', {'shell', 'settings'}, ensure, lambda request: None,
                   execution='worker', complete=lambda value: None))
    return specs, lambda: {}
