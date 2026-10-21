"""Real shell/Settings in a copied checkout; only the copy gains observability."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from clipboard import History
from test_clipboard import PNG

ROOT = Path(__file__).resolve().parents[1]
OBSERVE = '''
    property var sliceBars: []
    property var sliceSurface: null
    property var sliceFirstVisible: null
    property real sliceProgress: 0
    function sliceFind(item, name) {
        if (!item) return null;
        if (item.objectName === name || item.placeholderText === name || item.text === name) return item;
        for (const child of item.children || []) {
            const result = sliceFind(child, name); if (result) return result;
        }
        return null;
    }
    IpcHandler {
        target: "clipboardSlice"
        function state(): string {
            return JSON.stringify({ready: ShellState.backendReady && FeatureCatalog.settled,
                started: ClipboardState.started, workerReady: ClipboardState.ready,
                capturing: ClipboardState.capturing, count: ClipboardState.total,
                open: ShellState.panelOpen && ShellState.panelKind === "clipboard",
                history: !!root.sliceFind(root.sliceSurface, "Search clipboard history"),
                settings: ShellState.settingsApp, demo: ShellState.demo,
                firstVisible: root.sliceFirstVisible,
                visible: !!root.sliceSurface && root.sliceSurface.width > 0,
                progress: root.sliceProgress,
                page: ShellState.settingsPage, status: ShellState.statusMessage, panelKind: ShellState.panelKind, panelOpen: ShellState.panelOpen,
                bars: BarRegistry.modules.map(item => item.id),
                pages: SettingsRegistry.pages.map(item => item.key),
                gestures: BarGestures.actions.map(item => item.id),
                preferences: ShellState.preferences, lastResult: ShellState.lastResult});
        }
        function point(name: string): string {
            let button = root.sliceFind(root.sliceSurface, name);
            if (button) { const p = button.mapToItem(null, button.width/2, button.height/2); return JSON.stringify({x:p.x,y:p.y}); }
            for (const window of root.sliceBars) {
                button = root.sliceFind(window.contentItem, name);
                if (button) { const p = button.mapToItem(window.contentItem, button.width/2, button.height/2);
                    return JSON.stringify({x:p.x+Theme.barSideMargin,y:p.y+(Theme.barBottom?window.screen.height-Theme.barHeight:Theme.barTopMargin)}); }
            }
            return "null";
        }
        function capture(value: bool): void { ShellState.run("setting", {key:"clipboardEnabled",value}); }
        function search(text: string): bool {
            const field = root.sliceFind(root.sliceSurface, "Search settings");
            if (!field) return false; field.text = text; field.accepted(); return true;
        }
        function page(): string {
            const heading = root.sliceFind(root.sliceSurface, "Your clipboard, within reach");
            return heading ? "clipboard" : "";
        }
        function gesture(): void {
            const old = ShellState.snapshot;
            ShellState.snapshot = Object.assign({}, old, {preferences:Object.assign({},old.preferences,
                {barGestures:{clipboard:{right:"clipboard"}}})});
            BarGestures.perform("clipboard", "right", Quickshell.screens[0]);
        }
    }
'''


class World:
    def __init__(self, directory):
        self.home = directory; self.root = directory/'checkout'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        for name in ('config', 'state', 'data', 'cache', 'runtime'): (directory/name).mkdir(mode=0o700)
        self.settings = directory/'config/lme-shell/settings.json'; self.settings.parent.mkdir()
        self.settings.write_text(json.dumps(dict(clipboardEnabled=False, weatherAutoLocation=False, captureEditor='satty')))
        (directory/'config/user-dirs.dirs').write_text('XDG_PICTURES_DIR="'+str(directory/'Pictures')+'"\n')
        history = History(directory/'state/lme-shell/clipboard')
        history.store('text', b'Clipboard slice persisted text'); history.store('image', PNG); history.db.close()
        worker = self.root/'scripts/clipboard.py'; actual = worker.with_name('clipboard_slice_actual.py')
        shutil.copy2(worker, actual)
        worker.write_text('import os,sys\nfrom pathlib import Path\np=Path(os.environ["SLICE_WORKERS"])\n'
            'with p.open("a") as f: f.write(str(os.getpid())+"\\n")\n'
            'os.execv(sys.executable,[sys.executable,str(Path(__file__).with_name("clipboard_slice_actual.py"))])\n')
        binary = directory/'bin/satty'; binary.parent.mkdir()
        binary.write_text('#!'+sys.executable+'\nimport os,json,sys\nfrom pathlib import Path\n'
            'Path(os.environ["SLICE_EDITOR"]).write_text(json.dumps(sys.argv[1:]))\n'); binary.chmod(0o700)
        self.marker = directory/'workers.log'; self.editor = directory/'editor.json'
        wayland = str(Path(os.environ['XDG_RUNTIME_DIR'])/os.environ['WAYLAND_DISPLAY'])
        self.env = dict(os.environ, LME_SHELL_DEMO='0', LME_SHELL_BACKEND_DEMO='0',
            WAYLAND_DISPLAY=wayland, XDG_CONFIG_HOME=str(directory/'config'), XDG_STATE_HOME=str(directory/'state'),
            XDG_DATA_HOME=str(directory/'data'), XDG_CACHE_HOME=str(directory/'cache'), XDG_RUNTIME_DIR=str(directory/'runtime'),
            PATH=str(binary.parent)+':'+os.environ['PATH'], SLICE_WORKERS=str(self.marker), SLICE_EDITOR=str(self.editor),
            DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(directory/'no-system-bus'), NIRI_SOCKET=str(directory/'no-niri'))
        self.env.pop('LME_SHELL_PREVIEW', None); self.env.pop('LME_SHELL_SETTINGS', None)
        shell = self.root/'shell.qml'; text = shell.read_text()
        text = text.replace('import "qml/services"', 'import "qml/services"\nimport "qml/bar"\nimport "qml/settings"')
        text = text.replace('    id: root\n', '    id: root\n'+OBSERVE+'\n    Binding { target: root; property: "sliceSurface"; value: overlay.contentItem }\n    Binding { target: root; property: "sliceProgress"; value: panelLoader.progress }\n', 1)
        text = text.replace('id: barWindow\n', 'id: barWindow\n                Component.onCompleted: root.sliceBars = root.sliceBars.concat(barWindow)\n')
        shell.write_text(text)
        settings = self.root/'qml/settings/SettingsApplication.qml'; text = settings.read_text()
        text = text.replace('import "../services"', 'import "../services"\nimport "../bar"')
        text = text.replace('    id: root\n', '    id: root\n'+OBSERVE+'\n    Binding { target: root; property: "sliceSurface"; value: view.item }\n', 1)
        text = text.replace('        id: window\n', '        id: window\n        onVisibleChanged: if (visible && !root.sliceFirstVisible) root.sliceFirstVisible = {catalog:FeatureCatalog.ready,theme:Theme.ready,backend:ShellState.backendReady}\n')
        settings.write_text(text)

    def workers(self):
        return self.marker.read_text().splitlines() if self.marker.exists() else []

    @contextmanager
    def launch(self, mode='shell', page='clipboard'):
        env = dict(self.env)
        if mode in ('demo', 'preview'): env['LME_SHELL_DEMO'] = '1'
        if mode == 'preview': env['LME_SHELL_PREVIEW'] = '1'
        entry = self.root/('settings.qml' if mode == 'settings' else 'shell.qml')
        with tempfile.TemporaryFile(mode='w+') as log:
            argv = [str(self.root/'scripts/settings.sh'), '--page', page] if mode == 'settings' else ['quickshell', '-p', str(entry)]
            process = subprocess.Popen(argv, env=env, stdout=log, stderr=log)
            probe = Probe(entry, env, process, log)
            try:
                probe.wait(lambda state: state.get('ready'))
                if mode == 'settings': probe.wait(lambda state: state['visible'])
                yield probe
            finally:
                if process.poll() is None: process.terminate(); process.wait(timeout=8)
            log.seek(0); output = log.read()
            for error in ('ReferenceError', 'TypeError', 'Binding loop', 'Failed to load configuration', 'Unable to assign'):
                if error in output: raise AssertionError(output)


class Probe:
    def __init__(self, entry, env, process, log):
        self.entry, self.env, self.process, self.log = entry, env, process, log

    def call(self, method, *args, target='clipboardSlice'):
        return subprocess.check_output(['quickshell', '-p', str(self.entry), 'ipc', 'call', target, method, *args],
            env=self.env, text=True, stderr=subprocess.DEVNULL, timeout=4).strip()

    def wait(self, predicate):
        deadline = time.monotonic()+15; state = {}
        while time.monotonic()<deadline and self.process.poll() is None:
            try:
                state = json.loads(self.call('state'))
                if predicate(state): return state
            except (ValueError, subprocess.CalledProcessError): pass
            time.sleep(.05)
        self.log.seek(0); raise AssertionError(str(state)+'\n'+self.log.read())

    def click(self, name):
        if name.startswith('clipboard'): self.wait(lambda state: state['progress'] == 1)
        point = json.loads(self.call('point', name))
        if point is None: raise AssertionError('No visible control: '+name)
        subprocess.run([os.environ['LME_TEST_POINTER'], str(point['x']), str(point['y'])], env=self.env, check=True, timeout=5)
