"""Request-time palette options, followed by the existing preview state install."""
from dataclasses import dataclass
from typing import Callable
from backend_actions import ActionSpec, PreparedWork


@dataclass(frozen=True)
class PaletteCapabilities:
    executable: Callable
    preferences: Callable
    install: Callable
    preview: Callable


def provide(cap):
    def prepare(request):
        cap.executable('matugen')
        cap.install({'colors':{},'path':''})
        options={key:cap.preferences()[key] for key in ('paletteScheme','paletteMode','paletteContrast')}
        return PreparedWork(lambda:cap.preview(request.get('path'),options['paletteScheme'],options['paletteMode'],options['paletteContrast']))
    def complete(value):
        if not isinstance(value,Exception): cap.install(value)
    return ((ActionSpec('palettePreview',{'shell','settings'},lambda request:None,lambda request:None,
        execution='worker',complete=complete,presentation='Wallpaper palette preview ready',prepare=prepare),),lambda:{})
