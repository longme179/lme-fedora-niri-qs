"""Kitty palette sink orchestration: async latest-wins sync, reload, undo and status."""
# SPDX-License-Identifier: AGPL-3.0-or-later
# REL: scripts/desktop_backend.py (configure) + scripts/palette_actions.py (apply/undo/status) + scripts/wallpaper_palette.py, appearance_actions.py (request_sync hooks); qml/settings/WallpaperPage.qml; tests/test_palette_sinks.py; docs/WORKSPACE_MAP.md
import copy
import hashlib
import os
from pathlib import Path
import re
import signal
import threading
import time
from desktop_features import PALETTE_CATALOG
from palette_render import effective_palette, render_details
from sink_files import ManagedEdit, OwnedFile

EXPECTED_KEYS = {'background', 'foreground', 'cursor', 'selection_background', 'selection_foreground'} | \
                {'color%d' % index for index in range(16)}
VALID_LINE = re.compile(r'(?:#.*|[a-z_0-9]+ #[0-9a-f]{6})\Z')
SIGNAL_ERRORS = (ProcessLookupError, PermissionError)

_lock = threading.RLock()
_config = None
_status = {'kitty': {'enabled': False}}
_generation = 0
_done_generation = 0
_worker = None
_epoch = 0


def configure(prefs_getter, runner, config_home=None, state_home=None, proc_root='/proc'):
    """Bind the sink to its paths and prefs; a new epoch retires the old worker."""
    global _config, _status, _generation, _done_generation, _worker, _epoch
    if config_home is None:
        config_home = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
    if state_home is None:
        state_home = os.environ.get('XDG_STATE_HOME') or os.path.expanduser('~/.local/state')
    kitty_dir = Path(config_home) / 'kitty'
    with _lock:
        _epoch += 1
        _config = {'prefs': prefs_getter, 'runner': runner, 'kitty_dir': kitty_dir,
                   'kitty_conf': kitty_dir / 'kitty.conf', 'palette_conf': kitty_dir / 'lme-palette.conf',
                   'bookkeeping': Path(state_home) / 'lme-shell' / 'sink-managed.json',
                   'proc_root': Path(proc_root), 'epoch': _epoch}
        _status = {'kitty': {'enabled': False}}
        _generation = 0
        _done_generation = 0
        _worker = None


def request_sync():
    """A4: cheap gate, then a lazy background worker; never blocks and never raises."""
    global _generation, _worker
    with _lock:
        config = _config
    if config is None:
        return
    try:
        prefs = config['prefs']()
    except Exception:
        return
    if not isinstance(prefs, dict) or prefs.get('paletteSinkKitty') is not True:
        return
    with _lock:
        if _config is not config:
            return
        _generation += 1
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_worker_loop, name='palette-sink', daemon=True)
            _worker.start()


def _worker_loop():
    global _done_generation
    with _lock:
        epoch = _config['epoch'] if _config is not None else None
    while True:
        with _lock:
            if _config is None or _config['epoch'] != epoch:
                return
            current = _generation
            if current == _done_generation:
                return
        try:
            _run()
        except Exception as error:
            _record_error(error)
        with _lock:
            if _config is None or _config['epoch'] != epoch:
                return
            _done_generation = current


def _wait_for_idle(timeout=5.0):
    with _lock:
        worker = _worker
    if worker is not None:
        worker.join(timeout)


def _config_snapshot():
    with _lock:
        return dict(_config) if _config is not None else None


def _set_status(kitty):
    global _status
    with _lock:
        _status = {'kitty': dict(kitty)}


def _status_update(**fields):
    global _status
    with _lock:
        kitty = dict(_status.get('kitty', {}))
        kitty.update(fields)
        _status = {'kitty': kitty}


def _record_error(error):
    _status_update(enabled=True, file='error', validated=False, error=str(error)[:200])


def status():
    with _lock:
        if _config is None:
            return {'kitty': {'enabled': False, 'error': 'not-configured'}}
        return copy.deepcopy(_status)


def kitty_pids(proc_root='/proc'):
    root = Path(proc_root)
    try:
        entries = os.listdir(root)
    except OSError:
        return []
    pids = []
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            comm = (root / entry / 'comm').read_text(encoding='utf-8').strip()
        except OSError:
            continue
        if comm == 'kitty':
            pids.append(int(entry))
    return sorted(pids)


def _signal_kitty(proc_root):
    signaled = 0
    for pid in kitty_pids(proc_root):
        try:
            os.kill(pid, signal.SIGUSR1)
        except SIGNAL_ERRORS:
            continue
        signaled += 1
    return signaled


def _routine_valid(text):
    keys = []
    for line in text.splitlines():
        if not VALID_LINE.fullmatch(line):
            return False
        if not line.startswith('#'):
            keys.append(line.split(' ', 1)[0])
    return len(keys) == len(EXPECTED_KEYS) and set(keys) == EXPECTED_KEYS


def _heavy_valid(runner, palette_conf):
    code = ("from kitty.config import load_config\nbad=[]\n"
            "load_config(%r, accumulate_bad_lines=bad)\nprint('BADLINES', bad)" % str(palette_conf))
    try:
        output = runner.run('kitty', '+runpy', code)
    except Exception:
        return False
    return 'BADLINES []' in output and 'Ignoring' not in output and 'Could not find' not in output


def _run(force=False, heavy=False):
    try:
        _run_guarded(force, heavy)
    except Exception as error:
        _record_error(error)


def _run_guarded(force, heavy):
    config = _config_snapshot()
    if config is None:
        return
    prefs = config['prefs']()
    if not isinstance(prefs, dict) or prefs.get('paletteSinkKitty') is not True:
        _set_status({'enabled': False})
        return
    palette = effective_palette(prefs, PALETTE_CATALOG)
    if 'unsupported' in palette:
        _status_update(enabled=True, file='absent-or-kept',
                       error='unsupported-source: ' + str(palette['unsupported']))
        return
    details = render_details(palette)
    text = details['text']
    include_state = 'declined'
    include_inserted = False
    if prefs.get('paletteSinkKittyInclude') is True:
        config['kitty_dir'].mkdir(parents=True, exist_ok=True)
        result = ManagedEdit(config['bookkeeping']).ensure_block(config['kitty_conf'])
        include_state = result
        if result == 'inserted':
            heavy = True
            include_inserted = True
    existing = OwnedFile().read(config['palette_conf'])
    content_changed = existing != text
    if not content_changed and not include_inserted and not force:
        _status_update(enabled=True, include=include_state, file='written')
        return
    if content_changed or force:
        config['kitty_dir'].mkdir(parents=True, exist_ok=True)
        OwnedFile().write(config['palette_conf'], text)
    validated = _routine_valid(text) and (_heavy_valid(config['runner'], config['palette_conf']) if heavy else True)
    signaled = 0
    if validated and (content_changed or include_inserted or force):
        signaled = _signal_kitty(config['proc_root'])
    fields = {'enabled': True, 'include': include_state, 'file': 'written', 'validated': validated,
              'adjusted': details['adjusted']}
    if validated:
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
        fields.update(error=None, lastApply={'at': time.time(), 'digest': digest, 'pids': signaled})
    else:
        fields['error'] = 'validation failed'
    _status_update(**fields)


def run_apply_now():
    _run(force=True, heavy=True)
    kitty = status().get('kitty', {})
    if kitty.get('validated') is True and kitty.get('file') == 'written':
        return 'Kitty palette applied'
    return 'Kitty palette not applied: ' + str(kitty.get('error') or 'not enabled')


def run_undo(prefs_setter):
    config = _config_snapshot()
    if config is None:
        return 'Kitty sink is not configured'
    result = ManagedEdit(config['bookkeeping']).remove_block(config['kitty_conf'])
    if result == 'drifted':
        _status_update(enabled=True, include='drifted')
        return 'kitty.conf block is drifted; nothing removed (restore manually)'
    OwnedFile().remove(config['palette_conf'])
    _signal_kitty(config['proc_root'])
    prefs_setter({'paletteSinkKitty': False, 'paletteSinkKittyInclude': False})
    _set_status({'enabled': False})
    return 'Kitty palette sink undone'
