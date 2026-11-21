"""Background watcher for the settings file (P2.3 two-way hot-reload).
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: shared; P2.3 hot-reload).
A daemon thread stat-polls the preferences file; when the on-disk stamp
changes and the reload is not this process's own atomic write
(Preferences._write refreshes the stamp reload() compares against), it
reloads the values and wakes the serve loop through the callback, so an
external edit reaches the UI within the poll interval plus loop latency —
well under a second. Own writes stay silent: reload() no-ops and the values
object is unchanged by the time the watcher looks at it.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import threading


class PrefsWatcher:
    def __init__(self, path, preferences, on_change, interval=0.25):
        self._path = path
        self._preferences = preferences
        self._on_change = on_change
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="lme-prefs-watch", daemon=True)

    def _stat(self):
        try:
            stat = os.stat(self._path)
            return (stat.st_mtime_ns, stat.st_size, stat.st_ino)
        except OSError:
            return None

    def _run(self):
        last = self._stat()
        while not self._stop.wait(self._interval):
            current = self._stat()
            if current == last:
                continue
            last = current
            before = self._preferences.values
            self._preferences.reload()
            # A no-op reload keeps the values object; a real one replaces it
            # (external edit, or the file disappearing back to defaults).
            if self._preferences.values is not before:
                self._on_change()

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
