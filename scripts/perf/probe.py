#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Talk to the probe of a running stand-in, and read what it wrote.

  probe = Probe(env, tree, log_dir, state_dir)   # the session's shell through Quickshell IPC
  probe.state()                                 # {"shell": {...}, "settings": {...}}, merged by process
  probe.rect("perfTab_devices")                 # centre of a named item, to aim a real click
  probe.watch(True)                             # start / stop the 40 ms state sampler
  tail = probe.tail("shell")                    # events since the previous call, epoch ms

The IPC is only ever used to observe, to aim, and to OPEN a top-level panel. Never to switch
a tab or a page: that is what the real input is for (mission rule).

Log side: "@@PROBE" lines of the shell and of the Settings process, "@@HEARTBEAT" lines of
the shell's own log and the lines of the injector all end up on one timeline in epoch
milliseconds. Every event carries the time its process wrote it (performance.now() there,
converted through the sink line), so latencies do not depend on when Python got around to
reading the file.
"""
import json
import subprocess
import time
from pathlib import Path

QS = Path.home() / ".local/share/lme-shell/deployment/bin/quickshell"
PROBE_MS = 100.0 * 1000.0  # 100 s: an IPC call that is not answered by then is answered never
OVERLAY = "lme-overlay"    # the shell's layer that takes the keyboard while a panel is open


class ProbeError(RuntimeError):
    pass


def sh(args, env=None, timeout=5.0):
    """(rc, stdout, stderr) of a tool call; a timeout is rc 124, a missing tool rc 127."""
    try:
        done = subprocess.run([str(a) for a in args], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", f"no answer within {timeout}s"
    except OSError as error:
        return 127, "", str(error)
    return done.returncode, done.stdout, done.stderr


def niri(args, env, timeout=5.0):
    rc, out, err = sh(["niri", "msg", "--json", *args], env=env, timeout=timeout)
    if rc != 0:
        raise ProbeError(f"niri msg {' '.join(args)} failed rc={rc}: {err.strip()[:200]}")
    return json.loads(out)


class Event:
    """One probe line: kind (m, F, S, heartbeat, other), `epoch` in epoch milliseconds."""
    __slots__ = ("kind", "ms", "epoch", "text", "data")

    def __init__(self, kind, ms, epoch, text, data=None):
        self.kind, self.ms, self.epoch, self.text, self.data = kind, ms, epoch, text, data

    def __repr__(self):
        return f"Event({self.kind}, {self.epoch:.1f}, {self.text!r})"


def offset_of(sink_line: str) -> float:
    """epoch ms = probe ms + offset, from `sink epoch=E clock=C t0=T0 hires=H`."""
    fields = dict(part.split("=", 1) for part in sink_line.split()[1:] if "=" in part)
    epoch, clock, t0 = float(fields["epoch"]), float(fields["clock"]), float(fields["t0"])
    # With performance.now() the probe clock starts at t0 (also performance.now()); without it
    # every reading is Date.now() and t0 is already an epoch time.
    return t0 + (epoch - clock if fields.get("hires") == "true" else 0.0)


class Tail:
    """Incremental reader of a log: new complete lines since the previous call.

    A probe log starts with its sink line, which fixes the origin (probe ms -> epoch ms); lines
    before it are skipped. A plain shell log has no probe clock: its heartbeat lines carry
    their own epoch time, every other line is timed at the moment it was read."""

    def __init__(self, path: Path, probe_clock: bool = True):
        self.path = Path(path)
        self.probe_clock = probe_clock
        self.offset = 0
        self.rest = ""
        self.origin = None   # epoch ms of probe ms 0, None until the sink line has been read

    def read(self) -> list:
        try:
            size = self.path.stat().st_size
            if size < self.offset:
                self.offset, self.rest = 0, ""   # rotated or rewritten: start over
            if size == self.offset:
                return []
            with open(self.path, "rb") as handle:
                handle.seek(self.offset)
                data = handle.read().decode(errors="replace")
            self.offset = size
        except OSError:
            return []
        read_at = time.time() * 1000.0
        lines = (self.rest + data).split("\n")
        self.rest = lines.pop()
        events = []
        for line in lines:
            line = line.rstrip("\r")
            if line.startswith("@@PROBE sink "):
                try:
                    self.origin = offset_of(line)
                except (KeyError, ValueError):
                    pass
                events.append(Event("sink", 0.0, 0.0, line))
                continue
            if not self.origin and self.probe_clock:
                continue
            origin = self.origin or 0.0
            if line.startswith("@@PROBE S "):
                try:
                    _, ms, payload = line.split(" ", 3)[1:]
                    events.append(Event("S", float(ms), float(ms) + origin, line, json.loads(payload)))
                except ValueError:
                    continue
            elif line.startswith("@@PROBE m ") or line.startswith("@@PROBE F "):
                try:
                    kind, ms, text = line.split(" ", 3)[1:]
                except ValueError:
                    continue
                try:
                    ms = float(ms)
                except ValueError:
                    continue
                events.append(Event(kind, ms, ms + origin, text))
            elif "@@HEARTBEAT stall " in line:
                # console.warn: Quickshell may put a level or a time in front of the message.
                line = line[line.index("@@HEARTBEAT stall "):]
                fields = dict(part.split("=", 1) for part in line.split() if "=" in part)
                try:
                    late, at = float(fields["late"]), float(fields["at"])
                except (KeyError, ValueError):
                    continue
                events.append(Event("stall", at - origin, at, line,
                                    {"late": late, "marks": fields.get("marks", ""), "beats": fields.get("beats", "")}))
            elif line.strip():
                events.append(Event("log", 0.0, read_at, line))
        return events


class Probe:
    """The stand-in's probe. Quickshell addresses an instance by its config: the shell is
    `-c lme-shell` (through the symlink, so it is the stand-in), Settings is `-p <tree>/settings.qml`
    (settings.sh resolves the tree with pwd -P, and the shell spawns Settings from its own tree)."""

    def __init__(self, env: dict, tree: Path, log_dir: Path, state_dir: Path, qs: Path = QS):
        self.env, self.tree, self.log_dir, self.state_dir = env, Path(tree), Path(log_dir), Path(state_dir)
        self.qs = Path(qs)
        self.expect_settings = False   # a scenario that works with Settings sets it: Settings is then asked too
        self.tails = {}
        self.pings = []
        self.calls = 0

    # ---- IPC -------------------------------------------------------------------------
    def _ask(self, backend: str, function, args, timeout):
        config = ("-c", "lme-shell") if backend == "shell" else ("-p", str(self.tree / "settings.qml"))
        self.calls += 1
        return sh([self.qs, *config, "ipc", "call", "probe", function, *args], env=self.env, timeout=timeout)

    @staticmethod
    def _json_lines(out: str) -> list:
        found = []
        for line in out.splitlines():
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if isinstance(data, dict):
                found.append(data)
        return found

    def call(self, function, *args, backend="shell", timeout=3.0):
        """Non-empty output lines of `ipc call probe <function>`; timeout is capped at 100 s
        because an IPC call the GUI thread does not answer by then is never answered."""
        rc, out, err = self._ask(backend, function, args, min(timeout, PROBE_MS))
        if rc == 0 and out.strip():
            return [line for line in out.splitlines() if line.strip()]
        raise ProbeError(f"probe {function} ({backend}): rc={rc} out={out.strip()[:120]!r} err={err.strip()[:160]!r}")

    def answers(self, function, *args, timeout=3.0) -> dict:
        """Answers of the asked process(es), keyed by the `proc` field ("shell", "settings")."""
        found = {}
        for data in self._json_lines("\n".join(self.call(function, *args, timeout=timeout))):
            if "proc" in data:
                found[data["proc"]] = data
        if self.expect_settings:
            rc, out, _ = self._ask("settings", function, args, min(timeout, PROBE_MS))
            for data in self._json_lines(out if rc == 0 else ""):
                if data.get("proc") == "settings":
                    found["settings"] = data
        return found

    def state(self, proc="shell") -> dict:
        return self.answers("state")[proc]

    def states(self) -> dict:
        return self.answers("state")

    def rect(self, name: str, backend=None) -> dict:
        """Centre of the named item (window-relative), or {"item": name, "found": False}."""
        backend = backend or ("settings" if name.startswith(("perfNav_", "perfSearch", "perfWallpaper", "perfClose")) else "shell")
        best = {"item": name, "found": False}
        for data in self._json_lines("\n".join(self.call("rect", name, backend=backend))):
            if data.get("item") == name:
                best = data
                if data.get("found"):
                    break
        return best

    def watch(self, on: bool):
        self.call("watch", "true" if on else "false")
        if self.expect_settings:
            self._ask("settings", "watch", ("true" if on else "false",), 3.0)

    def ping(self) -> float:
        """Round trip of one IPC call, which the GUI thread of the shell has to answer: milliseconds."""
        started = time.perf_counter()
        self.call("ping")
        self.pings.append((time.time() * 1000.0, (time.perf_counter() - started) * 1000.0))
        return self.pings[-1][1]

    def shell(self, function, *args):
        """An IpcHandler of the product itself (`shell toggle <panel>` opens a top-level panel)."""
        rc, out, err = sh([self.qs, "-c", "lme-shell", "ipc", "call", "shell", function, *args], env=self.env, timeout=3.0)
        if rc != 0:
            raise ProbeError(f"shell {function} failed rc={rc}: {err.strip()[:200]}")
        return out.strip()

    # ---- logs ----------------------------------------------------------------------------
    def tail(self, name="shell") -> Tail:
        if name not in self.tails:
            paths = {"shell": (self.log_dir / "probe.shell.log", True),
                     "settings": (self.log_dir / "probe.settings.log", True),
                     "shelllog": (self.state_dir / "log/lme-shell.log", False),
                     "settingslog": (self.state_dir / "log/settings.log", False)}
            path, probe_clock = paths[name]
            self.tails[name] = Tail(path, probe_clock)
        return self.tails[name]

    def drain(self, name="shell") -> list:
        return self.tail(name).read()

    def screen(self) -> dict:
        """The focused output in logical pixels, the coordinate space of the injector and of the rects."""
        focused = niri(["focused-output"], self.env)
        name = focused.get("name") or next(iter(niri(["outputs"], self.env)), "")
        outputs = niri(["outputs"], self.env)
        info = outputs.get(name) or {}
        logical = info.get("logical") or {}
        mode = info.get("current_mode") or {}
        return {"name": name, "x": logical.get("x", 0), "y": logical.get("y", 0), "width": logical.get("width", 0),
                "height": logical.get("height", 0), "scale": info.get("logical", {}).get("scale"),
                "refresh_hz": round(mode.get("refresh", 0) / 1000.0, 2) if mode.get("refresh") else None,
                "outputs": len(outputs)}

    # ---- compositor ------------------------------------------------------------------------
    def focused_workspace(self) -> dict:
        """{id, idx} of the focused workspace as niri sees it, or {} when niri does not say."""
        for space in niri(["workspaces"], self.env):
            if space.get("is_focused"):
                return {"id": space.get("id"), "idx": space.get("idx")}
        return {}

    def layers(self) -> list:
        return niri(["layers"], self.env)

    def layer_keyboards(self) -> dict:
        """{namespace: [keyboard interactivity of each of its surfaces]} on every output, found
        wherever niri keeps them (the shape of `layers` changed between niri versions)."""
        found = {}

        def walk(node):
            if isinstance(node, dict):
                if "namespace" in node and "keyboard_interactivity" in node:
                    found.setdefault(node["namespace"], []).append(node["keyboard_interactivity"])
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(self.layers())
        return found

    def keyboard_exclusive(self) -> bool:
        """True when the shell's overlay layer (namespace lme-overlay) holds the keyboard, as niri
        reports it: an injected Escape can only be delivered to the shell then."""
        return any(mode == "Exclusive" for mode in self.layer_keyboards().get(OVERLAY, []))

    def foreign_keyboard(self) -> list:
        """Namespaces other than the shell's overlay that hold the keyboard (an authentication
        dialog, a layer of another program): nothing may be injected while one of them does."""
        return sorted(name for name, modes in self.layer_keyboards().items() if name != OVERLAY and "Exclusive" in modes)

    def quit(self, backend="settings"):
        """End a process of the stand-in through its probe (Settings lingers 60 s after its last close)."""
        config = ("-c", "lme-shell") if backend == "shell" else ("-p", str(self.tree / "settings.qml"))
        sh([self.qs, *config, "ipc", "call", "probe", "quit"], env=self.env, timeout=3.0)

    def settings_origin(self) -> dict:
        """Where the floating Settings window sits on the output, from niri's own layout. `others`
        counts further Settings windows (one that lingers from another tree of the shell)."""
        windows = niri(["windows"], self.env)
        outputs = niri(["outputs"], self.env)
        found = [w for w in windows if w.get("app_id") == "lme-shell-settings"]
        if not found:
            return {"found": False, "windows": len(windows)}
        window = found[0]
        output = next((o for o in outputs.values() if o.get("logical")), {})
        pos = (window.get("layout") or {}).get("pos_in_window_layout") or [0, 0]
        logical = output.get("logical") or {}
        return {"found": True, "id": window.get("id"), "focused": window.get("is_focused"), "others": len(found) - 1,
                "floating": window.get("is_floating"), "x": logical.get("x", 0) + pos[0], "y": logical.get("y", 0) + pos[1],
                "w": ((window.get("layout") or {}).get("window_size") or [0, 0])[0],
                "h": ((window.get("layout") or {}).get("window_size") or [0, 0])[1]}
