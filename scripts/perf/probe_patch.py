#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Instrument a SCRATCH COPY of the shell tree with the perf probe (Probe.qml + Heartbeat).

  probe_patch.py --src <tree>                 patch a pristine copy
  probe_patch.py --src <tree> --check         only verify an already patched copy
  probe_patch.py --src <tree> --list          print the edits without touching anything

The tree must not contain a .git directory: the probe is meant for throwaway copies made by
prepare.py, never for a working clone. Every edit is an exact-anchor replacement; the run
stops at the first anchor that is missing, ambiguous or already patched and names the file.
An edit to an anchor line in the product is therefore caught here (update the anchor and the
expected edit) instead of silently dropping a mark.

The probe never changes behaviour: it adds marks, registers objects with the Probe singleton
and adds one IPC target ("probe": state, rect, ping, stage, watch, quit).
"""
import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE_FILE = "qml/services/Probe.qml"
PROBE_SRC = HERE / "probe" / "Probe.qml"
MARKER = ".perf-probe.json"


@dataclass
class Edit:
    path: str
    old: str
    new: str
    count: int = 1
    note: str = ""


@dataclass
class EditAny:
    """One edit with alternative anchors: the first whose `old` occurs exactly `count`
    times wins. Used where the product itself changed shape between the baseline tree
    (pre-fix) and the branch tree (post-fix): the probe must instrument both, and a
    drifted anchor must still fail loudly when none of the variants matches."""
    path: str
    variants: list            # [(old, new, note), ...]
    count: int = 1
    note: str = ""


@dataclass
class LineEdit:
    """Edit one line: the needle must occur on exactly `count` lines."""
    path: str
    needle: str
    old_sub: str = ""      # replaced inside the line (must occur once in the line)
    new_sub: str = ""
    insert_after: list = field(default_factory=list)   # lines inserted after it, indented relative to it
    note: str = ""


EDITS = []
LINE_EDITS = []


def edit(path, old, new, count=1, note=""):
    EDITS.append(Edit(path, old, new, count, note))


def edit_any(path, variants, count=1, note=""):
    EDITS.append(EditAny(path, variants, count, note))


def line(path, needle, old_sub="", new_sub="", after=None, note=""):
    LINE_EDITS.append(LineEdit(path, needle, old_sub, new_sub, after or [], note))


def ipc_handler():
    return '''    IpcHandler { // PERF PROBE (scratch tree only, scripts/perf/probe_patch.py)
        target: "probe"
        function state(): string { return Probe.stateJson() }
        function rect(name: string): string { return Probe.rectJson(name) }
        function ping(): string { return "" + Probe.ms() }
        function stage(name: string): string { Probe.setStage(name); return "ok" }
        function watch(on: bool): string { Probe.watch = on; if (on) Probe.sample(); return "ok" }
        function quit(): string { Probe.mark("quit"); Qt.quit(); return "ok" }
    }
'''


def probe_state_fn(indent):
    i = indent
    return [
        i + "function probeState() {",
        i + '    return {key: key, shown: shown ? shown.pageKey : "", enter: Math.round(enter * 1000) / 1000,',
        i + "        leaving: Math.round(leaving * 1000) / 1000, opacity: Math.round(opacity * 1000) / 1000,",
        i + '        pending: pending ? pending.pageKey : "", prewarming: prewarming ? prewarming.pageKey : "",',
        i + "        queue: prewarmQueue.length, pages: pageCount, enterRun: enterMotion.running, leaveRun: leaveMotion.running,",
        i + "        status: shown ? shown.status : -1, active: active};",
        i + "}",
    ]


ESC_SITES = {
    "qml/panels/Overview.qml": 1,
    "qml/panels/NotificationCenter.qml": 1,
    "qml/panels/TrayMenu.qml": 1,
    "qml/panels/EqualizerPanel.qml": 1,
    "qml/panels/PowerMenu.qml": 1,
}

# ---- qmldir + services -----------------------------------------------------------
edit("qml/services/qmldir", "singleton Heartbeat 1.0 Heartbeat.qml\n",
     "singleton Heartbeat 1.0 Heartbeat.qml\nsingleton Probe 1.0 Probe.qml\n",
     note="register the Probe singleton (needs the diagnostics commit)")

# `after` lines are written relative to the matched line's own indentation.
line("qml/services/ShellState.qml", "function closePanels() {", after=[
    '    Probe.mark("closePanels", panelOpen ? "open" : "idle");'])
line("qml/services/ShellState.qml", "function togglePanel(name, screen) {", after=[
    '    Probe.mark("togglePanel " + name, (screen ? "screen " : "") + "panelOpen=" + panelOpen',
    '              + " kind=" + panelKind + " activity=" + activityOpen + " catalog=" + !!FeatureCatalog.panel(name));'])
line("qml/services/ShellState.qml", "function openSettingsPage(page) {", after=[
    '    Probe.mark("openSettingsPage " + page);'])
line("qml/services/ShellState.qml", "function accept(data) {", after=[
    "    const probeT0 = Probe.now();"])
edit("qml/services/ShellState.qml",
     '        } catch (error) { console.warn("Invalid desktop backend message:", error); }\n    }\n',
     '            Probe.mark("accept", (Probe.now() - probeT0).toFixed(2) + "ms bytes=" + data.length);\n'
     '        } catch (error) { console.warn("Invalid desktop backend message:", error); }\n    }\n',
     note="backend snapshot cost on the GUI thread")

# ---- PageHost --------------------------------------------------------------------
edit("qml/components/PageHost.qml",
     "    onKeyChanged: show()\n"
     "    onActiveFocusChanged: if (activeFocus && shown) shown.forceActiveFocus()\n"
     "    Component.onCompleted: show()\n",
     "    onKeyChanged: show()\n"
     "    onActiveFocusChanged: if (activeFocus && shown) shown.forceActiveFocus()\n"
     '    property string probeName: "panel"\n'
     "    // The registered name is unique per tree (the second unnamed host becomes panel#1).\n"
     "    Component.onCompleted: { show(); probeName = Probe.hostName(probeName); Probe.hosts[probeName] = this; }\n"
     + "\n".join(probe_state_fn("    ")) + "\n")
edit("qml/components/PageHost.qml",
     "    function present(page) {\n"
     "        leaving = 0;\n"
     "        if (shown === page) return;\n",
     "    function present(page) {\n"
     "        leaving = 0;\n"
     '        Probe.mark("host.present " + probeName + " " + page.pageKey + (shown === page ? " same" : shown ? " from=" + shown.pageKey : " first"));\n'
     "        if (shown === page) return;\n")
edit("qml/components/PageHost.qml",
     "        if (!page || page.status !== Loader.Loading) return;\n",
     "        if (!page || page.status !== Loader.Loading) return;\n"
     '        Probe.mark("host.drop " + probeName + " " + page.pageKey + (prewarming === page ? " prewarm" : "") + (pending === page ? " pending" : ""));\n')
edit("qml/components/PageHost.qml",
     "    function show() {\n"
     "        if (shown && shown.pageKey === key) return;\n",
     "    function show() {\n"
     '        Probe.mark("host.show " + probeName + " " + key + (shown && shown.pageKey === key ? " same" : "")\n'
     '            + " pending=" + (pending ? pending.pageKey : "-") + " prewarm=" + (prewarming ? prewarming.pageKey : "-"));\n'
     "        if (shown && shown.pageKey === key) return;\n")
line("qml/components/PageHost.qml", "function recede() {", after=[
    '    Probe.mark("host.recede " + probeName + " " + key);'])
edit("qml/components/PageHost.qml",
     "        const started = Heartbeat.enabled ? Heartbeat.now() : 0;\n"
     "        page.sourceComponent = content;\n",
     "        const started = Heartbeat.enabled ? Heartbeat.now() : 0;\n"
     "        const probeStarted = Probe.now();\n"
     "        page.sourceComponent = content;\n"
     '        Probe.mark("host.build " + probeName + " " + pageKey + (incubate === true ? " start" : " " + (Probe.now() - probeStarted).toFixed(2) + "ms"));\n')
edit("qml/components/PageHost.qml",
     "            onStatusChanged: {\n"
     "                if (status === Loader.Loading) return;\n",
     "            onStatusChanged: {\n"
     "                if (status === Loader.Loading) return;\n"
     '                Probe.mark("host.status " + root.probeName + " " + pageKey + " " + status);\n')
edit("qml/components/PageHost.qml",
     "            onLoaded: {\n"
     "                root.pageLoaded(item);\n",
     "            onLoaded: {\n"
     '                Probe.mark("host.loaded " + root.probeName + " " + pageKey);\n'
     "                root.pageLoaded(item);\n")

# ---- Panel stage (one retained page per panel kind) -----------------------------
line("qml/panels/PanelStage.qml", "    property var windowInfo: null", after=['probeName: "stage"'],
     note="name the overlay panel host")

# ---- Control Center --------------------------------------------------------------
edit("qml/panels/ControlCenter.qml",
     "    function selectTab(id) { currentTab = ControlRegistry.indexForId(id); }\n",
     '    function selectTab(id) { Probe.mark("cc.select " + id); currentTab = ControlRegistry.indexForId(id); }\n')
# `selectedTab` is a binding on currentTab; read inside the change handler it still names
# the tab the panel is LEAVING (the first live S1 run saw every mark one tab behind), so
# the mark reads the registry with the new index itself.
edit("qml/panels/ControlCenter.qml",
     "    onCurrentTabChanged: { editing = false; ShellState.controlTab = currentTab; markTabRead(); refreshControls(); }\n",
     '    onCurrentTabChanged: { Probe.mark("cc.tab " + (ControlRegistry.tabForIndex(currentTab).id || "?")); editing = false; ShellState.controlTab = currentTab; markTabRead(); refreshControls(); }\n')
edit("qml/panels/ControlCenter.qml",
     "    Component.onCompleted: { initialized = true; markTabRead(); refreshControls(); }\n",
     "    Component.onCompleted: { Probe.cc = this; initialized = true; markTabRead(); refreshControls(); }\n")
edit("qml/panels/ControlCenter.qml",
     "    Keys.onEscapePressed: if (editing) editing = false; else ShellState.closePanels()\n",
     '    Keys.onEscapePressed: { Probe.key("esc.cc", "editing=" + editing); if (editing) editing = false; else ShellState.closePanels(); }\n')
edit("qml/panels/ControlCenter.qml",
     "                delegate: LiquidButton {\n"
     "                    required property var modelData\n"
     "                    required property int index\n"
     "                    Layout.fillWidth: true\n"
     "                    Layout.preferredWidth: 1\n"
     "                    text: modelData.title\n",
     "                delegate: LiquidButton {\n"
     "                    required property var modelData\n"
     "                    required property int index\n"
     '                    objectName: "perfTab_" + modelData.id\n'
     "                    Component.onCompleted: Probe.tabs[modelData.id] = this\n"
     "                    Layout.fillWidth: true\n"
     "                    Layout.preferredWidth: 1\n"
     "                    text: modelData.title\n")
edit("qml/panels/ControlCenter.qml",
     "            id: dashboard\n"
     "            Layout.fillWidth: true; Layout.fillHeight: true\n",
     "            id: dashboard\n"
     '            probeName: "cc"\n'
     "            Layout.fillWidth: true; Layout.fillHeight: true\n")

# ---- island + bar button ---------------------------------------------------------
edit("qml/panels/ActivityIsland.qml",
     "    Keys.onEscapePressed: ShellState.closePanels()\n",
     '    Keys.onEscapePressed: { Probe.key("esc.island"); ShellState.closePanels(); }\n')
edit("qml/panels/ActivityIsland.qml",
     "    onDormantChanged: if (dormant) { widthSpring.snapTo(root.compactWidth); heightSpring.snapTo(30); radiusSpring.snapTo(root.compactRadius) }\n",
     "    onDormantChanged: { Probe.mark(\"island.dormant \" + dormant); if (dormant) { widthSpring.snapTo(root.compactWidth); heightSpring.snapTo(30); radiusSpring.snapTo(root.compactRadius) } }\n")
line("qml/panels/ActivityIsland.qml", "    shown: expanded", after=[
    'Component.onCompleted: Probe.island = this',
    'onShownChanged: Probe.mark("island.shown " + shown)'])
edit("qml/bar/ActivityButton.qml",
     "    onClicked: {\n"
     "        if (root.primaryAction()) return;\n",
     "    onClicked: {\n"
     '        Probe.mark("activityButton.click");\n'
     "        if (root.primaryAction()) return;\n")
line("qml/bar/ActivityButton.qml", "visible: !(ShellState.activityOpen &&", after=[
    'objectName: "perfActivity"'])

# ---- shell.qml -------------------------------------------------------------------
# Quickshell's window type carries no frame signal (see SettingsView.qml): the frames
# come from the attached Window.window, so the hooks sit on items inside each window.
edit("shell.qml",
     "pragma ComponentBehavior: Bound\nimport QtQuick\n",
     "pragma ComponentBehavior: Bound\nimport QtQuick\nimport QtQuick.Window\n",
     note="Window attached property for the frame hooks")
edit("shell.qml",
     '    Binding { target: ShellState; property: "overlayVisible"; value: overlay.surfaceLive }\n',
     '    Binding { target: ShellState; property: "overlayVisible"; value: overlay.surfaceLive }\n' + ipc_handler())
edit("shell.qml",
     "                    windowInfo: barWindow\n",
     "                    windowInfo: barWindow\n"
     "                    readonly property var probeWindow: Window.window\n"
     "                    Component.onCompleted: Probe.watchWindow(\"bar\", barWindow)\n"
     "                    Connections { target: probeWindow; function onFrameSwapped() { Probe.frame(\"bar\") } }\n")
edit("shell.qml",
     "        mask: Region { item: ShellState.panelOpen ? overlay.contentItem : null }\n"
     "        WlrLayershell.keyboardFocus: ShellState.panelOpen ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None\n",
     "        mask: Region { item: ShellState.panelOpen ? overlay.contentItem : null }\n"
     "        WlrLayershell.keyboardFocus: ShellState.panelOpen ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None\n"
     "        Connections {\n"
     "            target: ShellState\n"
     "            function onPanelOpenChanged() { Probe.mark(\"shell.panelOpen \" + ShellState.panelOpen + \" activity=\" + ShellState.activityOpen + \" kind=\" + ShellState.panelKind); }\n"
     "        }\n")
edit("shell.qml",
     "            focus: true\n"
     "            Keys.onEscapePressed: ShellState.closePanels()\n"
     "            ActivityIsland {\n"
     "                id: activityIsland; z: 2\n",
     "            focus: true\n"
     "            HoverHandler { id: probeHover }\n"
     "            Keys.onEscapePressed: { Probe.key(\"esc.overlay\"); ShellState.closePanels(); }\n"
     "            Keys.onPressed: event => Probe.key(\"unhandled.overlay\", \"code=\" + event.key + \" mod=\" + event.modifiers + \" ts=\" + event.timestamp)\n"
     "            readonly property var probeWindow: Window.window\n"
     "            Component.onCompleted: { Probe.hover = probeHover; Probe.loader = panelLoader; Probe.watchWindow(\"overlay\", overlay) }\n"
     "            Connections { target: probeWindow; function onFrameSwapped() { Probe.frame(\"overlay\") } }\n"
     "            ActivityIsland {\n"
     "                id: activityIsland; z: 2\n")
# shell.qml: the panel-open focus line has two shapes - the baseline (main, pre-fix) and
# the branch (post-fix). Both trees must be instrumentable: A-side and B-side of an A/B.
edit_any("shell.qml", [
    ("                    function onPanelOpenChanged() {\n"
     "                        if (ShellState.panelOpen) {\n"
     "                            if (panelLoader.item) (panelLoader.item as Item).forceActiveFocus();\n",
     "                    function onPanelOpenChanged() {\n"
     "                        Probe.mark(\"shell.panelOpen\" + \" state=\" + ShellState.panelOpen + \" activity=\" + ShellState.activityOpen + \" kind=\" + ShellState.panelKind + \" stage=\" + (panelLoader.item ? \"retained\" : \"none\"));\n"
     "                        if (ShellState.panelOpen) {\n"
     "                            if (panelLoader.item) (panelLoader.item as Item).forceActiveFocus();\n"
     "                            Qt.callLater(() => Probe.mark(\"shell.focusAfterOpen \" + Probe.focusOf(\"overlay\")));\n",
     "baseline (pre-fix) panel-open focus"),
    ("                    function onPanelOpenChanged() {\n"
     "                        if (ShellState.panelOpen) {\n"
     "                            // The panel stage is hidden while the activity island is the\n"
     "                            // open surface (shown: panelOpen && !activityOpen). Focusing a\n"
     "                            // hidden item clears the window's activeFocusItem, so no Keys\n"
     "                            // handler sees Escape any more and the island stops closing.\n"
     "                            if (panelLoader.item && !ShellState.activityOpen) (panelLoader.item as Item).forceActiveFocus();\n",
     "                    function onPanelOpenChanged() {\n"
     "                        Probe.mark(\"shell.panelOpen\" + \" state=\" + ShellState.panelOpen + \" activity=\" + ShellState.activityOpen + \" kind=\" + ShellState.panelKind + \" stage=\" + (panelLoader.item ? \"retained\" : \"none\"));\n"
     "                        if (ShellState.panelOpen) {\n"
     "                            // The panel stage is hidden while the activity island is the\n"
     "                            // open surface (shown: panelOpen && !activityOpen). Focusing a\n"
     "                            // hidden item clears the window's activeFocusItem, so no Keys\n"
     "                            // handler sees Escape any more and the island stops closing.\n"
     "                            if (panelLoader.item && !ShellState.activityOpen) (panelLoader.item as Item).forceActiveFocus();\n"
     "                            Qt.callLater(() => Probe.mark(\"shell.focusAfterOpen \" + Probe.focusOf(\"overlay\")));\n",
     "branch (post-fix) panel-open focus"),
], note="panel-open focus + marks")

# ---- Settings --------------------------------------------------------------------
edit("qml/settings/SettingsView.qml",
     "        history = history.concat(page); page = SettingsRegistry.page(key).key;\n",
     '        Probe.mark("settings.navigate " + page + ">" + key + " pending=" + (pageLoader.pending ? pageLoader.pending.pageKey : "-") + " prewarm=" + (pageLoader.prewarming ? pageLoader.prewarming.pageKey : "-"));\n'
     "        history = history.concat(page); page = SettingsRegistry.page(key).key;\n")
edit("qml/settings/SettingsView.qml",
     '    Shortcut { sequence: "Escape"; onActivated: { if (search.text) search.clear(); else root.closeRequested(); } }\n',
     '    Shortcut { sequence: "Escape"; onActivated: { Probe.key("esc.settingsShortcut", "search=" + search.text.length); if (search.text) search.clear(); else root.closeRequested(); } }\n')
edit("qml/settings/SettingsView.qml",
     "                    id: search\n"
     "                    Layout.fillWidth: true\n",
     '                    id: search\n'
     '                    objectName: "perfSearch"\n'
     "                    Layout.fillWidth: true\n")
edit("qml/settings/SettingsView.qml",
     "                            delegate: LiquidButton {\n"
     "                                id: nav\n"
     "                                required property var modelData\n",
     "                            delegate: LiquidButton {\n"
     "                                id: nav\n"
     '                                objectName: "perfNav_" + modelData.key\n'
     '                                Component.onCompleted: { Probe.nav[modelData.key] = this; Probe.mark("settings.nav " + modelData.key) }\n'
     "                                required property var modelData\n")
edit("qml/settings/SettingsView.qml",
     "        function onFrameSwapped() { root.framesRendered++ }\n",
     '        function onFrameSwapped() { root.framesRendered++; Probe.frame("settings") }\n')
edit("qml/settings/SettingsView.qml",
     "    property int framesRendered: 0\n",
     "    property int framesRendered: 0\n"
     '    Component.onCompleted: { Probe.settings = this; Probe.settingsHover = pointerWatch }\n'
     '    onHostWindowChanged: { Probe.mark("settings.window " + (hostWindow ? "up" : "down")); Probe.watchWindow("settings", hostWindow) }\n'
     "    function searchText() { return search.text }\n"
     '    function probePages() { return (FeatureCatalog.ready ? SettingsRegistry.pages : SettingsRegistry.legacyPages).map(p => p.key) }\n'

     '    function probeNavY() { return Math.round((navigationScroll ? navigationScroll.contentY : -1) * 10) / 10 }\n'
     '    function probeNavShown() { const out = {}; for (const k in Probe.nav) { const it = Probe.nav[k]; out[k] = !!(it && it.visible && it.width > 0); } return out }\n')
edit("qml/settings/WallpaperPage.qml",
     "            LiquidButton { text: ShellState.pendingActions.wallpaperScan ? \"Scanning…\" : \"Scan\"; enabled: !ShellState.pendingActions.wa",
     '            LiquidButton { objectName: "perfWallpaperScan"; text: ShellState.pendingActions.wallpaperScan ? \"Scanning…\" : \"Scan\"; enabled: !ShellState.pendingActions.wa')

edit("qml/settings/SettingsApplication.qml",
     "        function startupPending(): bool { return !root.startupFailed && (!root.initialized || view.status === Loader.Loading); }\n"
     "    }\n",
     "        function startupPending(): bool { return !root.startupFailed && (!root.initialized || view.status === Loader.Loading); }\n"
     "    }\n" + ipc_handler())
# One Component.onCompleted per object root: the pointer watch joins the existing registration
# (a second handler on the same root is a parse error that takes the whole Settings app down).
line("qml/settings/SettingsView.qml", "id: pageLoader", after=['probeName: "settings"'], note="name the Settings page host")
# The Settings window is a separate process: the shell never sets settingsOpen. What the user
# sees is the window, so its coming and going are marked where they happen, and the close
# button gets a name (the way a user closes a window that has no keyboard focus).
line("qml/settings/SettingsApplication.qml",
     "onPreparedChanged: if (prepared) { requestedPage = SettingsRegistry.page(requestedPage).key; initialized = true; }",
     old_sub="initialized = true; }", new_sub='initialized = true; Probe.mark("settings.ready"); }',
     note="cold start: the window is mapped")
line("qml/settings/SettingsApplication.qml", "            shown = true;", after=[
    'Probe.mark("settings.open " + root.requestedPage)'], note="warm reopen through the IPC")
line("qml/settings/SettingsApplication.qml", "    function close() {", after=[
    'Probe.mark("settings.close")'], note="the window is hidden (the linger starts)")
line("qml/settings/SettingsView.qml", 'tooltip: "Close settings"; onClicked: root.closeRequested() }',
     old_sub='IconButton { glyph:', new_sub='IconButton { objectName: "perfCloseSettings"; glyph:',
     note="the close button of the Settings window")

# ---- other Escape consumers (a swallowed Escape is the S4 signature) --------------
for _path, _count in ESC_SITES.items():
    _tag = Path(_path).stem.lower()
    edit(_path, "Keys.onEscapePressed: ShellState.closePanels()",
         'Keys.onEscapePressed: { Probe.key("esc.%s"); ShellState.closePanels(); }' % _tag, count=_count,
         note="plain Escape handler")
line("qml/panels/ControlDashboard.qml", "Keys.onEscapePressed: event => { if (root.editing)",
     old_sub="{ if (root.editing)", new_sub='{ Probe.key("esc.dashboard", "editing=" + root.editing); if (root.editing)',
     note="dashboard Escape (swallowed while editing)")
line("qml/panels/ClipboardPanel.qml", "Keys.onEscapePressed: { if (previewImage)",
     old_sub="{ if (previewImage)", new_sub='{ Probe.key("esc.clipboard", "preview=" + (previewImage ? 1 : 0)); if (previewImage)',
     note="clipboard Escape (swallowed by the image preview)")
line("qml/panels/Launcher.qml", "if (event.key === Qt.Key_Escape) { ShellState.closePanels();",
     old_sub="{ ShellState.closePanels();", new_sub='{ Probe.key("esc.launcher"); ShellState.closePanels();',
     note="launcher Escape")

ALL = EDITS + LINE_EDITS


def indent_of(text_line):
    return text_line[:len(text_line) - len(text_line.lstrip())]


def apply(tree: Path, check_only: bool) -> list:
    """Apply every edit; return the list of applied notes. Raises SystemExit on any mismatch."""
    files = {}
    for target in sorted({e.path for e in ALL}):
        path = tree / target
        if not path.is_file():
            sys.exit(f"PROBE PATCH REFUSED: {path} is missing")
        files[target] = path.read_text()
    already = any("Probe." in text for target, text in files.items() if target != "qml/services/qmldir")
    if already and not check_only:
        sys.exit("PROBE PATCH REFUSED: the tree already carries probe code (patch a pristine copy)")
    for e in ALL:
        if isinstance(e, EditAny):
            if check_only:
                # A checked tree carries one of the substituted variants.
                if not any(files[e.path].count(new) == e.count for _, new, _ in e.variants):
                    sys.exit(f"PROBE PATCH CHECK FAILED: {e.path}: no applied variant found ({e.note})")
                continue
            for old, new, note in e.variants:
                if files[e.path].count(old) == e.count:
                    files[e.path] = files[e.path].replace(old, new)
                    break
            else:
                shapes = "; ".join(f"{note}: {old.count('forceActiveFocus') and 'focus line' or '?'}" for old, _, note in e.variants)
                sys.exit(f"PROBE PATCH: {e.path}: no variant anchor matched ({e.note}; tried {shapes})")
            continue
        if isinstance(e, Edit):
            if check_only:
                if files[e.path].count(e.new) != e.count:
                    sys.exit(f"PROBE PATCH CHECK FAILED: {e.path}: expected edit missing ({e.note or e.old[:60]!r})")
                continue
            found = files[e.path].count(e.old)
            if found != e.count:
                sys.exit(f"PROBE PATCH: {e.path}: expected {e.count} anchor(s), found {found} ({e.note or e.old[:60]!r})")
            files[e.path] = files[e.path].replace(e.old, e.new)
            continue
        lines = files[e.path].split("\n")
        # A checked tree carries the substituted line, so look for that variant there.
        wanted = e.needle.replace(e.old_sub, e.new_sub) if check_only and e.old_sub else e.needle
        hits = [i for i, text in enumerate(lines) if wanted in text]
        if len(hits) != 1:
            sys.exit(f"PROBE PATCH: {e.path}: needle {e.needle!r} matched {len(hits)} lines, expected 1 ({e.note})")
        i = hits[0]
        pad = indent_of(lines[i])
        if check_only:
            for offset, extra in enumerate(e.insert_after):
                if i + 1 + offset >= len(lines) or lines[i + 1 + offset] != pad + extra:
                    sys.exit(f"PROBE PATCH CHECK FAILED: {e.path}: missing line after {e.needle!r}")
            continue
        if e.old_sub and lines[i].count(e.old_sub) != 1:
            sys.exit(f"PROBE PATCH: {e.path}: {e.old_sub!r} occurs {lines[i].count(e.old_sub)}x on the line with {e.needle!r}")
        text = lines[i].replace(e.old_sub, e.new_sub) if e.old_sub else lines[i]
        lines[i] = text
        for offset, extra in enumerate(e.insert_after):
            lines.insert(i + 1 + offset, pad + extra)
        files[e.path] = "\n".join(lines)
    if check_only:
        # A checked tree must carry the results, not the anchors.
        if not (tree / PROBE_FILE).is_file() or (tree / PROBE_FILE).read_text() != PROBE_SRC.read_text():
            sys.exit(f"PROBE PATCH CHECK FAILED: {PROBE_FILE} is missing or stale")
        return []
    for target, text in files.items():
        (tree / target).write_text(text)
    (tree / PROBE_FILE).write_text(PROBE_SRC.read_text())
    (tree / MARKER).write_text(json.dumps({"edits": len(ALL),
        "sha": hashlib.sha256(Path(__file__).read_bytes() + PROBE_SRC.read_bytes()).hexdigest()}, indent=1) + "\n")
    return [e.note or e.path for e in ALL]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path)
    ap.add_argument("--check", action="store_true", help="verify an already patched tree")
    ap.add_argument("--list", action="store_true", help="print the edits and exit")
    args = ap.parse_args()
    if args.list:
        for e in ALL:
            print(f"{e.path}: {e.note or (e.old[:70] if isinstance(e, Edit) else e.needle)!r}")
        return 0
    if not args.src:
        ap.error("--src is required")
    tree = args.src.resolve()
    if (tree / ".git").exists():
        sys.exit("PROBE PATCH REFUSED: --src is a git clone; instrument a copy made by prepare.py")
    notes = apply(tree, args.check)
    print(f"probe patch: {len(notes) or len(ALL)} edits {'verified' if args.check else 'applied'} in {tree}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
