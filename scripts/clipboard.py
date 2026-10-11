#!/usr/bin/env python3
"""Bounded local clipboard history and a JSON-lines Wayland capture service."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import sqlite3
import subprocess
import sys
import time
import shutil
import tempfile

MAX_TEXT = 1024 * 1024
MAX_IMAGE = 8 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_PINS = 20


def history_directory() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "lme-shell/clipboard"


def image_type(data: bytes) -> tuple[str, str]:
    for prefix, mime, suffix in [(b"\x89PNG\r\n\x1a\n", "image/png", "png"),
                                 (b"\xff\xd8\xff", "image/jpeg", "jpg"),
                                 (b"GIF87a", "image/gif", "gif"), (b"GIF89a", "image/gif", "gif"),
                                 (b"BM", "image/bmp", "bmp")]:
        if data.startswith(prefix): return mime, suffix
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP": return "image/webp", "webp"
    raise ValueError("Unsupported clipboard image format")


class History:
    def __init__(self, directory: Path, limit: int = 100, max_total: int = MAX_TOTAL):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        self.images = directory / "images"
        self.images.mkdir(exist_ok=True, mode=0o700)
        self.limit, self.max_total = limit, max_total
        self.db = sqlite3.connect(directory / "history.sqlite3", timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, mime TEXT NOT NULL,
                data BLOB NOT NULL, preview TEXT NOT NULL, search TEXT NOT NULL,
                suffix TEXT NOT NULL, created REAL NOT NULL, pinned INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
            INSERT OR IGNORE INTO meta VALUES ('revision', 0), ('paused', 0);
        """)
        (directory / "history.sqlite3").chmod(0o600)

    @property
    def revision(self) -> int:
        return self.db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0]

    @property
    def paused(self) -> bool:
        return bool(self.db.execute("SELECT value FROM meta WHERE key='paused'").fetchone()[0])

    def changed(self):
        self.db.execute("UPDATE meta SET value=value+1 WHERE key='revision'")

    def pause(self, value: bool):
        if type(value) is not bool: raise ValueError("Pause must be true or false")
        with self.db:
            self.db.execute("UPDATE meta SET value=? WHERE key='paused'", (int(value),))
            self.changed()

    def remove_rows(self, rows):
        for row in rows:
            self.db.execute("DELETE FROM entries WHERE id=?", (row['id'],))
            if row['suffix']: (self.images / (row['id'] + "." + row['suffix'])).unlink(missing_ok=True)

    def trim(self):
        rows = self.db.execute("SELECT id, suffix, pinned, length(data) AS bytes FROM entries ORDER BY created DESC, id").fetchall()
        count, size = len(rows), sum(row['bytes'] for row in rows)
        victims = []
        for row in reversed(rows):
            if count <= self.limit and size <= self.max_total: break
            if row['pinned']: continue
            victims.append(row); count -= 1; size -= row['bytes']
        self.remove_rows(victims)

    def configure(self, limit: int):
        if type(limit) is not int or not 20 <= limit <= 500: raise ValueError("History limit must be between 20 and 500")
        if limit == self.limit: return
        self.limit = limit
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self.trim(); self.changed()

    def store(self, kind: str, data: bytes) -> str | None:
        if not data or self.paused: return None
        if kind not in {"text", "image"}: raise ValueError("Unknown clipboard type")
        if len(data) > (MAX_TEXT if kind == "text" else MAX_IMAGE): raise ValueError("Clipboard item exceeds the size limit")
        if kind == "text":
            text = data.decode("utf-8", errors="replace")
            if "\0" in text: return None
            mime, suffix = "text/plain;charset=utf-8", ""
            preview, search = text[:240], text.casefold()
        else:
            mime, suffix = image_type(data)
            preview, search = f"{suffix.upper()} image · {round(len(data) / 1024)} KB", "image " + mime
        ident = hashlib.sha256(mime.encode() + b"\0" + data).hexdigest()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            # Re-check inside the write lock, after an in-flight pause action.
            if self.paused: return None
            self.db.execute("""INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(id) DO UPDATE SET created=excluded.created""",
                (ident, kind, mime, data, preview, search, suffix, time.time()))
            if suffix:
                path = self.images / (ident + "." + suffix)
                if not path.exists():
                    with tempfile.NamedTemporaryFile(dir=self.images, delete=False) as handle:
                        handle.write(data); temporary = Path(handle.name)
                    os.replace(temporary, path)
            self.trim(); self.changed()
        return ident

    def entries(self, query: str = "", kind: str = "all") -> list[dict]:
        if kind not in {"all", "text", "image"}: raise ValueError("Unknown history filter")
        rows = self.db.execute("""SELECT id, kind, mime, preview, suffix, created, pinned, length(data) AS bytes
            FROM entries WHERE instr(search, ?) > 0 AND (?='all' OR kind=?)
            ORDER BY pinned DESC, created DESC, id""", (query.casefold()[:300], kind, kind))
        return [{"id": r['id'], "kind": r['kind'], "mime": r['mime'], "preview": r['preview'],
                 "created": r['created'], "pinned": bool(r['pinned']), "bytes": r['bytes'],
                 "image": (self.images / (r['id'] + "." + r['suffix'])).as_uri() if r['suffix'] else ""} for r in rows]

    def item(self, ident: str):
        if not isinstance(ident, str) or len(ident) != 64: raise ValueError("Invalid clipboard item")
        row = self.db.execute("SELECT * FROM entries WHERE id=?", (ident,)).fetchone()
        if row is None: raise ValueError("This clipboard item is no longer available")
        return row

    def pin(self, ident: str):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.item(ident)
            if not row['pinned'] and self.db.execute("SELECT count(*) FROM entries WHERE pinned=1").fetchone()[0] >= MAX_PINS:
                raise ValueError("Up to 20 clipboard items can be pinned")
            self.db.execute("UPDATE entries SET pinned=? WHERE id=?", (int(not row['pinned']), ident))
            self.trim(); self.changed()

    def delete(self, ident: str):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self.remove_rows([self.item(ident)]); self.changed()

    def clear(self, include_pinned: bool):
        if type(include_pinned) is not bool: raise ValueError("Clear mode must be true or false")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            rows = self.db.execute("SELECT id, suffix FROM entries" + ("" if include_pinned else " WHERE pinned=0")).fetchall()
            self.remove_rows(rows); self.changed()


def capture(kind: str, directory: Path):
    if os.environ.get("CLIPBOARD_STATE", "data") != "data": return
    data = sys.stdin.buffer.read((MAX_TEXT if kind == "text" else MAX_IMAGE) + 1)
    config = preferences()
    if not config['clipboardEnabled'] or kind == "image" and not config['clipboardImages']: return
    history = History(directory, config['clipboardLimit'])
    try: history.store(kind, data)
    except ValueError: pass  # Oversized/unsupported selections never print clipboard contents.
    finally: history.db.close()


def preferences() -> dict:
    defaults = {"clipboardEnabled": True, "clipboardImages": True, "clipboardLimit": 100}
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "lme-shell/settings.json"
    try:
        value = json.loads(config.read_text())
        for key in ["clipboardEnabled", "clipboardImages"]:
            if type(value.get(key)) is bool: defaults[key] = value[key]
        if type(value.get('clipboardLimit')) is int and 20 <= value['clipboardLimit'] <= 500:
            defaults['clipboardLimit'] = value['clipboardLimit']
    except (OSError, ValueError, AttributeError): pass
    return defaults


class CaptureService:
    def __init__(self, history: History):
        self.history = history
        self.watchers = {}
        self.lock = None
        self.error = ""
        self.last_retry = 0

    def stop(self):
        for watcher in self.watchers.values():
            if watcher.poll() is None:
                watcher.terminate()
                try: watcher.wait(timeout=2)
                except subprocess.TimeoutExpired: watcher.kill(); watcher.wait()
        self.watchers = {}
        if self.lock is not None: self.lock.close(); self.lock = None

    def update(self, config: dict):
        self.history.configure(config['clipboardLimit'])
        wanted = ['text', 'image'] if config['clipboardImages'] else ['text']
        enabled = config['clipboardEnabled'] and not self.history.paused
        if not enabled:
            self.stop(); self.error = ""; return
        if set(self.watchers) == set(wanted) and all(p.poll() is None for p in self.watchers.values()): return
        if self.watchers and any(p.poll() is not None for p in self.watchers.values()):
            self.error = "Clipboard capture stopped. Check Wayland data-control support and the session."
        if time.monotonic() - self.last_retry < 5: return
        self.last_retry = time.monotonic()
        self.stop()
        executable = shutil.which('wl-paste')
        if not executable or not shutil.which('wl-copy'):
            self.error = "Install wl-clipboard to capture and copy clipboard items."; return
        lock = (self.history.directory / "capture.lock").open('a')
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close(); self.error = "Another shell instance owns clipboard capture."; return
        self.lock = lock
        try:
            for kind in wanted:
                self.watchers[kind] = subprocess.Popen([executable, '--no-newline', '--type', kind, '--watch',
                    sys.executable, str(Path(__file__).resolve()), '--capture', kind, '--directory', str(self.history.directory)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.error = ""
        except OSError:
            self.stop(); self.error = "Clipboard capture could not start. Check the Wayland session."


def serve(directory: Path):
    history = History(directory)
    capture_service = CaptureService(history)
    query, kind, last_result, sequence = "", "all", None, 0
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    selector = selectors.DefaultSelector()
    selector.register(sys.stdin, selectors.EVENT_READ)
    buffer, last_signature, last_config, available = b"", None, 0, False
    try:
        while running:
            if time.monotonic() - last_config >= 1:
                capture_service.update(preferences()); last_config = time.monotonic()
                available = bool(shutil.which('wl-copy') and shutil.which('wl-paste'))
            revision, paused = history.revision, history.paused
            capturing = bool(capture_service.watchers) and all(p.poll() is None for p in capture_service.watchers.values())
            signature = (revision, paused, capturing, available, capture_service.error, sequence, query, kind)
            # Poll a tiny revision counter; do not sort/serialize all history
            # four times a second when the clipboard is idle.
            if signature != last_signature:
                state = {"entries": history.entries(query, kind), "paused": paused,
                         "capturing": capturing, "available": available,
                         "total": history.db.execute('SELECT count(*) FROM entries').fetchone()[0],
                         "revision": revision, "error": capture_service.error, "lastResult": last_result}
                print(json.dumps(state, ensure_ascii=False, separators=(',', ':')), flush=True)
                last_signature = signature
            if not selector.select(.25): continue
            chunk = os.read(sys.stdin.fileno(), 8192)
            if not chunk: break
            buffer += chunk
            if len(buffer) > 65536: buffer = b""; continue
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                action, ok, message = "", True, ""
                try:
                    request = json.loads(line)
                    action = request['action']
                    if action == 'search':
                        query, kind = request.get('query', ''), request.get('kind', 'all')
                        if not isinstance(query, str) or kind not in {'all', 'text', 'image'}: raise ValueError('Invalid search')
                        query = query[:300]
                    elif action == 'copy':
                        item = history.item(request.get('id'))
                        command = shutil.which('wl-copy')
                        if not command: raise ValueError('Install wl-clipboard to copy items')
                        subprocess.run([command, '--type', item['mime']], input=item['data'], check=True,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
                        message = 'Copied to clipboard'
                    elif action == 'pin': history.pin(request.get('id'))
                    elif action == 'delete': history.delete(request.get('id'))
                    elif action == 'clear': history.clear(request.get('includePinned', False))
                    elif action == 'pause':
                        history.pause(request.get('value')); capture_service.last_retry = 0
                        capture_service.update(preferences())
                    else: raise ValueError('Unknown clipboard action')
                except (KeyError, TypeError, ValueError, OSError, sqlite3.Error, subprocess.SubprocessError) as error:
                    ok = False
                    message = str(error)[:180] if isinstance(error, ValueError) else 'Clipboard operation failed. Check the Wayland session and local storage.'
                    if action == 'search': query, kind = '', 'all'
                sequence += 1
                last_result = {'action': action, 'ok': ok, 'message': message, 'sequence': sequence}
    finally:
        capture_service.stop(); selector.close(); history.db.close()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=history_directory())
    parser.add_argument('--capture', choices=['text', 'image'])
    args = parser.parse_args()
    if args.capture: capture(args.capture, args.directory.resolve())
    else: serve(args.directory.resolve())


if __name__ == '__main__': main()
