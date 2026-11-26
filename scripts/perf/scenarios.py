#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The symptom scenarios: real input, the probe's own timeline, one functional assertion per number.

  s4  island      open by each route (keybind, bar click, IPC toggle), Escape after varied
                  delays, with and without CPU load, right after other panels
  s2  Settings    every page in turn, rapid A-B-A-B, switching while the wallpaper toast is up;
                  the page host's state machine is asserted after every burst
  s1  Control Center   every tab in order, random, as fast as possible, during the first prewarm
  s3  mixed       panels, workspaces and Settings back to back, like a working session

Every repetition ends in one record: the latencies on the probe's clock (input -> mark -> first
frame), the state the shell was in afterwards, and whether that state is what the user asked
for. run.py collects the records, analyze.py turns them into medians and failure rates.
Nothing here uses the IPC to switch a tab or a page. The IPC opens a top-level panel (one S4
route, and recovery), and reads state and geometry; keys go through niri's own binds, clicks
are pointer events on the rectangles of the real items.

Escape is only ever pressed while a panel of the shell holds the keyboard (or the Settings
window is focused), and each press is followed by its assertion. What Escape does not close
is closed again the way a user would, then through the product's own `shell close`; both are
recorded, and a panel that survives both ends the session (Stuck).
"""
import argparse
import bisect
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import idlegate  # noqa: E402  (sibling module of the harness)
from probe import ProbeError  # noqa: E402

SHORT_LOG = idlegate.DEFAULT_DIR / "short.log"
TAILS = ("shell", "settings", "shelllog", "settingslog")
ESC_BUDGET_MS = 100.0      # a panel must be gone this long after the Escape key-down
LATE_MS = 1000.0           # closed, but later than that: a stall, not a dropped key
CLOSE_WAIT_MS = 1500.0     # how long a miss is observed before recovery starts
OPEN_WAIT_MS = 8000.0
SETTLE_WAIT_MS = 10000.0
TOAST_TEXT = "Wallpaper library refreshed"

# name -> the niri bind that opens it (config/niri/lme-shell.kdl). Super+L (lock) is never here.
PANELS = {
    "activity": ("super", "shift", "a"),
    "clipboard": ("super", "v"),
    "overview": ("super", "shift", "tab"),
    "launcher": ("super", "space"),
    "control": ("super", "a"),
    "notifications": ("super", "n"),
    "settings": ("super", "comma"),
    "power": ("super", "shift", "e"),
}
S3_SCRIPT = ("control activity clipboard overview launcher notifications power settings activity "
             "control launcher notifications power overview clipboard settings activity").split()


class OwnerIsBack(Exception):
    """Input of the owner showed up: stop at once, run.py restores the deployed shell."""


class Stuck(RuntimeError):
    """A panel survived Escape and the product's own close: no further rep can be trusted."""


class Skip(RuntimeError):
    """The scenario cannot run in this session (nothing to click, a page is missing). Not a failure."""


# ---- reading the timeline -------------------------------------------------------------------------

def mark(*prefixes):
    """A probe mark whose text starts with one of `prefixes`."""
    prefixes = tuple(prefixes)
    return lambda event: event.kind == "m" and event.text.startswith(prefixes)


def frame(*windows):
    """A frame of one of the windows (bar, overlay, settings)."""
    return lambda event: event.kind == "F" and event.text.rsplit(" ", 1)[-1] in windows


def sample(proc, test=lambda data: True):
    return lambda event: event.kind == "S" and event.data.get("proc") == proc and test(event.data)


def host_of(data, name):
    return (data.get("hosts") or {}).get(name) or {}


def host_settled(name, key=None):
    """The named PageHost shows `key` (any page when None), is built, fully opaque, and no
    transition is running: the state the user expects to see after the click."""
    def test(data):
        host = host_of(data, name)
        return bool(host.get("shown")) and (key is None or host.get("shown") == key) \
            and host.get("status") == 1 and host.get("opacity", 0) >= 0.999 \
            and not host.get("leaving") and not host.get("enterRun") and not host.get("leaveRun") \
            and not host.get("pending")
    return test


def is_open(name):
    def test(data):
        if data.get(name + "Open"):
            return True
        return bool(data.get("panelOpen")) and data.get("kind") == name
    return sample("shell", test)


def any_open(data):
    return bool(data.get("panelOpen") or data.get("activityOpen") or data.get("controlOpen")
                or data.get("settingsOpen"))


NONE_OPEN = sample("shell", lambda data: not any_open(data))
SHELL_SAMPLE = sample("shell")
SETTINGS_SHOWN = mark("settings.ready", "settings.open")   # the Settings process mapped its window
SETTINGS_HIDDEN = mark("settings.close")                   # ... and hid it again


class Timeline:
    """Every line the probe and the heartbeat wrote, in epoch ms, read as it arrives."""

    def __init__(self, probe):
        self.probe = probe
        self.times, self.events = [], []

    def pump(self):
        for name in TAILS:
            for event in self.probe.drain(name):
                at = bisect.bisect_left(self.times, event.epoch)
                self.times.insert(at, event.epoch)
                self.events.insert(at, event)
        return self.events

    def after(self, t_ms, kinds=None):
        at = bisect.bisect_left(self.times, t_ms)
        return [event for event in self.events[at:] if kinds is None or event.kind in kinds]

    def first(self, t_ms, test):
        """The first event at or after t_ms that passes `test`, reading what arrived since.

        `wait` pumps while it polls; a bare `first` after a sleep would otherwise search a
        timeline that stopped at the last pump and miss a mark that is hours old in the log."""
        self.pump()
        for event in self.after(t_ms):
            if test(event):
                return event
        return None

    def wait(self, test, t_from, timeout_ms, poll_ms=3.0):
        """The first event at or after t_from that passes `test`, but never one later than
        t_from + timeout_ms — an event that shows up after the deadline belongs to a later
        interaction, not to this one (a blocked caller would otherwise read a frame of the
        next cycle as the answer to this one)."""
        end = t_from + timeout_ms
        deadline = time.monotonic() + timeout_ms / 1000.0
        while True:
            hit = self.first(t_from, test)
            if hit is not None:
                return hit if hit.epoch <= end else None
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            time.sleep(min(poll_ms / 1000.0, left))
            self.pump()


class Load:
    """Background CPU load, the way a build or an index job loads the machine: one spinner per
    requested core, each in its own transient user unit, so nothing outlives the run."""

    def __init__(self):
        self.units = []

    def __len__(self):
        return len(self.units)

    def start(self, count, max_seconds=1800):
        self.stop()
        for index in range(count):
            unit = f"lme-perf-load-{os.getpid()}-{index}"
            done = subprocess.run(["systemd-run", "--user", f"--unit={unit}", "--collect", "--quiet",
                                   f"--property=RuntimeMaxSec={int(max_seconds)}",
                                   "--", "python3", "-S", "-c", "while True: pass"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            if done.returncode == 0:
                self.units.append(unit)
        return len(self.units)

    def stop(self):
        if self.units:
            subprocess.run(["systemctl", "--user", "stop", *self.units], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=60)
            self.units = []


class Ctx:
    """What a scenario has: the injector, the probe, the timeline they fill, and the safety rules."""

    def __init__(self, inj, probe, deadline_ms=None, width=1920, height=1080):
        self.inj, self.probe = inj, probe
        self.timeline = Timeline(probe)
        self.records, self.problems, self.meta = [], [], {}
        self.injections = []        # epoch seconds of every input this harness wrote
        self.deadline_ms = deadline_ms
        self.width, self.height = width, height
        self.load = Load()
        self.box = None             # top-left of the Settings window on the output
        self.box_size = (0, 0)

    @staticmethod
    def now():
        return time.time() * 1000.0

    def time_left_ms(self):
        return None if self.deadline_ms is None else self.deadline_ms - self.now()

    def out_of_time(self):
        """True when less than 45 s remain: the session is ended before the dead-man timer fires."""
        return self.time_left_ms() is not None and self.time_left_ms() < 45000

    # ---- input -----------------------------------------------------------------------------
    def shot(self, reply):
        """Record the moment of an input of ours: every RESUME the idle watcher reports after one
        of these is ours, any other is the owner's."""
        at = reply.first_ms
        self.injections.append(at / 1000.0)
        return at

    def note(self, text):
        """A line in the injector log: what is about to happen, in replay order."""
        self.inj.note(text)

    def tap(self, *keys, hold=None):
        return self.shot(self.inj.tap(*keys, hold=hold))

    def move(self, x, y):
        return self.shot(self.inj.move(x, y))

    def click_at(self, x, y):
        return self.shot(self.inj.click_at(x, y))

    def sleep(self, ms):
        if ms > 0:
            time.sleep(ms / 1000.0)

    def park(self):
        try:
            self.move(self.width / 2, self.height / 2)
        except Exception:  # noqa: BLE001  (parking the pointer is courtesy, never a reason to fail)
            pass

    def guard(self, since_ms):
        """Input of the owner since `since_ms` that nothing of ours explains ends the session."""
        keep = since_ms / 1000.0 - 1.0
        self.injections = [shot for shot in self.injections if shot >= keep]
        foreign = idlegate.foreign_resume(SHORT_LOG, since_ms / 1000.0, self.injections)
        if foreign:
            raise OwnerIsBack(f"input of the owner at {foreign:.3f}")

    # ---- state -------------------------------------------------------------------------------
    def ask(self, proc="shell"):
        """State of one process, or None when its GUI thread did not answer in time."""
        try:
            return self.probe.state(proc)
        except ProbeError as error:
            self.problems.append({"t": round(self.now(), 3), "probe": proc, "error": str(error)[:240]})
            return None

    def ping(self):
        try:
            return round(self.probe.ping(), 2)
        except ProbeError as error:
            self.problems.append({"t": round(self.now(), 3), "probe": "ping", "error": str(error)[:240]})
            return None

    def first_frame(self, t_ms, windows=("overlay", "bar")):
        hit = self.timeline.first(t_ms, frame(*windows))
        return hit.epoch if hit else None

    def stalls(self, t_from, t_to):
        """Heartbeat stalls: [ms the GUI thread was unavailable, marks that ran inside it]."""
        found = []
        for event in self.timeline.after(t_from - 1.0, {"stall"}):
            if event.epoch <= t_to + 5.0:
                found.append([round(event.data["late"], 1), event.data.get("marks", "")[:300]])
        return found

    def holds_keyboard(self):
        """Whether the overlay layer holds the keyboard: an Escape can only reach the shell then."""
        try:
            return self.probe.keyboard_exclusive()
        except ProbeError as error:
            self.problems.append({"t": round(self.now(), 3), "probe": "layers", "error": str(error)[:240]})
            return None

    def recover(self, why, escape=True):
        """Close what Escape did not close: Escape again, then the product's own close."""
        self.timeline.pump()
        how = None
        if escape:
            at = self.tap("esc")
            if self.timeline.wait(NONE_OPEN, at - 1.0, CLOSE_WAIT_MS):
                how = "second_escape"
        if how is None:
            self.probe.shell("close")
            how = "ipc_close"
            if not self.timeline.wait(NONE_OPEN, self.now() - 1500.0, 3000):
                raise Stuck(f"{why}: neither Escape nor `shell close` closes the panel")
        self.problems.append({"t": round(self.now(), 3), "recover": why, "how": how})
        return how

    def settings_window(self):
        """niri's view of the Settings window ({found, focused, x, y, ...}), None when niri does not answer."""
        try:
            return self.probe.settings_origin()
        except ProbeError as error:
            self.problems.append({"t": round(self.now(), 3), "probe": "windows", "error": str(error)[:240]})
            return None

    def wait_settings(self, listed, t_from, timeout_ms, step_ms=60.0):
        """Epoch ms at which niri first reported the Settings window as listed (or gone) after
        t_from; None at the end of the timeout. An observation has the granularity of step_ms."""
        deadline = time.monotonic() + timeout_ms / 1000.0
        while True:
            if self.now() >= t_from:
                info = self.settings_window()
                if info is not None and bool(info.get("found")) is listed:
                    return self.now()
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            time.sleep(min(step_ms / 1000.0, left))

    def settings_point(self, name):
        """Output coordinates of the centre of an item of the Settings window, or None."""
        if not self.box:
            return None
        try:
            rect = self.probe.rect(name)
        except ProbeError as error:
            self.problems.append({"t": round(self.now(), 3), "probe": f"rect {name}", "error": str(error)[:240]})
            return None
        if not rect.get("found") or not rect.get("shown"):
            return None
        return self.box[0] + rect["x"], self.box[1] + rect["y"]

    def close_settings(self, why):
        """Close the Settings window as a user would: Escape while it has the keyboard, else its
        close button. `shell close` cannot do it: the window belongs to another process."""
        info = self.settings_window()
        if info is None or not info.get("found"):
            return "already_gone"
        if info.get("focused"):
            at = self.tap("esc")
            if self.timeline.wait(SETTINGS_HIDDEN, at - 1.0, CLOSE_WAIT_MS) and self.wait_settings(False, at, CLOSE_WAIT_MS):
                return "escape"
        point = self.settings_point("perfCloseSettings")
        if point is not None:
            at = self.click_at(*point)
            if self.timeline.wait(SETTINGS_HIDDEN, at - 1.0, CLOSE_WAIT_MS) and self.wait_settings(False, at, CLOSE_WAIT_MS):
                return "close_button"
        raise Stuck(f"{why}: neither Escape nor the close button closes the Settings window")

    def ensure_closed(self):
        """No panel and no Settings window open: the precondition of every cycle."""
        self.timeline.pump()
        state = self.ask("shell")
        if state is None:
            raise Stuck("the shell does not answer its probe")
        if state.get("locked") or state.get("auth"):
            raise Stuck("the session is locked or an authentication dialog is up: no key may be sent")
        if any_open(state):
            self.recover("a panel was still open before the cycle")
        info = self.settings_window()
        if info is not None and info.get("found"):
            how = self.close_settings("the Settings window was still open before the cycle")
            self.problems.append({"t": round(self.now(), 3), "recover": "the Settings window was still open",
                                  "how": how})

    def escape(self, why, settings=False):
        """Escape while the target is known to hold the keyboard: (key-down time, recovery).

        When the target does not hold it, nothing is pressed: the key would land in whatever
        window of the owner has the focus. The panel is closed through the product instead."""
        if settings:
            info = self.settings_window()
            if info is None or not info.get("found"):
                return None, None            # already gone (or niri does not say)
            if not info.get("focused"):
                self.focus_settings()
        elif self.holds_keyboard() is False:
            self.problems.append({"t": round(self.now(), 3), "no_keyboard_focus": why})
            return None, self.recover(why + ": the overlay does not hold the keyboard", escape=False)
        return self.tap("esc"), None

    # ---- aiming ------------------------------------------------------------------------------
    def item_point(self, name):
        """Output coordinates of the centre of a named shell item (bar or overlay), or None."""
        try:
            rect = self.probe.rect(name)
        except ProbeError as error:
            self.problems.append({"t": round(self.now(), 3), "probe": f"rect {name}", "error": str(error)[:240]})
            return None
        if not rect.get("found") or not rect.get("shown"):
            return None
        return rect["x"], rect["y"]

    def nav_point(self, key, scroll_for=True):
        """Output coordinates of a Settings nav entry; it has to lie inside the window.

        An entry outside the visible part of the sidebar is scrolled into view first
        (wheel notches over the sidebar): 18 entries do not fit the 780 px of the
        floating window. The rect is read again after the scroll, so what is returned
        is where the entry really is now."""
        if not self.box:
            return None
        rect = self.probe.rect(f"perfNav_{key}")
        if rect.get("found") and rect.get("shown") and 0 <= rect["y"] <= self.box_size[1] \
                and 0 <= rect["x"] <= self.box_size[0]:
            return self.box[0] + rect["x"], self.box[1] + rect["y"]
        if not scroll_for:
            return None

        def visible(entry):
            return (entry.get("found") and entry.get("shown")
                    and 0 <= entry["y"] <= self.box_size[1] and 0 <= entry["x"] <= self.box_size[0])

        # Scroll in steps towards the entry, in whichever direction it lies: compare the
        # rect before and after a notch - when the list stops moving the end is reached.
        # Every notch is recorded as an injection of ours (shot), or the idle watcher
        # reports the wheel as input of the owner and aborts the batch.
        last_y = rect.get("y")
        for _ in range(14):
            # The list's own y tells the direction: entries above the viewport scroll up.
            self.shot(self.inj.wheel_at(self.box[0] + 60, self.box[1] + self.box_size[1] / 2, 2))
            self.sleep(90)
            rect = self.probe.rect(f"perfNav_{key}")
            if visible(rect):
                return self.box[0] + rect["x"], self.box[1] + rect["y"]
            if rect.get("y") == last_y:
                break
            last_y = rect.get("y")
        last_y = None
        for _ in range(14):
            self.shot(self.inj.wheel_at(self.box[0] + 60, self.box[1] + self.box_size[1] / 2, -2))
            self.sleep(90)
            rect = self.probe.rect(f"perfNav_{key}")
            if visible(rect):
                return self.box[0] + rect["x"], self.box[1] + rect["y"]
            if rect.get("y") == last_y:
                break
            last_y = rect.get("y")
        return None

    def focus_settings(self):
        """Give the Settings window the keyboard by clicking the entry of the page it already shows."""
        key = ((self.ask("settings") or {}).get("settings") or {}).get("page")
        point = self.nav_point(key) if key else None
        if point is None:
            raise Skip("cannot focus the Settings window: no nav entry to click")
        self.click_at(*point)

    def calibrate_settings(self, pages):
        """Where the Settings window sits on the output, from the window's own Qt coordinates.

        niri's pos_in_window_layout is a coordinate of the WORKSPACE, not of the output: a
        window opened away from the workspace origin is reported at (0,0) while it sits in
        the middle of the screen. The probe's window state ([visible, width, height] from
        hostWindow) says nothing about position either, so the anchor is the pointer: the
        HoverHandler of the window reports where the output pointer is, window-relative,
        whenever the pointer is inside. Park the pointer, read the relative position, and
        the box follows: box = pointer_output - pointer_window."""
        deadline = time.monotonic() + 10
        info = self.probe.settings_origin()
        while not info.get("found") and time.monotonic() < deadline:
            time.sleep(0.1)
            info = self.probe.settings_origin()
        if not info.get("found"):
            raise Stuck("niri does not list the Settings window")
        self.box = [float(info["x"]), float(info["y"])]
        self.box_size = (float(info.get("w") or 0), float(info.get("h") or 0))
        self.meta["settings_window"] = info
        # Park the pointer mid-output; the window's HoverHandler then reports the same
        # point window-relative (and hovered=true) exactly when the box is right. The
        # floating window is not always where niri last left it, so if the mid-output
        # park misses, sweep a coarse grid until the window is under the pointer.
        park_x, park_y = self.width / 2, self.height / 2
        self.move(park_x, park_y)
        time.sleep(0.08)
        pointer = (self.ask("settings") or {}).get("pointer")
        if not (pointer and pointer[2]):
            for gy in range(1, 6):
                for gx in range(1, 6):
                    if gx == 3 and gy == 3:
                        continue        # the mid-output park, already tried
                    probe_x, probe_y = self.width * gx / 6, self.height * gy / 6
                    self.move(probe_x, probe_y)
                    time.sleep(0.05)
                    pointer = (self.ask("settings") or {}).get("pointer")
                    if pointer and pointer[2]:
                        park_x, park_y = probe_x, probe_y
                        break
                if pointer and pointer[2]:
                    break
        self.meta["settings_pointer"] = pointer
        if pointer and pointer[2]:
            self.box = [park_x - pointer[0], park_y - pointer[1]]
            self.meta["settings_box"] = [round(self.box[0], 1), round(self.box[1], 1)]
        rect = self.probe.rect(f"perfNav_{pages[0]}")
        if rect.get("found") and rect.get("shown"):
            # Prove the box with the first nav entry before anything is clicked.
            self.note(f"calibrate {rect['x']},{rect['y']}")
            self.move(self.box[0] + rect["x"], self.box[1] + rect["y"])
            time.sleep(0.12)
            pointer = (self.ask("settings") or {}).get("pointer")
            self.meta["settings_pointer_nav"] = pointer
            if not (pointer and pointer[2]):
                # The window does not see the pointer where we placed it: clicking
                # anything now would go to whatever is really there (a window of the
                # owner). No blind clicking - the run stops with the evidence attached.
                raise Skip("the Settings window does not see the pointer at its computed "
                           f"position (pointer={pointer}, box={self.box}, niri says {info})")

    def settings_ready(self, timeout_ms):
        """The Settings process answers its probe and its window is located. False at the timeout."""
        deadline = time.monotonic() + timeout_ms / 1000.0
        while True:
            try:
                self.probe.state("settings")
                break
            except ProbeError:
                if time.monotonic() > deadline:
                    return False
                time.sleep(0.1)
        self.probe.watch(True)        # a Settings that just started has its sampler off
        pages = list(((self.ask("settings") or {}).get("settings") or {}).get("pages") or [])
        self.box = None               # a new process may have put its window elsewhere
        if pages:
            self.calibrate_settings(pages)
        return True

    def settings_appears(self, at):
        """Epoch ms at which niri first listed the Settings window after the bind at `at`, else None."""
        if self.timeline.wait(mark("openSettingsPage "), at - 1.0, OPEN_WAIT_MS) is None:
            return None
        return self.wait_settings(True, at, 40000.0)

    def open_settings(self):
        """Settings open on a settled page; returns the page keys. A cold start takes seconds.

        The shell never sets a flag for Settings: it starts the process (or asks the one that
        lingers) and the window is what the user sees, so niri's own list of windows is the
        proof that it opened."""
        self.ensure_closed()
        self.probe.expect_settings = True
        at = self.tap(*PANELS["settings"])
        listed = self.settings_appears(at)
        if listed is None or not self.settings_ready(40000):
            raise Stuck("the Settings window did not appear within 40 s")
        if not self.timeline.wait(sample("settings", host_settled("settings")), listed - 1.0, 40000):
            raise Stuck("no Settings page settled within 40 s")
        pages = list(((self.ask("settings") or {}).get("settings") or {}).get("pages") or [])
        if len(pages) < 2:
            raise Skip(f"Settings lists {len(pages)} page(s)")
        return pages

    def open_control(self):
        """Control Center open with its current page settled; returns the tab ids."""
        self.ensure_closed()
        at = self.tap(*PANELS["control"])
        if not self.timeline.wait(is_open("control"), at - 1.0, OPEN_WAIT_MS):
            raise Stuck("the Control Center did not open")
        state = self.ask("shell")
        if not state:
            raise Stuck("the shell does not answer while the Control Center is open")
        shown = host_of(state, "cc").get("shown") or ""
        self.timeline.wait(sample("shell", host_settled("cc", shown or None)), at - 1.0, SETTLE_WAIT_MS)
        tabs = list((state.get("cc") or {}).get("tabs") or [])
        if len(tabs) < 2:
            raise Skip(f"the Control Center lists {len(tabs)} tab(s)")
        return tabs


# ---- S4: the island and Escape ----------------------------------------------------------------------

def classify_island(closed, close_ms, key_marks, frozen):
    """Why the island was, or was not, gone within the budget."""
    if closed:
        if frozen:
            return "frozen"
        return "ok" if close_ms <= ESC_BUDGET_MS else "late"
    if any(text.startswith(("key esc.island", "key esc.overlay")) for text in key_marks):
        return "handled_no_close"
    if any("unhandled" in text for text in key_marks):
        return "unhandled"
    return "frozen" if frozen else "not_delivered"


def island_cycle(ctx, rep, route, delay, prior, cold=False):
    """Open the island, press Escape `delay` ms after it was first on screen, assert it is gone."""
    rec = {"scenario": "s4", "rep": rep, "route": route, "pre_esc_ms": delay, "prior": prior or "",
           "load": len(ctx.load), "cold": cold}
    timeline = ctx.timeline
    ctx.ensure_closed()
    if prior:
        step = panel_cycle(ctx, prior, 300)
        rec["prior_close_ms"] = step["close_ms"]
        if step["closed"] is False:
            raise Stuck(f"the {prior} panel did not close before the island cycle")
    if route == "key":
        rec["t_open"] = ctx.tap(*PANELS["activity"])
    elif route == "click":
        point = ctx.item_point("perfActivity")
        if point is None:
            raise Skip("the bar's activity button is not on screen")
        rec["t_open"] = ctx.click_at(*point)
    else:
        rec["t_open"] = ctx.now()
        ctx.probe.shell("toggle", "activity")
    toggle = timeline.wait(mark("togglePanel activity"), rec["t_open"] - 200.0, OPEN_WAIT_MS)
    shown = timeline.wait(mark("island.shown true"), rec["t_open"] - 1.0, OPEN_WAIT_MS)
    rec["t_toggle_ms"] = round(toggle.epoch - rec["t_open"], 2) if toggle else None
    if shown is None:
        rec["class"] = "did_not_open"
        rec["recovery"] = ctx.recover("the island did not open", escape=False)
        return rec
    rec["open_ms"] = round(shown.epoch - rec["t_open"], 2)
    hit = timeline.wait(frame("overlay", "bar"), shown.epoch - 1.0, 300)
    rec["open_frame_ms"] = round(hit.epoch - rec["t_open"], 2) if hit else None
    # Escape counts from the first frame of the island: the moment it is on screen, and the
    # earliest moment the compositor can have moved the keyboard to its layer.
    base = hit.epoch if hit else shown.epoch
    rec["base"] = "frame" if hit else "mark"
    if cold:
        # The first island of the session answers two questions for all that follow: does its
        # layer hold the keyboard as soon as it is mapped, and does it still 400 ms later?
        ctx.sleep(base + 40.0 - ctx.now())
        ctx.meta["island_keyboard_early"] = ctx.holds_keyboard()
    if cold or delay >= 300:
        ctx.sleep(base + delay - ctx.now())
        rec["exclusive"] = ctx.holds_keyboard()
        if cold or rec["exclusive"] is not None:
            ctx.meta["island_keyboard"] = rec["exclusive"]
    if delay < 300 and not cold:
        # Measure at the actual moment of the press, every cycle: the cold-cycle answer
        # says nothing about a keyboard grant that races a previous panel's close
        # animation, and a missing meta must never stand in for a measurement.
        ctx.sleep(base + delay - ctx.now())
        rec["exclusive"] = ctx.holds_keyboard()
    if rec.get("exclusive") is False:
        # The keyboard is not on the shell: an Escape now would go to whichever window of the
        # owner has the focus. It is not pressed, and that is the finding of the cycle.
        rec["class"] = "no_keyboard_focus"
        rec["recovery"] = ctx.recover("the island does not hold the keyboard", escape=False)
        rec["after"] = {"island": (ctx.ask("shell") or {}).get("island")}
        return rec
    before = [event for event in timeline.after(shown.epoch - 60.0, {"S"})
              if event.data.get("proc") == "shell" and event.epoch <= ctx.now()]
    if before:
        rec["focus"] = before[-1].data.get("focus")
        rec["key_events"] = before[-1].data.get("keyEvents")
    rec["t_esc"] = ctx.tap("esc")
    closed = timeline.wait(mark("island.shown false"), rec["t_esc"] - 1.0, CLOSE_WAIT_MS)
    if closed is None:
        ctx.sleep(CLOSE_WAIT_MS)      # a frozen GUI thread answers late: give it the time
        closed = timeline.first(rec["t_esc"] - 1.0, mark("island.shown false"))
    rec["key_marks"] = [event.text for event in timeline.after(rec["t_esc"] - 1.0, {"m"})
                        if event.text.startswith("key ")]
    rec["closed"] = closed is not None
    rec["close_ms"] = round(closed.epoch - rec["t_esc"], 2) if closed else None
    frozen = any(event.epoch >= rec["t_esc"] and event.data["late"] >= ESC_BUDGET_MS
                 for event in timeline.after(rec["t_esc"] - 1.0, {"stall"}))
    rec["class"] = classify_island(rec["closed"], rec["close_ms"], rec["key_marks"], frozen)
    if closed:
        hit = timeline.wait(frame("overlay", "bar"), closed.epoch - 1.0, 300)
        rec["close_frame_ms"] = round(hit.epoch - rec["t_esc"], 2) if hit else None
        if not timeline.wait(NONE_OPEN, closed.epoch - 1.0, CLOSE_WAIT_MS):
            rec["closed"] = False
            rec["recovery"] = ctx.recover("the island hid but a panel flag stayed set")
    else:
        # The Escape was not answered. Was it the key or the focus? A second press says which.
        rec["recovery"] = ctx.recover("the island stayed open after Escape",
                                      escape=rec.get("exclusive") is not False)
        if rec["recovery"] == "second_escape":
            hit = timeline.first(rec["t_esc"] + 10.0, mark("island.shown false"))
            rec["gone_after_ms"] = round(hit.epoch - rec["t_esc"], 2) if hit else None
    state = ctx.ask("shell") or {}
    rec["after"] = {"activityOpen": state.get("activityOpen"), "panelOpen": state.get("panelOpen"),
                    "island": state.get("island")}
    rec["stalls"] = ctx.stalls(rec["t_open"], ctx.now())
    return rec


def s4_island(ctx, routes=("key", "click", "ipc"), delays=(5, 60, 150, 400), reps=10, prior="", load=0):
    """S4: the island opens and Escape does not close it. A rep is every route at every delay.

    A cold cycle (the first island of this shell, Escape after 400 ms) comes first: it is kept
    apart in the report, and it finds out where the keyboard is while the island is open."""
    if load:
        ctx.load.start(load)
    try:
        if not prior and "island_keyboard" not in ctx.meta:
            ctx.note("s4 cold cycle")
            ctx.records.append(island_cycle(ctx, -1, "key", 400, None, cold=True))
        for rep in range(reps):
            for route in routes:
                for delay in delays:
                    ctx.note(f"s4 rep={rep} route={route} delay={delay} prior={prior or '-'}")
                    ctx.records.append(island_cycle(ctx, rep, route, delay, prior or None))
                    ctx.guard(ctx.now() - 90000.0)
                    if ctx.out_of_time():
                        ctx.meta["truncated"] = f"s4 after rep {rep}"
                        return
    finally:
        ctx.load.stop()
        ctx.park()


# ---- S2: Settings pages ------------------------------------------------------------------------------

def anchors(pages):
    """The pages of the symptom, under the key the registry really uses."""
    found = {}
    for label in ("about", "wallpaper", "appearance"):
        key = label if label in pages else next((p for p in pages if label in p.lower()), None)
        if key:
            found[label] = key
    return found


def navigate_mark(key):
    def test(event):
        return event.kind == "m" and event.text.startswith("settings.navigate ") and f">{key} " in event.text
    return test


def page_ready(name, key):
    return mark(f"host.loaded {name} {key}", f"host.present {name} {key}")


def final_state(ctx, last, end):
    """The Settings page host after a burst, and how long it took to reach the expected state."""
    timeline = ctx.timeline
    settled = timeline.wait(sample("settings", host_settled("settings", last)), end - 1.0, 6000)
    state = ctx.ask("settings") or {}
    host = host_of(state, "settings")
    # `host` is the page host itself, the authority on what is shown; the view's `page`
    # is read a moment later and may already name the next click's target. Never let
    # this dict overwrite the caller's own "page" key either (that cost a false
    # "weather failed" in every rep: the entry's page was replaced by the NEXT page).
    checks = {"shown_is_page": host.get("shown") == last,
              "built": host.get("status") == 1, "opaque": host.get("opacity", 0) >= 0.999,
              "not_receding": not host.get("leaving"), "no_pending": not host.get("pending"),
              "no_animation": not host.get("enterRun") and not host.get("leaveRun")}
    return {"settle_ms": round(settled.epoch - end, 2) if settled else None, "ok": settled is not None,
            "failed_checks": [name for name, passed in checks.items() if not passed], "host": host,
            "state_page": (state.get("settings") or {}).get("page"),
            "toast": (state.get("settings") or {}).get("toastText", "")}


def latency(timeline, t_ms, test, timeout_ms):
    hit = timeline.wait(test, t_ms - 1.0, timeout_ms)
    return round(hit.epoch - t_ms, 2) if hit else None


def settings_burst(ctx, rec, sequence, gap_ms):
    """Click the pages of `sequence`, then assert the state machine of the page host."""
    timeline = ctx.timeline
    ctx.inj.note("burst " + "+".join(sequence) + f" gap={gap_ms}")
    stamps = []
    if gap_ms <= 0:
        commands = []
        for key in sequence:
            point = ctx.nav_point(key)
            if point is None:
                raise Skip(f"perfNav_{key} is not inside the Settings window")
            commands += [f"move {int(round(point[0]))} {int(round(point[1]))}", "click left"]
        replies = ctx.inj.send(*commands)
        stamps = [ctx.shot(replies[index]) for index in range(1, len(replies), 2)]
    else:
        for key in sequence:
            point = ctx.nav_point(key)
            if point is None:
                raise Skip(f"perfNav_{key} is not inside the Settings window")
            stamps.append(ctx.click_at(*point))
            ctx.sleep(gap_ms)
    rec["clicks"] = [[key, round(at, 3)] for key, at in zip(sequence, stamps)]
    rec["react_ms"] = [latency(timeline, at, navigate_mark(key), 5000) for key, at in zip(sequence, stamps)]
    rec["first_frame_ms"] = latency(timeline, stamps[0], frame("settings"), 400)
    rec.update(final_state(ctx, sequence[-1], stamps[-1]))
    now = ctx.now()
    rec["marks"] = [event.text for event in timeline.after(stamps[0] - 1.0, {"m"})
                    if event.text.startswith(("settings.navigate", "host.")) and event.epoch <= now][:120]
    rec["stalls"] = ctx.stalls(stamps[0], now)
    ctx.park()


def s2_settings(ctx, variants=("all", "aba", "toast"), reps=10, burst=6, gap_ms=60, pairs=""):
    """S2: rapid page switching leaves a page half way into its animation."""
    pages = ctx.open_settings()
    names = anchors(pages)
    if pairs:
        wanted = []
        for item in pairs.split("+"):
            first, _, second = item.partition("-")
            if first in pages and second in pages:
                wanted.append((first, second))
    else:
        keys = list(dict.fromkeys(names.values()))
        wanted = [(keys[i], keys[j]) for i in range(len(keys)) for j in range(i + 1, len(keys))]
    if not wanted:
        raise Skip("none of the about / wallpaper / appearance pages exist")
    ctx.meta["s2_pairs"] = wanted
    timeline = ctx.timeline
    try:
        for variant in variants:
            for rep in range(reps):
                pair = wanted[rep % len(wanted)]
                ctx.note(f"s2 {variant} rep={rep} pair={pair[0]}+{pair[1]}")
                rec = {"scenario": "s2", "variant": variant, "rep": rep, "pair": list(pair), "burst": burst, "gap_ms": gap_ms}
                if variant == "all":
                    rec["pages"] = []
                    for key in pages:
                        point = ctx.nav_point(key)
                        if point is None:
                            rec["pages"].append({"page": key, "unreachable": True})
                            continue
                        ctx.note(f"page {key}")
                        at = ctx.click_at(*point)
                        entry = {"page": key, "t": round(at, 3)}
                        # A click on the page that is already shown navigates nowhere
                        # (navigate() returns early, no mark): "already there" is the
                        # reaction. The entry's ok comes from final_state anyway.
                        already = ((ctx.ask("settings") or {}).get("settings") or {}).get("page") == key
                        entry["react_ms"] = 0.0 if already else latency(timeline, at, navigate_mark(key), 5000)
                        entry["frame_ms"] = latency(timeline, at, frame("settings"), 300)
                        entry["page_ms"] = latency(timeline, at, page_ready("settings", key), SETTLE_WAIT_MS)
                        entry.update(final_state(ctx, key, at))
                        rec["pages"].append(entry)
                    reached = [page for page in rec["pages"] if not page.get("unreachable")]
                    rec["ok"] = bool(reached) and all(page["ok"] for page in reached)
                    rec["stalls"] = ctx.stalls(reached[0]["t"], ctx.now()) if reached else []
                else:
                    if variant == "toast" and "wallpaper" in names and names.get("about"):
                        point = ctx.nav_point(names["wallpaper"])
                        if point is not None:
                            at = ctx.click_at(*point)
                            hit = timeline.wait(sample("settings", lambda d: TOAST_TEXT in (d.get("settings") or {}).get("toastText", "")),
                                                at - 1.0, 30000)
                            rec["toast_seen"] = hit is not None
                            rec["toast_ms"] = round(hit.epoch - at, 2) if hit else None
                        pair = (names["wallpaper"], names["about"])
                    settings_burst(ctx, rec, [pair[index % 2] for index in range(burst)], gap_ms)
                rec["ping_ms"] = ctx.ping()
                ctx.records.append(rec)
                ctx.guard(ctx.now() - 90000.0)
                if ctx.out_of_time():
                    ctx.meta["truncated"] = f"s2 {variant} after rep {rep}"
                    return
    finally:
        try:
            ctx.close_settings("the Settings window stayed open at the end of s2")
        except Stuck as error:
            ctx.problems.append({"t": round(ctx.now(), 3), "stuck": str(error)})
        ctx.park()


# ---- S1: Control Center tabs ------------------------------------------------------------------------

def cc_clicks(ctx, order, rects, rec):
    """Click the tabs of `order`, each waiting for its page to settle: the per-tab latencies."""
    timeline = ctx.timeline
    entries = []
    for tab in order:
        at = ctx.click_at(*rects[tab])
        entry = {"tab": tab, "t": round(at, 3)}
        entry["react_ms"] = latency(timeline, at, mark(f"cc.tab {tab}"), 5000)
        entry["page_ms"] = latency(timeline, at, page_ready("cc", tab), SETTLE_WAIT_MS)
        entry["settle_ms"] = latency(timeline, at, sample("shell", host_settled("cc", tab)), SETTLE_WAIT_MS)
        entry["frame_ms"] = latency(timeline, at, frame("overlay"), 300)
        entries.append(entry)
    rec["clicks"] = entries
    return entries[-1]["t"]


def reaction_times(timeline, clicks, limit_of):
    """For each click the time until the shell switched to that tab; None when the next click
    (or `limit_of` ms for the last one) came first, or the mark never showed."""
    out = []
    for index, click in enumerate(clicks):
        limit = click["t"] + limit_of(index)
        hit = timeline.first(click["t"] - 1.0, mark(f"cc.tab {click['tab']}"))
        out.append(round(hit.epoch - click["t"], 2) if hit and hit.epoch <= limit else None)
    return out


def s1_control(ctx, variants=("ordered", "random", "fast"), reps=10, clicks=12, seconds=3.0, seed=1,
               max_clicks=400):
    """S1: switching tabs freezes the shell. A rep is one pass, one random walk or one burst."""
    rng = random.Random(seed)
    tabs = ctx.open_control()
    rects = {}
    for tab in tabs:
        point = ctx.item_point(f"perfTab_{tab}")
        if point is None:
            raise Skip(f"perfTab_{tab} is not on screen")
        rects[tab] = point
    timeline = ctx.timeline
    ctx.park()
    try:
        for variant in variants:
            for rep in range(reps):
                ctx.note(f"s1 {variant} rep={rep}")
                rec = {"scenario": "s1", "variant": variant, "rep": rep, "tabs": tabs}
                started = ctx.now()
                clicks_ = []
                if variant == "ordered":
                    end = cc_clicks(ctx, tabs, rects, rec)
                    clicks_ = rec["clicks"]
                else:
                    if variant == "random":
                        current = host_of(ctx.ask("shell") or {}, "cc").get("shown") or tabs[0]
                        for _ in range(clicks):
                            current = rng.choice([tab for tab in tabs if tab != current])
                            at = ctx.click_at(*rects[current])
                            clicks_.append({"tab": current, "t": round(at, 3)})
                            ctx.sleep(rng.uniform(20, 300))
                    else:      # fast: as many clicks as fit into `seconds`, capped for fast models
                        stop = started + seconds * 1000.0
                        index = 0
                        while index < max_clicks and ctx.now() < stop:
                            tab = tabs[index % len(tabs)]
                            at = ctx.click_at(*rects[tab])
                            clicks_.append({"tab": tab, "t": round(at, 3)})
                            index += 1
                    rec["clicks"] = clicks_
                    if not clicks_:                 # a rep can end before its first click
                        ctx.records.append(rec)
                        continue
                    gaps = [clicks_[index + 1]["t"] - click["t"] for index, click in enumerate(clicks_[:-1])]
                    rec["react_ms"] = reaction_times(timeline, clicks_, lambda index: gaps[index] if index < len(gaps) else 5000.0)
                    end = clicks_[-1]["t"]
                if not clicks_:                     # a fast rep can end before its first click
                    ctx.records.append(rec)
                    continue
                last = clicks_[-1]["tab"]
                rec["duration_ms"] = round(end - clicks_[0]["t"], 1)
                final = timeline.wait(sample("shell", host_settled("cc", last)), end - 1.0, SETTLE_WAIT_MS)
                rec["final_settle_ms"] = round(final.epoch - end, 2) if final else None
                state = ctx.ask("shell") or {}
                rec["final"] = {"wanted": last, "tab": (state.get("cc") or {}).get("tab"), "host": host_of(state, "cc")}
                rec["ok"] = final is not None and (state.get("cc") or {}).get("tab") == last
                rec["ping_ms"] = ctx.ping()
                at, rec["close_recovery"] = ctx.escape(f"s1 {variant} rep {rep}")
                if at is not None:
                    closed = timeline.wait(mark("shell.panelOpen state=false"), at - 1.0, CLOSE_WAIT_MS)
                    rec["close_ms"] = round(closed.epoch - at, 2) if closed else None
                    if closed is None:
                        rec["close_recovery"] = ctx.recover("the Control Center stayed open after Escape")
                    else:
                        hit = timeline.wait(frame("overlay"), closed.epoch - 1.0, 300)
                        rec["close_frame_ms"] = round(hit.epoch - at, 2) if hit else None
                rec["stalls"] = ctx.stalls(started, ctx.now())
                ctx.records.append(rec)
                ctx.guard(ctx.now() - 90000.0)
                if ctx.out_of_time():
                    ctx.meta["truncated"] = f"s1 {variant} after rep {rep}"
                    return
                ctx.open_control()
    finally:
        ctx.park()


# ---- S3: a working session -----------------------------------------------------------------------------

def panel_cycle(ctx, name, dwell_ms):
    """Open a panel through its niri bind, dwell, Escape, and time both halves.

    Settings is the exception in both halves: it is another process, so "open" is niri listing
    its window and "closed" is niri dropping it again, with the process's own marks for the
    exact moments."""
    rec = {"panel": name, "dwell_ms": dwell_ms}
    timeline = ctx.timeline
    settings = name == "settings"
    if settings:
        ctx.probe.expect_settings = True
    at = ctx.tap(*PANELS[name])
    rec["t_open"] = round(at, 3)
    if settings:
        opened = ctx.settings_appears(at)
        if opened is not None and not ctx.settings_ready(40000):
            opened = None
        rec["open_ms"] = round(opened - at, 1) if opened else None
        rec["open_frame_ms"] = latency(timeline, at, frame("settings"), 45000) if opened else None
    else:
        opened = timeline.wait(is_open(name), at - 1.0, OPEN_WAIT_MS)
        rec["open_ms"] = round(opened.epoch - at, 1) if opened else None
        rec["open_frame_ms"] = latency(timeline, at, frame("overlay", "bar"), 400)
    if opened is None:
        rec["closed"] = None
        rec["recovery"] = ctx.recover(f"{name} did not open", escape=False)
        return rec
    ctx.sleep(dwell_ms)
    rec["stalls_open"] = ctx.stalls(at, ctx.now())
    esc, rec["recovery"] = ctx.escape(f"s3 {name}", settings=settings)
    if esc is None:
        rec["closed"] = not settings or not (ctx.settings_window() or {}).get("found")
        return rec
    if settings:
        hit = timeline.wait(SETTINGS_HIDDEN, esc - 1.0, CLOSE_WAIT_MS)
        gone = ctx.wait_settings(False, esc, CLOSE_WAIT_MS) if hit else None
        rec["close_ms"] = round(hit.epoch - esc, 1) if hit else None      # the process hid its window
        rec["gone_ms"] = round(gone - esc, 1) if gone else None           # niri stopped listing it
        rec["closed"] = gone is not None
        if gone is None:
            rec["recovery"] = ctx.close_settings("Settings stayed open after Escape")
        rec["stalls_close"] = ctx.stalls(esc - 1.0, ctx.now())
        return rec
    closed = timeline.wait(NONE_OPEN, esc - 1.0, CLOSE_WAIT_MS)
    rec["close_ms"] = round(closed.epoch - esc, 1) if closed else None
    rec["closed"] = closed is not None
    if closed is None:
        rec["recovery"] = ctx.recover(f"{name} stayed open after Escape")
    elif name != "settings":
        rec["close_frame_ms"] = latency(timeline, closed.epoch, frame("overlay", "bar"), 300)
    rec["stalls_close"] = ctx.stalls(esc - 1.0, ctx.now())
    return rec


def s3_mixed(ctx, reps=2, seed=1, load=0, dwell="150-900", script="", workspaces=True):
    """S3: the whole shell goes quiet for a moment. Panels, workspaces and Settings in a row."""
    rng = random.Random(seed)
    low, _, high = dwell.partition("-")
    steps = script.replace(",", " ").split() if script else list(S3_SCRIPT)
    unknown = [name for name in steps if name not in PANELS]
    if unknown:
        raise Skip(f"unknown panel(s) {unknown}")
    if load:
        ctx.load.start(load)
    try:
        for rep in range(reps):
            ctx.ensure_closed()
            ctx.note(f"s3 rep={rep} load={load}")
            rec = {"scenario": "s3", "rep": rep, "load": len(ctx.load), "steps": []}
            started = ctx.now()
            for name in steps:
                ctx.note(f"panel {name}")
                rec["steps"].append(panel_cycle(ctx, name, int(rng.uniform(float(low), float(high or low)))))
            if workspaces:
                rec["workspace"] = workspace_round(ctx)
            rec["ping_ms"] = ctx.ping()
            rec["final_open"] = any_open(ctx.ask("shell") or {}) or bool((ctx.settings_window() or {}).get("found"))
            rec["stalls"] = ctx.stalls(started, ctx.now())
            ctx.records.append(rec)
            ctx.guard(ctx.now() - 90000.0)
            if ctx.out_of_time():
                ctx.meta["truncated"] = f"s3 after rep {rep}"
                return
    finally:
        ctx.load.stop()
        ctx.park()


def workspace_round(ctx):
    """To the next workspace and back, through niri's own binds (Mod+<index>)."""
    rec = {}
    before = ctx.probe.focused_workspace()
    rec["before"] = before
    idx = (before or {}).get("idx")
    if not idx:
        rec["skipped"] = "niri does not say which workspace is focused"
        return rec
    other = idx + 1 if idx < 9 else idx - 1
    if other < 1:
        rec["skipped"] = "no other workspace index"
        return rec
    ctx.tap("super", str(other))
    ctx.sleep(700)
    rec["away"] = ctx.probe.focused_workspace()
    ctx.tap("super", str(idx))
    ctx.sleep(700)
    rec["after"] = ctx.probe.focused_workspace()
    rec["restored"] = (rec["after"] or {}).get("idx") == idx
    if not rec["restored"]:
        ctx.tap("super", str(idx))
        ctx.sleep(700)
        rec["after_retry"] = ctx.probe.focused_workspace()
    return rec


def warmup(ctx, rounds=2):
    """Open and close every panel twice: the first opens of a fresh shell are one-off costs."""
    for _ in range(rounds):
        for name in S3_SCRIPT[:8]:
            ctx.note(f"warmup {name}")
            panel_cycle(ctx, name, 400)
    ctx.ensure_closed()
    ctx.park()


# ---- dispatch -----------------------------------------------------------------------------------------

DEFAULTS = {
    "warmup": (warmup, {"rounds": 2}),
    "s4": (s4_island, {"routes": ("key", "click", "ipc"), "delays": (5, 60, 150, 400), "reps": 10, "prior": "", "load": 0}),
    "s2": (s2_settings, {"variants": ("all", "aba", "toast"), "reps": 10, "burst": 6, "gap_ms": 60, "pairs": ""}),
    "s1": (s1_control, {"variants": ("ordered", "random", "fast"), "reps": 10, "clicks": 12, "seconds": 3.0, "seed": 1,
                        "max_clicks": 400}),
    "s3": (s3_mixed, {"reps": 2, "seed": 1, "load": 0, "dwell": "150-900", "script": "", "workspaces": True}),
}


def parse(spec):
    """`s4` or `s4:reps=5,routes=key+ipc,load=8`: the function and its options."""
    name, _, rest = spec.partition(":")
    if name not in DEFAULTS:
        raise Skip(f"unknown scenario {name!r} (known: {', '.join(DEFAULTS)})")
    function, defaults = DEFAULTS[name]
    options = dict(defaults)
    for item in filter(None, rest.split(",")):
        key, _, value = item.partition("=")
        if key not in options:
            raise Skip(f"{name}: unknown option {key!r} (known: {', '.join(options)})")
        default = options[key]
        if isinstance(default, bool):
            options[key] = value in ("1", "true", "yes", "on")
        elif isinstance(default, int):
            options[key] = int(value)
        elif isinstance(default, float):
            options[key] = float(value)
        elif isinstance(default, tuple):
            # Tuple options (routes, delays, pairs, ...) keep the type of their parts:
            # a delays list of strings compares against no number.
            parts = tuple(part for part in value.split("+") if part)
            if default and isinstance(default[0], int) and all(part.lstrip("-").isdigit() for part in parts):
                parts = tuple(int(part) for part in parts)
            options[key] = parts
        else:
            options[key] = value
    return function, options


def run(ctx, specs):
    """Run each spec in order. OwnerIsBack and Stuck propagate; a Skip is recorded and the rest
    runs. What completed is kept in ctx.meta["specs_done"], also when a scenario is cut short."""
    done = ctx.meta.setdefault("specs_done", [])
    for spec in specs:
        try:
            function, options = parse(spec)
        except Skip as error:
            ctx.problems.append({"skip": str(error)})
            continue
        started = ctx.now()
        try:
            function(ctx, **options)
        except Skip as error:
            ctx.load.stop()
            ctx.problems.append({"t": round(ctx.now(), 3), "scenario": spec, "skip": str(error)})
        done.append({"scenario": spec, "started_ms": started, "ended_ms": ctx.now()})
    return done


def warmup_end(ctx):
    """Epoch ms from which the shell counts as warm: the end of the warm-up, or else the start
    of the first scenario; the start of the run when nothing ran."""
    done = ctx.meta.get("specs_done") or []
    ends = {entry["scenario"].split(":")[0]: entry["ended_ms"] for entry in done}
    return ends.get("warmup", done[0]["started_ms"] if done else None)


def dump(ctx, path):
    """Everything a run produced, for analyze.py."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"records": ctx.records, "problems": ctx.problems, "meta": ctx.meta}, indent=1) + "\n")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List the scenarios and parse specs.")
    parser.add_argument("specs", nargs="*")
    arguments = parser.parse_args()
    for spec in arguments.specs or list(DEFAULTS):
        function, options = parse(spec)
        print(f"{spec}: {function.__name__}{options}")
