"""Observe the actual shell/Settings only in a disposable copied checkout."""
from contextlib import contextmanager
import json
from pathlib import Path

from clipboard_slice_fixture import World, Probe as SliceProbe, ROOT

FEATURES = {
    'nightLight': ('NightLightPage', 'Warmer evenings', 'nightLightTemperature', 4700),
    'idle': ('IdlePage', 'Laptop idle profiles', 'idleLockBeforeSleep', False),
    'keybinds': ('KeybindsPage', 'Niri keybindings', 'niriConfigPath', ''),
    'weather': ('WeatherPage', 'Find me automatically', 'weatherUnit', 'fahrenheit'),
}
QUERIES = ['', 'temperature', 'config', 'blue', 'battery', 'location', 'idle', 'keys', 'weather']
OBSERVE = '''
    IpcHandler {
        target: "lightFeatures"
        function state(): string {
            const surface = root.sliceSurface;
            const query = ["", "temperature", "config", "blue", "battery", "location", "idle", "keys", "weather"];
            const marks = ["Warmer evenings", "Laptop idle profiles", "Niri keybindings", "Find me automatically", "Fifth feature"];
            const weatherRoute = root.sliceFind(surface, "Weather location settings");
            return JSON.stringify({ready: ShellState.backendReady && FeatureCatalog.ready && Theme.ready,
                page: surface && surface.page || ShellState.settingsPage, panelOpen: ShellState.panelOpen, progress: root.sliceProgress,
                pages: SettingsRegistry.pages.map(p => p.key), searches: query.map(q => SettingsRegistry.search(q).map(p => p.key)),
                marks: marks.filter(name => !!root.sliceFind(surface, name)), preferences: ShellState.preferences,
                lastResult: ShellState.lastResult, weatherRouteEnabled: weatherRoute ? weatherRoute.enabled : null,
                nightTile: !!root.sliceFind(surface, "controlTile-nightLight") && root.sliceFind(surface, "controlTile-nightLight").visible,
                idleTile: !!root.sliceFind(surface, "controlTile-stayAwake") && root.sliceFind(surface, "controlTile-stayAwake").visible,
                weatherCard: !!root.sliceFind(surface, "controlCard-weather") && root.sliceFind(surface, "controlCard-weather").visible,
                weatherGear: !!root.sliceFind(surface, "Weather settings")});
        }
        function open(page: string): void { ShellState.openSettingsPage(page); }
        function setting(key: string, value: string): void { ShellState.run("setting", {key:key,value:JSON.parse(value)}); }
        function search(text: string): bool {
            const field = root.sliceFind(root.sliceSurface, "Search settings");
            if (!field) return false; field.text = text; field.accepted(); return true;
        }
        function gear(): bool {
            const button = root.sliceFind(root.sliceSurface, "Weather settings");
            if (!button || !button.enabled) return false; button.clicked(); return true;
        }
    }
'''


class Probe(SliceProbe):
    def call(self, method, *args, target='lightFeatures'):
        return super().call(method, *args, target=target)


class LightWorld(World):
    def __init__(self, directory):
        super().__init__(directory)
        for name in ('shell.qml', 'qml/settings/SettingsApplication.qml'):
            path = self.root/name
            text = path.read_text().replace('    id: root\n', '    id: root\n'+OBSERVE, 1)
            text = text.replace('item.text === name)', 'item.text === name || item.tooltip === name)')
            path.write_text(text)

    @contextmanager
    def launch(self, mode='demo', page='appearance'):
        with super().launch(mode, page) as original:
            probe = Probe(original.entry, original.env, original.process, original.log)
            probe.wait(lambda state: state['ready'])
            yield probe

    def toggle(self, feature, enabled):
        from feature_catalog import canonical_index
        path = self.root/'config/features.json'; data = json.loads(path.read_text())
        next(record for record in data['features'] if record['id'] == feature)['enabled'] = enabled
        path.write_text(canonical_index(data))


def converted(root=ROOT):
    index = json.loads((root/'config/features.json').read_text())
    return [record['id'] for record in index['features'] if record['id'] in FEATURES
            and 'settingsPage' in record.get('startup', {})]
