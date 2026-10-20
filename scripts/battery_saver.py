#!/usr/bin/env python3
"""Reversible hardware changes for the shell's battery-saver overlay."""
from __future__ import annotations

import contextlib
import fcntl
import json
import math
import os
from pathlib import Path
import time

from display_control import apply_layout, current_layout, locked, validate_layout, write_json

# Allow nominal 60 Hz EDID timings below 60.5 Hz; send the exact timing to niri.
MAX_REFRESH_MILLIHZ = 60_500


def brightness_state(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid saved backlight state")
    device = value.get("device")
    current, maximum = value.get("current"), value.get("maximum")
    if (not isinstance(device, str) or not device or len(device) > 256
            or any(ord(char) < 32 for char in device)
            or type(current) is not int or type(maximum) is not int
            or not 0 <= current <= maximum or maximum <= 0):
        raise ValueError("Invalid saved backlight state")
    return {"device": device, "current": current, "maximum": maximum}


class BatterySaver:
    def __init__(self, runner, path, *, outputs, read_brightness, set_brightness,
                 read_profile, profiles, set_profile):
        self.runner, self.path = runner, Path(path)
        self.outputs = outputs
        self.read_brightness, self.set_brightness = read_brightness, set_brightness
        self.read_profile, self.profiles, self.set_profile = read_profile, profiles, set_profile

    def _load(self):
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, UnicodeError) as exc:
            raise ValueError("Battery-saver restore data cannot be read; keep the saved journal for recovery") from exc
        try:
            if (not isinstance(state, dict) or type(state.get("version")) is not int or state["version"] != 1
                    or type(state.get("active")) is not bool
                    or not isinstance(state.get("original"), dict)
                    or not isinstance(state.get("pending"), dict)
                    or not isinstance(state.get("warnings"), list)
                    or not all(isinstance(item, str) for item in state["warnings"])
                    or not isinstance(state.get("socket"), str)
                    or not isinstance(state.get("error"), str)):
                raise ValueError()
            original, pending = state["original"], state["pending"]
            layouts = original.get("displays", [])
            if layouts:
                validate_layout(layouts)
            elif layouts != []:
                raise ValueError()
            if (not isinstance(pending.get("displays"), list)
                    or not all(isinstance(name, str) for name in pending["displays"])
                    or len(set(pending["displays"])) != len(pending["displays"])
                    or not set(pending["displays"]) <= {item["name"] for item in layouts}
                    or type(pending.get("brightness")) is not bool
                    or type(pending.get("profile")) is not bool):
                raise ValueError()
            if original.get("brightness") is not None:
                brightness_state(original["brightness"])
            if pending["brightness"] and original.get("brightness") is None:
                raise ValueError()
            profile = original.get("profile")
            if profile is not None and profile not in {"power-saver", "balanced", "performance"}:
                raise ValueError()
            if pending["profile"] and profile is None:
                raise ValueError()
            if not state["active"] and (pending["displays"] or pending["brightness"] or pending["profile"]):
                raise ValueError()
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("Battery-saver restore data is invalid; keep the saved journal for recovery") from exc
        return state

    def snapshot(self):
        busy = False
        lock_path = self.path.with_suffix(".lock")
        if lock_path.exists():
            try:
                with open(lock_path, "a", encoding="utf-8") as stream:
                    try:
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        busy = True
            except OSError:
                pass
        try:
            state = self._load() or {}
            warnings = list(state.get("warnings", []))
            socket = os.environ.get("NIRI_SOCKET", "")
            if (state.get("active") and state["pending"]["displays"] and state["socket"]
                    and socket and state["socket"] != socket):
                warnings.append("The niri session changed; temporary display caps expired. Turn Battery saver off and on to apply them to current displays")
            return {"active": state.get("active", False), "busy": busy,
                    "error": state.get("error", ""), "warnings": warnings}
        except ValueError as exc:
            # Do not enable an overlay that the damaged restore data cannot reverse.
            return {"active": False, "busy": busy, "error": str(exc), "warnings": []}

    @contextlib.contextmanager
    def guard(self, *, allow_active=False):
        """Serialize conflicting display/profile writes with saver transitions."""
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with open(self.path.with_suffix(".lock"), "a", encoding="utf-8") as stream:
            os.chmod(stream.name, 0o600)
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("Battery saver is changing settings; wait for it to finish") from exc
            state = self._load()
            if state and state["active"] and not allow_active:
                raise ValueError("Turn off Battery saver before changing display modes or the power profile")
            yield

    def toggle(self, enabled, brightness_target=70, *, preflight=None):
        if type(enabled) is not bool:
            raise ValueError("Battery saver must be enabled or disabled")
        if (type(brightness_target) not in (int, float) or not math.isfinite(brightness_target)
                or not 1 <= brightness_target <= 100):
            raise ValueError("Battery-saver brightness must be between 1 and 100")
        with locked(self.path.with_suffix(".lock")):
            state = self._load()
            if enabled:
                if not state or not state["active"]:
                    if preflight is not None:
                        preflight(enabled, state)
                    self._enable(brightness_target)
            elif state and state["active"]:
                if preflight is not None:
                    preflight(enabled, state)
                self._restore(state)
        return self.snapshot()

    def _enable(self, target):
        original = {"displays": [], "brightness": None, "profile": None}
        pending = {"displays": [], "brightness": False, "profile": False}
        warnings, desired = [], []
        try:
            outputs = self.outputs()
            for item in current_layout(outputs):
                if item["width"] <= 1920 and item["height"] <= 1080 and item["refresh"] < MAX_REFRESH_MILLIHZ:
                    continue
                output = next(output for output in outputs if output["name"] == item["name"])
                modes = [mode for mode in output["modes"]
                         if mode["width"] <= min(item["width"], 1920)
                         and mode["height"] <= min(item["height"], 1080)
                         and mode["refresh"] <= item["refresh"] and mode["refresh"] < MAX_REFRESH_MILLIHZ]
                if not modes:
                    warnings.append(f'{item["name"]}: no supported lower mode within 1920 × 1080 / 60 Hz')
                    continue
                mode = max(modes, key=lambda mode: (mode["width"] * mode["height"], mode["refresh"]))
                original["displays"].append(item)
                desired.append({**item, **{key: mode[key] for key in ("width", "height", "refresh")}})
                pending["displays"].append(item["name"])
            if not outputs:
                warnings.append("No niri displays are available; display modes were not changed")
        except (RuntimeError, OSError, ValueError) as exc:
            warnings.append(f"Display modes were not changed: {exc}")
        backlight = None
        try:
            value = self.read_brightness()
            if value is not None:
                backlight = brightness_state(value)
                capped = max(1, math.floor(backlight["maximum"] * target / 100))
                if backlight["current"] > capped:
                    original["brightness"] = backlight
                    pending["brightness"] = True
            else:
                warnings.append("No controllable backlight is available")
        except (RuntimeError, OSError, ValueError) as exc:
            warnings.append(f"Brightness was not changed: {exc}")
        try:
            profile = self.read_profile()
            available = self.profiles()
            if profile in {"balanced", "performance"} and "power-saver" in available:
                original["profile"] = profile
                pending["profile"] = True
            elif profile != "power-saver":
                warnings.append("A compatible power-saver profile is not available")
        except (RuntimeError, OSError, ValueError) as exc:
            warnings.append(f"Power profile was not changed: {exc}")
        if original["displays"]:
            validate_layout(original["displays"])
            validate_layout(desired)
        state = {"version": 1, "active": True, "socket": os.environ.get("NIRI_SOCKET", ""),
                 "original": original, "pending": pending,
                 "warnings": warnings, "error": ""}
        # Every original value reaches disk before the first hardware operation.
        write_json(self.path, state)
        errors = []
        for item in desired:
            try:
                self._apply_display(item)
            except (RuntimeError, OSError, ValueError) as exc:
                errors.append(f'{item["name"]}: {exc}')
        if pending["brightness"]:
            try:
                self.set_brightness({**backlight, "current": max(1, math.floor(backlight["maximum"] * target / 100))})
            except (RuntimeError, OSError, ValueError) as exc:
                errors.append(f"Brightness: {exc}")
        if pending["profile"]:
            try:
                self.set_profile("power-saver")
            except (RuntimeError, OSError, ValueError) as exc:
                errors.append(f"Power profile: {exc}")
        state["error"] = "; ".join(errors)[:2000]
        write_json(self.path, state)

    def _apply_display(self, item):
        apply_layout([item], self.runner.run)
        deadline = time.monotonic() + 1
        while True:
            output = next((output for output in self.outputs() if output['name'] == item['name']), None)
            current = output.get('current') if output else None
            if current and all(current[key] == item[key] for key in ('width', 'height', 'refresh')):
                return
            if time.monotonic() >= deadline:
                actual = f'{current["width"]} × {current["height"]} @ {current["refresh"] / 1000:g} Hz' if current else 'unavailable'
                raise ValueError(f'niri did not confirm {item["width"]} × {item["height"]} @ {item["refresh"] / 1000:g} Hz (current: {actual})')
            time.sleep(.1)

    def _restore(self, state):
        original, pending = state["original"], state["pending"]
        errors, warnings = [], []
        socket = os.environ.get("NIRI_SOCKET", "")
        if pending["displays"] and state["socket"] and socket and state["socket"] != socket:
            # niri output overrides disappear with their compositor session.
            pending["displays"] = []
            warnings.append("The previous niri session ended; its temporary display overrides were discarded")
            write_json(self.path, state)
        if pending["displays"]:
            try:
                outputs = self.outputs()
            except (RuntimeError, OSError, ValueError) as exc:
                outputs = []
                errors.append(f"Displays: {exc}")
            for item in original["displays"]:
                if item["name"] not in pending["displays"]:
                    continue
                try:
                    validate_layout([item], outputs)
                    if item not in current_layout(outputs):
                        self._apply_display(item)
                    pending["displays"].remove(item["name"])
                    write_json(self.path, state)
                except (RuntimeError, OSError, ValueError) as exc:
                    errors.append(f'{item["name"]}: restore pending ({exc})')
        if pending["brightness"]:
            try:
                if self.read_brightness() != original["brightness"]:
                    self.set_brightness(original["brightness"])
                pending["brightness"] = False
                write_json(self.path, state)
            except (RuntimeError, OSError, ValueError) as exc:
                errors.append(f"Brightness: restore pending ({exc})")
        if pending["profile"]:
            try:
                if self.read_profile() != original["profile"]:
                    if original["profile"] not in self.profiles():
                        raise ValueError("The original power profile is not available")
                    self.set_profile(original["profile"])
                pending["profile"] = False
                write_json(self.path, state)
            except (RuntimeError, OSError, ValueError) as exc:
                errors.append(f"Power profile: restore pending ({exc})")
        state.update(active=bool(pending["displays"] or pending["brightness"] or pending["profile"]),
                     error="; ".join(errors)[:2000], warnings=warnings)
        if not state["active"]:
            state["original"] = {}
        write_json(self.path, state)
