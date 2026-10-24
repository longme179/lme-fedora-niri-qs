"""Request-time palette options, followed by the existing preview state install."""
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
    return ((ActionSpec('palettePreview',{'shell','settings'},lambda request:None,lambda request:None,
        execution='worker',complete=complete,presentation='Wallpaper palette preview ready',prepare=prepare),
        ActionSpec('paletteApply',{'shell','settings'},apply,lambda request:None)),lambda:{})
