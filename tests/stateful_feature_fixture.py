"""Observe stateful feature composition in a copied checkout, never the real session."""
from contextlib import contextmanager
import json
from light_feature_fixture import LightWorld, Probe as LightProbe, ROOT

FEATURES = {'notifications': ('NotificationsPage', 'Live preview'),
            'wallpaper': ('WallpaperPage', 'Wallpaper library'),
            'utilities': ('UtilitiesPage', 'Wallpaper engine'),
            'desktop': ('DesktopPage', 'Floating wallpaper shapes')}
OBSERVE = '''
    function statefulView(item) {
        if (!item) return null;
        if (item.currentPage !== undefined && item.navigate !== undefined) return item;
        for (const child of item.children || []) { const found=statefulView(child); if (found) return found; }
        return null;
    }
    IpcHandler {
        target: "statefulFeatures"
        function state(): string {
            const surface = root.sliceSurface;
            const names = ["Live preview", "Wallpaper library", "Wallpaper engine", "Floating wallpaper shapes", "Warmer evenings", "Find me automatically"];
            const windows = DesktopState.fixtureWindows || [];
            return JSON.stringify({ready: ShellState.backendReady && FeatureCatalog.ready && Theme.ready,
                page: root.statefulView(surface)?.page || ShellState.settingsPage, panelOpen: ShellState.panelOpen,
                pages: SettingsRegistry.pages.map(p => p.key), bars: BarRegistry.modules.map(p => p.id),
                searches: ["", "wallpaper", "notification", "desktop", "scripts"].map(q => SettingsRegistry.search(q).map(p => p.key)),
                marks: names.filter(name => !!root.sliceFind(surface, name)), preferences: ShellState.preferences,
                progress: root.sliceProgress, editing: DesktopState.editing,
                windows: windows.map(w => ({id:w.widgetId,screen:w.screenInfo.name,width:w.width,height:w.height,
                    x:w.margins.left,y:w.margins.top,layer:w.WlrLayershell.layer,keyboard:w.WlrLayershell.keyboardFocus,
                    clickthrough:w.mask.item===null})), ambient: (DesktopState.fixtureAmbient || []).length,
                lastResult:ShellState.lastResult, notes:NotesState.content});
        }
        function button(name: string): bool {
            const button=root.sliceFind(root.sliceSurface,name);
            if (!button || !button.enabled) return false; button.clicked(); return true;
        }
        function setting(key: string, value: string): void { ShellState.run("setting",{key,value:JSON.parse(value)}); }
        function open(page: string): void { ShellState.openSettingsPage(page); }
        function search(text: string): bool {
            const field=root.sliceFind(root.sliceSurface,"Search settings");
            if (!field) return false; field.text=text; field.accepted(); return true;
        }
    }
'''

class Probe(LightProbe):
    def call(self, method, *args, target='statefulFeatures'):
        reply=super().call(method, *args, target=target)
        if method=='close' and target=='shell': self.wait(lambda s:s['progress']==0 and not s['panelOpen'])
        return reply

class StatefulWorld(LightWorld):
    def __init__(self, directory):
        super().__init__(directory)
        for name in ('shell.qml','qml/settings/SettingsApplication.qml'):
            path=self.root/name; text=path.read_text()
            text=text.replace('import Quickshell.Io','import Quickshell.Io\nimport Quickshell.Wayland')
            path.write_text(text.replace('    id: root\n','    id: root\n'+OBSERVE,1))
        service=self.root/'qml/services/DesktopState.qml'
        service.write_text(service.read_text().replace('    id: root','    property var fixtureWindows: []\n    property var fixtureAmbient: []\n    id: root',1))
        window=self.root/'qml/panels/DesktopWidgetWindow.qml'
        window.write_text(window.read_text().replace('    id: root','    Component.onCompleted: DesktopState.fixtureWindows = DesktopState.fixtureWindows.concat(root)\n    Component.onDestruction: DesktopState.fixtureWindows = DesktopState.fixtureWindows.filter(w => w !== root)\n    id: root',1))
        ambient=self.root/'qml/panels/DesktopAmbient.qml'
        ambient.write_text(ambient.read_text().replace('        required property var modelData','        id: fixtureAmbient\n        Component.onCompleted: DesktopState.fixtureAmbient = DesktopState.fixtureAmbient.concat(fixtureAmbient)\n        Component.onDestruction: DesktopState.fixtureAmbient = DesktopState.fixtureAmbient.filter(w => w !== fixtureAmbient)\n        required property var modelData',1))

    @contextmanager
    def launch(self, mode='demo', page='appearance'):
        with super().launch(mode,page) as original:
            probe=Probe(original.entry,original.env,original.process,original.log)
            probe.wait(lambda s:s['ready']); yield probe

def catalog_id(feature):
    return "launchpad" if feature == "utilities" else feature

def converted(feature):
    return any(r['id']==catalog_id(feature) for r in json.loads((ROOT/'config/features.json').read_text())['features'])
