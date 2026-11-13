# DEPRECATED(Q5->Q6): real sessions run the native surface (qml/services/EqualizerState.qml —
# staging, daemon runner, test tone); this module keeps the fixture demos (A/B window).
"""Serpantinum equalizer state machine (equalizer.sh port); the daemon stays external.

The shell owns a persisted eq_state document (like upstream's eq_state.json):
band edits are staged client-side, presets and live settings are pushed to the
serpantinum-audio daemon immediately, and every push retries once after an
auto-start so a stopped daemon never blocks the UI.
"""
import json
import math
import os
import signal
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backend_actions import ActionSpec
from command_runner import CommandError
from storage import read_json, write_json


@dataclass(frozen=True)
class EqualizerCapabilities:
    run: Callable
    available: Callable


DYNAMICS = ("off", "balanced", "night")
GAINS = 10
PRESETS = {
    "Flat": (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    "Bass": (5, 7, 5, 2, 1, 0, 0, 0, 1, 2),
    "Treble": (-2, -1, 0, 1, 2, 3, 4, 5, 6, 6),
    "Vocal": (-2, -1, 1, 3, 5, 5, 4, 2, 1, 0),
    "Pop": (2, 4, 2, 0, 1, 2, 4, 2, 1, 2),
    "Rock": (5, 4, 2, -1, -2, -1, 2, 4, 5, 6),
    "Jazz": (3, 3, 1, 1, 1, 1, 2, 1, 2, 3),
    "Classic": (0, 1, 2, 2, 2, 2, 1, 2, 3, 4),
}
ACTIONS = ("eqStart", "eqStop", "eqStatus", "eqGet", "eqSetBand", "eqApply", "eqRevert",
           "eqPreset", "eqBalance", "eqMono", "eqSwap", "eqDyneq", "eqDynamics",
           "eqReset", "eqTest", "eqTestStop")


def default_state():
    return {"b1": 0, "b2": 0, "b3": 0, "b4": 0, "b5": 0, "b6": 0, "b7": 0, "b8": 0,
            "b9": 0, "b10": 0, "preset": "Flat", "pending": False, "balance": 0,
            "mono": False, "swap": False, "dynamics": "off", "dyneq": False}


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Equalizer settings must use numeric gain")
    try:
        value = float(value)
    except OverflowError:
        raise ValueError("Equalizer gain is out of range") from None
    if value < -12 or value > 12 or value != value:
        raise ValueError("Equalizer gain is out of range")
    return value


def _balance(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Balance must be numeric")
    try:
        value = float(value)
    except OverflowError:
        raise ValueError("Balance must be between -1 and 1") from None
    if value != value or value < -1 or value > 1:
        raise ValueError("Balance must be between -1 and 1")
    return value


def _flag(value):
    if type(value) is not bool:
        raise ValueError("Equalizer switches must be boolean")
    return value


def _dynamics(value):
    if value not in DYNAMICS:
        raise ValueError("Unknown dynamics mode")
    return value


def _band(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= GAINS:
        raise ValueError("Band must be an integer between 1 and 10")
    return value


def _stored(value):
    """A persisted number: real, non-boolean, finite (storage.finite_number port)."""
    return type(value) in (int, float) and not isinstance(value, bool) and math.isfinite(value)


def _finite(value):
    return _stored(value) and -12 <= value <= 12


def preset_for_gains(gains):
    formatted = tuple(f"{value:g}" for value in gains)
    for name, values in PRESETS.items():
        if tuple(f"{value:g}" for value in values) == formatted:
            return name
    return "Custom"


def normalize(state):
    """Accept only a complete, well-typed eq_state document."""
    if not isinstance(state, dict):
        return None
    result = {}
    for index in range(1, GAINS + 1):
        value = state.get(f"b{index}")
        if not _finite(value):
            return None
        result[f"b{index}"] = value
    balance = state.get("balance", 0)
    if not _stored(balance) or not -1 <= balance <= 1:
        return None
    result["balance"] = balance
    for key in ("mono", "swap", "dyneq"):
        if type(state.get(key, False)) is not bool:
            return None
        result[key] = state[key]
    if state.get("dynamics", "off") not in DYNAMICS:
        return None
    result["dynamics"] = state["dynamics"]
    result["pending"] = state.get("pending") is True
    preset = state.get("preset", "Flat")
    result["preset"] = preset if isinstance(preset, str) and preset else "Flat"
    return result


def state_from_daemon_line(line):
    """Seed an eq_state from the daemon's 17-token `ctl get` report."""
    tokens = str(line or "").strip().split()
    if len(tokens) != 17 or tokens[0] != "set":
        return None
    try:
        gains = [float(token) for token in tokens[1:11]]
        balance = float(tokens[11])
    except ValueError:
        return None
    if any(not -12 <= value <= 12 for value in gains) or not -1 <= balance <= 1:
        return None
    def flag(token):
        return token in ("1", "true")
    if not all(token in ("0", "1", "true", "false") for token in (tokens[12], tokens[13], tokens[15], tokens[16])):
        return None
    if tokens[14] not in DYNAMICS:
        return None
    state = default_state()
    for index, gain in enumerate(gains, 1):
        state[f"b{index}"] = gain
    state.update(preset=preset_for_gains(gains), balance=balance,
                 mono=flag(tokens[12]), swap=flag(tokens[13]), dynamics=tokens[14],
                 dyneq=flag(tokens[16]))
    return state


class EqualizerStore:
    """Owns the persisted eq_state document (equalizer.sh get/set_band port)."""

    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        state = normalize(read_json(self.path, None))
        return state if state is not None else default_state()

    def save(self, state):
        write_json(self.path, state)

    def seed(self, run, available):
        """First-use hydration: prefer the daemon's own report (seed_from_daemon)."""
        if available("serpantinum-audio"):
            try:
                state = state_from_daemon_line(run("serpantinum-audio", "ctl", "get"))
                if state is not None:
                    return state
            except CommandError:
                pass
        return default_state()


class ChannelTestTone:
    """L 660 Hz, R 880 Hz, then both 770 Hz; killable (equalizer.sh test port)."""

    PROPERTIES = json.dumps({"application.id": "lme-shell-audio-test",
                             "application.name": "LME Shell audio test",
                             "media.role": "music"})

    def __init__(self, path):
        self.path = Path(path)
        self.process = None

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def ensure_wave(self):
        if self.path.exists() and self.path.stat().st_size > 0:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        rate = 48000
        segments = ((0.75, 660, 0), (0.18, 0, 0), (0.75, 0, 880),
                    (0.18, 0, 0), (1.0, 770, 770))
        with wave.open(str(self.path), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(rate)
            for duration, left_hz, right_hz in segments:
                for index in range(int(duration * rate)):
                    fade = min(1.0, index / (rate * 0.015),
                               (duration * rate - index) / (rate * 0.015))
                    def sample(freq):
                        return int(9000 * fade * math.sin(2 * math.pi * freq * index / rate)) if freq else 0
                    stream.writeframesraw(sample(left_hz).to_bytes(2, "little", signed=True)
                                          + sample(right_hz).to_bytes(2, "little", signed=True))

    def start(self, run, available):
        self.stop()
        if not available("pw-play"):
            raise CommandError("pw-play is unavailable")
        self.ensure_wave()
        if available("serpantinum-audio"):
            try:
                run("serpantinum-audio", "start")
            except CommandError:
                pass
        target = []
        if available("pw-dump"):
            try:
                if "serpantinum_sink" in run("pw-dump", "-n", "Node", timeout=4):
                    target = ["--target=serpantinum_sink"]
            except CommandError:
                pass
        argv = ["pw-play", *target, "-P", self.PROPERTIES, str(self.path)]
        try:
            self.process = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                            stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL,
                                            start_new_session=True)
        except OSError as error:
            raise CommandError(f"Unable to launch pw-play: {error.strerror}") from None

    def stop(self):
        process, self.process = self.process, None
        if process is None or process.poll() is not None:
            if process is not None:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream:
                        stream.close()
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream:
                stream.close()


def _daemon_set(run, available, state):
    """Push the full state; retry once after an auto-start (audio_ctl port)."""
    if not available("serpantinum-audio"):
        raise CommandError("serpantinum-audio is unavailable")
    args = ["ctl", "set", *[f"{state[f'b{index}']:g}" for index in range(1, GAINS + 1)],
            f"{state['balance']:g}", "1" if state["mono"] else "0",
            "1" if state["swap"] else "0", state["dynamics"], "0",
            "1" if state["dyneq"] else "0"]
    try:
        return run("serpantinum-audio", *args)
    except CommandError:
        run("serpantinum-audio", "start")
        return run("serpantinum-audio", *args)


def provide(capabilities):  # REL: qml/services/EqualizerState.qml, scripts/desktop_backend.py::actions.provide
    run, available = capabilities.run, capabilities.available
    state_dir = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "lme-shell"
    store = EqualizerStore(state_dir / "equalizer.json")
    tone = ChannelTestTone(state_dir / "equalizer-test.wav")
    committed = {}

    def current():
        state = store.load()
        if not store.path.exists():
            state = store.seed(run, available)
            store.save(state)
            committed["state"] = dict(state)
        return state

    def saved_view():
        """Revert target: committed bands, current live values (restoreLastSavedEqualizer)."""
        state = current()
        base = dict(committed.get("state") or state)
        for key in ("balance", "mono", "swap", "dynamics", "dyneq"):
            base[key] = state[key]
        base["pending"] = False
        base["preset"] = preset_for_gains([base[f"b{index}"] for index in range(1, GAINS + 1)])
        return base

    def push(state, commit_bands=True):
        """Push to the daemon, then persist; live pushes keep the committed bands."""
        result = _daemon_set(run, available, state)
        store.save(state)
        saved = committed.get("state")
        if commit_bands or saved is None:
            committed["state"] = {**state, "pending": False}
        else:
            for key in ("balance", "mono", "swap", "dynamics", "dyneq"):
                saved[key] = state[key]
        return result

    def live(request, action):
        if action == "eqStart":
            if not available("serpantinum-audio"):
                raise CommandError("serpantinum-audio is unavailable")
            return run("serpantinum-audio", "start")
        if action == "eqStop":
            tone.stop()
            try:
                return run("serpantinum-audio", "ctl", "quit")
            except CommandError as error:
                if "timed out" in str(error):
                    raise
                return "Equalizer stopped"
        if action == "eqStatus":
            ping = run("serpantinum-audio", "ctl", "ping")
            status = run("serpantinum-audio", "ctl", "status")
            return ping.strip() + "\n" + status.strip()
        if action == "eqGet":
            return json.dumps(current())
        if action == "eqSetBand":
            band = _band(request.get("band"))
            value = _number(request.get("value"))
            state = current()
            state[f"b{band}"] = value
            state["preset"] = "Custom"
            state["pending"] = True
            store.save(state)
            return ""
        if action == "eqApply":
            state = current()
            state["pending"] = False
            push(state)
            return ""
        if action == "eqRevert":
            state = saved_view()
            push(state)
            return ""
        if action == "eqPreset":
            name = request.get("name")
            if name not in PRESETS:
                raise ValueError("Unknown equalizer preset")
            state = current()
            for index, gain in enumerate(PRESETS[name], 1):
                state[f"b{index}"] = gain
            state["preset"] = name
            state["pending"] = False
            push(state)
            return ""
        if action == "eqBalance":
            state = current()
            state["balance"] = round(_balance(request.get("value")), 2)
            push(state, commit_bands=False)
            return ""
        if action in ("eqMono", "eqSwap", "eqDyneq"):
            state = current()
            state[action[2:].lower()] = _flag(request.get("value"))
            push(state, commit_bands=False)
            return ""
        if action == "eqDynamics":
            state = current()
            state["dynamics"] = _dynamics(request.get("value"))
            push(state, commit_bands=False)
            return ""
        if action == "eqReset":
            tone.stop()
            state = current()
            state.update(balance=0, mono=False, swap=False, dynamics="off")
            push(state, commit_bands=False)
            return ""
        if action == "eqTest":
            tone.start(run, available)
            return "Channel test playing"
        if action == "eqTestStop":
            tone.stop()
            return "Channel test stopped"
        raise ValueError("Unknown equalizer action: " + str(action))

    def demo(request, action):
        if action == "eqGet":
            return json.dumps(default_state())
        if action == "eqStatus":
            return "ok\nDemo Serpantinum status"
        if action == "eqTest":
            return "Demo channel test playing"
        if action == "eqTestStop":
            return "Demo channel test stopped"
        return ""

    specs = []
    for ident in ACTIONS:
        specs.append(ActionSpec(ident, {"shell", "settings"},
                                 lambda request, action=ident: live(request, action),
                                 lambda request, action=ident: demo(request, action)))
    return (tuple(specs), lambda: {})
