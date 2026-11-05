"""Niri workspace/window snapshots and the already-running event stream."""
import json

IGNORED = {"KeyboardLayoutsChanged", "KeyboardLayoutSwitched", "OverviewOpenedOrClosed", "ConfigLoaded",
           "ScreenshotCaptured", "CastsChanged", "CastStartedOrChanged", "CastStopped", "TouchpadToggled"}


def read_niri_state(try_run):
    workspaces = try_run("niri", "msg", "--json", "workspaces")
    windows = try_run("niri", "msg", "--json", "windows")
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


class NiriStateCache:
    def __init__(self):
        self.revision = 0
        self.valid = False
        self.streaming = False
        self.workspaces = []
        self.windows = []
        self.buffer = b""

    def connect(self):
        self.streaming = True; self.invalidate()

    def close(self):
        self.streaming = False; self.invalidate()

    def invalidate(self):
        self.valid = False; self.buffer = b""

    def seed(self, state):
        self.workspaces = list(state.get("workspaces") or [])
        self.windows = list(state.get("windows") or [])
        self.valid = state.get("available") is True
        self.revision += 1

    def snapshot(self):
        if not (self.valid and self.streaming): return None
        return {"available": True, "workspaces": self.workspaces, "windows": self.windows}

    def feed(self, data):
        self.buffer += data
        if len(self.buffer) > 8 * 1024 * 1024: self.invalidate(); return
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if line.strip(): self.apply(line)

    def apply(self, line):
        try: event = json.loads(line)
        except (ValueError, UnicodeError): self.invalidate(); return
        if not isinstance(event, dict) or len(event) != 1: self.invalidate(); return
        name, payload = next(iter(event.items()))
        if name in IGNORED: return
        handler = getattr(self, "_" + name, None)
        if handler is None or not isinstance(payload, dict) or not handler(payload): self.invalidate()

    def _sort(self):
        self.workspaces.sort(key=lambda item: (str(item.get("output") or ""), item.get("idx") or 0, item.get("id") or 0))

    def _WorkspacesChanged(self, payload):
        rows = payload.get("workspaces")
        if not isinstance(rows, list) or not all(isinstance(item, dict) for item in rows): return False
        self.workspaces = rows; self._sort(); self.revision += 1; return True

    def _WorkspaceActivated(self, payload):
        ident, focused = payload.get("id"), payload.get("focused")
        if type(ident) is not int or type(focused) is not bool: return False
        target = next((item for item in self.workspaces if item.get("id") == ident), None)
        if target is None: return False
        for item in self.workspaces:
            if item.get("output") == target.get("output"): item["is_active"] = item.get("id") == ident
            if focused: item["is_focused"] = item.get("id") == ident
        self.revision += 1; return True

    def _WorkspaceActiveWindowChanged(self, payload):
        ident, active = payload.get("workspace_id"), payload.get("active_window_id")
        if type(ident) is not int or active is not None and type(active) is not int: return False
        target = next((item for item in self.workspaces if item.get("id") == ident), None)
        if target is None: return False
        target["active_window_id"] = active; self.revision += 1; return True

    def _WorkspaceUrgencyChanged(self, payload):
        ident, urgent = payload.get("id"), payload.get("urgent")
        if type(ident) is not int or type(urgent) is not bool: return False
        target = next((item for item in self.workspaces if item.get("id") == ident), None)
        if target is None: return False
        target["is_urgent"] = urgent; self.revision += 1; return True

    def _WindowsChanged(self, payload):
        rows = payload.get("windows")
        if not isinstance(rows, list) or not all(isinstance(item, dict) for item in rows): return False
        self.windows = rows; self.revision += 1; return True

    def _WindowOpenedOrChanged(self, payload):
        window = payload.get("window")
        if not isinstance(window, dict) or type(window.get("id")) is not int: return False
        ident = window["id"]
        for index, item in enumerate(self.windows):
            if item.get("id") == ident:
                self.windows[index] = window; break
        else:
            self.windows.append(window)
        if window.get("is_focused"): self._focus_window(ident)
        self.revision += 1; return True

    def _focus_window(self, ident):
        for item in self.windows: item["is_focused"] = item.get("id") == ident

    def _WindowClosed(self, payload):
        ident = payload.get("id")
        if type(ident) is not int or not any(item.get("id") == ident for item in self.windows): return False
        self.windows = [item for item in self.windows if item.get("id") != ident]
        self.revision += 1; return True

    def _WindowFocusChanged(self, payload):
        ident = payload.get("id")
        if ident is not None and type(ident) is not int: return False
        self._focus_window(ident); self.revision += 1; return True

    def _WindowFocusTimestampChanged(self, payload):
        ident = payload.get("id")
        if type(ident) is not int: return False
        target = next((item for item in self.windows if item.get("id") == ident), None)
        if target is None: return False
        target["focus_timestamp"] = payload.get("focus_timestamp"); self.revision += 1; return True

    def _WindowUrgencyChanged(self, payload):
        ident, urgent = payload.get("id"), payload.get("urgent")
        if type(ident) is not int or type(urgent) is not bool: return False
        target = next((item for item in self.windows if item.get("id") == ident), None)
        if target is None: return False
        target["is_urgent"] = urgent; self.revision += 1; return True

    def _WindowLayoutsChanged(self, payload):
        changes = payload.get("changes")
        if not isinstance(changes, list): return False
        for change in changes:
            if not isinstance(change, list) or len(change) != 2 or type(change[0]) is not int: return False
            target = next((item for item in self.windows if item.get("id") == change[0]), None)
            if target is None: return False
            target["layout"] = change[1]
        self.revision += 1; return True
