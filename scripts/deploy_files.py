"""Deterministic user launchers and deployment target admission."""
from pathlib import Path
import shlex

WRAPPER_MARKER = '# Managed by LME Shell deploy.\n'


def desktop_exec(path):
    value = str(path)
    if any(c in value for c in '\n\r\0'): raise ValueError('Launcher path contains a control character')
    for old, new in (('\\', '\\\\\\\\'), ('"', '\\\\"'), ('`', '\\\\`'), ('$', '\\\\$'), ('%', '%%')):
        value = value.replace(old, new)
    return '"'+value+'"'


def desktop(command):
    return ('[Desktop Entry]\nType=Application\nName=LME Shell Settings\n'
            'Comment=Personalize your smoked glass desktop\nExec='+command+'\n'
            'Icon=preferences-system\nTerminal=false\nCategories=Settings;DesktopSettings;\nStartupNotify=false\n').encode()


def wrapper(repo, runtime):
    return ('''#!/usr/bin/env bash
'''+WRAPPER_MARKER+'''set -euo pipefail
export PATH="${HOME}/.local/bin:${PATH}"
export LME_QS_BINARY='''+shlex.quote(str(runtime))+'''
repo='''+shlex.quote(str(repo))+'''
command="${1:-start}"
if (($#)); then shift; fi
case "$command" in
    start) exec "$repo/scripts/start.sh" --no-duplicate "$@" ;;
    settings) exec "$repo/scripts/settings.sh" "$@" ;;
    doctor) exec "$repo/scripts/doctor.sh" "$@" ;;
    toggle) exec "$LME_QS_BINARY" -c lme-shell ipc call shell toggle "$@" ;;
    *) printf 'Usage: lme-shell [start|settings|doctor|toggle PANEL] [options]\\n' >&2; exit 2 ;;
esac
''').encode()


def admit(path, repo, expected=None, replace=False, marker=None):
    """Check final symlinks without following them; never replace the checkout."""
    path = path.parent.resolve()/path.name
    if path == Path('/') or path == repo or path in repo.parents or repo in path.parents:
        raise ValueError(f'Deployment target must be outside the checkout: {path}')
    if not path.exists() and not path.is_symlink(): return path
    if expected is not None and path.is_symlink() and path.resolve() == expected: return path
    if marker and path.is_file() and not path.is_symlink() and marker in path.read_text(): return path
    if not replace: raise ValueError(f'Target exists: {path}. Use --replace to back it up and replace it.')
    return path


def paths(repo, config, data, replace=False):
    shell = admit(config/'quickshell/lme-shell', repo, expected=repo, replace=replace)
    command = admit(Path.home()/'.local/bin/lme-shell', repo, replace=replace, marker=WRAPPER_MARKER)
    entry = data/'applications/lme-shell-settings.desktop'
    if entry.is_file() and not entry.is_symlink() and entry.read_bytes() == desktop(desktop_exec(repo/'scripts/settings.sh')):
        entry = admit(entry, repo, replace=True)
    else:
        entry = admit(entry, repo, replace=replace, marker='X-LME-Deployment=true\n')
    runtime = data/'lme-shell/deployment/bin/quickshell'
    owned = command.is_file() and not command.is_symlink() and WRAPPER_MARKER in command.read_text()
    runtime = admit(runtime, repo, replace=replace or (owned and runtime.is_symlink()))
    return shell, command, entry, runtime
