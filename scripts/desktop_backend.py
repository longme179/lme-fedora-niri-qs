#!/usr/bin/env python3
"""LME shell's unprivileged JSON-lines backend (Python standard library only).

Every output line is a complete state snapshot. Input lines are objects such as
{"action":"volume","value":45}. Commands never go through a shell. --demo is
explicitly isolated from the live machine; --once performs read-only sampling.
"""

from __future__ import annotations

import argparse
import configparser
import json
import math
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any


DEFAULT_PREFERENCES = {
    "language": "en", "animations": True, "opacity": 0.90,
    "accent": "#9580ff", "wallpaper": "", "dockAutoHide": True,
    "terminal": "kitty",
}
TOOLS = (
    "niri", "nmcli", "bluetoothctl", "wpctl", "brightnessctl",
    "busctl", "powerprofilesctl", "gio", "swaylock", "systemctl",
    "swww", "nm-connection-editor", "blueman-manager", "pavucontrol",
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

    def available(self, name: str) -> bool:
        return bool(self.commands.get(name))

    def executable(self, name: str) -> str:
        path = self.commands.get(name)
        if not path:
            raise CommandError(f"Required command is unavailable: {name}")
        return path

    def run(self, name: str, *args: str, timeout: float = 3.0) -> str:
        argv = [self.executable(name), *map(str, args)]
        try:
            result = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout,
                check=False, encoding="utf-8", errors="replace",
                env={**os.environ, "LC_ALL": "C"},
            )
        except subprocess.TimeoutExpired as exc:
            raise CommandError(f"{name} timed out") from exc
        except OSError as exc:
            raise CommandError(f"Unable to run {name}: {exc.strerror}") from exc
        if result.returncode:
            detail = (result.stderr.strip() or result.stdout.strip())[:350]
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
    if key in {"animations", "dockAutoHide"} and type(value) is bool:
        return value
    if key == "opacity" and type(value) in {int, float} and math.isfinite(value) and 0.60 <= value <= 1:
        return float(value)
    if key == "accent" and isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value.lower()
    if key == "language" and value == "en":
        return value
    if key == "terminal" and isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.+-]{1,80}", value):
        return value
    if key == "wallpaper" and isinstance(value, str) and (value == "" or (Path(value).is_absolute() and Path(value).is_file())):
        return value
    raise ValueError(f"Invalid preference: {key}")


class Preferences:
    def __init__(self, path: Path | None = None) -> None:
        config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        self.path = path or config / "lme-shell/settings.json"
        self.values = dict(DEFAULT_PREFERENCES)
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                for key, value in saved.items():
                    try:
                        self.values[key] = validate_preference(key, value)
                    except ValueError:
                        pass
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass

    def set(self, key: str, value: Any) -> None:
        value = validate_preference(key, value)
        updated = {**self.values, key: value}
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
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
                 demo: bool = False) -> None:
        self.demo = demo
        self.runner = runner or CommandRunner()
        self.preferences = preferences or Preferences()
        self.applications = apps or Applications()
        self.proc, self.sysfs = proc, sysfs
        self.apps = [] if demo else self.applications.scan()
        self.last_app_scan = time.monotonic()
        self.last_cpu: tuple[int, int] | None = None
        self.system_cache: dict[str, Any] | None = None
        self.last_system_sample = 0.0
        self.power_profile_provider: tuple[str, ...] | None = None
        self.result_sequence = 0
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
                "charging": charging}

    def network(self) -> dict[str, Any]:
        result = {"available": False, "enabled": False, "connected": False, "ssid": "", "strength": None}
        radio = self.try_run("nmcli", "radio", "wifi")
        if radio is None:
            return result
        result.update(available=True, enabled=radio.strip() == "enabled")
        devices = self.try_run("nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "device", "status")
        for line in (devices or "").splitlines():
            fields = split_nmcli(line)
            if len(fields) >= 3 and fields[1] == "connected":
                result["connected"] = True
                if fields[0] == "ethernet":
                    result["ssid"] = "Ethernet"
        wireless = self.try_run("nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL", "device", "wifi", "list", "--rescan", "no")
        for line in (wireless or "").splitlines():
            fields = split_nmcli(line)
            if len(fields) >= 3 and fields[0] == "yes":
                result.update(connected=True, ssid=fields[1])
                try:
                    result["strength"] = max(0, min(100, int(fields[2])))
                except ValueError:
                    pass
                break
        return result

    def bluetooth(self) -> dict[str, Any]:
        output = self.try_run("bluetoothctl", "show")
        if output is None or not re.search(r"^\s*Controller\s", output, re.MULTILINE):
            return {"available": False, "enabled": False}
        return {"available": True, "enabled": bool(re.search(r"Powered:\s+yes", output))}

    def audio(self) -> dict[str, Any]:
        output = self.try_run("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
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
            return {"available": True, "workspaces": workspaces_data, "windows": windows_data}
        except (ValueError, TypeError):
            return {"available": False, "workspaces": [], "windows": []}

    def snapshot(self) -> dict[str, Any]:
        if self.demo:
            return self.demo_snapshot()
        if time.monotonic() - self.last_app_scan > 60:
            self.apps = self.applications.scan()
            self.last_app_scan = time.monotonic()
        self.niri = self.niri_state()
        # Window/focus event bursts must not cause expensive hardware probes.
        if self.system_cache is None or time.monotonic() - self.last_system_sample >= 1.5:
            system = self.cpu_memory()
            system.update(tempC=self.temperature(), battery=self.battery(), network=self.network(),
                          bluetooth=self.bluetooth(), audio=self.audio(), brightness=self.brightness(),
                          powerProfile=self.power_profile())
            self.system_cache = system
            self.last_system_sample = time.monotonic()
        return {"apps": self.apps, "niri": self.niri, "system": self.system_cache,
                "preferences": dict(self.preferences.values), "lastResult": dict(self.last_result)}

    def demo_snapshot(self) -> dict[str, Any]:
        if hasattr(self, "_demo_state"):
            self._demo_state["preferences"] = dict(self.preferences.values)
            self._demo_state["lastResult"] = dict(self.last_result)
            return self._demo_state
        self._demo_state = {
            "apps": [{"id": "org.mozilla.firefox.desktop", "name": "Firefox", "icon": "firefox", "path": "", "terminal": False},
                     {"id": "kitty.desktop", "name": "Kitty", "icon": "kitty", "path": "", "terminal": False},
                     {"id": "org.gnome.Nautilus.desktop", "name": "Files", "icon": "org.gnome.Nautilus", "path": "", "terminal": False}],
            "niri": {"available": True, "workspaces": [
                {"id": i, "idx": i, "name": None, "output": "eDP-1", "is_focused": i == 1, "is_active": i == 1}
                for i in range(1, 5)], "windows": [{"id": 1, "title": "LME Shell — Preview", "app_id": "firefox", "workspace_id": 1, "is_focused": True}]},
            "system": {"cpu": 12.4, "memoryPercent": 34.2, "memoryUsedGiB": 5.47, "memoryTotalGiB": 16,
                       "tempC": 47, "battery": {"available": True, "percent": 82, "charging": False},
                       "network": {"available": True, "enabled": True, "connected": True, "ssid": "Home Wi-Fi", "strength": 88},
                       "bluetooth": {"available": True, "enabled": True}, "audio": {"available": True, "volume": 42, "muted": False},
                       "brightness": {"available": True, "percent": 65}, "powerProfile": "balanced"},
            "preferences": dict(self.preferences.values), "lastResult": dict(self.last_result),
        }
        return self._demo_state

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
        action = request.get("action", "") if isinstance(request, dict) else ""
        try:
            if not isinstance(request, dict) or not isinstance(action, str) or not action:
                raise ValueError("Input must be an object with an action")
            if self.demo:
                self.perform_demo(action, request)
                self.last_result = {"ok": True, "action": action, "message": "Demo preview: no system command executed",
                                    "sequence": self.result_sequence}
                return dict(self.last_result)
            message = self.perform(action, request)
            if action in {"refresh", "volume", "mute", "brightness", "wifiToggle", "bluetoothToggle", "powerProfile"}:
                self.system_cache = None
            self.last_result = {"ok": True, "action": action, "message": message}
        except (CommandError, ValueError, TypeError, KeyError, OSError) as exc:
            self.last_result = {"ok": False, "action": action if isinstance(action, str) else "", "message": str(exc)[:400]}
        self.last_result["sequence"] = self.result_sequence
        return dict(self.last_result)

    def perform_demo(self, action: str, request: dict[str, Any]) -> None:
        state = self.demo_snapshot()
        system = state["system"]
        if action == "setting":
            key = request.get("key")
            if not isinstance(key, str) or key == "wallpaper":
                raise ValueError("Use the wallpaper action to change wallpaper")
            self.preferences.values[key] = validate_preference(key, request.get("value"))
        elif action == "volume":
            system["audio"]["volume"] = self.percentage(request.get("value"))
        elif action == "mute":
            system["audio"]["muted"] = not system["audio"]["muted"]
        elif action == "brightness":
            system["brightness"]["percent"] = self.percentage(request.get("value"), 1)
        elif action == "wifiToggle":
            network = system["network"]
            network["enabled"] = not network["enabled"]
            network["connected"] = network["enabled"]
        elif action == "bluetoothToggle":
            system["bluetooth"]["enabled"] = not system["bluetooth"]["enabled"]
        elif action == "powerProfile":
            value = request.get("value")
            if value not in POWER_PROFILES:
                raise ValueError("Invalid power profile")
            system["powerProfile"] = value
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
        elif action not in {"refresh", "lock", "screenshot", "logout", "suspend", "reboot", "poweroff"}:
            raise ValueError(f"Unknown action: {action}")

    def perform(self, action: str, request: dict[str, Any]) -> str:
        run = self.runner.run
        if action == "refresh":
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
        if action == "brightness":
            value = self.percentage(request.get("value"), 1)
            run("brightnessctl", "--class=backlight", "set", f"{value}%")
            return f"Brightness {value}%"
        if action == "wifiToggle":
            status = run("nmcli", "radio", "wifi")
            run("nmcli", "radio", "wifi", "off" if status.strip() == "enabled" else "on")
            return "Wi-Fi toggled"
        if action == "bluetoothToggle":
            status = run("bluetoothctl", "show")
            if not re.search(r"^\s*Controller\s", status, re.MULTILINE):
                raise CommandError("No Bluetooth adapter is available")
            run("bluetoothctl", "power", "off" if re.search(r"Powered:\s+yes", status) else "on")
            return "Bluetooth toggled"
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
            self.runner.spawn([self.runner.executable("swaylock"), "--color", "22212c"])
            return "Lock requested"
        if action == "screenshot":
            # niri owns capture and clipboard integration. Traditional grim uses
            # wlr-screencopy, which is not the portable screenshot path on niri.
            # Let a just-dismissed control panel finish its surface teardown.
            time.sleep(0.2)
            run("niri", "msg", "action", "screenshot-screen")
            return "Screenshot requested; output follows niri's screenshot-path setting"
        if action == "logout":
            run("niri", "msg", "action", "quit", "--skip-confirmation")
            return "Logout requested"
        if action in {"suspend", "reboot", "poweroff"}:
            run("systemctl", action)
            return f"{action.capitalize()} requested"
        if action == "wallpaper":
            raw = request.get("path")
            if not isinstance(raw, str):
                raise ValueError("A wallpaper file path is required")
            path = Path(raw).expanduser().resolve()
            if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
                raise ValueError("Select an existing PNG, JPEG, WebP, GIF, or BMP wallpaper")
            run("swww", "img", str(path), "--transition-type", "fade" if self.preferences.values["animations"] else "none")
            self.preferences.set("wallpaper", str(path))
            return "Wallpaper updated"
        if action == "setting":
            key = request.get("key")
            if not isinstance(key, str) or key == "wallpaper":
                raise ValueError("Use the wallpaper action to change wallpaper")
            self.preferences.set(key, request.get("value"))
            return "Preferences saved"
        if action == "openSettings":
            target = request.get("target")
            commands = {"network": "nm-connection-editor", "bluetooth": "blueman-manager", "audio": "pavucontrol"}
            if not isinstance(target, str) or target not in commands:
                raise ValueError("Unknown settings panel")
            self.runner.spawn([self.runner.executable(commands[target])])
            return f"Opened {target} settings"
        raise ValueError(f"Unknown action: {action}")

def emit(backend: DesktopBackend) -> None:
    print(json.dumps(backend.snapshot(), ensure_ascii=False, allow_nan=False, separators=(",", ":")), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Print one read-only state snapshot and exit")
    parser.add_argument("--demo", action="store_true", help="Use sample state; never mutate system or saved preferences")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds (minimum 0.5)")
    args = parser.parse_args(argv)
    if not math.isfinite(args.interval) or args.interval < 0.5:
        parser.error("--interval must be at least 0.5 seconds")
    backend = DesktopBackend(demo=args.demo)
    emit(backend)
    if args.once:
        return 0
    selector = selectors.DefaultSelector()
    event_process: subprocess.Popen | None = None
    input_buffer = b""
    next_poll = time.monotonic() + args.interval
    event_refresh_due: float | None = None
    try:
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
                if len(input_buffer) > 65536:
                    backend.last_result = {"ok": False, "action": "", "message": "Input exceeds 64 KiB limit"}
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
            if changed or now >= next_poll or (event_refresh_due is not None and now >= event_refresh_due):
                emit(backend)
                next_poll = time.monotonic() + args.interval
                event_refresh_due = None
    except (KeyboardInterrupt, BrokenPipeError):
        return 0
    finally:
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
