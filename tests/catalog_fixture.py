"""Disposable catalog probes; native extension tests use a copied checkout."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
QML = '''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/bar"
import "qml/settings"
import "qml/services"
import "qml/panels"
ShellRoot {
    function find(item, name) {
        if (!item) return false;
        if (item.objectName === name) return true;
        for (const child of item.children || []) if (find(child, name)) return true;
        return false;
    }
    FloatingWindow {
        id: window; implicitWidth: 1100; implicitHeight: 780
        Loader { id: bar; active: false; sourceComponent: BarModule { moduleId: "catalogFixture" } }
        Loader { id: page; anchors.fill: parent; active: false; sourceComponent: SettingsView { page: "catalogFixture" } }
        Loader { id: center; anchors.fill: parent; active: false; sourceComponent: ControlCenter {} }
    }
    IpcHandler {
        target: "catalogFixture"
        function state(): string {
            return JSON.stringify({registriesReady: FeatureCatalog.settled, bars: BarRegistry.modules, defaults: BarRegistry.defaults,
                pages: SettingsRegistry.pages, tabs: ControlRegistry.tabs, agenda: ControlRegistry.agendaTabs,
                barLoaded: find(bar.item, "injectedBar"), pageLoaded: find(page.item, "injectedPage"),
                tabLoaded: find(center.item, "injectedTab")});
        }
        function entries(): void { bar.active = true; page.active = true; }
        function control(): void { page.active = false; center.active = true; center.item.selectTab("catalogFixture"); }
    }
}
'''


class Probe:
    def __init__(self, root, entry, env, log):
        self.root, self.entry, self.env, self.log = root, entry, env, log

    def call(self, method, *args):
        return subprocess.check_output(['quickshell', '-p', str(self.entry), 'ipc', 'call',
            'catalogFixture', method, *args], env=self.env, text=True, stderr=subprocess.DEVNULL, timeout=4).strip()

    def wait(self, predicate):
        deadline = time.monotonic() + 12
        state = {}
        while time.monotonic() < deadline:
            try:
                state = json.loads(self.call('state'))
                if predicate(state): return state
            except (ValueError, subprocess.CalledProcessError): pass
            time.sleep(.03)
        self.log.seek(0)
        raise AssertionError(str(state) + '\n' + self.log.read())


@contextmanager
def session(native=False, prepare=None):
    with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
        root = Path(directory)/'checkout'
        if native:
            shutil.copytree(REPO, root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        else:
            root.mkdir()
            for name in ('qml', 'config', 'scripts', 'assets'):
                (root/name).symlink_to(REPO/name, target_is_directory=True)
        entry = root/'catalog-fixture.qml'; entry.write_text(QML)
        if prepare: prepare(root)
        env = dict(os.environ, LME_SHELL_DEMO='1', PYTHONDONTWRITEBYTECODE='1', XDG_CONFIG_HOME=directory+'/user-config',
            XDG_STATE_HOME=directory+'/state', XDG_DATA_HOME=directory+'/data', XDG_CACHE_HOME=directory+'/cache',
            DBUS_SYSTEM_BUS_ADDRESS='unix:path='+directory+'/no-system-bus',
            QT_QPA_PLATFORM='wayland' if native else 'offscreen', QT_QUICK_BACKEND='rhi' if native else 'software')
        process = subprocess.Popen(['quickshell', '-p', str(entry)], env=env, stdout=log, stderr=log)
        try:
            probe = Probe(root, entry, env, log)
            probe.wait(lambda state: state['registriesReady'] and len(state['tabs']) >= 6)
            yield probe
        finally:
            process.terminate(); process.wait(timeout=6)
        log.seek(0); text = log.read()
        for error in ('ReferenceError', 'TypeError', 'Binding loop', 'Failed to load configuration'):
            if error in text: raise AssertionError(text)


def inject(root, enabled=True):
    descriptor = {'id': 'catalogFixture', 'sources': [], 'preferences': {'catalogFixtureSetting': {'type': 'boolean', 'default': True}},
        'bar': {'id': 'catalogFixture', 'title': 'Fixture bar', 'icon': 'applications', 'entry': 'qml/bar/CatalogFixture.qml'},
        'settingsPage': {'key': 'catalogFixture', 'title': 'Fixture page', 'icon': 'settings',
            'description': 'Catalog fixture', 'keywords': 'fixture', 'entry': 'qml/settings/CatalogFixture.qml'},
        'controlTab': {'id': 'catalogFixture', 'title': 'Fixture tab', 'entry': 'qml/panels/CatalogFixture.qml'}}
    for path, name in [('qml/bar/CatalogFixture.qml', 'injectedBar'), ('qml/settings/CatalogFixture.qml', 'injectedPage'),
                       ('qml/panels/CatalogFixture.qml', 'injectedTab')]:
        (root/path).write_text('import QtQuick\nItem { objectName: "'+name+'"; implicitWidth: 40; implicitHeight: 80 }\n')
    (root/'config/feature-fixture.json').write_text(json.dumps(descriptor))
    record = {'id': 'catalogFixture', 'descriptor': 'config/feature-fixture.json', 'enabled': enabled}
    if (root/'catalog-fixture.qml').exists():
        record['startup'] = {kind: descriptor[kind] for kind in ('bar', 'settingsPage', 'controlTab')}
    index = root/'config/features.json'
    existing = json.loads(index.read_text())['features'] if index.exists() else []
    index.write_text(json.dumps({'version': 1, 'features': [record] +
        [item for item in existing if item['id'] != record['id']]}))
    return descriptor


def legacy_expected():
    """Frozen metadata minus only ownership declared by the shipped catalog."""
    import sys
    sys.path.insert(0, str(REPO/'scripts'))
    from feature_catalog import load_catalog
    expected = json.loads((REPO/'tests/fixtures/catalog-legacy.json').read_text())
    catalog = load_catalog(REPO)
    for kind, source, key in [('bars', 'bar', 'id'), ('pages', 'settingsPage', 'key'), ('tabs', 'controlTab', 'id')]:
        expected[kind] = [item for item in expected[kind] if item[key] not in catalog['ids'][source]]
    return expected
