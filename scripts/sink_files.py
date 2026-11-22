"""Safe file primitives for the kitty palette sink: one owned file and one managed block."""
# SPDX-License-Identifier: AGPL-3.0-or-later
# REL: scripts/palette_sinks.py (caller) + scripts/palette_render.py (content); tests/test_sink_files.py; docs/WORKSPACE_MAP.md
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import time


def _sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _atomic_write(path, text, mode):
    """Write in the target's directory, then replace, so readers see a whole file."""
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix='.lme-')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8', newline='') as stream:
            stream.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


class OwnedFile:
    """A file lme owns completely; undo is delete, so it keeps no backup."""

    def write(self, path: Path, content: str) -> None:
        _atomic_write(path, content, 0o600)

    def read(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding='utf-8')
        except FileNotFoundError:
            return None

    def remove(self, path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


class ManagedEdit:
    """One marked include block inside a user-owned file, plus JSON bookkeeping."""

    MARKER_BEGIN = '# BEGIN lme-shell palette (managed)'
    MARKER_END = '# END lme-shell palette (managed)'
    PAYLOAD = 'include lme-palette.conf'

    def __init__(self, bookkeeping_path: Path):
        self.bookkeeping_path = Path(bookkeeping_path)

    @classmethod
    def block_lines(cls) -> list[str]:
        return [cls.MARKER_BEGIN, cls.PAYLOAD, cls.MARKER_END]

    def _block_text(self):
        return '\n'.join(self.block_lines()) + '\n'

    def _load(self):
        try:
            state = json.loads(self.bookkeeping_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            state = None
        if not isinstance(state, dict) or not isinstance(state.get('paths'), dict):
            return {'paths': {}}
        return state

    def _save(self, state):
        self.bookkeeping_path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(state, indent=2, sort_keys=True) + '\n'
        _atomic_write(self.bookkeeping_path, text, 0o600)

    def _entry(self, state, target):
        return state['paths'].setdefault(str(target), {'backup': None, 'digest': None,
                                                       'created_by_lme': False, 'edited_at': 0.0})

    def _layout(self, text):
        """Classify markers: present, drifted (broken), or none."""
        lines = text.splitlines()
        begins = [index for index, line in enumerate(lines) if line.strip() == self.MARKER_BEGIN]
        ends = [index for index, line in enumerate(lines) if line.strip() == self.MARKER_END]
        if not begins and not ends:
            return 'none', lines, None
        if len(begins) != 1 or len(ends) != 1 or ends[0] != begins[0] + 2:
            return 'drifted', lines, None
        if lines[begins[0] + 1].strip() != self.PAYLOAD:
            return 'drifted', lines, None
        return 'present', lines, begins[0]

    def _write_backup(self, text, backup, mode):
        destination = Path(backup)
        destination.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(destination, text, mode)

    def ensure_block(self, path: Path) -> str:
        target = Path(os.path.realpath(path))
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            text = self._block_text()
            _atomic_write(target, text, 0o644)
            state = self._load()
            entry = self._entry(state, target)
            entry.update(backup=None, digest=_sha256(text), created_by_lme=True, edited_at=time.time())
            self._save(state)
            return 'inserted'
        text = target.read_text(encoding='utf-8')
        layout, lines, _ = self._layout(text)
        if layout == 'present':
            return 'present'
        if layout == 'drifted':
            return 'drifted'
        state = self._load()
        entry = self._entry(state, target)
        mode = stat.S_IMODE(target.stat().st_mode)
        # Keep created_by_lme only while the file still holds no user content.
        created = bool(entry.get('created_by_lme')) and not ''.join(lines).strip()
        backup = entry.get('backup')
        if not created and not backup:
            backup = str(self.bookkeeping_path.parent / 'kitty.conf.backup')
            self._write_backup(text, backup, mode)
        if not text or text.endswith('\n\n'):
            separator = ''
        elif text.endswith('\n'):
            separator = '\n'
        else:
            separator = '\n\n'
        final = text + separator + self._block_text()
        _atomic_write(target, final, mode)
        entry.update(backup=backup, digest=_sha256(final), created_by_lme=created, edited_at=time.time())
        self._save(state)
        return 'inserted'

    def remove_block(self, path: Path) -> str:
        target = Path(os.path.realpath(path))
        if not target.exists():
            return 'absent'
        text = target.read_text(encoding='utf-8')
        layout, lines, start = self._layout(text)
        if layout == 'drifted':
            return 'drifted'
        if layout == 'none':
            return 'absent'
        state = self._load()
        entry = self._entry(state, target)
        kept = lines[:start] + lines[start + 3:]
        if entry.get('created_by_lme') and not ''.join(kept).strip():
            target.unlink()
            state['paths'].pop(str(target), None)
            self._save(state)
            return 'created-removed'
        final = '\n'.join(kept) + '\n' if kept else ''
        while final.endswith('\n\n'):
            final = final[:-1]
        _atomic_write(target, final, stat.S_IMODE(target.stat().st_mode))
        entry.update(digest=_sha256(final), edited_at=time.time())
        self._save(state)
        return 'removed'

    def restore_backup(self, path: Path) -> None:
        """A5: restoring is an explicit user action, never part of undo."""
        target = Path(os.path.realpath(path))
        backup = self._load()['paths'].get(str(target), {}).get('backup')
        if not backup or not Path(backup).is_file():
            raise FileNotFoundError('No kitty.conf backup recorded for ' + str(target))
        mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
        _atomic_write(target, Path(backup).read_text(encoding='utf-8'), mode)
