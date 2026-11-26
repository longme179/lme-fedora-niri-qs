#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A stand-in for the stand-in: the scenarios run against a model instead of a desktop.

  run.py --simulate --out DIR --faults s4:swallow@2,s2:ghost@2 -- s4:reps=2 s2:reps=3 s1 s3

The model answers the same probe calls, writes the same log lines (probe marks, frames, state
samples, heartbeat stalls) and accepts the same injector calls, so run.py, scenarios.py and
analyze.py can be exercised where there is no Quickshell, no niri and no /dev/uinput. Its
shell is a handful of dictionaries that a 4 ms thread advances. Faults make it misbehave on
purpose, one fault per symptom: an Escape that is swallowed, a page left half faded, a GUI
thread that freezes for a second. A detector that does not report them is wrong, which is the
point of the exercise. The timings are made up and prove nothing about the real shell.

What the model copies from the product (ShellState.qml, SettingsApplication.qml):
  - Settings is another process with its own window. The shell only starts it, or asks the
    one that lingers (60 s) to show a page; it never sets a flag for it. "Settings is open"
    is a fact of the window list, not of the shell's state.
  - The overlay layer takes the keyboard while any panel flag is set.
  - Escape reaches whichever surface has the keyboard: the island, the overlay, the Settings
    window, or (none of them) a window of the owner.

Faults (`tag:name@n,key=value`; tag = s1 / s2 / s4 / *, n = the n-th occurrence):
  swallow   the island's Escape handler runs, the island stays open
  unhandled the island has the focus, the key reaches nothing that handles it
  nofocus   the overlay does not take the keyboard when the island opens
  late=ms   the island closes, but only after ms
  frozen=ms the GUI thread freezes for ms right after the Escape
  ghost     a burst of page clicks ends with the page faded and its animation "running"
  stall=ms  a tab click freezes the GUI thread for ms
"""
import heapq
import json
import math
import threading
import time
from pathlib import Path

from probe import ProbeError, Tail

TABS = ["dashboard", "devices", "audio", "network", "bluetooth", "display", "power"]
PAGES = ["elements", "appearance", "topbar", "controlLayout", "display", "behavior", "about", "wallpaper",
         "clipboard", "desktop", "idle", "keybinds", "lock", "nightLight", "notifications", "equalizer",
         "utilities", "weather"]
BUILD_MS = {"devices": 1300, "wallpaper": 260, "about": 140}       # every other page: 60
FRAME_MS = 1000.0 / 120.0        # the model renders once per refresh, as a shell without drops would
SETTINGS_BOX = (410, 150, 1100, 780)     # x, y, w, h on the output, as niri would report it
SETTINGS_COLD_MS = 900.0         # process start until the window is mapped
SETTINGS_WARM_MS = 18.0          # reopen through the IPC of the process that lingers
SETTINGS_LINGER_MS = 60000.0     # LME_SETTINGS_LINGER_MS
FIRST_PAGE = "appearance"
FLAGS = ("activity", "control", "clipboard", "overview", "launcher", "notifications", "power")
BINDS = {("super", "a"): "control", ("super", "shift", "a"): "activity", ("super", "v"): "clipboard",
         ("super", "shift", "tab"): "overview", ("super", "space"): "launcher", ("super", "n"): "notifications",
         ("super", "comma"): "settings", ("super", "shift", "e"): "power"}
TOAST = "Wallpaper library refreshed"


def fresh_host(key=""):
    return {"key": key, "shown": key, "enter": 1.0, "leaving": 0.0, "opacity": 1.0, "pending": "", "prewarming": "",
            "queue": 0, "pages": 0, "enterRun": False, "leaveRun": False, "status": 1, "active": bool(key),
            "stuck": False}


class Reply:
    """What inject.py returns for one command; the scenarios only read `first_ms`."""

    def __init__(self, first_ms):
        self.first_ms = first_ms


def parse_faults(faults):
    """`tag:name@n,key=value` — the n-th occurrence of the fault, with parameters.

    The number is everything up to the first character that is not a digit, so both
    `s4:late@5,ms=400` and `s4:late@5 ms=400` name the 5th occurrence."""
    parsed = []
    for text in faults:
        head, _, tail = text.partition("@")
        tag, _, name = head.partition(":")
        digits = ""
        while tail[:1].isdigit():
            digits, tail = digits + tail[0], tail[1:]
        parsed.append({"tag": tag, "name": name, "n": int(digits or 1),
                       "params": dict(part.split("=", 1) for part in tail.replace(",", " ").split() if "=" in part)})
    return parsed


class SimShell:
    def __init__(self, out: Path, faults=()):
        self.out = Path(out)
        (self.out / "probe").mkdir(parents=True, exist_ok=True)
        (self.out / "state" / "log").mkdir(parents=True, exist_ok=True)
        self.paths = {"shell": self.out / "probe/probe.shell.log", "settings": self.out / "probe/probe.settings.log",
                      "shelllog": self.out / "state/log/lme-shell.log", "settingslog": self.out / "state/log/settings.log"}
        self.origin = time.time() * 1000.0        # epoch ms of probe ms 0
        self.mutex = threading.Lock()
        self.tasks, self.order = [], 0
        self.alive = True
        self.freeze = None            # (start, end) of a frozen GUI thread
        self.captured = None          # marks written while a freeze thaws
        self.late = False             # set while the tasks that were due inside a freeze are run
        self.last = {}                # window -> probe ms of its last frame (the refresh grid)
        self.grid = {}                # window -> probe ms of its first frame (the vblank anchor)
        self.closing = {}             # window -> probe ms until which its close animation renders
        self.beats = 0
        self.frames = {"bar": 0, "overlay": 0, "settings": 0}
        self.key_events = 0
        self.faults = parse_faults(faults)
        self.counts = {}
        self.burst = (0, 0)           # (token of the last page click, clicks since the last burst ended)
        self.workspace = 1
        self.pointer = (960.0, 540.0)
        self.toast = ""
        self.nofocus = False
        self.s = {name + "Open": False for name in FLAGS}
        self.s.update({"panelOpen": False, "kind": "control", "island": False, "tab": TABS[0]})
        self.hosts = {"cc": fresh_host(TABS[0]), "settings": fresh_host("")}
        self.built = {"cc": {TABS[0]}, "settings": set()}
        self.building = {"cc": set(), "settings": set()}
        self.settings = {"alive": False, "shown": False, "page": FIRST_PAGE}    # the other process
        self.handles = {name: open(path, "a", buffering=1) for name, path in self.paths.items()}
        self.write("shell", f"@@PROBE sink epoch={self.origin + 5:.0f} clock=5 t0=0 hires=true")
        threading.Thread(target=self.loop, daemon=True).start()

    # ---- faults --------------------------------------------------------------------------------
    def fault(self, tag, name):
        """True when a fault of that kind is due: this is its n-th occurrence."""
        due = False
        for fault in self.faults:
            if fault["name"] == name and fault["tag"] in (tag, "*"):
                key = (fault["tag"], name)
                self.counts[key] = self.counts.get(key, 0) + 1
                due = due or self.counts[key] == fault["n"]
        return due

    def param(self, name, key, default):
        for fault in self.faults:
            if fault["name"] == name and key in fault["params"]:
                return float(fault["params"][key])
        return default

    # ---- clock, tasks, log ------------------------------------------------------------------------
    @staticmethod
    def now():
        return time.time() * 1000.0

    def ms(self):
        return self.now() - self.origin

    def write(self, name, line):
        self.handles[name].write(line + "\n")

    def mark(self, name, text):
        if self.captured is not None and self.freeze is not None:
            self.captured.append(text.split(" ", 1)[0] + f"+{self.now() - self.freeze[0]:.1f}")
        self.write(name, f"@@PROBE m {self.ms():.2f} {text}")

    def frame(self, window, due_ms=0.0):
        """One frame of `window`, on the refresh grid of that window. A compositor swaps at
        vblank: a frame that is late does not land between two refreshes, it waits for the
        next one, so the gaps stay multiples of the refresh even when the Python thread that
        runs the model jitters. The task that writes the line may run a few ms late (the loop
        wakes every 4 ms); the frame itself was rendered at its due slot, so the time written
        is the slot, never `now`. Frames due while the GUI thread was frozen are presented
        when it came back — one per window per thaw: the compositor shows the newest frame,
        the skipped ones were never presented."""
        if self.late:
            if window in self.thawed:
                return                      # this window already presented its catch-up frame
            self.thawed.add(window)
            at = self.now()
        else:
            # The frame is presented at its due slot of the window's vblank grid — never at
            # `now`: the Python thread that runs the model delivers tasks with milliseconds
            # of jitter, and that jitter is not time of the modelled shell.
            anchor = self.grid.setdefault(window, due_ms)
            steps = max(1, math.ceil((due_ms - anchor) / FRAME_MS))
            at = anchor + steps * FRAME_MS
            last = self.last.get(window)
            if last is not None and at <= last:      # never two frames in one slot
                at = last + FRAME_MS                                 # the next vblank after it
        self.last[window] = at
        self.frames[window] += 1
        self.write("settings" if window == "settings" else "shell", f"@@PROBE F {at - self.origin:.2f} {window}")

    def render_frames(self, window, count):
        """Start the render loop of `window`: one frame per refresh while it is on screen,
        beginning with `count` frames of this animation. One scheduler per window — the
        bursts of open/close/page-show only make sure the loop is running, they never run
        their own frame tasks next to it (two writers on one vblank grid is what makes
        gaps that no compositor produces). The loop continues on the window's grid from
        its last frame, so a panel swap (close mark, then open mark) leaves no hole."""
        last = self.last.get(window)
        # Continue the window's grid when the last frame is at most a couple of refreshes
        # away (a panel swap: close mark, then open mark, no hole between them); after a
        # longer idle the window was hidden, so the animation starts at the next vblank.
        floor = self.now() - 2 * FRAME_MS
        due = max(last + FRAME_MS, floor) if last is not None else self.now()
        slot = self.grid.get(window)
        if slot is not None and last is not None:
            # Snap to the grid slot at or after `due`: continuing on anchor + k*refresh.
            step = math.ceil((due - slot) / FRAME_MS)
            due = slot + step * FRAME_MS
        self.at(max(0.0, due - self.now()), self.render_while_shown, window, due, count)

    def render_while_shown(self, window, due_ms, burst=0):
        """The render loop of an open window: one frame per refresh until it is hidden.

        `due_ms` is the grid slot of THIS frame (render_frames snaps it to the window's
        vblank anchor); the next slot is anchor + (k+1) * refresh with the integer step
        taken from the grid — a chain of float additions drifts a fraction of a millisecond
        per frame until ceil() reads it as a whole skipped refresh."""
        anchor = self.grid.setdefault(window, due_ms)
        self.frame(window, due_ms)
        step = math.floor((due_ms - anchor) / FRAME_MS + 1e-6) + 1
        nxt = anchor + step * FRAME_MS
        if burst > 1:
            self.at(max(0.0, nxt - self.now()), self.render_while_shown, window, nxt, burst - 1)
            return
        if not self.window_shown(window):
            return
        self.at(max(0.0, nxt - self.now()), self.render_while_shown, window, nxt)

    def window_shown(self, window):
        """Whether `window` has anything on screen. A closing panel still animates out for
        a few frames (the recede cue); the render loop must not stop at the flag itself or
        the last frames of every close leave a hole in the frame series."""
        if window == "settings":
            return self.settings["shown"] or self.now() < self.closing.get("settings", 0)
        if window == "bar":
            return True
        return self.s["panelOpen"] or self.s["island"] or self.now() < self.closing.get("overlay", 0)

    def at(self, delay_ms, function, *args):
        with self.mutex:
            self.order += 1
            heapq.heappush(self.tasks, (self.now() + delay_ms, self.order, function, args))

    def run_due(self, now):
        while True:
            with self.mutex:
                if not self.tasks or self.tasks[0][0] > now:
                    return
                _, _, function, args = heapq.heappop(self.tasks)
            function(*args)

    def freeze_for(self, ms):
        """The GUI thread takes nothing for `ms`; whatever was due inside runs at the thaw and is
        reported as one heartbeat stall, as the real Heartbeat does."""
        start = self.now()
        end = start + ms
        if self.freeze:
            self.freeze = (self.freeze[0], max(self.freeze[1], end))
        else:
            self.freeze = (start, end)
        self.at(ms + 1, self.thaw)

    def thaw(self):
        freeze = self.freeze
        if not freeze or freeze[1] > self.now():
            return          # no freeze, or the task of a freeze that was merged into this one
        start, end = freeze
        self.freeze = None  # cleared first: whatever freezes inside the catch-up is a new freeze
        captured = []
        self.captured = captured
        self.thawed = set()
        self.late = True
        self.run_due(end)
        self.late = False
        self.captured = None
        self.beats += 1
        self.write("shelllog", f"@@HEARTBEAT stall late={end - start - 4:.1f} at={end:.0f} beats={self.beats} "
                               f"marks={';'.join(captured) or '-'}")

    def loop(self):
        next_sample = self.now()
        while self.alive:
            time.sleep(0.004)
            now = self.now()
            if self.freeze and self.freeze[1] > now:
                continue
            self.run_due(now)
            if now >= next_sample:
                self.sample()
                next_sample = now + 40

    # ---- what the probe answers ------------------------------------------------------------------
    def state(self, proc):
        if proc == "settings":
            if not self.settings["alive"]:
                raise ProbeError("sim: Settings is not running (rc=1)")
            x, y, w, h = SETTINGS_BOX
            over = self.settings["shown"] and x <= self.pointer[0] <= x + w and y <= self.pointer[1] <= y + h
            return {"ms": round(self.ms(), 2), "proc": "settings", "stage": "boot", "frames": self.frames["settings"],
                    "keyEvents": self.key_events, "beats": self.beats, "status": self.toast,
                    "hosts": {"settings": dict(self.hosts["settings"])},
                    "settings": {"page": self.settings["page"], "search": "", "toast": bool(self.toast),
                                 "toastText": self.toast, "pages": list(PAGES)},
                    "window": [self.settings["shown"], w, h],
                    "pointer": [self.pointer[0] - x, self.pointer[1] - y, over]}
        return {"ms": round(self.ms(), 2), "proc": "shell", "stage": "boot", "panelOpen": self.s["panelOpen"],
                "activityOpen": self.s["activityOpen"], "controlOpen": self.s["controlOpen"], "settingsOpen": False,
                "locked": False, "auth": False, "kind": self.s["kind"], "status": "",
                "frames": self.frames["bar"], "keyEvents": self.key_events, "beats": self.beats,
                "focus": "overlay" if self.s["panelOpen"] else "-",
                "hosts": {"cc": dict(self.hosts["cc"], active=self.s["controlOpen"])},
                "cc": {"tab": self.s["tab"], "tabs": list(TABS), "editing": False},
                "island": {"shown": self.s["island"], "mounted": True, "dormant": not self.s["island"],
                           "warmup": False, "moving": self.hosts["cc"]["enterRun"]},
                "pointer": [self.pointer[0], self.pointer[1], self.pointer[1] <= 28]}

    def rect(self, name):
        """Centre of the named item, relative to its window (as the real probe reports)."""
        if name == "perfActivity":
            item = {"x": 330.0, "y": 14.0, "shown": not self.s["activityOpen"], "win": "bar", "w": 160, "h": 30}
        elif name.startswith("perfTab_") and name[len("perfTab_"):] in TABS:
            item = {"x": 290.0 + 120 * TABS.index(name[len("perfTab_"):]), "y": 64.0, "shown": self.s["controlOpen"],
                    "win": "overlay", "w": 160, "h": 30}
        elif name.startswith("perfNav_") and name[len("perfNav_"):] in PAGES:
            item = {"x": 190.0, "y": 95.0 + 36 * PAGES.index(name[len("perfNav_"):]), "shown": self.settings["shown"],
                    "win": "settings", "w": 160, "h": 30}
        elif name == "perfCloseSettings":
            item = {"x": 1062.0, "y": 28.0, "shown": self.settings["shown"], "win": "settings", "w": 28, "h": 28}
        else:
            return {"item": name, "found": False}
        item.update(item=name, found=True)
        return item

    def hit(self, x, y):
        names = ["perfActivity", "perfCloseSettings"] + [f"perfTab_{tab}" for tab in TABS] + [f"perfNav_{key}" for key in PAGES]
        for name in names:
            item = self.rect(name)
            if not item.get("shown"):
                continue
            ix, iy = item["x"], item["y"]
            if item["win"] == "settings":
                ix, iy = SETTINGS_BOX[0] + ix, SETTINGS_BOX[1] + iy
            if abs(ix - x) <= item["w"] / 2 and abs(iy - y) <= item["h"] / 2:
                return name
        return None

    def keyboard_exclusive(self):
        return self.s["panelOpen"] and not self.nofocus

    def settings_origin(self):
        """niri's window list: the Settings window is there while it is shown."""
        if not self.settings["shown"]:
            return {"found": False, "windows": 0}
        x, y, w, h = SETTINGS_BOX
        return {"found": True, "id": 7, "focused": not self.s["panelOpen"], "floating": True, "others": 0,
                "x": x, "y": y, "w": w, "h": h}

    def focused_workspace(self):
        return {"id": self.workspace, "idx": self.workspace}

    def ipc(self, function, args):
        if function == "toggle":
            self.toggle(args[0])
        elif function == "close":
            self.close_panels()

    # ---- input ------------------------------------------------------------------------------------
    def key(self, keys):
        self.key_events += 1
        keys = tuple(keys)
        if keys in BINDS:
            self.at(28, self.toggle, BINDS[keys])        # niri spawns the ipc client, the shell answers
        elif keys == ("esc",):
            self.at(4, self.escape)
        elif len(keys) == 2 and keys[0] == "super" and keys[1].isdigit():
            self.at(20, setattr, self, "workspace", int(keys[1]))

    def click(self, x, y):
        item = self.hit(x, y)
        if item == "perfActivity":
            self.mark("shell", "activityButton.click")
            self.at(2, self.toggle, "activity")
        elif item == "perfCloseSettings":
            self.at(2, self.settings_hide)
        elif item and item.startswith("perfTab_"):
            self.at(6, self.select_tab, item[len("perfTab_"):])
        elif item and item.startswith("perfNav_"):
            self.burst = (self.burst[0] + 1, self.burst[1] + 1)
            self.at(6, self.navigate, item[len("perfNav_"):])
            self.at(150, self.end_of_burst, self.burst[0])

    # ---- panels -----------------------------------------------------------------------------------
    def toggle(self, name):
        """ShellState.togglePanel(): every other panel closes first (closePanels), then this one opens."""
        low = str(self.s["panelOpen"]).lower()
        self.mark("shell", f"togglePanel {name} panelOpen={low} kind={self.s['kind']} "
                           f"activity={str(self.s['activityOpen']).lower()}")
        if name == "settings":
            self.mark("shell", "openSettingsPage appearance")
            self.close_panels()
            cold = not self.settings["alive"]
            self.at(SETTINGS_COLD_MS if cold else SETTINGS_WARM_MS, self.settings_show)
            return
        was_open = self.s[name + "Open"]
        self.close_panels()
        if name != "activity":                # the island does not change the panel kind
            self.s["kind"] = name
        self.s[name + "Open"] = not was_open
        if was_open:
            return
        self.s["panelOpen"] = True
        self.mark("shell", f"shell.panelOpen state=true activity={str(self.s['activityOpen']).lower()} "
                           f"kind={self.s['kind']} stage=retained")
        self.at(1, self.opened, name)

    def close_panels(self):
        """ShellState.closePanels(): every flag down, the island hidden."""
        self.mark("shell", "closePanels " + ("open" if self.s["panelOpen"] else "idle"))
        was_open = self.s["panelOpen"]
        for flag in FLAGS:
            self.s[flag + "Open"] = False
        self.s["panelOpen"] = False
        if self.s["island"]:
            self.s["island"] = False
            self.mark("shell", "island.shown false")
        if was_open:
            self.mark("shell", f"shell.panelOpen state=false activity=false kind={self.s['kind']} stage=retained")
            self.closing["overlay"] = self.now() + 3 * FRAME_MS    # the recede animation
            self.render_frames("overlay", 3)

    def close_later(self, delay):
        self.at(delay, self.close_panels)

    def opened(self, name):
        if name == "activity":
            self.nofocus = self.fault("s4", "nofocus")
            self.s["island"] = True
            self.mark("shell", "island.shown true")
        self.render_frames("overlay", 6)

    def escape(self):
        """Escape reaches whichever surface has the keyboard."""
        if self.s["activityOpen"] and self.nofocus:
            # The island is open, the keyboard is not on it: the key goes to a window of the owner.
            self.write("shelllog", "sim: the Escape went to a window of the owner")
        elif self.s["activityOpen"]:
            if self.fault("s4", "frozen"):
                self.freeze_for(self.param("frozen", "ms", 1800))
            if self.fault("s4", "unhandled"):
                self.mark("shell", "key unhandled.overlay code=16777216 mod=0 ts=1")
                return
            self.mark("shell", "key esc.island")
            if self.fault("s4", "swallow"):
                return                  # ActivityIsland: the handler ran, closePanels was not reached
            self.close_later(self.param("late", "ms", 250) if self.fault("s4", "late") else 1)
        elif self.s["panelOpen"]:
            self.mark("shell", f"key esc.{self.s['kind']}")
            self.close_later(1)
        elif self.settings["shown"]:
            self.mark("settings", "key esc.settingsShortcut search=0")     # SettingsView: Shortcut "Escape"
            self.at(1, self.settings_hide)
        else:
            self.write("shelllog", "sim: the Escape went to a window of the owner")

    # ---- the Settings process ---------------------------------------------------------------------
    def settings_show(self):
        """The window is mapped: a cold process builds its first page, a lingering one navigates."""
        settings = self.settings
        if not settings["alive"]:
            settings["alive"] = True
            settings["page"] = FIRST_PAGE
            self.hosts["settings"] = fresh_host("")
            self.built["settings"] = set()
            self.building["settings"] = set()
            self.write("settings", f"@@PROBE sink epoch={self.origin + self.ms():.0f} clock={self.ms():.0f} t0=0 hires=true")
            self.show_page("settings", FIRST_PAGE)
            self.mark("settings", "settings.ready")
        else:
            self.navigate(FIRST_PAGE)                       # IpcHandler settings.openPage
            self.mark("settings", "settings.open " + FIRST_PAGE)
        settings["shown"] = True
        self.render_frames("settings", 6)

    def settings_hide(self):
        """SettingsApplication.close(): hidden, not quit; the linger starts."""
        self.mark("settings", "settings.close")
        self.settings["shown"] = False
        self.closing["settings"] = self.now() + 3 * FRAME_MS       # the window fades out
        self.render_frames("settings", 3)
        self.at(SETTINGS_LINGER_MS, self.settings_quit)

    def settings_quit(self):
        self.settings["alive"] = False

    # ---- pages -------------------------------------------------------------------------------------
    def enter(self, host, duration):
        """The enter transition: opacity from 0.35 to 1 while enterRun is set. A new show()
        cancels the one before it (PageHost.stopAll): an old step firing into the new
        transition would fake `enterRun=false` on a page that never settled."""
        state = self.hosts[host]
        state.update(enter=0.0, leaving=0.0, opacity=0.35, enterRun=True, leaveRun=False, stuck=False)
        generation = state.get("generation", 0) + 1
        state["generation"] = generation

        def step(part, my=generation):
            if state["generation"] != my or state["stuck"]:
                return          # superseded by a newer show(), or the transition stopped half way
            state["enter"] = part
            state["opacity"] = round(0.35 + 0.65 * part, 3)
            state["enterRun"] = part < 1.0
        for part in (0.33, 0.66, 1.0):
            self.at(duration * part, step, part, generation)

    def show_page(self, host_name, key):
        """Marks of a PageHost showing `key`, in the order the real one makes them. A slow build
        freezes the GUI thread: the marks of the finished page only exist once it thaws. A page
        that is already building is not built again (PageHost `pending`): a burst of clicks on
        it waits for the one build, it does not queue a freeze per click."""
        process = "settings" if host_name == "settings" else "shell"
        host = self.hosts[host_name]
        self.mark(process, f"host.show {host_name} {key} pending=- prewarm=-")
        if host["shown"] == key and key in self.built[host_name]:
            return                                       # PageHost.show(): that page is already shown
        if key not in self.built[host_name] and key not in self.building[host_name]:
            build = BUILD_MS.get(key, 60)
            if build > 500:
                self.building[host_name].add(key)
                self.freeze_for(build)
                self.at(build + 1, self.finish_build, host_name, key, build)
                return
            self.build_page(host_name, key, build)
        self.present_page(host_name, key)

    def build_page(self, host_name, key, build):
        process = "settings" if host_name == "settings" else "shell"
        self.built[host_name].add(key)
        self.building[host_name].discard(key)
        self.mark(process, f"host.build {host_name} {key} {build - 1.5:.2f}ms")
        self.mark(process, f"host.status {host_name} {key} 1")
        self.mark(process, f"host.loaded {host_name} {key}")

    def finish_build(self, host_name, key, build):
        self.build_page(host_name, key, build)
        self.present_page(host_name, key)

    def present_page(self, host_name, key):
        process = "settings" if host_name == "settings" else "shell"
        host = self.hosts[host_name]
        self.mark(process, f"host.present {host_name} {key} from={host['shown']}")
        host.update(key=key, shown=key, status=1)
        self.enter(host_name, 250)
        self.render_frames(process if process == "settings" else "overlay", 4)

    def select_tab(self, tab):
        self.mark("shell", f"cc.select {tab}")
        self.mark("shell", f"cc.tab {tab}")
        self.s["tab"] = tab
        if self.fault("s1", "stall"):
            self.freeze_for(self.param("stall", "ms", 400))
        self.show_page("cc", tab)

    def navigate(self, key):
        self.mark("settings", f"settings.navigate {self.settings['page']}>{key} pending=- prewarm=-")
        self.settings["page"] = key
        self.show_page("settings", key)
        if key == "wallpaper":
            self.at(900, self.scan)

    def scan(self):
        self.mark("settings", "accept 3.21ms bytes=4100")
        self.toast = TOAST
        self.at(4500, setattr, self, "toast", "")

    def end_of_burst(self, token):
        """No further page click followed: the burst is over. This is where a page can get stuck:
        mid-transition, faded, with the recede cue held (the S2 fault)."""
        if token != self.burst[0]:
            return          # a later click came: the burst is still going
        clicks, self.burst = self.burst[1], (self.burst[0], 0)
        if clicks >= 2 and self.fault("s2", "ghost"):
            self.hosts["settings"].update(opacity=0.45, leaving=1.0, leaveRun=True, enterRun=False, stuck=True)

    def sample(self):
        for proc in ("shell", "settings"):
            if proc == "settings" and not self.settings["alive"]:
                continue
            payload = json.dumps(self.state(proc), separators=(",", ":"))
            self.write(proc, f"@@PROBE S {self.ms():.1f} {payload}")


class FakeInjector:
    """The injector protocol as far as scenarios.py uses it, driving the model instead of uinput.

    The real injector costs ~8 ms per command (the uinput write, the wait for the reply); the
    model answers in microseconds, which turns every time-boxed burst into one machine-gun
    instant. Each command here takes a comparable moment, so a 3 s "as fast as possible" burst
    is a few hundred clicks in the model too."""

    COST_MS = 6.0

    def __init__(self, sim: SimShell):
        self.sim = sim
        self.log = open(sim.out / "inject.log", "a", buffering=1)

    def _spend(self):
        time.sleep(self.COST_MS / 1000.0)
        return SimShell.now()

    def tap(self, *keys, hold=None):
        self.log.write(f"{time.time_ns()} tap {' '.join(keys)}\n")
        at = self._spend()
        self.sim.key(keys)
        return Reply(at)

    def move(self, x, y):
        self.sim.pointer = (float(x), float(y))
        return Reply(self._spend())

    def click_at(self, x, y):
        self.log.write(f"{time.time_ns()} click {x:g} {y:g}\n")
        at = self._spend()
        self.sim.pointer = (float(x), float(y))
        self.sim.click(float(x), float(y))
        return Reply(at)

    def send(self, *commands):
        """`move x y` and `click left` in pairs, as scenarios.py writes them for a burst."""
        replies = []
        words = [command.split() for command in commands]
        for index, parts in enumerate(words):
            if parts[0] == "move":
                replies.append(self.move(parts[1], parts[2]))
            elif parts[0] == "click" and index and words[index - 1][0] == "move":
                replies.append(self.click_at(words[index - 1][1], words[index - 1][2]))
            else:
                replies.append(Reply(self._spend()))
        return replies

    def note(self, text):
        self.log.write(f"{time.time_ns()} @ {text}\n")


class FakeProbe:
    """The probe API of probe.py, answered by the model; the logs are read with the real Tail."""

    def __init__(self, sim: SimShell):
        self.sim = sim
        self.expect_settings = False
        self.tails = {}

    def state(self, proc="shell"):
        return self.sim.state(proc)

    def ping(self):
        return 0.8

    def rect(self, name, backend=None):
        return self.sim.rect(name)

    def watch(self, on):
        pass

    def shell(self, function, *args):
        self.sim.ipc(function, args)

    def drain(self, name="shell"):
        if name not in self.tails:
            self.tails[name] = Tail(self.sim.paths[name], name in ("shell", "settings"))
        return self.tails[name].read()

    def keyboard_exclusive(self):
        return self.sim.keyboard_exclusive()

    def settings_origin(self):
        return self.sim.settings_origin()

    def focused_workspace(self):
        return self.sim.focused_workspace()


def build(out: Path, faults=()):
    sim = SimShell(out, faults)
    return sim, FakeInjector(sim), FakeProbe(sim)
