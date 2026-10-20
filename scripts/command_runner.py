"""Shared unprivileged command execution and its public error type."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
from threading import Event, Lock
import time


TOOLS = (
    "wl-mirror", "niri", "nmcli", "bluetoothctl", "wpctl", "brightnessctl",
    "busctl", "powerprofilesctl", "gio", "swaylock", "systemctl",
    "gowall", "awww", "awww-daemon", "pkexec", "nm-connection-editor", "blueman-manager", "pavucontrol", "rfkill", "wl-copy", "swayidle", "quickshell", "wlsunset", "tesseract", "pw-dump", "matugen", "wf-recorder", "ffprobe", "ffmpeg", "pactl", "slurp", "satty", "swappy",
)


class CommandError(RuntimeError):
    """A missing command, timeout, or unsuccessful subprocess."""


class CommandRunner:
    def __init__(self) -> None:
        # Existing commands stay cached; missing or removed tools are rechecked on demand.
        self.commands = {name: shutil.which(name) for name in TOOLS}
        self.commands['quickshell'] = shutil.which(os.environ.get('LME_QS_BINARY', 'quickshell')) or self.commands['quickshell'] or shutil.which('qs')
        self.closed = Event()
        self.pending: set[Event] = set()
        self.lock = Lock()

    def available(self, name: str) -> bool:
        if name not in self.commands: return False
        path = self.commands[name]
        if not path or not os.access(path, os.X_OK):
            search = os.pathsep.join([os.environ.get("PATH", ""), str(Path.home()/".local/bin"), "/usr/local/bin", "/usr/bin", "/bin"])
            self.commands[name] = shutil.which(name, path=search)
            if name == 'quickshell':
                self.commands[name] = shutil.which(os.environ.get('LME_QS_BINARY','quickshell'),path=search) or self.commands[name] or shutil.which('qs',path=search)
        return bool(self.commands[name])

    def executable(self, name: str) -> str:
        if not self.available(name):
            raise CommandError(f"Required command is unavailable: {name}")
        return self.commands[name]

    def run(self, name: str, *args: str, timeout: float = 3.0, input: str | None = None) -> str:
        argv = [self.executable(name), *map(str, args)]
        if name == 'gowall':
            argv = [sys.executable, str(Path(__file__).with_name('managed_command.py')), '--parent', str(os.getpid()), '--', *argv]
        # wl-copy's clipboard owner keeps inherited pipes open after its parent exits.
        output = subprocess.DEVNULL if name == "wl-copy" else subprocess.PIPE
        done = Event()
        process = None
        input_stream = None
        try:
            if input is not None:
                # Keep retries independent of pipe capacity, without staging passwords on disk.
                input_stream = os.fdopen(os.memfd_create("lme-command-input", os.MFD_CLOEXEC), "w+b")
                input_stream.write(input.encode("utf-8"))
                input_stream.seek(0)
            with self.lock:
                if self.closed.is_set(): raise CommandError(f"{name} canceled: backend is closing")
                process = subprocess.Popen(
                    argv, stdin=input_stream,
                    stdout=output, stderr=output, text=True, encoding="utf-8", errors="replace",
                    env={**os.environ, "LC_ALL": "C"}, start_new_session=True,
                )
                self.pending.add(done)
            deadline = time.monotonic() + timeout
            while True:
                if self.closed.is_set():
                    self.stop(process)
                    raise CommandError(f"{name} canceled: backend is closing")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.stop(process)
                    raise CommandError(f"{name} timed out")
                try:
                    stdout, stderr = process.communicate(timeout=min(.1, remaining))
                    break
                except subprocess.TimeoutExpired: pass
        except OSError as exc:
            raise CommandError(f"Unable to run {name}: {exc.strerror}") from exc
        finally:
            try:
                if process is not None and process.returncode is None: self.stop(process)
            finally:
                if input_stream: input_stream.close()
                with self.lock: self.pending.discard(done)
                done.set()
        if process.returncode:
            detail = (stderr or "").strip() or (stdout or "").strip()
            detail = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', detail).strip()
            if input and input.strip(): detail = detail.replace(input.strip(), "[redacted]")
            detail = detail[:350]
            raise CommandError(f"{name} failed ({process.returncode})" + (f": {detail}" if detail else ""))
        return (stdout or "").strip()

    @staticmethod
    def stop(process):
        # The communicating thread alone signals/reaps, keeping the group ID reserved until kill.
        if process.returncode is None:
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            time.sleep(.1)
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        try: process.communicate(timeout=.5)
        except subprocess.TimeoutExpired:
            # A descendant that detached from the owned session must not hold shutdown's pipes open.
            process.wait(timeout=.5)
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream: stream.close()

    def close(self):
        with self.lock:
            self.closed.set()
            pending = tuple(self.pending)
        deadline = time.monotonic() + 2
        for done in pending: done.wait(max(0, deadline-time.monotonic()))

    def spawn(self, argv: list[str]) -> None:
        try:
            subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as exc:
            raise CommandError(f"Unable to launch {Path(argv[0]).name}: {exc.strerror}") from exc
