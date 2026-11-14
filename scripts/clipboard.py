#!/usr/bin/env python3
"""Bounded local clipboard history, one-shot native actions and the capture worker.

The Q5 native port retired the JSON-lines serve daemon: ClipboardState.qml owns the
flows, spawns scripts/clipboard_watch.py for capture and calls these one-shot
subcommands through a Process (one JSON line on stdout; exit 0 = ok, 1 = failure).
The capture worker prints one JSON event line ({"revision": N}) after every committed
store: wl-paste --watch forwards the worker's stdout, so the shell's watcher pipe
delivers the event and the open list refreshes immediately."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import shutil
import tempfile

from content_types import MAX_TEXT, image_type
from settings_schema import clipboard_schema as PREFERENCE_SCHEMA

MAX_IMAGE = 8 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_PINS = 20
# Undo-first (the iNiR pattern, rewritten): delete/clear park rows in the trash table
# under a fresh batch id; --restore takes a batch back, --settle finishes the removal.
MAX_KEEP_BATCHES = 12


def history_directory() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "lme-shell/clipboard"


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
            CREATE TABLE IF NOT EXISTS trash (
                batch INTEGER NOT NULL, id TEXT NOT NULL, kind TEXT NOT NULL, mime TEXT NOT NULL,
                data BLOB NOT NULL, preview TEXT NOT NULL, search TEXT NOT NULL, suffix TEXT NOT NULL,
                created REAL NOT NULL, pinned INTEGER NOT NULL DEFAULT 0, kept_at REAL NOT NULL,
                PRIMARY KEY (batch, id)
            );
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
            INSERT OR IGNORE INTO meta VALUES ('revision', 0), ('paused', 0), ('trash_batch', 0);
        """)
        (directory / "history.sqlite3").chmod(0o600)
        # Self-heal the file size: image churn leaves freelist pages nothing ever
        # reclaims (the live DB reached 42 MB holding 13 entries), so any opener
        # reclaims once when the waste passes 2048 pages (~8 MB).
        try:
            if self.db.execute("PRAGMA freelist_count").fetchone()[0] > 2048:
                self.db.execute("VACUUM")
        except sqlite3.Error:
            pass

    @property
    def revision(self) -> int:
        return self.db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0]

    @property
    def paused(self) -> bool:
        return bool(self.db.execute("SELECT value FROM meta WHERE key='paused'").fetchone()[0])

    @property
    def total(self) -> int:
        return self.db.execute("SELECT count(*) FROM entries").fetchone()[0]

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

    def delete(self, ident: str) -> int:
        """Undo-first delete: the row leaves history and parks in trash as one batch."""
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            rows = [self.item(ident)]
            batch = self._new_batch()
            self._park(batch, rows)
            self.remove_rows(rows)
            self.changed()
        return batch

    def clear(self, include_pinned: bool) -> int:
        if type(include_pinned) is not bool: raise ValueError("Clear mode must be true or false")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            ids = self.db.execute("SELECT id FROM entries" + ("" if include_pinned else " WHERE pinned=0")).fetchall()
            rows = [self.item(row['id']) for row in ids]
            batch = self._new_batch()
            self._park(batch, rows)
            self.remove_rows(rows)
            self.changed()
        return batch

    # ---- the undo-first seam: park rows in trash under one batch, take them back or finish --
    def _new_batch(self) -> int:
        batch = self.db.execute("SELECT value FROM meta WHERE key='trash_batch'").fetchone()[0] + 1
        self.db.execute("UPDATE meta SET value=? WHERE key='trash_batch'", (batch,))
        return batch

    def _park(self, batch: int, rows) -> None:
        """Park full rows under the batch; batches older than the window settle for good.
        The image files go with remove_rows — restore rewrites them from the parked data."""
        self.db.execute("DELETE FROM trash WHERE batch <= ?", (batch - MAX_KEEP_BATCHES,))
        for row in rows:
            self.db.execute("INSERT OR REPLACE INTO trash VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (batch, row['id'], row['kind'], row['mime'], row['data'], row['preview'],
                 row['search'], row['suffix'], row['created'], row['pinned'], time.time()))

    def restore(self, batch: int) -> int:
        """Take a trash batch back into history (trim keeps the size invariants)."""
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            rows = self.db.execute("SELECT * FROM trash WHERE batch=?", (batch,)).fetchall()
            if not rows: raise ValueError("Nothing to restore for this batch")
            for row in rows:
                self.db.execute("INSERT OR REPLACE INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (row['id'], row['kind'], row['mime'], row['data'], row['preview'],
                     row['search'], row['suffix'], row['created'], row['pinned']))
                if row['suffix']:
                    path = self.images / (row['id'] + "." + row['suffix'])
                    if not path.exists() and row['data']:
                        with tempfile.NamedTemporaryFile(dir=self.images, delete=False) as handle:
                            handle.write(row['data']); temporary = Path(handle.name)
                        os.replace(temporary, path)
            self.db.execute("DELETE FROM trash WHERE batch=?", (batch,))
            self.trim(); self.changed()
            return len(rows)

    def settle(self, batch: int) -> int:
        """Finish the removal: drop the parked batch. History and revision stay untouched."""
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            cursor = self.db.execute("DELETE FROM trash WHERE batch=?", (batch,))
            return cursor.rowcount


def capture(kind: str, directory: Path):  # REL: qml/services/ClipboardState.qml – spawned worker JSON-lines protocol
    if os.environ.get("CLIPBOARD_STATE", "data") != "data": return
    data = sys.stdin.buffer.read((MAX_TEXT if kind == "text" else MAX_IMAGE) + 1)
    config = preferences()
    if not config['clipboardEnabled'] or kind == "image" and not config['clipboardImages']: return
    history = History(directory, config['clipboardLimit'])
    try:
        ident = history.store(kind, data)
        # The event line rides the watcher pipe back to the shell (wl-paste --watch
        # forwards the worker's stdout — probed live 2026-11-13); silent on refusals.
        if ident: print(json.dumps({"revision": history.revision}), flush=True)
    except ValueError: pass  # Oversized/unsupported selections never print clipboard contents.
    finally: history.db.close()


def preferences() -> dict:
    defaults = PREFERENCE_SCHEMA.defaults("clipboard")
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "lme-shell/settings.json"
    try:
        value = json.loads(config.read_text())
        for key in defaults:
            try: defaults[key] = PREFERENCE_SCHEMA.validate(key, value.get(key))
            except ValueError: pass
    except (OSError, ValueError, AttributeError): pass
    return defaults


def reply(ok, **payload):
    print(json.dumps(dict(ok=ok, **payload), ensure_ascii=False, separators=(',', ':')), flush=True)
    return 0 if ok else 1


def run_action(args) -> int:
    """One native action per process: the serve loop's handlers, message for message."""
    history = History(args.directory)
    try:
        if args.state:
            return reply(True, available=bool(shutil.which('wl-copy') and shutil.which('wl-paste')),
                         paused=history.paused, total=history.total, revision=history.revision)
        if args.search is not None:
            query, kind = args.search
            if kind not in {'all', 'text', 'image'}: raise ValueError('Invalid search')
            return reply(True, entries=history.entries(query[:300], kind),
                         total=history.total, revision=history.revision)
        if args.copy is not None:
            item = history.item(args.copy)
            command = shutil.which('wl-copy')
            if not command: raise ValueError('Install wl-clipboard to copy items')
            subprocess.run([command, '--type', item['mime']], input=item['data'], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
            return reply(True, message='Copied to clipboard', total=history.total, revision=history.revision)
        batch = None
        if args.pin is not None:
            history.pin(args.pin)
        elif args.delete is not None:
            batch = history.delete(args.delete)
        elif args.clear is not None:
            batch = history.clear(args.clear)
        elif args.restore is not None:
            history.restore(args.restore)
        elif args.settle is not None:
            history.settle(args.settle)
        elif args.pause is not None:
            history.pause(args.pause)
        elif args.configure is not None:
            history.configure(args.configure)
        payload = dict(paused=history.paused, total=history.total, revision=history.revision)
        if batch is not None: payload['batch'] = batch
        return reply(True, **payload)
    except (KeyError, TypeError, ValueError, OSError, sqlite3.Error, subprocess.SubprocessError) as error:
        message = str(error)[:180] if isinstance(error, ValueError) else 'Clipboard operation failed. Check the Wayland session and local storage.'
        return reply(False, message=message)
    finally:
        history.db.close()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=history_directory())
    parser.add_argument('--capture', choices=['text', 'image'])
    parser.add_argument('--state', action='store_true')
    parser.add_argument('--search', nargs=2, metavar=('QUERY', 'KIND'))
    parser.add_argument('--copy', metavar='ID')
    parser.add_argument('--pin', metavar='ID')
    parser.add_argument('--delete', metavar='ID')
    parser.add_argument('--restore', type=int, metavar='BATCH')
    parser.add_argument('--settle', type=int, metavar='BATCH')
    parser.add_argument('--clear', type=lambda value: value == 'true', metavar='BOOL')
    parser.add_argument('--pause', type=lambda value: value == 'true', metavar='BOOL')
    parser.add_argument('--configure', type=int, metavar='LIMIT')
    args = parser.parse_args()
    if args.capture:
        capture(args.capture, args.directory.resolve())
        return 0
    return run_action(args)


if __name__ == '__main__': raise SystemExit(main())
