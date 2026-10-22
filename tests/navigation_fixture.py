"""Private QML navigation probe shared by characterization and Wayland checks."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


QML = '''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import QtQuick.Window
import Quickshell
import Quickshell.Io
import "qml/panels"
import "qml/services"
import "qml/bar"
ShellRoot {
    id: root
    property int refreshes: 0
    Connections { target: ShellState; function onLastResultChanged() {
        if (ShellState.lastResult?.action === "controlsRefresh") root.refreshes++;
    } }
    FloatingWindow {
        id: window; implicitWidth: 1050; implicitHeight: 1000; fullscreen: true
        property int frames: 0
        Connections { target: window.contentItem.Window.window; function onFrameSwapped() { window.frames++; } }
        BarModule { id: bar; objectName: "navigationBar"; moduleId: "audio"; anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter }
        Loader { id: center; anchors.fill: parent; anchors.topMargin: 60; active: false; sourceComponent: ControlCenter {} }
        Loader { id: agenda; anchors.fill: parent; anchors.topMargin: 60; active: false; sourceComponent: Agenda {} }
    }
    function find(item, name) {
        if (!item) return null;
        if (item.objectName === name || item.text === name || item.placeholderText === name) return item;
        for (const child of item.children || []) { const result = find(child, name); if (result) return result; }
        if (item.contentItem && item.contentItem !== item) return find(item.contentItem, name);
        return null;
    }
    function page(item) {
        if (!item) return "";
        const types = {ControlDashboard:"controls", AudioMixer:"audio", DeviceControls:"devices", Agenda:"agenda", NotificationCenter:"notifications", SystemMonitor:"system"};
        for (const type of Object.keys(types)) if (String(item).startsWith(type + "_")) return types[type];
        for (const child of item.children || []) { const result = page(child); if (result) return result; }
        return "";
    }
    IpcHandler {
        target: "navigationFixture"
        function open(): void { center.active = true; }
        function closePanels(): void { ShellState.closePanels(); }
        function setVisible(value: string): void { center.visible = value === "true"; }
        function number(value: int): void { center.item.currentTab = value; }
        function globalNumber(value: int): void { ShellState.controlTab = value; }
        function focus(): void { center.item.forceActiveFocus(); }
        function seed(): void { Notifications.unreadCount = 7; }
        function setting(key: string, value: string): void { ShellState.run("setting", {key, value: JSON.parse(value)}); }
        function agendaNumber(value: int): void { center.active = false; agenda.active = true; agenda.item.tab = value; }
        function initializedGuard(): bool {
            center.item.initialized = false; center.item.refreshControls();
            const blocked = !ShellState.pendingActions.controlsRefresh;
            center.item.initialized = true; return blocked;
        }
        function backendGuard(): bool {
            center.item.currentTab = 1; ShellState.backendReady = false;
            center.item.currentTab = 0; center.item.refreshControls();
            const blocked = !ShellState.pendingActions.controlsRefresh;
            center.item.currentTab = 1; ShellState.backendReady = true; return blocked;
        }
        function state(): string {
            const item = center.item, indicator = root.find(item, "controlTabIndicator");
            return JSON.stringify({ready: ShellState.backendReady, pending: Object.values(ShellState.pendingActions).some(v => v),
                preferences: ShellState.preferences, current: item ? item.currentTab : -1, global: ShellState.controlTab,
                tabs: item ? item.tabs : [], selected: indicator?.targetItem?.text || "", refreshes: root.refreshes,
                unread: Notifications.unreadCount, controlOpen: ShellState.controlOpen,
                kind: root.page(item),
                notes: !!root.find(agenda.item,"Notes"), editor: !!root.find(agenda.item,"quickNotesEditor"),
                tasks: !!root.find(agenda.item,"Add a task…"), timer: !!root.find(agenda.item,"Focus timer")});
        }
        function position(name: string): string {
            const item = root.find(window.contentItem, name);
            if (!item) return "{}";
            for (let p = item.parent; p; p = p.parent) if (typeof p.contentY === "number" && p.contentItem) {
                const point = item.mapToItem(p.contentItem, 0, 0);
                if (point.y < p.contentY || point.y + item.height > p.contentY + p.height)
                    p.contentY = Math.max(0, Math.min(p.contentHeight - p.height, point.y - 20));
            }
            const point = item.mapToGlobal(item.width / 2, item.height / 2);
            window.contentItem.Window.window.update();
            return JSON.stringify({x: Math.round(point.x), y: Math.round(point.y), frame: window.frames, ready: item.visible && item.enabled});
        }
    }
}
'''


class Probe:
    def __init__(self, entry, env, log):
        self.entry, self.env, self.log = entry, env, log

    def call(self, name, *args):
        result = subprocess.run(['quickshell', '-p', str(self.entry), 'ipc', 'call',
                                 'navigationFixture', name, *map(str, args)],
                                env=self.env, text=True, capture_output=True, timeout=4)
        if result.returncode: raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)
        return result.stdout.strip()

    def wait(self, predicate):
        deadline = time.monotonic() + 12
        state = {}
        while time.monotonic() < deadline:
            try:
                state = json.loads(self.call('state'))
                if state.get('ready') and not state.get('pending') and predicate(state): return state
            except (ValueError, subprocess.CalledProcessError): pass
            time.sleep(.05)
        self.log.seek(0)
        raise AssertionError(str(state) + '\n' + self.log.read())

    def click(self, name):
        previous = None
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            point = json.loads(self.call('position', name))
            if point.get('ready') and previous and point['frame'] > previous['frame'] and (point['x'], point['y']) == (previous['x'], previous['y']):
                subprocess.run([self.env['LME_TEST_POINTER'], str(point['x']), str(point['y'])], env=self.env, check=True, timeout=5)
                return
            previous = point
            time.sleep(.05)
        raise AssertionError('Click target did not settle: ' + name)


@contextmanager
def session(native=False, environment=None, catalog=None):
    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
        root = Path(directory)
        for name in ('qml', 'scripts', 'assets'): (root/name).symlink_to(repo/name, target_is_directory=True)
        if catalog is None: (root/'config').symlink_to(repo/'config', target_is_directory=True)
        else:
            (root/'config').mkdir()
            for path in (repo/'config').iterdir():
                if path.name not in ('control-grid.json', 'features.json'): (root/'config'/path.name).symlink_to(path)
            # Keep the reordered fixture authoritative across legacy/catalog ownership.
            index = json.loads((repo/'config/features.json').read_text())
            tabs = list(catalog['tabs'])
            for record in index['features']:
                entry = record.get('startup', {}).get('controlTab')
                if not entry: continue
                position = next((i for i,t in enumerate(tabs) if t['id'] == entry['id']), None)
                if position is not None:
                    record['startup']['controlTab'] = dict(entry, after=tabs[position-1]['id'])
                    tabs.pop(position)
            (root/'config/features.json').write_text(json.dumps(index))
            (root/'config/control-grid.json').write_text(json.dumps(dict(catalog,tabs=tabs)))
        entry = root/'shell.qml'; entry.write_text(QML)
        env = dict(os.environ, LME_SHELL_DEMO='1', XDG_CONFIG_HOME=str(root/'home'), XDG_STATE_HOME=str(root/'state'),
                   XDG_DATA_HOME=str(root/'data'), DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(root/'no-system-bus'),
                   LME_SHELL_CONTROL_TAB='', QT_QPA_PLATFORM='wayland' if native else 'offscreen',
                   QT_QUICK_BACKEND='rhi' if native else 'software')
        env.update(environment or {})
        keyboard = subprocess.Popen(['wtype', '-s', '60000'], env=env) if native else None
        process = subprocess.Popen(['quickshell', '-p', str(entry)], env=env, stdout=log, stderr=log)
        try:
            probe = Probe(entry, env, log); probe.wait(lambda s: True)
            yield probe
        finally:
            process.terminate(); process.wait(timeout=6)
            if keyboard: keyboard.terminate(); keyboard.wait(timeout=3)
        log.seek(0); content = log.read()
        for error in ('ReferenceError', 'TypeError', 'Binding loop', 'Unable to assign', 'Failed to load configuration'):
            if error in content: raise AssertionError(content)
