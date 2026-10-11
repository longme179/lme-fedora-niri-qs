#!/usr/bin/env python3
"""LME shell's unprivileged JSON-lines backend (Python standard library only).

Every output line is a complete state snapshot. Input lines are objects such as
{"action":"volume","value":45}. Commands never go through a shell. --demo is
explicitly isolated from the live machine; --once performs read-only sampling.
"""

from __future__ import annotations

import argparse
import configparser
from concurrent.futures import ThreadPoolExecutor
import copy
import fcntl
import json
import math
import os
from pathlib import Path
import re
import selectors
import shlex
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any

from charge_control import ChargeControl, HELPER_PATH, trusted_helper
from weather import WeatherClient, location
from desktop_features import (APPEARANCE_KEYS, DRACULA_PROFILE, DEFAULT_CONTROL_LAYOUT, MOTION_DEFAULTS, THEME_DEFAULTS,
                              appearance_profile, control_layout, wallpaper_library, calculate, theme_overrides, theme_token)
from display_control import DisplayControl, validate_layout, read_json, write_json, apply_layout, current_layout
from system_monitor import SystemMonitor
from idle_control import IdleControl, DEFAULT_IDLE_PROFILES, validate_profiles, secure_lock
from niri_keybinds import read_keybinds
from night_light import NightLight, clock_minutes
from screen_capture import ScreenCapture


DEFAULT_PREFERENCES = {
    "language": "en", "animations": True, "opacity": 0.90,
    "accent": "#9580ff", "wallpaper": "",
    "density": "comfortable", "appearanceProfiles": [DRACULA_PROFILE],
    "controlLayout": DEFAULT_CONTROL_LAYOUT, "controlWidth": 600,
    "wallpaperFolder": "", "wallpaperFavorites": [], "favoriteApps": [],
    "notificationMutedApps": [], "dndUntil": 0, "displayLayout": [],
    "idleEnabled": False, "idleProfiles": DEFAULT_IDLE_PROFILES, "idleLockBeforeSleep": True,
    "niriConfigPath": "", "popupBlur": True, **MOTION_DEFAULTS, **THEME_DEFAULTS,
    "barEdge": "top", "barEdgeMargin": 8, "barSideMargin": 12, "barHeight": 42,
    "nightLightEnabled": False, "nightLightMode": "manual", "nightLightTemperature": 4500,
    "nightLightStart": "20:00", "nightLightEnd": "07:00",
    "terminal": "kitty", "bluetoothAdapter": "", "tasks": [],
    "weatherAutoLocation": True, "weatherLocation": {}, "weatherUnit": "celsius",
    "activityEnabled": True, "clipboardEnabled": True, "clipboardImages": True, "clipboardLimit": 100,
    "barStyle": "connected", "barFontSize": 13,
    "barLayout": {"left": ["launcher", "overview", "workspaces"], "center": ["activity"],
                  "right": ["clipboard", "tray", "notifications", "audio", "network", "battery", "clock", "settings"]},
}
BAR_MODULES = {"launcher", "overview", "workspaces", "windowTitle", "media", "resources", "tray",
               "notifications", "audio", "network", "battery", "clock", "settings", "clipboard", "activity"}
TOOLS = (
    "niri", "nmcli", "bluetoothctl", "wpctl", "brightnessctl",
    "busctl", "powerprofilesctl", "gio", "swaylock", "systemctl",
    "awww", "awww-daemon", "pkexec", "nm-connection-editor", "blueman-manager", "pavucontrol", "rfkill", "wl-copy", "swayidle", "quickshell", "wlsunset", "tesseract",
)
POWER_PROFILE_SERVICES = (
    ("org.freedesktop.UPower.PowerProfiles", "/org/freedesktop/UPower/PowerProfiles", "org.freedesktop.UPower.PowerProfiles"),
    ("net.hadess.PowerProfiles", "/net/hadess/PowerProfiles", "net.hadess.PowerProfiles"),
)
POWER_PROFILES = {"power-saver", "balanced", "performance"}


class CommandError(RuntimeError):
    """A missing command, timeout, or unsuccessful subprocess."""


class CommandRunner:
    def __init__(self) -> None:
        # Cache capability discovery once, including known missing commands.
        self.commands = {name: shutil.which(name) for name in TOOLS}
        self.commands['quickshell'] = shutil.which(os.environ.get('LME_QS_BINARY', 'quickshell')) or self.commands['quickshell'] or shutil.which('qs')

    def available(self, name: str) -> bool:
        return bool(self.commands.get(name))

    def executable(self, name: str) -> str:
        path = self.commands.get(name)
        if not path:
            raise CommandError(f"Required command is unavailable: {name}")
        return path

    def run(self, name: str, *args: str, timeout: float = 3.0, input: str | None = None) -> str:
        argv = [self.executable(name), *map(str, args)]
        try:
            result = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout,
                check=False, encoding="utf-8", errors="replace",
                env={**os.environ, "LC_ALL": "C"},
                input=input,
            )
        except subprocess.TimeoutExpired as exc:
            raise CommandError(f"{name} timed out") from exc
        except OSError as exc:
            raise CommandError(f"Unable to run {name}: {exc.strerror}") from exc
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip()
            if input and input.strip(): detail = detail.replace(input.strip(), "[redacted]")
            detail = detail[:350]
            raise CommandError(f"{name} failed ({result.returncode})" + (f": {detail}" if detail else ""))
        return result.stdout.strip()

    def spawn(self, argv: list[str]) -> None:
        try:
            subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as exc:
            raise CommandError(f"Unable to launch {Path(argv[0]).name}: {exc.strerror}") from exc


def desktop_unescape(value: str) -> str:
    """Decode desktop-entry string escapes, leaving Exec quoting escapes intact."""
    mapping = {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
    return re.sub(r"\\([sntr\\])", lambda match: mapping[match[1]], value)


def desktop_exec(value: str, name: str, icon: str, path: str) -> list[str]:
    """Tokenize Exec without shell expansion and implement desktop field codes.

    File/URL codes are omitted for an ordinary launcher invocation. %i expands
    to two arguments; %c and %k are values, never parsed as executable syntax.
    Invalid field codes and embedded multi-argument codes reject the entry.
    """
    tokens = shlex.split(desktop_unescape(value), posix=True)
    result: list[str] = []
    removed = set("fFuUdDnNvm")  # Includes deprecated codes still in older entries.
    for token in tokens:
        if token == "%i":
            if icon:
                result.extend(["--icon", icon])
            continue
        if token in {f"%{code}" for code in removed}:
            continue
        expanded = ""
        index = 0
        while index < len(token):
            if token[index] != "%":
                expanded += token[index]
                index += 1
                continue
            index += 1
            if index >= len(token):
                raise ValueError("Incomplete desktop field code")
            code = token[index]
            index += 1
            if code == "%":
                expanded += "%"
            elif code == "c":
                expanded += name
            elif code == "k":
                expanded += path
            elif code in "FUi":
                raise ValueError("Multi-argument field code embedded in token")
            elif code in removed:
                continue
            else:
                raise ValueError(f"Unknown desktop field code: %{code}")
        if expanded:
            result.append(expanded)
    if not result or not result[0]:
        raise ValueError("Desktop entry has no executable")
    return result


def locale_candidates() -> list[str]:
    raw = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    language = raw.split(".")[0]
    if language in {"C", "POSIX", ""}:
        return []
    base, _, modifier = language.partition("@")
    short = base.split("_")[0]
    return list(dict.fromkeys([language, base, short + (f"@{modifier}" if modifier else ""), short]))


class Applications:
    def __init__(self, paths: list[Path] | None = None) -> None:
        if paths is None:
            user = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
            system = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
            paths = [user / "applications", *[Path(p) / "applications" for p in system if p]]
        self.paths = paths
        self.entries: dict[str, dict[str, Any]] = {}

    def scan(self) -> list[dict[str, Any]]:
        self.entries = {}
        seen: set[str] = set()
        for base in self.paths:
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.desktop")):
                desktop_id = str(path.relative_to(base)).replace(os.sep, "-")
                if desktop_id in seen:
                    continue
                # A Hidden user override must suppress its system counterpart.
                seen.add(desktop_id)
                try:
                    parser = configparser.ConfigParser(interpolation=None, strict=False)
                    parser.optionxform = str
                    parser.read(path, encoding="utf-8")
                    entry = parser["Desktop Entry"]
                    if entry.get("Type") != "Application" or entry.get("Hidden", "false").lower() == "true":
                        continue
                    if entry.get("NoDisplay", "false").lower() == "true":
                        continue
                    desktops = set(os.environ.get("XDG_CURRENT_DESKTOP", "niri").split(":"))
                    only = set(filter(None, entry.get("OnlyShowIn", "").split(";")))
                    excluded = set(filter(None, entry.get("NotShowIn", "").split(";")))
                    if (only and not only.intersection(desktops)) or excluded.intersection(desktops):
                        continue
                    try_exec = desktop_unescape(entry.get("TryExec", ""))
                    if try_exec and not shutil.which(try_exec):
                        continue
                    name = entry.get("Name", "")
                    for candidate in locale_candidates():
                        if entry.get(f"Name[{candidate}]"):
                            name = entry[f"Name[{candidate}]"]
                            break
                    name = desktop_unescape(name)
                    if not name:
                        continue
                    icon = desktop_unescape(entry.get("Icon", ""))
                    absolute = str(path.resolve())
                    argv = desktop_exec(entry.get("Exec", ""), name, icon, absolute)
                    terminal = entry.get("Terminal", "false").lower() == "true"
                    self.entries[desktop_id] = {
                        "id": desktop_id, "name": name, "icon": icon, "path": absolute,
                        "terminal": terminal, "argv": argv,
                    }
                    for field, key in [("GenericName", "genericName"), ("Comment", "comment"), ("Keywords", "keywords")]:
                        value = entry.get(field, "")
                        for candidate in locale_candidates():
                            if entry.get(f"{field}[{candidate}]"):
                                value = entry[f"{field}[{candidate}]"]
                                break
                        value = desktop_unescape(value)
                        self.entries[desktop_id][key] = [word for word in value.split(";") if word] if key == "keywords" else value
                except (OSError, UnicodeError, configparser.Error, KeyError, ValueError):
                    continue
        return sorted(
            [{key: value for key, value in entry.items() if key != "argv"} for entry in self.entries.values()],
            key=lambda app: (app["name"].casefold(), app["id"]),
        )


def validate_preference(key: str, value: Any) -> Any:
    if key in {'themeOverrides', 'fontOverrides'}: return theme_overrides(value, fonts=key == 'fontOverrides')
    if key == 'fontSize' and type(value) is int and 12 <= value <= 20: return value
    if key == 'barEdge' and value in ('top', 'bottom'): return value
    if key in {'barEdgeMargin', 'barSideMargin', 'barHeight'} and type(value) is int:
        low, high = {'barEdgeMargin': (0, 64), 'barSideMargin': (0, 160), 'barHeight': (36, 64)}[key]
        if low <= value <= high: return value
    if key == "nightLightEnabled" and type(value) is bool: return value
    if key == "nightLightMode" and value in ("manual", "schedule", "sunset"): return value
    if key == "nightLightTemperature" and type(value) is int and 2500 <= value <= 6500: return value
    if key in {"nightLightStart", "nightLightEnd"}: clock_minutes(value); return value
    if key == "motionPreset" and value in ("smooth", "expressive", "jelly"): return value
    if key == "motionSpeed" and type(value) in (int, float) and math.isfinite(value) and .5 <= value <= 2: return float(value)
    if key == "motionBounce" and type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1: return float(value)
    if key in {"idleEnabled", "idleLockBeforeSleep", "popupBlur"} and type(value) is bool: return value
    if key == "idleProfiles": return validate_profiles(value)
    if key == "niriConfigPath" and isinstance(value, str) and len(value) <= 4096 and not any(ord(c) < 32 for c in value):
        return str(Path(value).expanduser().resolve()) if value else ""
    if key == "density" and value in ("compact", "comfortable"): return value
    if key == "appearanceProfiles" and isinstance(value, list) and 1 <= len(value) <= 20:
        profiles = [appearance_profile(item, validate_preference) for item in value]
        if len({p["name"].casefold() for p in profiles}) != len(profiles): raise ValueError("Duplicate profile names")
        normalized = [dict(DRACULA_PROFILE), *[p for p in profiles if p["name"].casefold() != "dracula"]]
        if len(normalized) > 20: raise ValueError("Keep at most 19 custom profiles plus Dracula")
        return normalized
    if key == "controlLayout": return control_layout(value)
    if key == "controlWidth" and type(value) is int and 480 <= value <= 900: return value
    if key == "displayLayout" and value == []: return []
    if key == "displayLayout": return validate_layout(value)
    if key == "dndUntil" and type(value) is int and -1 <= value <= 4102444800000: return value
    if key in {"wallpaperFolder"} and isinstance(value, str) and len(value) <= 4096 and "\x00" not in value:
        return str(Path(value).expanduser().resolve()) if value else ""
    if key in {"wallpaperFavorites", "favoriteApps", "notificationMutedApps"} and isinstance(value, list) and len(value) <= 100:
        if all(isinstance(item, str) and 0 < len(item) <= (4096 if key == "wallpaperFavorites" else 256)
               and not any(ord(c) < 32 for c in item) for item in value):
            return list(dict.fromkeys(value))
        raise ValueError("Invalid favorite or notification rule")
    if key in {"activityEnabled", "clipboardEnabled", "clipboardImages"} and type(value) is bool: return value
    if key == "clipboardLimit" and type(value) is int and 20 <= value <= 500: return value
    if key == "barStyle" and isinstance(value, str) and value in {"islands", "connected"}:
        return value
    if key == "barFontSize" and type(value) is int and 12 <= value <= 16:
        return value
    if key == "barLayout" and isinstance(value, dict) and set(value) == {"left", "center", "right"}:
        seen, normalized = set(), {}
        for zone in ("left", "center", "right"):
            modules = value[zone]
            if not isinstance(modules, list) or len(modules) > len(BAR_MODULES):
                raise ValueError("Invalid bar zone")
            for module in modules:
                if not isinstance(module, str) or module not in BAR_MODULES or module in seen:
                    raise ValueError("Unknown or duplicate bar module")
                seen.add(module)
            normalized[zone] = list(modules)
        return normalized
    if key in {"animations", "weatherAutoLocation"} and type(value) is bool:
        return value
    if key == "weatherLocation":
        return location(value)
    if key == "weatherUnit" and isinstance(value, str) and value in {"celsius", "fahrenheit"}:
        return value
    if key == "opacity" and type(value) in {int, float} and math.isfinite(value) and 0.60 <= value <= 1:
        return float(value)
    if key == "accent" and isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value.lower()
    if key == "language" and value == "en":
        return value
    if key == "terminal" and isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.+-]{1,80}", value):
        return value
    if key == "bluetoothAdapter" and isinstance(value, str) and (value == "" or re.fullmatch(r"/org/bluez/hci[0-9]+", value)):
        return value
    if key == "tasks" and isinstance(value, list) and len(value) <= 100:
        tasks, ids = [], set()
        for item in value:
            if not isinstance(item, dict):
                raise ValueError("Invalid task")
            ident, text, done = item.get("id"), item.get("text"), item.get("done")
            if (not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", ident)
                    or ident in ids or not isinstance(text, str) or not 1 <= len(text.strip()) <= 240 or type(done) is not bool):
                raise ValueError("Invalid task")
            ids.add(ident)
            tasks.append({"id": ident, "text": text.strip(), "done": done})
        return tasks
    if key == "wallpaper" and isinstance(value, str) and (value == "" or (Path(value).is_absolute() and Path(value).is_file())):
        return value
    raise ValueError(f"Invalid preference: {key}")


class Preferences:
    def __init__(self, path: Path | None = None) -> None:
        config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        self.path = path or config / "lme-shell/settings.json"
        self.values = copy.deepcopy(DEFAULT_PREFERENCES)
        self._stamp: tuple[int, int, int] | None = None
        self.reload()

    def reload(self, force: bool = False) -> None:
        """Observe atomic writes from the standalone settings app or shell."""
        try:
            stat = self.path.stat()
            stamp = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
            if not force and stamp == self._stamp:
                return
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                values = copy.deepcopy(DEFAULT_PREFERENCES)
                for key, value in saved.items():
                    try:
                        values[key] = validate_preference(key, value)
                    except ValueError:
                        pass
                self.values = values
                self._stamp = stamp
        except FileNotFoundError:
            if self._stamp is not None:
                self.values = copy.deepcopy(DEFAULT_PREFERENCES)
                self._stamp = None
        except (OSError, UnicodeError, json.JSONDecodeError):
            # Retain the last valid snapshot while an external editor is writing.
            pass

    def set(self, key: str, value: Any, token: str | None = None) -> None:
        self.update({key: theme_token(key, token, value) if token is not None else value}, token=token)

    def update(self, values: dict[str, Any], token: str | None = None) -> None:
        values = {key: validate_preference(key, value) for key, value in values.items()}
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Serialize the app and shell's writers, including task updates.
        lock_fd = os.open(self.path.with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lock_fd, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.reload(force=True)
            if token is not None:
                key = next(iter(values))
                merged = dict(self.values[key]); merged.pop(token, None); merged.update(values[key])
                values[key] = merged
            self._write({**self.values, **values})

    def _write(self, updated: dict[str, Any]) -> None:
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=".settings-", suffix=".json", delete=False) as handle:
                temporary = handle.name
                os.chmod(temporary, 0o600)
                json.dump(updated, handle, indent=2, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            self.values = updated
            stat = self.path.stat()
            self._stamp = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)


def split_nmcli(line: str) -> list[str]:
    fields, current, escaped = [], "", False
    for character in line:
        if escaped:
            current += character
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == ":":
            fields.append(current)
            current = ""
        else:
            current += character
    fields.append(current + ("\\" if escaped else ""))
    return fields


class DesktopBackend:
    def __init__(self, runner: CommandRunner | None = None, preferences: Preferences | None = None,
                 apps: Applications | None = None, proc: Path = Path("/proc"), sysfs: Path = Path("/sys"),
                 demo: bool = False, settings_only: bool = False, weather: WeatherClient | None = None,
                 weather_fetch: bool = True, manage_idle: bool = False) -> None:
        self.demo = demo
        self.settings_only = settings_only
        self.shell_entry = os.environ.get('LME_SHELL_ENTRY') or str(Path(__file__).resolve().parents[1] / 'shell.qml')
        self.manage_idle = manage_idle
        self.runner = runner or CommandRunner()
        self.preferences = preferences or Preferences()
        self.applications = apps or Applications()
        self.proc, self.sysfs = proc, sysfs
        self.weather = weather or WeatherClient()
        self.weather_fetch = weather_fetch
        self.charger = ChargeControl(sysfs)
        self.charge_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lme-charge")
        self.charge_job = None
        self.feature_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="lme-feature")
        self.feature_jobs = {}
        self.wallpaper_library = {"entries": [], "folder": "", "error": "", "truncated": False}
        self.displays = {"outputs": [], "preview": {}}
        self.monitor_enabled = False
        self.monitor = SystemMonitor(proc)
        self.idle_control = IdleControl(self.runner)
        self.idle_state = {}
        self.keybinds = {"path": "", "bindings": [], "errors": []}
        self.night_light = NightLight(self.runner)
        self.night_state = {}
        self.capture = ScreenCapture(self.runner)
        self.platform = {"niriVersion": "Demo" if demo else "Not checked", "popupBlurSupported": demo}
        if manage_idle and not demo and not settings_only: self.platform = self.compositor_features()
        self.display_control = DisplayControl(self.runner)
        self.notification_path = self.preferences.path.parent / "notification-history.json"
        self.notification_history = self.valid_notifications(read_json(self.notification_path, [])) if not demo and not settings_only else []
        self.apps = [] if demo or settings_only else self.applications.scan()
        self.last_app_scan = time.monotonic()
        self.last_cpu: tuple[int, int] | None = None
        self.system_cache: dict[str, Any] | None = None
        self.last_system_sample = 0.0
        self.power_profile_provider: tuple[str, ...] | None = None
        self.result_sequence = 0
        self.result_unemitted = False
        self.last_result = {"ok": True, "action": "ready", "message": "Backend ready", "sequence": 0}
        self.niri = {"available": False, "workspaces": [], "windows": []}

    def try_run(self, name: str, *args: str) -> str | None:
        if not self.runner.available(name):
            return None
        try:
            return self.runner.run(name, *args)
        except CommandError:
            return None

    @staticmethod
    def read(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return None

    def cpu_memory(self) -> dict[str, Any]:
        result = {"cpu": None, "memoryPercent": None, "memoryUsedGiB": None, "memoryTotalGiB": None}
        stat = self.read(self.proc / "stat")
        if stat:
            try:
                # guest and guest_nice already count in user and nice.
                times = [int(v) for v in stat.splitlines()[0].split()[1:9]]
                total, idle = sum(times), times[3] + (times[4] if len(times) > 4 else 0)
                if self.last_cpu:
                    delta_total = total - self.last_cpu[0]
                    delta_idle = idle - self.last_cpu[1]
                    if delta_total > 0:
                        result["cpu"] = round(max(0, min(100, 100 * (1 - delta_idle / delta_total))), 1)
                self.last_cpu = (total, idle)
            except (ValueError, IndexError):
                pass
        memory = self.read(self.proc / "meminfo")
        if memory:
            data = {}
            for line in memory.splitlines():
                key, _, value = line.partition(":")
                try:
                    data[key] = int(value.split()[0])
                except (ValueError, IndexError):
                    continue
            total = data.get("MemTotal", 0)
            available = data.get("MemAvailable")
            if total > 0 and available is not None:
                used = max(0, total - available)
                result.update(memoryPercent=round(100 * used / total, 1),
                              memoryUsedGiB=round(used / 1024 ** 2, 2), memoryTotalGiB=round(total / 1024 ** 2, 2))
        return result

    def temperature(self) -> float | None:
        # Read CPU sensors only: querying the NVIDIA GPU can wake a sleeping dGPU.
        candidates: list[Path] = []
        for directory in sorted((self.sysfs / "class/hwmon").glob("hwmon*")):
            name = self.read(directory / "name")
            if name not in {"k10temp", "zenpower", "coretemp"}:
                continue
            for sensor in sorted(directory.glob("temp*_input")):
                label = self.read(sensor.with_name(sensor.name.replace("_input", "_label")))
                if not label or label in {"Tctl", "Tdie", "Package id 0"}:
                    candidates.append(sensor)
        for directory in sorted((self.sysfs / "class/thermal").glob("thermal_zone*")):
            if self.read(directory / "type") in {"x86_pkg_temp", "cpu-thermal", "acpitz"}:
                candidates.append(directory / "temp")
        for sensor in candidates:
            try:
                value = float(self.read(sensor) or "nan") / 1000
                if math.isfinite(value) and -20 <= value <= 150:
                    return round(value, 1)
            except ValueError:
                continue
        return None

    def battery(self) -> dict[str, Any]:
        supplies = self.sysfs / "class/power_supply"
        batteries = [p for p in sorted(supplies.glob("*")) if self.read(p / "type") == "Battery"]
        capacities: list[float] = []
        charging = False
        for battery in batteries:
            try:
                capacity = float(self.read(battery / "capacity") or "nan")
                if math.isfinite(capacity) and 0 <= capacity <= 100:
                    capacities.append(capacity)
            except ValueError:
                pass
            status = self.read(battery / "status")
            charging = charging or status == "Charging"
        return {"available": bool(capacities), "percent": round(sum(capacities) / len(capacities)) if capacities else None,
                "charging": charging, "acOnline": self.ac_online()}

    def compositor_features(self):
        version = self.try_run("niri", "--version") or "Unavailable"
        release = re.search(r"\b(\d{2})\.(\d{2})\b", version)
        return {"niriVersion": version, "popupBlurSupported": bool(release and tuple(map(int, release.groups())) >= (26, 4))}

    def ac_online(self):
        supplies = list((self.sysfs / "class/power_supply").glob("*"))
        online = [self.read(p / "online") for p in supplies if self.read(p / "type") != "Battery"]
        if any(v in {"0", "1"} for v in online): return "1" in online
        statuses = [self.read(p / "status") for p in supplies if self.read(p / "type") == "Battery"]
        return not statuses or "Charging" in statuses or "Full" in statuses

    def network(self) -> dict[str, Any]:
        result = {"available": False, "enabled": False, "connected": False, "wifiConnected": False, "ssid": "", "strength": None, "networks": [], "saved": [], "device": ""}
        radio = self.try_run("nmcli", "radio", "wifi")
        if radio is None:
            return result
        result.update(available=True, enabled=radio.strip() == "enabled")
        devices = self.try_run("nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status")
        for line in (devices or "").splitlines():
            fields = split_nmcli(line)
            if len(fields) < 4: continue
            if fields[1] == "wifi" and (not result["device"] or fields[2] == "connected"):
                result["device"] = fields[0]
            if fields[2] == "connected":
                result["connected"] = True
                if fields[1] == "ethernet":
                    result["ssid"] = "Ethernet"
        connections = self.try_run("nmcli", "-t", "-f", "UUID,TYPE,NAME", "connection", "show")
        for line in (connections or "").splitlines():
            fields = split_nmcli(line)
            if len(fields) == 3 and fields[1] in {"wifi", "802-11-wireless"}:
                result["saved"].append({"uuid": fields[0], "name": fields[2]})
        wireless = self.try_run("nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY,BSSID,DEVICE", "device", "wifi", "list", "--rescan", "no")
        seen = set()
        for line in (wireless or "").splitlines():
            fields = split_nmcli(line)
            if len(fields) < 6 or fields[5] != result["device"]: continue
            if fields[1] and fields[1] not in seen:
                seen.add(fields[1])
                try:
                    strength = max(0, min(100, int(fields[2])))
                except ValueError:
                    strength = 0
                result["networks"].append({"ssid": fields[1], "strength": strength, "connected": fields[0] == "yes",
                                          "security": fields[3], "secured": fields[3] not in {"", "--"},
                                          "enterprise": "802.1X" in fields[3] or "EAP" in fields[3], "bssid": fields[4]})
            if len(fields) >= 3 and fields[0] == "yes":
                result.update(connected=True, wifiConnected=True, ssid=fields[1])
                try:
                    result["strength"] = max(0, min(100, int(fields[2])))
                except ValueError:
                    pass
        result["networks"] = sorted(result["networks"], key=lambda item: (not item["connected"], -item["strength"]))[:60]
        return result

    def bluez_objects(self) -> dict[str, Any] | None:
        output = self.try_run("busctl", "--system", "--json=short", "call", "org.bluez", "/",
                              "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")
        try:
            data = json.loads(output or "null")["data"]
            if isinstance(data, list) and len(data) == 1:
                data = data[0]
            return data if isinstance(data, dict) else None
        except (ValueError, TypeError, KeyError):
            return None

    def bluetooth_blocks(self) -> list[dict[str, Any]]:
        blocks = []
        for path in sorted((self.sysfs / "class/rfkill").glob("rfkill*")):
            if self.read(path / "type") == "bluetooth":
                blocks.append({"id": path.name.removeprefix("rfkill"),
                               "soft": self.read(path / "soft") == "1", "hard": self.read(path / "hard") == "1"})
        return blocks

    def bluetooth(self) -> dict[str, Any]:
        blocks = self.bluetooth_blocks()
        result = {"available": False, "enabled": False, "adapters": [], "devices": [], "adapter": "",
                  "softBlocked": any(item["soft"] for item in blocks), "hardBlocked": any(item["hard"] for item in blocks)}
        objects = self.bluez_objects()
        if objects is not None:
            for path, interfaces in sorted(objects.items()):
                if not isinstance(interfaces, dict) or not re.fullmatch(r"/org/bluez/hci[0-9]+", path):
                    continue
                adapter = interfaces.get("org.bluez.Adapter1")
                if isinstance(adapter, dict):
                    result["adapters"].append({"path": path, "name": self.bluez_value(adapter, "Alias", path.rsplit("/", 1)[-1]),
                                               "enabled": self.bluez_value(adapter, "Powered", False) is True})
            preferred = self.preferences.values["bluetoothAdapter"]
            selected = next((item for item in result["adapters"] if item["path"] == preferred), None)
            selected = selected or next(iter(result["adapters"]), None)
            if selected:
                result.update(available=True, enabled=selected["enabled"], adapter=selected["path"])
                for path, interfaces in sorted(objects.items()):
                    device = interfaces.get("org.bluez.Device1") if isinstance(interfaces, dict) else None
                    if not isinstance(device, dict) or not path.startswith(selected["path"] + "/dev_"):
                        continue
                    if self.bluez_value(device, "Paired", False) or self.bluez_value(device, "Connected", False):
                        result["devices"].append({"path": path, "name": self.bluez_value(device, "Alias", "Bluetooth device"),
                                                  "connected": self.bluez_value(device, "Connected", False) is True})
            return result
        output = self.try_run("bluetoothctl", "show")
        if output is not None and re.search(r"^\s*Controller\s", output, re.MULTILINE):
            result.update(available=True, enabled=bool(re.search(r"Powered:\s+yes", output)))
        return result

    @staticmethod
    def bluez_value(properties: dict[str, Any], key: str, default: Any) -> Any:
        value = properties.get(key, default)
        return value.get("data", default) if isinstance(value, dict) else value

    def set_bluetooth(self, enabled: bool) -> str:
        state = self.bluetooth()
        if not state["available"]:
            raise CommandError("No Bluetooth adapter is available. Check bluetooth.service and the adapter firmware.")
        if enabled and state["hardBlocked"]:
            raise CommandError("Bluetooth is hardware-blocked. Disable airplane mode or use the laptop's radio switch.")

        def write_power() -> None:
            if state["adapter"]:
                self.runner.run("busctl", "--system", "set-property", "org.bluez", state["adapter"],
                                "org.bluez.Adapter1", "Powered", "b", "true" if enabled else "false", timeout=12.0)
            else:
                output = self.runner.run("bluetoothctl", "--timeout", "10", "power", "on" if enabled else "off", timeout=12.0)
                # bluetoothctl can return exit code zero while BlueZ reports a failure.
                if re.search(r"failed|not available|not authorized|blocked|error", output, re.IGNORECASE):
                    raise CommandError(output.strip()[:240])

        try:
            write_power()
        except CommandError as exc:
            if enabled and state["softBlocked"]:
                if not self.runner.available("rfkill"):
                    raise CommandError("Bluetooth is software-blocked. Install rfkill and unblock Bluetooth.") from exc
                try:
                    for block in self.bluetooth_blocks():
                        if block["soft"] and not block["hard"] and block["id"].isdigit():
                            self.runner.run("rfkill", "unblock", block["id"])
                    write_power()
                except CommandError as unblock_error:
                    raise CommandError("Bluetooth is software-blocked; unblock it in Fedora's radio settings or run rfkill unblock bluetooth. " + str(unblock_error)) from exc
            else:
                raise CommandError("BlueZ could not change Bluetooth power. Check the Bluetooth service, firmware and session authorization. " + str(exc)) from exc
        for attempt in range(3):
            if self.bluetooth()["enabled"] == enabled:
                return "Bluetooth turned " + ("on" if enabled else "off")
            if attempt < 2:
                time.sleep(0.12)
        raise CommandError("BlueZ did not confirm the requested power state. Check journalctl -b -u bluetooth and rfkill list bluetooth.")

    def audio(self, source: str = "@DEFAULT_AUDIO_SINK@") -> dict[str, Any]:
        output = self.try_run("wpctl", "get-volume", source)
        match = re.search(r"Volume:\s+([0-9.]+)", output or "")
        if not match:
            return {"available": False, "volume": None, "muted": False}
        try:
            value = float(match[1])
        except ValueError:
            return {"available": False, "volume": None, "muted": False}
        if not math.isfinite(value) or value < 0:
            return {"available": False, "volume": None, "muted": False}
        return {"available": True, "volume": round(value * 100), "muted": "[MUTED]" in (output or "")}

    def brightness(self) -> dict[str, Any]:
        output = self.try_run("brightnessctl", "--class=backlight", "-m")
        # Backlight-only class excludes keyboard and wireless status LEDs.
        for line in (output or "").splitlines():
            match = re.search(r",([0-9]+)%,", line)
            if match:
                return {"available": True, "percent": min(100, int(match[1]))}
        return {"available": False, "percent": None}

    def read_power_profile(self, provider: tuple[str, ...]) -> str | None:
        if provider[0] == "dbus":
            output = self.try_run("busctl", "--system", "get-property", *provider[1:], "ActiveProfile")
            if output is None:
                return None
            try:
                fields = shlex.split(output)
            except ValueError:
                return None
            # busctl prints the D-Bus signature followed by its quoted value.
            if len(fields) != 2 or fields[0] != "s":
                return None
            value = fields[1]
        else:
            value = self.try_run("powerprofilesctl", "get")
        return value if value in POWER_PROFILES else None

    def power_profile(self) -> str | None:
        # Fedora uses tuned-ppd. Both tuned-ppd and power-profiles-daemon expose
        # this standard API, so neither swapping the provider nor its CLI is
        # required. Keep the working endpoint first on later samples.
        candidates = [("dbus", *service) for service in POWER_PROFILE_SERVICES] + [("cli",)]
        if self.power_profile_provider in candidates:
            candidates.remove(self.power_profile_provider)
            candidates.insert(0, self.power_profile_provider)
        for provider in candidates:
            value = self.read_power_profile(provider)
            if value is not None:
                self.power_profile_provider = provider
                return value
        self.power_profile_provider = None
        return None

    def niri_state(self) -> dict[str, Any]:
        workspaces = self.try_run("niri", "msg", "--json", "workspaces")
        windows = self.try_run("niri", "msg", "--json", "windows")
        try:
            workspaces_data = json.loads(workspaces) if workspaces is not None else None
            windows_data = json.loads(windows) if windows is not None else None
            if not isinstance(workspaces_data, list) or not isinstance(windows_data, list):
                raise ValueError("No niri session")
            if not all(isinstance(item, dict) for item in workspaces_data + windows_data):
                raise ValueError("Invalid niri response")
            workspaces_data.sort(key=lambda item: (str(item.get("output") or ""), item.get("idx") or 0, item.get("id") or 0))
            return {"available": True, "workspaces": workspaces_data, "windows": windows_data}
        except (ValueError, TypeError):
            return {"available": False, "workspaces": [], "windows": []}

    def snapshot(self) -> dict[str, Any]:
        if self.demo:
            return self.demo_snapshot()
        self.preferences.reload()
        # Emit each input acknowledgement before a completed background job
        # replaces lastResult. Otherwise a fast charge job could hide another
        # action's acknowledgement and leave its QML button pending forever.
        if not self.result_unemitted:
            if self.charge_job is not None and self.charge_job.done(): self.finish_charge()
            else: self.finish_features()
        self.result_unemitted = False
        weather = self.weather.snapshot(self.preferences.values, allow_fetch=self.weather_fetch and not self.settings_only)
        if self.manage_idle and not self.settings_only:
            place = self.weather.auto_location if self.preferences.values['weatherAutoLocation'] else self.preferences.values['weatherLocation']
            self.night_state = self.night_light.sync(self.preferences.values, place)
        self.capture.refresh()
        if self.settings_only:
            return {"apps": [], "niri": self.niri, "system": {}, "weather": weather, "preferences": dict(self.preferences.values),
                    "lastResult": dict(self.last_result), "wallpaperLibrary": self.wallpaper_library, "displays": self.displays,
                    "keybinds": self.keybinds, "idle": self.idle_state, "platform": self.platform, "nightLight": self.night_state, "capture": self.capture.state}
        if time.monotonic() - self.last_app_scan > 60:
            self.apps = self.applications.scan()
            self.last_app_scan = time.monotonic()
        self.niri = self.niri_state()
        # Window/focus event bursts must not cause expensive hardware probes.
        if self.system_cache is None or time.monotonic() - self.last_system_sample >= 1.5:
            system = self.cpu_memory()
            system.update(tempC=self.temperature(), battery=self.battery(), network=self.network(),
                          bluetooth=self.bluetooth(), audio=self.audio(), microphone=self.audio("@DEFAULT_AUDIO_SOURCE@"), brightness=self.brightness(),
                          powerProfile=self.power_profile(), charging=self.charging(), recording=self.recording())
            self.system_cache = system
            self.last_system_sample = time.monotonic()
        if self.manage_idle: self.idle_state = self.idle_control.sync(self.preferences.values, self.system_cache["battery"]["acOnline"])
        if self.monitor_enabled and (not self.monitor.state or time.monotonic() - self.monitor.state["sampledAt"] >= 1.5):
            self.monitor.sample(self.system_cache)
        return {"apps": self.apps, "niri": self.niri, "system": self.system_cache, "weather": weather,
                "preferences": dict(self.preferences.values), "lastResult": dict(self.last_result),
                "wallpaperLibrary": self.wallpaper_library, "displays": self.displays, "notificationHistory": self.notification_history,
                "monitor": self.monitor.state if self.monitor_enabled else {}, "idle": self.idle_state, "keybinds": self.keybinds, "platform": self.platform, "nightLight": self.night_state, "capture": self.capture.state}

    @staticmethod
    def valid_notifications(value):
        if not isinstance(value, list): return []
        result = []
        for item in value[:200]:
            if not isinstance(item, dict) or item.get("transient"): continue
            if (not all(isinstance(item.get(k), str) for k in ("id", "appName", "summary", "body"))
                    or type(item.get("timestamp")) not in (int, float) or not math.isfinite(item["timestamp"])
                    or type(item.get("urgency")) is not int): continue
            result.append({"id": item["id"][:128], "appName": item["appName"][:256], "summary": item["summary"][:512],
                           "body": item["body"][:4096], "appIcon": str(item.get("appIcon") or "")[:512],
                           "timestamp": item["timestamp"], "urgency": max(0, min(2, item["urgency"])),
                           "actions": [], "active": False, "popup": False, "transient": False})
        return result

    def start_feature(self, action, operation):
        if action in self.feature_jobs: raise ValueError("This operation is already running")
        self.feature_jobs[action] = self.feature_executor.submit(operation)
        return "Working…"

    def finish_features(self):
        for action, job in list(self.feature_jobs.items()):
            if not job.done(): continue
            self.result_sequence += 1
            try:
                if getattr(job, 'capture_token', self.capture.state.get('token')) != self.capture.state.get('token'):
                    self.last_result = {'ok': True, 'action': action, 'message': '', 'sequence': self.result_sequence}
                    del self.feature_jobs[action]
                    break
                value = job.result()
                if action == "wallpaperScan": self.wallpaper_library = value; message = "Wallpaper library refreshed"
                elif action == "captureOcr":
                    token, content = value
                    if self.capture.state.get('token') == token: self.capture.state['ocrText'] = content
                    message = "Text recognized" if content else "No text found. Try a tighter capture or another OCR language."
                else: message = value
                self.last_result = {"ok": True, "action": action, "message": message, "sequence": self.result_sequence}
            except (CommandError, ValueError, OSError) as error:
                self.last_result = {"ok": False, "action": action, "message": str(error)[:400], "sequence": self.result_sequence}
                if action == "wallpaperScan": self.wallpaper_library = {**self.wallpaper_library, "error": str(error)[:400]}
            del self.feature_jobs[action]
            self.system_cache = None
            # Deliver each completion separately so every pending QML action clears.
            break

    def recording(self) -> dict[str, Any]:
        """Read supported recorder processes belonging to this session's user."""
        supported = {"wf-recorder": "wf-recorder", "gpu-screen-recorder": "GPU Screen Recorder"}
        try:
            uptime = float((self.proc / "uptime").read_text().split()[0])
            ticks = os.sysconf("SC_CLK_TCK")
            matches = []
            for entry in self.proc.iterdir():
                if not entry.name.isdigit(): continue
                try:
                    if entry.stat().st_uid != os.getuid(): continue
                    name = Path(os.readlink(entry / "exe")).name
                    if name not in supported: continue
                    fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                    if fields[0] == "Z": continue
                    elapsed = max(0, int(uptime - int(fields[19]) / ticks))
                    matches.append({"active": True, "name": supported[name], "elapsed": elapsed})
                except (OSError, ValueError, IndexError): continue
            return max(matches, key=lambda item: item["elapsed"]) if matches else {"active": False}
        except (OSError, ValueError): return {"active": False}

    def demo_snapshot(self) -> dict[str, Any]:
        if hasattr(self, "_demo_state"):
            self._demo_state["preferences"] = dict(self.preferences.values)
            self._demo_state["lastResult"] = dict(self.last_result)
            self._demo_state.update(wallpaperLibrary=self.wallpaper_library, displays=self.displays, notificationHistory=[],
                monitor=self.monitor.state if self.monitor_enabled else {}, idle=self.idle_state, keybinds=self.keybinds, platform=self.platform, nightLight=self.night_state, capture=self.capture.state)
            unit = self.preferences.values["weatherUnit"]
            self._demo_state["weather"].update(automatic=self.preferences.values["weatherAutoLocation"],
                unit="°F" if unit == "fahrenheit" else "°C", temperature=84 if unit == "fahrenheit" else 29,
                feelsLike=90 if unit == "fahrenheit" else 32,
                wind=6 if unit == "fahrenheit" else 10, windUnit="mph" if unit == "fahrenheit" else "km/h",
                daily=[{"date": date, "min": low if unit == "celsius" else round(low * 1.8 + 32),
                        "max": high if unit == "celsius" else round(high * 1.8 + 32), "rainChance": rain}
                       for date, low, high, rain in [("2026-10-11", 25, 31, 30), ("2026-10-12", 24, 30, 65), ("2026-10-13", 25, 32, 20)]])
            if not self.preferences.values["weatherAutoLocation"]:
                self._demo_state["weather"]["location"] = self.preferences.values["weatherLocation"]
            else:
                self._demo_state["weather"]["location"] = {"name": "Ho Chi Minh City", "country": "Vietnam", "latitude": 10.82, "longitude": 106.63}
            return self._demo_state
        self._demo_state = {
            "apps": [{"id": "org.mozilla.firefox.desktop", "name": "Firefox", "icon": "firefox", "path": "", "terminal": False},
                     {"id": "kitty.desktop", "name": "Kitty", "icon": "kitty", "path": "", "terminal": False},
                     {"id": "org.gnome.Nautilus.desktop", "name": "Files", "icon": "org.gnome.Nautilus", "path": "", "terminal": False}],
            "niri": {"available": True, "workspaces": [
                {"id": i, "idx": i, "name": None, "output": "eDP-1", "is_focused": i == 1, "is_active": i == 1}
                for i in range(1, 5)], "windows": [
                    {"id": 1, "title": "LME Shell — Preview", "app_id": "firefox", "workspace_id": 1, "is_focused": True},
                    {"id": 2, "title": "Terminal · project", "app_id": "kitty", "workspace_id": 1, "is_focused": False},
                    {"id": 3, "title": "Documents", "app_id": "org.gnome.Nautilus", "workspace_id": 2, "is_focused": False}]},
            "system": {"cpu": 12.4, "memoryPercent": 34.2, "memoryUsedGiB": 5.47, "memoryTotalGiB": 16,
                       "tempC": 47, "battery": {"available": True, "percent": 82, "charging": False, "acOnline": False},
                       "network": {"available": True, "enabled": True, "connected": True, "ssid": "Home Wi-Fi", "strength": 88,
                                   "device": "wlp1s0", "saved": [{"uuid": "demo-home", "name": "Home Wi-Fi"}],
                                   "networks": [{"ssid": "Home Wi-Fi", "strength": 88, "connected": True, "secured": True, "security": "WPA2", "bssid": "AA:BB:CC:DD:EE:01"}, {"ssid": "Guest", "strength": 62, "connected": False, "secured": True, "security": "WPA2", "bssid": "AA:BB:CC:DD:EE:02"}]},
                       "bluetooth": {"available": True, "enabled": True, "softBlocked": False, "hardBlocked": False, "adapter": "/org/bluez/hci0",
                                     "adapters": [{"path": "/org/bluez/hci0", "name": "Laptop Bluetooth", "enabled": True}],
                                     "devices": [{"path": "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF", "name": "Headphones", "connected": True}]},
                       "audio": {"available": True, "volume": 42, "muted": False}, "microphone": {"available": True, "volume": 60, "muted": False},
                       "brightness": {"available": True, "percent": 65}, "powerProfile": "balanced",
                       "charging": {"available": True, "canSet": True, "kind": "threshold", "mode": "conservation",
                                    "limitPercent": 85, "supports85": True, "reason": "", "busy": False}},
            "weather": {"available": True, "configured": True, "automatic": True, "loading": False, "stale": False, "error": "",
                        "location": {"name": "Ho Chi Minh City", "country": "Vietnam", "latitude": 10.82, "longitude": 106.63},
                        "temperature": 29, "feelsLike": 32, "humidity": 76, "wind": 10, "windUnit": "km/h", "unit": "°C",
                        "condition": "Partly cloudy", "icon": "weather-cloud", "updatedAt": time.time(),
                        "daily": [{"date": "2026-10-11", "min": 25, "max": 31, "rainChance": 30},
                                  {"date": "2026-10-12", "min": 24, "max": 30, "rainChance": 65},
                                  {"date": "2026-10-13", "min": 25, "max": 32, "rainChance": 20}],
                        "search": {"query": "", "loading": False, "results": [], "error": ""}},
            "preferences": dict(self.preferences.values), "lastResult": dict(self.last_result),
        }
        return self.demo_snapshot()

    def charging(self) -> dict[str, Any]:
        state = self.charger.state()
        state["canSet"] = state["available"] and (state["writable"] or (self.runner.available("pkexec") and trusted_helper()))
        state["busy"] = self.charge_job is not None
        if state["available"] and not state["canSet"]:
            state["reason"] = "Install the administrator charge helper. See docs/CHARGING.md."
        return state

    def set_charge(self, limit: int) -> str:
        if self.charger.state()["writable"]:
            self.charger.set_mode(limit)
        else:
            self.runner.run("pkexec", "--disable-internal-agent", "/usr/bin/python3", "-I", str(HELPER_PATH), str(limit), timeout=90)
        state = self.charger.state()
        desired = "conservation" if limit == 85 else "max"
        if not state["available"] or state["mode"] != desired or (state["supports85"] and state["limitPercent"] != limit):
            raise ValueError("The kernel did not confirm the requested charge mode.")
        return "Charge mode updated" + (f" · {limit}%" if state["supports85"] else " · firmware limit")

    def finish_charge(self) -> None:
        if self.charge_job is None or not self.charge_job.done():
            return
        self.result_sequence += 1
        try:
            self.last_result = {"ok": True, "action": "chargeMode", "message": self.charge_job.result()}
        except (CommandError, ValueError, OSError) as error:
            self.last_result = {"ok": False, "action": "chargeMode", "message": str(error)[:400]}
        self.last_result["sequence"] = self.result_sequence
        self.charge_job = None
        self.system_cache = None

    def apply_wallpaper(self, raw: Any, save: bool = True, animate: bool = True) -> str:
        if self.demo:
            raise ValueError("Wallpaper commands are disabled in demo mode")
        if not isinstance(raw, str):
            raise ValueError("A wallpaper file path is required")
        path = Path(raw).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
            raise ValueError("Select an existing PNG, JPEG, WebP, GIF, or BMP wallpaper")
        self.runner.executable("awww")
        try:
            self.runner.run("awww", "query", timeout=1)
        except CommandError:
            self.runner.spawn([self.runner.executable("awww-daemon")])
            deadline = time.monotonic() + 4
            while True:
                try:
                    self.runner.run("awww", "query", timeout=1)
                    break
                except CommandError:
                    if time.monotonic() >= deadline:
                        raise CommandError("awww-daemon did not become ready. Check your Wayland session.")
                    time.sleep(0.1)
        self.runner.run("awww", "img", str(path), "--transition-type",
                        "fade" if animate and self.preferences.values["animations"] else "none", timeout=15)
        if save:
            self.preferences.set("wallpaper", str(path))
        return "Wallpaper updated"

    @staticmethod
    def percentage(value: Any, minimum: int = 0) -> int:
        if type(value) not in {int, float} or not math.isfinite(value) or not minimum <= value <= 100:
            raise ValueError(f"Value must be between {minimum} and 100")
        return round(value)

    @staticmethod
    def identifier(value: Any) -> str:
        if type(value) is not int or value < 0:
            raise ValueError("A non-negative numeric ID is required")
        return str(value)

    def handle(self, request: Any) -> dict[str, Any]:
        self.result_sequence += 1
        self.result_unemitted = True
        action = request.get("action", "") if isinstance(request, dict) else ""
        try:
            if not isinstance(request, dict) or not isinstance(action, str) or not action:
                raise ValueError("Input must be an object with an action")
            if self.settings_only and action not in {"setting", "wallpaper", "refresh", "weatherSearch", "weatherDetect", "weatherSelect", "appearanceSave", "appearanceApply", "appearanceDelete", "displayRefresh", "displayApply", "displayConfirm", "displayRevert", "wallpaperScan", "keybindRefresh", "idleRefresh", "platformRefresh", "nightLightRefresh"}:
                raise ValueError("This action is unavailable in the settings app")
            if self.demo:
                self.perform_demo(action, request)
                self.last_result = {"ok": True, "action": action, "message": "Demo preview: no system command executed",
                                    "sequence": self.result_sequence}
                if action == "calculate": self.last_result.update(query=request.get("query"), message=calculate(request.get("query")))
                return dict(self.last_result)
            message = self.perform(action, request)
            if action == "chargeMode" or action in self.feature_jobs:
                self.last_result = {"ok": True, "action": action, "message": message, "pending": True, "sequence": self.result_sequence}
                return dict(self.last_result)
            if action in {"refresh", "volume", "mute", "micVolume", "micMute", "brightness", "wifiToggle", "bluetoothToggle", "bluetoothDevice", "powerProfile"}:
                self.system_cache = None
            self.last_result = {"ok": True, "action": action, "message": message}
        except (CommandError, ValueError, TypeError, KeyError, OSError) as exc:
            self.last_result = {"ok": False, "action": action if isinstance(action, str) else "", "message": str(exc)[:400]}
            if action in {"bluetoothToggle", "bluetoothDevice"}:
                self.system_cache = None
        self.last_result["sequence"] = self.result_sequence
        if action == "calculate": self.last_result["query"] = request.get("query")
        return dict(self.last_result)

    def perform_demo(self, action: str, request: dict[str, Any]) -> None:
        state = self.demo_snapshot()
        system = state["system"]
        if action == "monitor":
            if type(request.get("enabled")) is not bool: raise ValueError("Monitor enabled must be boolean")
            self.monitor_enabled = request["enabled"]
            self.monitor.state = {"history": [{"cpu": 18+12*math.sin(i/4), "memory": 34+i/20, "download": 200000+80000*math.sin(i/3), "upload": 16000} for i in range(60)],
                "cores": [{"name": "CPU"+str(i), "percent": 12+i*2} for i in range(12)],
                "interfaces": [{"name": "wlp1s0", "download": 245760, "upload": 18432}],
                "processes": [{"pid": 1820, "name": "firefox", "user": "user", "cpu": 18.4, "memoryBytes": 943718400}, {"pid": 1142, "name": "niri", "user": "user", "cpu": 3.8, "memoryBytes": 188743680}, {"pid": 1250, "name": "quickshell", "user": "user", "cpu": 1.2, "memoryBytes": 125829120}],
                "processCount": 3, "sampledAt": 1, "error": ""}
        elif action == "keybindRefresh":
            self.keybinds = read_keybinds(str(Path(__file__).resolve().parents[1]/"config/niri/lme-shell.kdl"))
        elif action == "platformRefresh": pass
        elif action == "nightLightRefresh":
            self.night_state = {'available': True, 'enabled': self.preferences.values['nightLightEnabled'], 'active': self.preferences.values['nightLightEnabled'], 'temperature': self.preferences.values['nightLightTemperature'], 'mode': self.preferences.values['nightLightMode'], 'start': self.preferences.values['nightLightStart'], 'end': self.preferences.values['nightLightEnd'], 'error': ''}
        elif action in {"captureClose", "captureLanguages"}:
            if action == 'captureClose': self.capture.close()
            else: self.capture.state['languages'] = ['eng', 'vie']
        elif action == "captureExport":
            if request.get('operation') not in ('copy', 'save'): raise ValueError('Unknown screenshot export')
        elif action == "captureOcr": self.capture.state['ocrText'] = 'LME Shell\nLocal screenshot text recognition'
        elif action == "idleRefresh":
            self.idle_state = {"source": "battery", "available": True, "running": False, "error": "", "profile": self.preferences.values["idleProfiles"]["battery"]}
        elif action == "idleInhibit":
            if type(request.get("value")) is not bool: raise ValueError("Idle inhibit must be boolean")
            self.idle_control.paused = request["value"]
        elif action.startswith("appearance"):
            self.appearance_action(action, request)
        elif action == "displayRefresh":
            if not self.displays["outputs"]:
                self.displays = {"outputs": [{"name": "eDP-1", "description": "Lenovo laptop display", "enabled": True,
                    "modes": [{"width": 1920, "height": 1080, "refresh": hz * 1000, "label": f"1920 × 1080 · {hz} Hz"} for hz in (60, 120)],
                    "current": {"width": 1920, "height": 1080, "refresh": 120000}, "scale": 1, "x": 0, "y": 0, "width": 1920, "height": 1080}], "preview": {}}
            if self.displays["preview"].get("status") == "pending" and time.time() >= self.displays["preview"]["deadline"]:
                self.displays["preview"]["status"] = "reverted"
        elif action == "displayApply":
            layout = validate_layout(request.get("layout"), self.displays["outputs"])
            self.displays["preview"] = {"token": "demo", "status": "pending", "deadline": time.time() + 20, "layout": layout}
        elif action in {"displayConfirm", "displayRevert"}:
            if self.displays["preview"].get("status") != "pending": raise ValueError("No display preview")
            if action == "displayConfirm": self.preferences.values["displayLayout"] = self.displays["preview"]["layout"]
            self.displays["preview"]["status"] = "confirmed" if action == "displayConfirm" else "reverted"
        elif action == "wallpaperScan":
            bundled = Path(__file__).resolve().parents[1] / "assets/wallpapers"
            self.wallpaper_library = wallpaper_library(str(bundled))
        elif action == "calculate":
            state["calculator"] = {"query": request.get("query"), "result": calculate(request.get("query")), "error": ""}
        elif action == "copyText":
            if not isinstance(request.get("text"), str): raise ValueError("Text is required")
        elif action == "notificationSave": pass
        elif action in {"wifiScan", "wifiConnect", "wifiSaved", "wifiDisconnect", "wifiForget"}:
            if action in {"wifiConnect", "wifiSaved"}:
                system["network"].update(connected=True, ssid=request.get("ssid", "Home Wi-Fi"))
            elif action == "wifiDisconnect": system["network"].update(connected=False, ssid="")
        elif action == "setting":
            key = request.get("key")
            if not isinstance(key, str) or key == "wallpaper":
                raise ValueError("Use the wallpaper action to change wallpaper")
            if 'token' in request:
                delta = theme_token(key, request['token'], request.get('value'))
                current = dict(self.preferences.values[key]); current.pop(request['token'], None); current.update(delta)
                self.preferences.values[key] = current
            else: self.preferences.values[key] = validate_preference(key, request.get("value"))
        elif action == "volume":
            system["audio"]["volume"] = self.percentage(request.get("value"))
        elif action == "mute":
            system["audio"]["muted"] = not system["audio"]["muted"]
        elif action == "micVolume":
            system["microphone"]["volume"] = self.percentage(request.get("value"))
        elif action == "micMute":
            system["microphone"]["muted"] = not system["microphone"]["muted"]
        elif action == "brightness":
            system["brightness"]["percent"] = self.percentage(request.get("value"), 1)
        elif action == "wifiToggle":
            network = system["network"]
            network["enabled"] = not network["enabled"]
            network["connected"] = network["enabled"]
        elif action == "bluetoothToggle":
            system["bluetooth"]["enabled"] = not system["bluetooth"]["enabled"]
        elif action == "bluetoothDevice":
            device = next((item for item in system["bluetooth"]["devices"] if item["path"] == request.get("path")), None)
            if not device or type(request.get("connected")) is not bool:
                raise ValueError("Unknown Bluetooth device or state")
            device["connected"] = request["connected"]
        elif action == "powerProfile":
            value = request.get("value")
            if value not in POWER_PROFILES:
                raise ValueError("Invalid power profile")
            system["powerProfile"] = value
        elif action == "chargeMode":
            value = request.get("value")
            if type(value) is not int or value not in (85, 100):
                raise ValueError("Choose conservation (85) or maximum charge (100).")
            system["charging"].update(mode="conservation" if value == 85 else "max", limitPercent=value)
        elif action == "weatherSearch":
            query = request.get("query")
            if not isinstance(query, str) or not 2 <= len(query.strip()) <= 100:
                raise ValueError("Enter a city name of 2–100 characters.")
            state["weather"]["search"] = {"query": query, "loading": False, "error": "",
                "results": [{"name": query.strip(), "country": "Demo", "latitude": 10.82, "longitude": 106.63}]}
        elif action == "weatherSelect":
            place = location(request.get("location"))
            if not place:
                raise ValueError("Select a city first.")
            self.preferences.values.update(weatherLocation=place, weatherAutoLocation=False)
        elif action in {"weatherRefresh", "weatherDetect"}:
            pass
        elif action == "workspace":
            workspace_id = self.identifier(request.get("id"))
            if not any(str(item["id"]) == workspace_id for item in state["niri"]["workspaces"]):
                raise ValueError("Workspace is no longer available")
            for workspace in state["niri"]["workspaces"]:
                workspace["is_focused"] = workspace["is_active"] = str(workspace["id"]) == workspace_id
        elif action == "focusWindow":
            window_id = self.identifier(request.get("id"))
            if not any(str(item["id"]) == window_id for item in state["niri"]["windows"]):
                raise ValueError("Window is no longer available")
            for window in state["niri"]["windows"]:
                window["is_focused"] = str(window["id"]) == window_id
        elif action == "moveWindow":
            window_id = self.identifier(request.get("id"))
            workspace_id = self.identifier(request.get("workspaceId"))
            window = next((item for item in state["niri"]["windows"] if str(item["id"]) == window_id), None)
            if window is None or not any(str(item["id"]) == workspace_id for item in state["niri"]["workspaces"]):
                raise ValueError("Window or workspace is no longer available")
            window["workspace_id"] = int(workspace_id)
        elif action == "launch":
            if not any(item["id"] == request.get("id") for item in state["apps"]):
                raise ValueError("Application is no longer available")
        elif action == "wallpaper":
            value = request.get("path")
            if not isinstance(value, str):
                raise ValueError("A wallpaper file path is required")
            path = str(Path(value).expanduser().resolve())
            self.preferences.values["wallpaper"] = validate_preference("wallpaper", path)
        elif action == "openSettings":
            if request.get("target") not in {"network", "bluetooth", "audio"}:
                raise ValueError("Unknown settings panel")
        elif action not in {"refresh", "lock", "screenshot", "screenshotArea", "screenshotWindow", "nativeOverview", "logout", "suspend", "reboot", "poweroff"}:
            raise ValueError(f"Unknown action: {action}")

    def perform(self, action: str, request: dict[str, Any]) -> str:
        run = self.runner.run
        if action == 'nightLightRefresh':
            if type(request.get('retry', False)) is not bool: raise ValueError('Night Light retry must be boolean')
            if self.settings_only:
                self.night_state = {'available': self.runner.available('wlsunset'), 'active': False,
                                    'error': 'Start LME Shell to control Night Light.'}
                if request.get('retry'):
                    run('quickshell', '-p', self.shell_entry, 'ipc', 'call', 'shell', 'retryNightLight')
                reply = self.try_run('quickshell', '-p', self.shell_entry, 'ipc', 'call', 'shell', 'nightLightStatus')
                try:
                    state = json.loads(reply or '{}')
                    if isinstance(state, dict) and 'active' in state: self.night_state = state
                except ValueError: pass
            else: self.night_light.signature = None
            return 'Night Light refreshed'
        if action == 'captureClose': self.capture.close(); return 'Screenshot closed'
        if action == 'captureLanguages': self.capture.languages(); return 'OCR languages refreshed'
        if action == 'captureExport':
            if type(request.get('token')) is not str: raise ValueError('Missing screenshot session')
            message = self.start_feature(action, lambda: self.capture.export(request['token'], request.get('operation'), request.get('folder')))
            self.feature_jobs[action].capture_token = request['token']
            return message
        if action == 'captureOcr':
            token, language = request.get('token'), request.get('language')
            if type(token) is not str: raise ValueError('Missing screenshot session')
            message = self.start_feature(action, lambda: (token, self.capture.ocr(token, language)))
            self.feature_jobs[action].capture_token = token
            return message
        if action == "monitor":
            if type(request.get("enabled")) is not bool: raise ValueError("Monitor enabled must be boolean")
            self.monitor_enabled = request["enabled"]
            self.monitor = SystemMonitor(self.proc)
            return "System monitor started" if self.monitor_enabled else "System monitor stopped"
        if action == "keybindRefresh":
            self.keybinds = read_keybinds(self.preferences.values["niriConfigPath"])
            return "Keybindings refreshed"
        if action == "platformRefresh":
            self.platform = self.compositor_features()
            return "Compositor version checked"
        if action == "idleRefresh":
            self.idle_state = {"source": "ac" if self.ac_online() else "battery", "available": all(self.runner.available(n) for n in ("swayidle", "swaylock", "niri")), "error": ""}
            if self.settings_only:
                reply = self.try_run("quickshell", "-p", self.shell_entry, "ipc", "call", "shell", "idleStatus")
                try:
                    state = json.loads(reply or "{}")
                    if isinstance(state, dict) and state.get("source") in {"ac", "battery"}: self.idle_state = state
                except ValueError: pass
            return "Idle profile refreshed"
        if action == "idleInhibit":
            if type(request.get("value")) is not bool: raise ValueError("Idle inhibit must be boolean")
            self.idle_control.paused = request["value"]
            return "Idle paused" if request["value"] else "Idle resumed"
        if action.startswith("appearance"): return self.appearance_action(action, request)
        if action == "wallpaperScan":
            return self.start_feature(action, lambda: wallpaper_library(request.get("folder")))
        if action == "displayRefresh":
            self.displays = self.display_control.snapshot()
            return "Displays refreshed"
        if action == "displayApply":
            self.display_control.start(request.get("layout"))
            self.displays = self.display_control.snapshot()
            return "Display preview requested; confirm within 20 seconds"
        if action in {"displayConfirm", "displayRevert"}:
            layout = self.display_control.decide(request.get("token"), action == "displayConfirm")
            if action == "displayConfirm": self.preferences.set("displayLayout", layout)
            self.displays = self.display_control.snapshot()
            return "Display layout saved" if action == "displayConfirm" else "Restoring displays"
        if action == "notificationSave":
            if not isinstance(request.get("entries"), list): raise ValueError("Invalid notification history")
            self.notification_history = self.valid_notifications(request["entries"])
            write_json(self.notification_path, self.notification_history)
            return ""
        if action == "calculate":
            # Query/result travel in the acknowledgement so stale queries can be ignored.
            return calculate(request.get("query"))
        if action == "copyText":
            text = request.get("text")
            if not isinstance(text, str) or len(text.encode()) > 65536: raise ValueError("Invalid copy text")
            run("wl-copy", "--type", "text/plain;charset=utf-8", input=text)
            return "Copied"
        if action in {"wifiScan", "wifiConnect", "wifiSaved", "wifiDisconnect", "wifiForget"}:
            return self.start_feature(action, lambda: self.wifi_action(action, request))
        if action == "chargeMode":
            value = request.get("value")
            if type(value) is not int or value not in (85, 100):
                raise ValueError("Choose conservation (85) or maximum charge (100).")
            state = self.charging()
            if not state["canSet"]:
                raise ValueError(state["reason"])
            if self.charge_job is not None:
                raise ValueError("A charge-mode change is already running.")
            self.charge_job = self.charge_executor.submit(self.set_charge, value)
            self.system_cache = None
            return "Changing charge mode; administrator authentication may be required"
        if action == "weatherSearch":
            self.weather.search(request.get("query"))
            return "Searching locations"
        if action == "weatherDetect":
            self.weather.detect()
            return "Detecting approximate location"
        if action == "weatherRefresh":
            self.weather.refresh(self.preferences.values["weatherAutoLocation"])
            return "Refreshing weather"
        if action == "weatherSelect":
            place = location(request.get("location"))
            if not place:
                raise ValueError("Select a city first.")
            self.preferences.update({"weatherLocation": place, "weatherAutoLocation": False})
            return "Weather location updated"
        if action == "refresh":
            if self.settings_only:
                self.preferences.reload(force=True)
                return "Preferences refreshed"
            self.apps = self.applications.scan()
            self.last_app_scan = time.monotonic()
            return "State refreshed"
        if action == "launch":
            app_id = request.get("id")
            if not isinstance(app_id, str) or app_id not in self.applications.entries:
                raise ValueError("Application is no longer available; refresh the launcher")
            app = self.applications.entries[app_id]
            if app["terminal"]:
                # gio chooses the desktop's terminal independently of our
                # setting; terminal applications must honor the user's choice.
                terminal = shutil.which(self.preferences.values["terminal"])
                if not terminal:
                    raise CommandError("The configured terminal is unavailable")
                self.runner.spawn([terminal, "-e", *app["argv"]])
            elif self.runner.available("gio"):
                run("gio", "launch", app["path"])
            else:
                self.runner.spawn(list(app["argv"]))
            return f"Launched {app['name']}"
        if action == "focusWindow":
            run("niri", "msg", "action", "focus-window", "--id", self.identifier(request.get("id")))
            return "Window focused"
        if action == "moveWindow":
            window_id = int(self.identifier(request.get("id")))
            workspace_id = int(self.identifier(request.get("workspaceId")))
            self.niri = self.niri_state()
            if (not any(item.get("id") == window_id for item in self.niri["windows"])
                    or not any(item.get("id") == workspace_id for item in self.niri["workspaces"])):
                raise ValueError("Window or workspace is no longer available")
            self.niri_action({"MoveWindowToWorkspace": {"window_id": window_id, "reference": {"Id": workspace_id}, "focus": False}})
            return "Window moved to workspace"
        if action == "nativeOverview":
            run("niri", "msg", "action", "toggle-overview")
            return "Native overview toggled"
        if action == "workspace":
            workspace_id = self.identifier(request.get("id"))
            workspace = next((item for item in self.niri["workspaces"] if str(item.get("id")) == workspace_id), None)
            if workspace is None:
                self.niri = self.niri_state()
                workspace = next((item for item in self.niri["workspaces"] if str(item.get("id")) == workspace_id), None)
            if workspace is None:
                raise ValueError("Workspace is no longer available")
            if workspace.get("output"):
                run("niri", "msg", "action", "focus-monitor", str(workspace["output"]))
            run("niri", "msg", "action", "focus-workspace", str(workspace["idx"]))
            return "Workspace focused"
        if action == "volume":
            value = self.percentage(request.get("value"))
            run("wpctl", "set-volume", "--limit", "1.0", "@DEFAULT_AUDIO_SINK@", f"{value}%")
            return f"Volume {value}%"
        if action == "mute":
            run("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle")
            return "Mute toggled"
        if action == "micVolume":
            value = self.percentage(request.get("value"))
            run("wpctl", "set-volume", "--limit", "1.0", "@DEFAULT_AUDIO_SOURCE@", f"{value}%")
            return f"Microphone {value}%"
        if action == "micMute":
            run("wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle")
            return "Microphone mute toggled"
        if action == "brightness":
            value = self.percentage(request.get("value"), 1)
            run("brightnessctl", "--class=backlight", "set", f"{value}%")
            return f"Brightness {value}%"
        if action == "wifiToggle":
            status = run("nmcli", "radio", "wifi")
            run("nmcli", "radio", "wifi", "off" if status.strip() == "enabled" else "on")
            return "Wi-Fi toggled"
        if action == "bluetoothToggle":
            return self.set_bluetooth(not self.bluetooth()["enabled"])
        if action == "bluetoothDevice":
            path, connected = request.get("path"), request.get("connected")
            state = self.bluetooth()
            if (not isinstance(path, str) or not re.fullmatch(r"/org/bluez/hci[0-9]+/dev_(?:[A-Fa-f0-9]{2}_){5}[A-Fa-f0-9]{2}", path)
                    or type(connected) is not bool or not any(item["path"] == path for item in state["devices"])):
                raise ValueError("Unknown Bluetooth device or state")
            run("busctl", "--system", "call", "org.bluez", path, "org.bluez.Device1", "Connect" if connected else "Disconnect", timeout=15.0)
            return "Bluetooth device " + ("connected" if connected else "disconnected")
        if action == "powerProfile":
            value = request.get("value")
            if value not in POWER_PROFILES:
                raise ValueError("Invalid power profile")
            if self.power_profile() is None or self.power_profile_provider is None:
                raise CommandError("No compatible power-profile service is available")
            provider = self.power_profile_provider
            if provider[0] == "dbus":
                # An active local session is normally authorized by polkit;
                # allow a bounded interaction if the administrator changed it.
                run("busctl", "--system", "set-property", *provider[1:], "ActiveProfile", "s", value, timeout=30.0)
            else:
                run("powerprofilesctl", "set", value, timeout=30.0)
            return f"Power profile: {value}"
        if action == "lock":
            self.runner.executable("swaylock")
            return self.start_feature(action, self.lock_session)
        if action in {"screenshot", "screenshotArea", "screenshotWindow"}:
            # niri owns capture and clipboard integration. Traditional grim uses
            # wlr-screencopy, which is not the portable screenshot path on niri.
            # Let a just-dismissed control panel finish its surface teardown.
            time.sleep(0.2)
            return self.capture.start({'screenshot': 'screen', 'screenshotArea': 'area', 'screenshotWindow': 'window'}[action])
        if action == "logout":
            run("niri", "msg", "action", "quit", "--skip-confirmation")
            return "Logout requested"
        if action == "suspend" and self.preferences.values["idleLockBeforeSleep"]:
            self.runner.executable("swaylock")
            return self.start_feature(action, lambda: self.lock_session(suspend=True))
        if action in {"suspend", "reboot", "poweroff"}:
            run("systemctl", action)
            return f"{action.capitalize()} requested"
        if action == "wallpaper":
            return self.apply_wallpaper(request.get("path"))
        if action == "setting":
            key = request.get("key")
            if not isinstance(key, str) or key == "wallpaper":
                raise ValueError("Use the wallpaper action to change wallpaper")
            if 'token' in request and not isinstance(request['token'], str): raise ValueError('Invalid theme token')
            self.preferences.set(key, request.get("value"), token=request.get('token'))
            return "Preferences saved"
        if action == "openSettings":
            target = request.get("target")
            commands = {"network": "nm-connection-editor", "bluetooth": "blueman-manager", "audio": "pavucontrol"}
            if not isinstance(target, str) or target not in commands:
                raise ValueError("Unknown settings panel")
            self.runner.spawn([self.runner.executable(commands[target])])
            return f"Opened {target} settings"
        raise ValueError(f"Unknown action: {action}")

    def lock_session(self, suspend=False):
        try: secure_lock()
        except RuntimeError as exc: raise CommandError(str(exc)) from exc
        if suspend: self.runner.run("systemctl", "suspend", timeout=30)
        return "Session locked" if not suspend else "Suspend requested after locking"

    def appearance_action(self, action, request):
        if not self.demo: self.preferences.reload(force=True)
        profiles = copy.deepcopy(self.preferences.values["appearanceProfiles"])
        name = request.get("name")
        if not isinstance(name, str): raise ValueError("Choose a profile name")
        found = next((p for p in profiles if p["name"].casefold() == name.strip().casefold()), None)
        if action == "appearanceSave":
            if name.strip().casefold() == "dracula": raise ValueError("Dracula is the built-in profile; choose another name")
            profile = appearance_profile({"name": name, **{k: self.preferences.values[k] for k in APPEARANCE_KEYS}}, validate_preference)
            profiles = [p for p in profiles if p["name"].casefold() != profile["name"].casefold()] + [profile]
            changes = {"appearanceProfiles": validate_preference("appearanceProfiles", profiles)}
        elif action == "appearanceApply" and found:
            changes = {k: found[k] for k in APPEARANCE_KEYS}
        elif action == "appearanceDelete" and found and found["name"].casefold() != "dracula":
            changes = {"appearanceProfiles": [p for p in profiles if p != found]}
        else: raise ValueError("Unknown profile, or the built-in Dracula profile cannot be deleted")
        if self.demo: self.preferences.values.update(changes)
        else: self.preferences.update(changes)
        return "Appearance profile " + {"appearanceSave": "saved", "appearanceApply": "applied", "appearanceDelete": "deleted"}[action]

    def wifi_action(self, action, request):
        state = self.network()
        if not state["available"]: raise CommandError("NetworkManager is unavailable")
        interface = request.get("device") or state.get("device")
        if not isinstance(interface, str) or interface != state.get("device") or not interface:
            raise ValueError("No Wi-Fi adapter is available")
        run = self.runner.run
        if action == "wifiScan":
            run("nmcli", "--wait", "15", "device", "wifi", "rescan", "ifname", interface, timeout=18)
            return "Wi-Fi scan completed"
        if action == "wifiDisconnect":
            run("nmcli", "--wait", "15", "device", "disconnect", interface, timeout=18)
            return "Wi-Fi disconnected"
        if action in {"wifiSaved", "wifiForget"}:
            ident = request.get("uuid")
            if not isinstance(ident, str) or not any(n["uuid"] == ident for n in state.get("saved", [])):
                raise ValueError("Saved network is no longer available")
            if action == "wifiForget":
                run("nmcli", "connection", "delete", "uuid", ident)
                return "Saved network removed"
            args = ("connection", "up", "uuid", ident, "ifname", interface)
        else:
            network = next((n for n in state["networks"] if n.get("bssid") == request.get("bssid")), None)
            if not network: raise ValueError("Network is no longer visible; scan again")
            if network.get("enterprise"): raise ValueError("Enterprise Wi-Fi needs a certificate or account. Use Advanced network settings.")
            args = ("device", "wifi", "connect", network["bssid"], "ifname", interface)
        password = request.get("password", "")
        if not isinstance(password, str) or len(password) > 128 or any(c in password for c in "\r\n\x00"):
            raise ValueError("Invalid Wi-Fi password")
        # nmcli's secret agent reads stdin; the password never appears in argv, state or logs.
        run("nmcli", "--wait", "45", "--ask", *args, input=password + "\n", timeout=50)
        return "Wi-Fi connected"

    @staticmethod
    def niri_action(action: dict[str, Any]) -> None:
        path = os.environ.get("NIRI_SOCKET")
        if not path:
            raise CommandError("NIRI_SOCKET is unavailable. Run the shell inside the niri session.")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3.0)
            client.connect(path)
            client.sendall(json.dumps({"Action": action}, separators=(",", ":")).encode() + b"\n")
            with client.makefile("rb") as stream:
                line = stream.readline(1024 * 1024 + 1)
            if len(line) > 1024 * 1024:
                raise CommandError("The niri reply was too large")
            try:
                reply = json.loads(line)
            except (ValueError, UnicodeError) as exc:
                raise CommandError("Invalid niri reply") from exc
            if not isinstance(reply, dict) or "Ok" not in reply:
                raise CommandError(str(reply.get("Err", "The niri action failed")) if isinstance(reply, dict) else "Invalid niri reply")

def emit(backend: DesktopBackend) -> None:
    print(json.dumps(backend.snapshot(), ensure_ascii=False, allow_nan=False, separators=(",", ":")), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Print one read-only state snapshot and exit")
    parser.add_argument("--demo", action="store_true", help="Use sample state; never mutate system or saved preferences")
    parser.add_argument("--settings", action="store_true", help="Preferences and wallpaper only; no desktop probes")
    parser.add_argument("--restore-wallpaper", metavar="FILE", help="Restore with awww, without changing saved preferences")
    parser.add_argument("--restore-displays", action="store_true", help="Restore confirmed modes on currently attached displays")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds (minimum 0.5)")
    args = parser.parse_args(argv)
    if not math.isfinite(args.interval) or args.interval < 0.5:
        parser.error("--interval must be at least 0.5 seconds")
    if args.demo and (args.restore_wallpaper or args.restore_displays):
        parser.error("Wallpaper restoration is disabled in demo mode")
    backend = DesktopBackend(demo=args.demo, settings_only=args.settings or bool(args.restore_wallpaper) or args.restore_displays, weather_fetch=not args.once, manage_idle=not (args.once or args.settings or args.demo or args.restore_wallpaper or args.restore_displays))
    if args.restore_displays:
        saved = backend.preferences.values["displayLayout"]
        if not saved: return 0
        outputs = backend.display_control.outputs()
        original = current_layout(outputs)
        compatible = []
        for item in saved:
            try: compatible.extend(validate_layout([item], outputs))
            except ValueError: continue
        if not compatible: return 0
        try: apply_layout(compatible, backend.runner.run)
        except (CommandError, ValueError, OSError) as error:
            if original: apply_layout(original, backend.runner.run, best_effort=True)
            print("Displays: " + str(error), file=sys.stderr)
            return 1
        return 0
    if args.restore_wallpaper:
        try:
            backend.apply_wallpaper(args.restore_wallpaper, save=False, animate=False)
            return 0
        except (CommandError, ValueError, OSError) as error:
            print(f"Wallpaper: {error}", file=sys.stderr)
            return 1
    if args.once:
        emit(backend)
        return 0
    selector = selectors.DefaultSelector()
    event_process: subprocess.Popen | None = None
    input_buffer = b""
    next_poll = time.monotonic() + args.interval
    event_refresh_due: float | None = None
    def stop_backend(_signal, _frame): raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGTERM, stop_backend)
        emit(backend)
        try:
            selector.register(sys.stdin, selectors.EVENT_READ, "input")
        except PermissionError:
            # epoll does not accept regular files or /dev/null as stdin.
            selector.close()
            selector = selectors.SelectSelector()
            selector.register(sys.stdin, selectors.EVENT_READ, "input")
        if not args.demo and backend.niri["available"]:
            try:
                event_process = subprocess.Popen(
                    [backend.runner.executable("niri"), "msg", "--json", "event-stream"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                )
                if event_process.stdout:
                    selector.register(event_process.stdout, selectors.EVENT_READ, "niri")
            except (OSError, CommandError):
                event_process = None
        while True:
            changed = False
            deadline = min(next_poll, event_refresh_due) if event_refresh_due is not None else next_poll
            if backend.capture.state['status'] == 'pending' or backend.feature_jobs: deadline = min(deadline, time.monotonic() + .2)
            for key, _mask in selector.select(max(0, deadline - time.monotonic())):
                data = os.read(key.fd, 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    if key.data == "input":
                        return 0
                    continue
                if key.data == "niri":
                    if event_refresh_due is None:
                        event_refresh_due = time.monotonic() + 0.1
                    continue
                input_buffer += data
                if len(input_buffer) > 8 * 1024 * 1024:
                    backend.last_result = {"ok": False, "action": "", "message": "Input exceeds 8 MiB limit"}
                    input_buffer = b""
                    changed = True
                while b"\n" in input_buffer:
                    line, input_buffer = input_buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        backend.handle(json.loads(line.decode("utf-8")))
                    except (UnicodeError, json.JSONDecodeError):
                        backend.last_result = {"ok": False, "action": "", "message": "Invalid JSON input"}
                    # Send each result even if several commands arrived together.
                    emit(backend)
                    next_poll = time.monotonic() + args.interval
                    event_refresh_due = None
            now = time.monotonic()
            capture_status = backend.capture.state['status']
            backend.capture.refresh()
            changed = changed or capture_status != backend.capture.state['status']
            if changed or now >= next_poll or any(job.done() for job in backend.feature_jobs.values()) or (event_refresh_due is not None and now >= event_refresh_due):
                emit(backend)
                next_poll = time.monotonic() + args.interval
                event_refresh_due = None
    except (KeyboardInterrupt, BrokenPipeError):
        return 0
    finally:
        backend.idle_control.close()
        backend.night_light.close()
        backend.capture.close()
        backend.weather.close()
        backend.charge_executor.shutdown(wait=False, cancel_futures=True)
        backend.feature_executor.shutdown(wait=False, cancel_futures=True)
        selector.close()
        if event_process and event_process.poll() is None:
            event_process.terminate()
            try:
                event_process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                event_process.kill()
                event_process.wait(timeout=1)


if __name__ == "__main__":
    raise SystemExit(main())
