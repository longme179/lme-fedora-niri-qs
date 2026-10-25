"""Read-only lifecycle counters injected into a disposable checkout only."""
import json

from release_session_fixture import ReleaseWorld


def close_settings(probe):
    # Exercise the X button's signal, without relying on compositor decorations.
    probe.call('closeNormally')


class RenderWorld(ReleaseWorld):
    def __init__(self, directory, style='liquid'):
        super().__init__(directory, style)
        preferences = json.loads(self.settings.read_text())
        # Synthetic low-battery toasts would cover Settings' close button at startup.
        preferences.update(peripheralBatteryAlerts=False,
                           wallpaper=str(self.root/'assets/wallpapers/liquid-dracula.png'))
        self.settings.write_text(json.dumps(preferences))
        service = self.root/'qml/services/GlassState.qml'
        text = service.read_text().replace('    id: root', '''    id: root
    property int lifetimeMaterial: 0
    property int lifetimeOptics: 0
    property int lifetimeBackdrop: 0
    property int lifetimeJelly: 0''', 1)
        service.write_text(text)
        for name, key, completed, destroyed in (
            ('GlassMaterial', 'Material', 'updateBackdrop()', 'if (backdrop) GlassState.release(backdrop)'),
            ('GlassBackdrop', 'Backdrop', None, 'GlassState.backdrops = GlassState.backdrops.filter(item => item !== root)'),
            ('GlassOptics', 'Optics', None, None),
            ('PopupElasticity', 'Jelly', 'attach()', None),
        ):
            path = self.root/'qml/components'/f'{name}.qml'; text = path.read_text()
            if 'import "../services"' not in text:
                text = text.replace('import QtQuick', 'import "../services"\nimport QtQuick', 1)
            for signal, old, amount in (('Completed', completed, '++'), ('Destruction', destroyed, '--')):
                body = f'{{ GlassState.lifetime{key}{amount}; {old+";" if old else ""} }}'
                if old:
                    original = f'Component.on{signal}: {old}'
                    assert text.count(original) == 1, (name, original)
                    text = text.replace(original, f'Component.on{signal}: {body}')
                else:
                    text = text.replace('\n    id: root', f'\n    Component.on{signal}: {body}\n    id: root', 1)
            path.write_text(text)
        path = self.root/'shell.qml'; text = path.read_text()
        text = text.replace('function state(): string {', '''function lifetime(): string {
            return JSON.stringify({material:GlassState.lifetimeMaterial, optics:GlassState.lifetimeOptics,
                backdrop:GlassState.lifetimeBackdrop, jelly:GlassState.lifetimeJelly,
                panelLayer:panelLoader.layer.enabled, islandLayer:activityIsland.layer.enabled});
        }
        function state(): string {''', 1)
        path.write_text(text)
        path = self.root/'qml/settings/SettingsApplication.qml'; text = path.read_text()
        text = text.replace('function state(): string {', '''function closeNormally(): void {
            (root.sliceSurface as SettingsView).closeRequested();
        }
        function state(): string {''', 1)
        path.write_text(text)
