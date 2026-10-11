#!/usr/bin/env python3
"""niri output previews with an independent, crash-resistant revert timer."""
from __future__ import annotations

import contextlib
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid


def normalized_outputs(raw):
    if not isinstance(raw, dict):
        raise ValueError("Invalid niri outputs response")
    outputs = []
    for name, output in raw.items():
        if not isinstance(output, dict) or not isinstance(name, str): continue
        modes = output.get("modes") or []
        modes = [{"width": m["width"], "height": m["height"], "refresh": m["refresh_rate"],
                  "label": f'{m["width"]} × {m["height"]} · {m["refresh_rate"] / 1000:g} Hz'}
                 for m in modes if isinstance(m, dict) and all(type(m.get(k)) is int and m[k] > 0 for k in ("width", "height", "refresh_rate"))]
        index = output.get("current_mode")
        logical = output.get("logical") or {}
        current = modes[index] if type(index) is int and 0 <= index < len(modes) else None
        outputs.append({"name": name, "description": " ".join(str(output.get(k) or "") for k in ("make", "model")).strip(),
                        "modes": modes, "current": current, "enabled": current is not None,
                        "scale": logical.get("scale", 1), "x": logical.get("x", 0), "y": logical.get("y", 0),
                        "width": logical.get("width", 0), "height": logical.get("height", 0)})
    return sorted(outputs, key=lambda item: item["name"])


def validate_layout(value, outputs=None):
    if not isinstance(value, list) or not 1 <= len(value) <= 16:
        raise ValueError("Choose at least one display")
    result, seen = [], set()
    for item in value:
        if not isinstance(item, dict): raise ValueError("Invalid display settings")
        name = item.get("name")
        if not isinstance(name, str) or not 1 <= len(name) <= 128 or any(ord(c) < 32 for c in name) or name in seen:
            raise ValueError("Invalid or duplicate output name")
        seen.add(name)
        for key in ("width", "height", "refresh"):
            if type(item.get(key)) is not int or not 1 <= item[key] <= 1000000:
                raise ValueError("Invalid display mode")
        scale = item.get("scale")
        if type(scale) not in (int, float) or not math.isfinite(scale) or not .5 <= scale <= 3:
            raise ValueError("Scale must be between 0.5 and 3")
        if any(type(item.get(key)) is not int or not -32768 <= item[key] <= 32768 for key in ("x", "y")):
            raise ValueError("Display coordinates must be integers between -32768 and 32768")
        if outputs is not None:
            output = next((o for o in outputs if o["name"] == name and o["enabled"]), None)
            if not output or not any(all(m[k] == item[k] for k in ("width", "height", "refresh")) for m in output["modes"]):
                raise ValueError("Display or mode is no longer available; refresh displays")
        result.append({key: item[key] for key in ("name", "width", "height", "refresh", "scale", "x", "y")})
    return result


def current_layout(outputs):
    return [{"name": o["name"], **{k: o["current"][k] for k in ("width", "height", "refresh")},
             **{k: o[k] for k in ("scale", "x", "y")}} for o in outputs if o["current"]]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = stream.name
            os.chmod(temporary, 0o600)
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)


def read_json(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError): return default


@contextlib.contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(path, "a", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def apply_layout(layout, run, best_effort=False):
    errors = []
    for item in validate_layout(layout):
        mode = f'{item["width"]}x{item["height"]}@{item["refresh"] / 1000:.3f}'
        for args in (("mode", mode), ("scale", str(item["scale"])), ("position", "set", str(item["x"]), str(item["y"]))):
            try: run("niri", "msg", "output", item["name"], *args)
            except (RuntimeError, OSError) as exc:
                if not best_effort: raise
                errors.append(str(exc))
    return errors


class DisplayControl:
    def __init__(self, runner, directory=None):
        self.runner = runner
        self.directory = directory or Path(os.environ.get("XDG_RUNTIME_DIR", os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))) / "lme-shell"
        self.path = self.directory / "display-preview.json"

    def outputs(self):
        try: return normalized_outputs(json.loads(self.runner.run("niri", "msg", "--json", "outputs")))
        except (RuntimeError, OSError, ValueError): return []

    def snapshot(self):
        state = read_json(self.path, {})
        # A previous compositor session cannot be confirmed or applied here.
        if state.get("socket") != os.environ.get("NIRI_SOCKET", ""): state = {}
        return {"outputs": self.outputs(), "preview": {k: state[k] for k in ("token", "status", "deadline", "error") if k in state}}

    def start(self, layout):
        state = read_json(self.path, {})
        if state.get("status") in {"applying", "pending", "reverting"} and time.time() < state.get("deadline", 0) + 5:
            raise ValueError("Confirm or revert the current preview first")
        outputs = self.outputs()
        layout = validate_layout(layout, outputs)
        original = current_layout(outputs)
        if not original: raise ValueError("No active niri displays")
        token = uuid.uuid4().hex
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {"token": token, "original": original, "layout": layout, "socket": os.environ.get("NIRI_SOCKET", "")}
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--watch", str(self.path)],
                                   stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try: process.communicate(json.dumps(payload).encode(), timeout=3)
        except subprocess.TimeoutExpired as exc:
            process.kill(); process.communicate()
            raise ValueError("The display preview worker did not start") from exc
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            state = read_json(self.path, {})
            if state.get("token") == token: return
            time.sleep(.01)
        raise ValueError("Another display preview is running, or the preview worker could not start")

    def decide(self, token, keep):
        with locked(self.path.with_suffix(".lock")):
            state = read_json(self.path, {})
            if (not isinstance(token, str) or state.get("token") != token or state.get("status") != "pending"
                    or state.get("socket") != os.environ.get("NIRI_SOCKET", "") or time.time() >= state["deadline"]):
                raise ValueError("This display preview has expired")
            state["status"] = "confirmed" if keep else "reverting"
            write_json(self.path, state)
            return state["layout"]


def watch(path, payload, run, duration=20):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(path.with_suffix(".owner"), "a") as owner:
        try: fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return
        state = {**payload, "status": "applying", "deadline": time.time() + duration, "error": ""}
        validate_layout(state["original"]); validate_layout(state["layout"])
        write_json(path, state)
        confirmed = False
        try:
            apply_layout(state["layout"], run)
            with locked(path.with_suffix(".lock")):
                state.update(status="pending", deadline=time.time() + duration)
                write_json(path, state)
            # NTP/manual clock changes must not extend the safety timeout.
            revert_at = time.monotonic() + duration
            while time.monotonic() < revert_at:
                with locked(path.with_suffix(".lock")):
                    latest = read_json(path, {})
                    if latest.get("status") == "confirmed": confirmed = True; break
                    if latest.get("status") == "reverting": break
                time.sleep(.15)
        except (RuntimeError, OSError, ValueError) as exc:
            state["error"] = str(exc)[:400]
        finally:
            if not confirmed:
                errors = apply_layout(state["original"], run, best_effort=True)
                state.update(status="reverted" if not errors else "error", error=state["error"] or "; ".join(errors)[:400])
                write_json(path, state)


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "--watch": return 2
    payload = json.loads(sys.stdin.buffer.read(65536))
    # Detach the wait from the initiating Settings/backend process.
    if os.fork(): return 0
    from desktop_backend import CommandRunner
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(RuntimeError("Display preview interrupted")))
    watch(Path(sys.argv[2]), payload, CommandRunner().run)
    return 0


if __name__ == "__main__": raise SystemExit(main())
