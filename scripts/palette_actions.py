"""Request-time palette options, followed by the existing preview state install.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: wallpaper; Phase 3 graph).
"""
# REL: qml/settings/AppearancePage.qml – ActionSpec dispatch via scripts/backend_actions.py::ActionRegistry; scripts/desktop_backend.py host.
from dataclasses import dataclass
from typing import Callable
from backend_actions import ActionSpec, PreparedWork
from wallpaper_palette import validate_palette


@dataclass(frozen=True)
class PaletteCapabilities:
    executable: Callable
    preferences: Callable
    install: Callable
    preview: Callable
    current: Callable
    update: Callable


def provide(cap):
    def prepare(request):
        cap.executable('matugen')
        cap.install({'colors':{},'path':''})
        options={key:cap.preferences()[key] for key in ('paletteScheme','paletteMode','paletteContrast')}
        return PreparedWork(lambda:cap.preview(request.get('path'),options['paletteScheme'],options['paletteMode'],options['paletteContrast']))
    def complete(value):
        if not isinstance(value,Exception): cap.install(value)
    def apply(request):
        preview = cap.current()
        colors = validate_palette(preview.get('colors'))
        if (not colors or preview.get('path') != request.get('path')
                or any(preview.get(key) != cap.preferences()[key] for key in ('paletteScheme','paletteMode','paletteContrast'))):
            raise ValueError('Generate a preview for this image first')
        cap.update({'wallpaperPalette':colors,'paletteSource':'wallpaper','accent':colors['accent']})
        return 'Wallpaper palette applied; element overrides preserved'
    def sync(request):
        path=request.get('path')
        cap.executable('matugen')
        options={key:cap.preferences().get(key,default) for key,default in
            (('paletteScheme','tonal-spot'),('paletteMode','dark'),('paletteContrast',0))}
        return PreparedWork(lambda:cap.preview(path,options['paletteScheme'],options['paletteMode'],options['paletteContrast']))
    def sync_complete(value):
        if not isinstance(value,dict): return
        try: colors=validate_palette(value.get('colors'))
        except ValueError: return
        if not colors: return
        cap.install(value)
        cap.update({'wallpaperPalette':colors,'paletteSource':'wallpaper','accent':colors['accent']})
    return ((ActionSpec('palettePreview',{'shell','settings'},lambda request:None,lambda request:None,
        execution='worker',complete=complete,presentation='Wallpaper palette preview ready',prepare=prepare),
        ActionSpec('paletteApply',{'shell','settings'},apply,lambda request:None),
        ActionSpec('paletteSync',{'shell','settings'},lambda request:None,lambda request:None,
            execution='worker',complete=sync_complete,presentation='Wallpaper palette updated',prepare=sync)),lambda:{})
