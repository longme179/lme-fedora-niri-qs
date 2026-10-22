"""Launcher and compositor actions; current state and history remain host services."""
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Callable

from backend_actions import ActionSpec
from command_runner import CommandError


@dataclass(frozen=True)
class WindowCapabilities:
    run: Callable
    spawn: Callable
    executable: Callable
    available: Callable
    preferences: Callable
    applications: Callable
    search_entries: Callable
    record_launch: Callable
    identifier: Callable
    niri: Callable
    refresh_niri: Callable
    niri_action: Callable
    demo_niri: Callable
    demo_apps: Callable


def provide(capabilities):
    def launch(request):
        app_id = request.get('id')
        entries = capabilities.applications()
        if not isinstance(app_id, str) or app_id not in entries:
            raise ValueError('Application is no longer available; refresh the launcher')
        app = entries[app_id]
        if app['terminal']:
            terminal = shutil.which(capabilities.preferences()['terminal'])
            if not terminal: raise CommandError('The configured terminal is unavailable')
            capabilities.spawn([terminal, '-e', *app['argv']])
        elif capabilities.available('gio'): capabilities.run('gio', 'launch', app['path'])
        else: capabilities.spawn(list(app['argv']))
        if capabilities.preferences()['launcherRanking']: capabilities.record_launch(app_id)
        return f"Launched {app['name']}"

    def file_open(request):
        path = request.get('path')
        if not isinstance(path, str) or not any(e['path'] == path for e in capabilities.search_entries()):
            raise ValueError('Search again before opening this file')
        target = Path(path)
        if str(target.resolve()) != path or not (target.is_file() or target.is_dir()):
            raise ValueError('File moved or became unavailable')
        capabilities.spawn([capabilities.executable('gio'), 'open', target.as_uri()])
        return 'Opened file'

    def focus(request):
        capabilities.run('niri', 'msg', 'action', 'focus-window', '--id', capabilities.identifier(request.get('id')))
        return 'Window focused'

    def move(request):
        window_id = int(capabilities.identifier(request.get('id')))
        workspace_id = int(capabilities.identifier(request.get('workspaceId')))
        niri = capabilities.refresh_niri()
        if (not any(item.get('id') == window_id for item in niri['windows'])
                or not any(item.get('id') == workspace_id for item in niri['workspaces'])):
            raise ValueError('Window or workspace is no longer available')
        capabilities.niri_action({'MoveWindowToWorkspace': {'window_id': window_id, 'reference': {'Id': workspace_id}, 'focus': False}})
        return 'Window moved to workspace'

    def overview(request):
        capabilities.run('niri', 'msg', 'action', 'toggle-overview')
        return 'Native overview toggled'

    def workspace(request):
        workspace_id = capabilities.identifier(request.get('id'))
        current = next((item for item in capabilities.niri()['workspaces'] if str(item.get('id')) == workspace_id), None)
        if current is None:
            current = next((item for item in capabilities.refresh_niri()['workspaces'] if str(item.get('id')) == workspace_id), None)
        if current is None: raise ValueError('Workspace is no longer available')
        capabilities.niri_action({'FocusWorkspace': {'reference': {'Id': int(workspace_id)}}})
        return 'Workspace focused'

    def demo(action, request):
        if action == 'launch':
            if not any(item['id'] == request.get('id') for item in capabilities.demo_apps()):
                raise ValueError('Application is no longer available')
        elif action in ('workspace', 'focusWindow', 'moveWindow'):
            niri = capabilities.demo_niri()
            ident = capabilities.identifier(request.get('id'))
            if action == 'workspace':
                if not any(str(item['id']) == ident for item in niri['workspaces']): raise ValueError('Workspace is no longer available')
                for item in niri['workspaces']: item['is_focused'] = item['is_active'] = str(item['id']) == ident
            elif action == 'focusWindow':
                if not any(str(item['id']) == ident for item in niri['windows']): raise ValueError('Window is no longer available')
                for item in niri['windows']: item['is_focused'] = str(item['id']) == ident
            else:
                workspace_id = capabilities.identifier(request.get('workspaceId'))
                window = next((item for item in niri['windows'] if str(item['id']) == ident), None)
                if window is None or not any(str(item['id']) == workspace_id for item in niri['workspaces']):
                    raise ValueError('Window or workspace is no longer available')
                window['workspace_id'] = int(workspace_id)

    handlers = {'launch': launch, 'focusWindow': focus, 'moveWindow': move, 'nativeOverview': overview, 'workspace': workspace, 'fileOpen': file_open}
    return tuple(ActionSpec(name, {'shell'}, live, lambda request, name=name: demo(name, request))
                 for name, live in handlers.items()), lambda: {}
