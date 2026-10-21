"""Faults and observation live only in fully copied private checkouts."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from catalog_fixture import REPO, inject

FAULTS = ('missing_index', 'malformed_json', 'unsupported_version', 'descriptor_missing',
          'path_traversal', 'symlink_escape', 'duplicate_id', 'validation_timeout',
          'legacy_bar_id', 'legacy_page_id', 'legacy_tab_id')
OBSERVE = '''
    IpcHandler {
        target: "catalogFailure"
        function state(): string {
            return JSON.stringify({settled: FeatureCatalog.settled, error: FeatureCatalog.error,
                status: ShellState.statusMessage, ready: ShellState.backendReady,
                bars: BarRegistry.modules.map(item => item.id), pages: SettingsRegistry.pages.map(item => item.key),
                tabs: ControlRegistry.tabs.map(item => item.id), control: ShellState.controlOpen,
                page: ShellState.settingsApp ? root.requestedPage : ""});
        }
    }
'''


def damage(root, fault):
    descriptor = inject(root)
    index = root/'config/features.json'
    if fault == 'missing_index': index.unlink()
    elif fault == 'malformed_json': index.write_text('{bad json')
    elif fault == 'unsupported_version': index.write_text('{"version":99,"features":[]}')
    elif fault == 'descriptor_missing': (root/'config/feature-fixture.json').unlink()
    elif fault == 'path_traversal':
        data = json.loads(index.read_text()); data['features'][0]['descriptor'] = '../outside.json'
        index.write_text(json.dumps(data))
    elif fault == 'symlink_escape':
        outside = root.parent/'outside.qml'; outside.write_text('import QtQuick\nItem {}')
        path = root/'qml/bar/CatalogFixture.qml'; path.unlink(); path.symlink_to(outside)
    elif fault == 'duplicate_id':
        data = json.loads(index.read_text()); data['features'] *= 2; index.write_text(json.dumps(data))
    elif fault.startswith('legacy_'):
        kind, key, value = {'legacy_bar_id': ('bar', 'id', 'audio'),
            'legacy_page_id': ('settingsPage', 'key', 'appearance'),
            'legacy_tab_id': ('controlTab', 'id', 'audio')}[fault]
        descriptor[kind][key] = value
        (root/'config/feature-fixture.json').write_text(json.dumps(descriptor))
    elif fault == 'validation_timeout':
        path = root/'scripts/feature_catalog.py'
        source = path.read_text().replace('def document(path):', 'def document(path):\n    __import__("time").sleep(10)')
        path.write_text(source)
    else: raise ValueError(fault)


class Probe:
    def __init__(self, root, entry, env, process, log):
        self.root, self.entry, self.env, self.process, self.log = root, entry, env, process, log

    def ipc(self, target, method, *args):
        return subprocess.check_output(['quickshell', '-p', str(self.entry), 'ipc', 'call', target, method, *args],
            env=self.env, text=True, stderr=subprocess.DEVNULL, timeout=3).strip()

    def wait(self, predicate, timeout=12):
        deadline = time.monotonic() + timeout
        state = {}
        while time.monotonic() < deadline:
            if self.process.poll() is not None: break
            try:
                state = json.loads(self.ipc('catalogFailure', 'state'))
                if predicate(state): return state
            except (subprocess.CalledProcessError, ValueError): pass
            time.sleep(.03)
        self.log.seek(0)
        raise AssertionError(str(state)+'\n'+self.log.read())


@contextmanager
def session(mode, fault):
    with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
        root = Path(directory)/'checkout'
        shutil.copytree(REPO, root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        damage(root, fault)
        if mode == 'shell':
            source = root/'shell.qml'
            code = source.read_text().replace('import "qml/services"', 'import "qml/services"\nimport "qml/bar"\nimport "qml/settings"')
            entry = source
        else:
            source = root/'qml/settings/SettingsApplication.qml'
            code = source.read_text().replace('import "../services"', 'import "../services"\nimport "../bar"')
            entry = root/'settings-demo.qml'
        source.write_text(code.replace('    id: root\n', '    id: root\n'+OBSERVE, 1))
        runtime = Path(directory)/'runtime'; runtime.mkdir(mode=0o700)
        wayland = str(Path(os.environ['XDG_RUNTIME_DIR'])/os.environ['WAYLAND_DISPLAY'])
        env = dict(os.environ, LME_SHELL_DEMO='1', PYTHONDONTWRITEBYTECODE='1', QT_QPA_PLATFORM='wayland', QT_QUICK_BACKEND='rhi',
            XDG_CONFIG_HOME=directory+'/config', XDG_STATE_HOME=directory+'/state', XDG_CACHE_HOME=directory+'/cache',
            XDG_DATA_HOME=directory+'/data', XDG_RUNTIME_DIR=str(runtime), WAYLAND_DISPLAY=wayland,
            DBUS_SYSTEM_BUS_ADDRESS='unix:path='+directory+'/no-system-bus')
        env.pop('LME_SHELL_PREVIEW', None)
        argv = ['quickshell', '-p', str(entry)] if mode == 'shell' else [str(root/'scripts/settings.sh'), '--demo', '--page', 'appearance']
        process = subprocess.Popen(argv, env=env, stdout=log, stderr=log)
        try: yield Probe(root, entry, env, process, log)
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=4)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)
        log.seek(0); text = log.read()
        for error in ('ReferenceError', 'TypeError', 'Binding loop', 'Failed to load configuration'):
            if error in text: raise AssertionError(text)
