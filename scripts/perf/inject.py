#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Drive scripts/perf/uinput_inject.c from Python: real input through one long-lived device pair.

  from inject import Injector
  with Injector(log_path) as inj:
      inj.tap("super", "a")                   # Mod+A, through the compositor's own bind
      reply = inj.click_at(960, 540)          # real pointer events
      reply.first_ns                          # CLOCK_REALTIME ns of the key-down / button-down

The device pair exists for the whole `with` block: creating a device reconfigures the
compositor seat, so that happens once per session, never per event. Every line the injector
prints is appended to the log together with the time it arrived, so a run can be replayed and
aligned with the probe log (which carries epoch milliseconds too).

Nothing here decides what to inject: scenarios.py does, and standin.py puts the owner's shell
back when input of theirs shows up.
"""
import os
import subprocess
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "uinput_inject.c"
DEFAULT_BINARY = HERE / "uinput_inject"


class InjectorError(RuntimeError):
    pass


def build(out: Path = DEFAULT_BINARY) -> Path:
    """Compile the injector next to its source unless that build is already current."""
    out = Path(out)
    if out.is_file() and out.stat().st_mtime >= SOURCE.stat().st_mtime:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["gcc", "-O2", "-Wall", "-o", str(out), str(SOURCE)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise InjectorError(f"cannot build {SOURCE.name}: {result.stderr.strip()[:400]}")
    return out


class Reply:
    """One answered command. `events` are the event batches it wrote: (mono_ns, real_ns, text)."""
    __slots__ = ("text", "ok", "seq", "mono_ns", "real_ns", "events", "arrived_ns")

    def __init__(self, text, ok, seq, mono_ns, real_ns, events, arrived_ns):
        self.text, self.ok, self.seq = text, ok, seq
        self.mono_ns, self.real_ns, self.arrived_ns = mono_ns, real_ns, arrived_ns
        self.events = events

    @property
    def first_ns(self):
        """CLOCK_REALTIME ns right after the first event batch of the command was written."""
        return self.events[0][1] if self.events else self.real_ns

    @property
    def first_ms(self):
        return self.first_ns / 1e6


class Injector:
    def __init__(self, log_path=None, width=1920, height=1080, deadman_ms=3000, binary=None, settle_ms=600):
        self.binary = Path(binary or DEFAULT_BINARY)
        self.width, self.height = width, height
        self.deadman_ms, self.settle_ms = deadman_ms, settle_ms
        self.log_path = Path(log_path) if log_path else None
        self.proc = None
        self.log = None
        self.seq = 0
        self.pending = {}
        self.before = []          # event lines seen since the previous reply
        self.lines = []           # every line, in arrival order
        self.condition = threading.Condition()
        self.write_lock = threading.Lock()
        self.failed = ""

    # ---- lifecycle -----------------------------------------------------------------
    def start(self, timeout=10.0):
        if not self.binary.is_file():
            raise InjectorError(f"{self.binary} is missing (inject.build())")
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log = open(self.log_path, "a", buffering=1)
        self.proc = subprocess.Popen([str(self.binary), "--width", str(self.width), "--height", str(self.height),
                                      "--deadman-ms", str(self.deadman_ms), "--settle-ms", str(self.settle_ms)],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()
        deadline = time.monotonic() + timeout
        with self.condition:
            while not self.failed and not self._ready():
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                self.condition.wait(timeout=left)
            ready = self._ready()
        if self.failed or not ready:
            self.close()
            raise InjectorError(f"the injector did not become ready: {self.failed or 'no ready line (is /dev/uinput writable?)'}")
        return self

    def _ready(self):
        return any(line.startswith("ready ") for line in self.lines)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()

    def _read(self):
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            arrived = time.time_ns()
            with self.condition:
                self.lines.append(line)
                if self.log:
                    self.log.write(f"{arrived} {line}\n")
                parts = line.split()
                if parts and parts[0] in ("ok", "bad") and len(parts) >= 5:
                    try:
                        seq = int(parts[1])
                        reply = Reply(" ".join(parts[5:]), parts[0] == "ok", seq, int(parts[2]), int(parts[3]),
                                      self.before, arrived)
                    except ValueError:
                        continue
                    self.before = []
                    slot = self.pending.get(seq)
                    if slot is not None:
                        slot.append(reply)
                        self.condition.notify_all()
                elif parts and parts[0] == "ev":
                    self.before.append((int(parts[1]), int(parts[2]), " ".join(parts[3:])))
                elif parts and parts[0] in ("err", "deadman"):
                    if parts[0] == "err":
                        self.failed = line
                    self.condition.notify_all()

    def close(self):
        """Ask the injector to quit (it releases everything it holds); make sure it is gone."""
        proc, self.proc = self.proc, None
        if not proc:
            return
        try:
            if proc.stdin:
                proc.stdin.write("quit\n")
                proc.stdin.flush()
                proc.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        if self.log:
            self.log.close()
            self.log = None

    # ---- commands ------------------------------------------------------------------
    def send(self, *commands, timeout=5.0):
        """Write the commands in one write (they run back to back) and wait for their replies."""
        text = ""
        with self.write_lock:
            for command in commands:
                self.seq += 1
                self.pending[self.seq] = []
                text += command + "\n"
            if self.proc is None or self.proc.poll() is not None:
                raise InjectorError(f"the injector is gone: {self.failed or 'exited'}")
            try:
                self.proc.stdin.write(text)
                self.proc.stdin.flush()
            except (OSError, ValueError) as error:
                raise InjectorError(f"cannot command the injector: {error}") from None
            deadline = time.monotonic() + timeout
            with self.condition:
                while not all(self.pending[seq] for seq in range(self.seq - len(commands) + 1, self.seq + 1)):
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise InjectorError(f"no reply to {commands!r}: {self.failed or 'timeout'}")
                    self.condition.wait(timeout=left)
                    if self.failed:
                        raise InjectorError(self.failed)
                replies = [self.pending.pop(seq)[0] for seq in range(self.seq - len(commands) + 1, self.seq + 1)]
        for reply in replies:
            if not reply.ok:
                raise InjectorError(f"the injector refused {reply.text!r}")
        return replies

    def note(self, text):
        """A driver annotation in the injector log (what is about to happen, in replay order)."""
        if self.log:
            self.log.write(f"{time.time_ns()} @ {text}\n")

    def key_down(self, name):
        return self.send(f"key {name} down")[0]

    def key_up(self, name):
        return self.send(f"key {name} up")[0]

    def tap(self, *names, hold=None):
        """Press in order, release in reverse order (modifiers first). One injector command."""
        options = f" hold={hold}" if hold is not None else ""
        return self.send("tap " + " ".join(names) + options)[0]

    def move(self, x, y):
        return self.send(f"move {int(round(x))} {int(round(y))}")[0]

    def click(self, button="left", hold=None):
        return self.send(f"click {button}" + (f" {int(hold)}" if hold is not None else ""))[0]

    def click_at(self, x, y, button="left", hold=None):
        """Pointer to (x, y) and click, written in one go so no other event can slip in between."""
        return self.send(f"move {int(round(x))} {int(round(y))}", f"click {button}" + (f" {int(hold)}" if hold is not None else ""))[1]

    def sleep(self, ms):
        self.note(f"sleep {ms}")
        time.sleep(ms / 1000.0)

    def release(self):
        return self.send("release")[0]

    def sync(self):
        return self.send("sync")[0]


if __name__ == "__main__":
    # Manual smoke test: create the devices, report, quit. Verifies /dev/uinput access only.
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        with Injector(Path(folder) / "inject.log") as injector:
            print(f"ready; devices created, reply to sync: {injector.sync().ok}")
