"""Wallpaper actions own domain state, never scheduling or result publication."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backend_actions import ActionSpec, PreparedWork
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


@dataclass(frozen=True)
class WallpaperChangeCapabilities:
    pending: Callable
    apply: Callable
    advance: Callable
    reset: Callable
    preferences: Callable
    validate_path: Callable
    validate_outputs: Callable


def provide_changes(cap):
    def prepare(action, request):
        if any(key.startswith('wallpaper') for key in cap.pending()):
            raise ValueError('A wallpaper change is already running')
        if action=='wallpaper':
            operation=lambda:cap.apply(request.get('path'),output=request.get('output',''))
        elif action=='wallpaperNext': operation=lambda:cap.advance(request.get('output'))
        else: operation=lambda:cap.reset(request.get('output'))
        return PreparedWork(operation)
    def demo(action, request):
        prefs=cap.preferences()
        if action=='wallpaper':
            value=request.get('path')
            if not isinstance(value,str): raise ValueError('A wallpaper file path is required')
            path=str(Path(value).expanduser().resolve())
            if request.get('output'):
                prefs['wallpaperOutputs']={**prefs['wallpaperOutputs'],**cap.validate_outputs({request['output']:path})}
            else: prefs['wallpaper']=cap.validate_path(path)
        elif action=='wallpaperNext':
            if not prefs['wallpaperPlaylist']: raise ValueError('The playlist is empty')
        else:
            output=request.get('output')
            cap.validate_outputs({output:'/preview.png'})
            prefs['wallpaperOutputs']={key:value for key,value in prefs['wallpaperOutputs'].items() if key!=output}
    names=('wallpaper','wallpaperNext','wallpaperResetOutput')
    return tuple(ActionSpec(name,{'shell','settings'},lambda request:None,
        lambda request,name=name:demo(name,request),execution='worker',complete=lambda value:None,
        prepare=lambda request,name=name:prepare(name,request)) for name in names),lambda:{}
