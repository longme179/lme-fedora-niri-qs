"""Private deployment journal and conservative, atomic rollback (desktop user only)."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

from storage import write_json


def fingerprint(path):
    if path.is_symlink(): return ['link', os.readlink(path)]
    if not path.exists(): return ['absent']
    mode = stat.S_IMODE(path.stat().st_mode)
    if path.is_dir():
        return ['directory', mode, [[str(p.relative_to(path)), fingerprint(p)]
                                    for p in sorted(path.iterdir())]]
    if not path.is_file(): raise ValueError(f'Not an ordinary file: {path}')
    return ['file', mode, hashlib.sha256(path.read_bytes()).hexdigest()]


def remove(path):
    if path.is_dir() and not path.is_symlink(): shutil.rmtree(path)
    elif path.exists() or path.is_symlink(): path.unlink()


def atomic(path, data=None, link=None, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix='.lme-', dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(fd, 'wb') as stream:
            if data is not None: stream.write(data)
            stream.flush(); os.fsync(stream.fileno())
        temporary.chmod(mode)
        if link is not None:
            temporary.unlink(); temporary.symlink_to(link)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if temporary.exists() or temporary.is_symlink(): temporary.unlink()


class Transaction:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, mode=0o700, exist_ok=False)
        self.entries = []
        self.status = 'applying'
        (self.folder/'changes.diff').touch(mode=0o600)
        self.save()

    def save(self):
        write_json(self.folder/'manifest.json', dict(version=1, status=self.status, entries=self.entries))

    def _put(self, path, data=None, link=None, mode=None):
        path = Path(os.path.abspath(path))
        before = fingerprint(path)
        if mode is None: mode = before[1] if before[0] == 'file' else 0o644
        after = ['link', str(link)] if link is not None else ['file', mode, hashlib.sha256(data).hexdigest()]
        if before == after: return False
        backup = self.folder/str(len(self.entries))
        if before[0] == 'link': backup.symlink_to(os.readlink(path))
        elif before[0] == 'directory': shutil.copytree(path, backup, symlinks=True)
        elif before[0] == 'file': shutil.copy2(path, backup)
        entry = dict(path=str(path), before=before, after=after, backup=backup.name)
        self.entries.append(entry); self.save()
        if data is not None:
            old = path.read_text(errors='replace') if before[0] == 'file' else ''
            with (self.folder/'changes.diff').open('a') as stream:
                stream.write(''.join(difflib.unified_diff(old.splitlines(True), data.decode(errors='replace').splitlines(True),
                                                       fromfile=str(path)+' (before)', tofile=str(path)+' (after)')))
        else:
            with (self.folder/'changes.diff').open('a') as stream:
                stream.write(f'{path}: {before} -> symlink {link}\n')
        if fingerprint(path) != before: raise ValueError(f'File changed during deployment: {path}')
        if before[0] == 'directory': path.rename(self.folder/(backup.name+'.displaced'))
        atomic(path, data=data, link=link, mode=mode)
        return True

    def write(self, path, data, mode=None): return self._put(path, data=data, mode=mode)
    def link(self, path, target): return self._put(path, link=target)

    def finish(self):
        self.status = 'complete'; self.save()

    @staticmethod
    def rollback(folder):
        folder = Path(folder)
        manifest = json.loads((folder/'manifest.json').read_text())
        if manifest.get('version') != 1: raise ValueError('Unsupported deployment journal')
        # Check all targets before restoring any: preserve later user edits as a unit.
        for item in manifest['entries']:
            current = fingerprint(Path(item['path']))
            displaced = folder/(item['backup']+'.displaced')
            if current not in (item['before'], item['after']) and not (current == ['absent'] and displaced.exists()):
                raise ValueError(f"File changed since deployment; rollback refused: {item['path']}")
        for item in reversed(manifest['entries']):
            path, before = Path(item['path']), item['before']
            if fingerprint(path) == before: continue
            backup = folder/item['backup']
            if before[0] == 'absent': remove(path)
            elif before[0] == 'link': atomic(path, link=before[1])
            elif before[0] == 'file': atomic(path, data=backup.read_bytes(), mode=before[1])
            else:
                remove(path); shutil.copytree(backup, path, symlinks=True)
        manifest['status'] = 'rolled-back'; write_json(folder/'manifest.json', manifest)
