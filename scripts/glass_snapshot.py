"""Per-output glass backdrop snapshots from live awww state; no rendering daemon."""
# SPDX-License-Identifier: GPL-3.0-or-later
# Behavioral reference: Serpantinum's WallpaperBlur snapshot cache (one file
# per output with a ?rev= invalidator). This module is an original LME
# implementation; no upstream source is vendored.
from pathlib import Path
from threading import RLock
import os
import re
import shutil
import struct
import tempfile
import zlib
from urllib.parse import quote

MAX_TOTAL = 64 * 1024 * 1024
MAX_FILES = 32
OUTPUT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}')
TEXT = re.compile(r'^(?:[^:\n]*:\s*)?([A-Za-z0-9][A-Za-z0-9_.-]*):\s*\d+x\d+[^\n]*?currently displaying:\s*(image|color):\s*(.+)$')


def color6(value):
    """Normalize an awww color token to lowercase RRGGBB, or None."""
    if not isinstance(value, str): return None
    text = value.strip().lower()
    if text.startswith('0x'): text = text[2:]
    if text.startswith('#'): text = text[1:]
    if not re.fullmatch(r'[0-9a-f]{6}(?:[0-9a-f]{2})?', text): return None
    return text[:6]


def query_displays(text):
    """Parse awww query output into {output: (kind, value)}.

    Kind is "image" (file path) or "color" (RRGGBB). Both text and
    ``--json`` forms are feature-detected; unrecognized output yields {} so
    callers fall back to the direct-file path.
    """
    if not isinstance(text, str) or not text.strip(): return {}
    stripped = text.strip()
    if stripped.startswith('{'):
        try:
            import json
            raw = json.loads(stripped)
        except ValueError: return {}
        if not isinstance(raw, dict): return {}
        found = {}
        for rows in raw.values():
            if not isinstance(rows, list): continue
            for row in rows:
                if not isinstance(row, dict): continue
                name = row.get('name')
                if not isinstance(name, str) or not OUTPUT.fullmatch(name): continue
                showing = row.get('displaying')
                if not isinstance(showing, dict): continue
                if isinstance(showing.get('image'), str) and showing['image'].strip():
                    found[name] = ('image', showing['image'].strip())
                elif isinstance(showing.get('color'), str) and color6(showing['color']):
                    found[name] = ('color', color6(showing['color']))
        return found
    found = {}
    for line in text.splitlines():
        match = TEXT.match(line)
        if not match: continue
        name, kind, rest = match.groups()
        if kind == 'image':
            path = rest.strip()
            if path: found[name] = ('image', path)
        else:
            token = color6(rest.strip().split()[0] if rest.strip() else '')
            if token: found[name] = ('color', token)
    return found


def flat_png(hexcolor):
    """Return a 1x1 RGB PNG filled with hexcolor (stdlib only)."""
    value = color6(hexcolor)
    if value is None: raise ValueError('Invalid color')
    rgb = bytes.fromhex(value)
    raw = b'\x00' + rgb

    def chunk(kind, data):
        body = kind + data
        return (struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xffffffff))
    signature = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    return signature + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


class GlassSnapshots:
    """One snapshot file per output under $XDG_CACHE_HOME/lme-shell/glass."""

    def __init__(self, directory=None, max_total=None, max_files=None):
        if directory is None:
            directory = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'lme-shell/glass'
        self.directory = Path(directory)
        self.max_total = MAX_TOTAL if max_total is None else max_total
        self.max_files = MAX_FILES if max_files is None else max_files
        self.revisions = {}
        self.fingerprints = {}
        self.kinds = {}
        self.lock = RLock()

    def path_for(self, output):
        if not isinstance(output, str) or not OUTPUT.fullmatch(output): return None
        return self.directory / (output + '.png')

    def snapshot(self):
        with self.lock:
            outputs = {}
            for name, rev in self.revisions.items():
                target = self.path_for(name)
                if target is None or not target.is_file(): continue
                url = 'file://' + quote(str(target), safe='/:')
                outputs[name] = {'rev': rev, 'kind': self.kinds.get(name, ''), 'url': url}
            return {'outputs': outputs}

    def _write(self, target, data=None, source=None):
        fd, temp = tempfile.mkstemp(prefix='.tmp-', suffix='.png', dir=str(self.directory))
        os.close(fd)
        temp = Path(temp)
        try:
            if source is not None: shutil.copyfile(source, temp)
            else:
                temp.write_bytes(data)
            os.replace(temp, target)
        finally:
            try: temp.unlink(missing_ok=True)
            except OSError: pass

    def _enforce(self):
        try: files = [p for p in self.directory.glob('*.png') if p.is_file()]
        except OSError: return
        try:
            items = sorted(files, key=lambda p: p.stat().st_mtime)
        except OSError: return
        total = 0
        sizes = {}
        for p in items:
            try: sizes[p] = p.stat().st_size
            except OSError: sizes[p] = 0
            total += sizes[p]
        for p in items:
            if total <= self.max_total and len([x for x in sizes if x.is_file()]) <= self.max_files: break
            try:
                total -= sizes.pop(p, 0)
                p.unlink()
                stem = p.stem
                if stem in self.revisions:
                    del self.revisions[stem]
                    self.fingerprints.pop(stem, None)
                    self.kinds.pop(stem, None)
            except OSError: continue

    def refresh(self, live_outputs, displays, enabled):
        """Write snapshots for live outputs from daemon state.

        Skips entirely (no I/O, no directory) when glass is off, mirroring
        Theme.liquidGlass. Stale outputs are pruned and the directory is
        bounded; failures keep the previous snapshot for that output.
        """
        if not enabled: return self.snapshot()
        live = set(live_outputs) if live_outputs is not None else set(displays)
        displays = displays or {}
        with self.lock:
            try: self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            except OSError: return self.snapshot()
            # Prune outputs that are no longer connected, including files
            # left by an earlier session (self.revisions is empty then).
            try: existing = list(self.directory.glob('*.png'))
            except OSError: existing = []
            for path in existing:
                if path.stem not in live:
                    try: path.unlink()
                    except OSError: pass
                    stem = path.stem
                    if stem in self.revisions:
                        del self.revisions[stem]
                        self.fingerprints.pop(stem, None)
                        self.kinds.pop(stem, None)
            for name in list(self.revisions):
                if name not in live:
                    del self.revisions[name]
                    self.fingerprints.pop(name, None)
                    self.kinds.pop(name, None)
            for name, entry in displays.items():
                target = self.path_for(name)
                if target is None or name not in live: continue
                if not isinstance(entry, (tuple, list)) or len(entry) != 2: continue
                kind, value = entry
                if kind == 'color':
                    color = color6(value) if isinstance(value, str) else None
                    if color is None: continue
                    fingerprint = ('color', color)
                    if self.fingerprints.get(name) == fingerprint and target.is_file(): continue
                    try: self._write(target, data=flat_png(color))
                    except OSError: continue
                elif kind == 'image':
                    if not isinstance(value, str) or not value.strip(): continue
                    source = Path(value.strip())
                    fingerprint = ('image', str(source))
                    if self.fingerprints.get(name) == fingerprint and target.is_file(): continue
                    try:
                        if not source.is_file(): continue
                        if source.stat().st_size > self.max_total: continue
                    except OSError: continue
                    try: self._write(target, source=source)
                    except OSError: continue
                else: continue
                self.fingerprints[name] = fingerprint
                self.kinds[name] = kind
                self.revisions[name] = self.revisions.get(name, 0) + 1
            self._enforce()
            return self.snapshot()
