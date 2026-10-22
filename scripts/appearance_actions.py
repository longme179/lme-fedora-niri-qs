"""Synchronous palette/profile and transfer actions; existing transactions stay authoritative."""
from dataclasses import dataclass
from typing import Callable

from backend_actions import ActionSpec
from desktop_features import DRACULA_PROFILE, PALETTE_CATALOG
from settings_transfer import export_document, read_document


@dataclass(frozen=True)
class AppearanceCapabilities:
    preferences: Callable
    reload: Callable
    update: Callable
    validate: Callable
    defaults: Callable
    profile: Callable


def provide(capabilities):
    def preset(request):
        ident = capabilities.validate('palettePreset', request.get('id'))
        selected = next(p for p in PALETTE_CATALOG if p['id'] == ident)
        capabilities.update({'palettePreset': ident, 'paletteSource': 'preset', 'accent': selected['colors']['accent']})
        return selected['name'] + ' palette applied; manual overrides preserved'

    def reset(request):
        capabilities.update({'paletteSource': 'dracula', 'accent': DRACULA_PROFILE['accent']})
        return 'Dracula palette restored; element overrides preserved'

    def export(request):
        capabilities.reload(force=True)
        return 'Exported ' + export_document(request.get('path'), capabilities.preferences(), request.get('kind'))

    def import_settings(request):
        values = read_document(request.get('path'), capabilities.validate, capabilities.defaults())
        backup = capabilities.update(values, backup=True)
        return 'Imported settings. Previous settings: ' + str(backup)

    def demo_preset(request):
        ident = capabilities.validate('palettePreset', request.get('id'))
        colors = next(p['colors'] for p in PALETTE_CATALOG if p['id'] == ident)
        capabilities.preferences().update(palettePreset=ident, paletteSource='preset', accent=colors['accent'])

    no_op = lambda request: None
    handlers = [('palettePreset', preset, demo_preset),
                ('paletteReset', reset, lambda request: capabilities.preferences().update(paletteSource='dracula', accent=DRACULA_PROFILE['accent'])),
                ('settingsExport', export, no_op), ('settingsImport', import_settings, no_op)]
    for name in ('appearanceSave', 'appearanceApply', 'appearanceDelete'):
        profile = lambda request, name=name: capabilities.profile(name, request)
        handlers.append((name, profile, profile))
    return tuple(ActionSpec(name, {'shell', 'settings'}, live, demo) for name, live, demo in handlers), lambda: {}
