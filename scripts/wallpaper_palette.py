"""Isolated Matugen preview: never executes the user's theme templates.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: wallpaper; Phase 3 graph).
"""
# SPDX-License-Identifier: AGPL-3.0-or-later
import json
from pathlib import Path
import re
import tempfile
from desktop_features import IMAGE_SUFFIXES, THEME_SCHEMA, PALETTE_SCHEMES, validate_palette
import palette_sinks

ROLES={'background':'background','panel':'surface_container','surface':'surface_container_high','text':'on_surface','muted':'on_surface_variant','border':'outline',
       'green':'tertiary','yellow':'secondary','purple':'primary','pink':'secondary','cyan':'tertiary','red':'error','primaryContainer':'primary_container','secondaryContainer':'secondary_container',
       'tertiaryContainer':'tertiary_container','surfaceContainer':'surface_container','surfaceContainerHigh':'surface_container_high','onPrimary':'on_primary','accent':'primary'}

def colors_from_json(raw, mode="dark"):
    start=raw.find('{')
    if start<0 or len(raw)>1024*1024: raise ValueError('Matugen returned no valid color document')
    data=json.loads(raw[start:]);colors=data.get('colors')
    if not isinstance(colors,dict): raise ValueError('Matugen returned no colors')
    mapped={}
    for role,source in ROLES.items():
        value=colors.get(source)
        if isinstance(value,dict): value=value.get(mode)
        if not isinstance(value,str): raise ValueError('Matugen is missing '+mode+' role '+source)
        mapped[role]=value
    return validate_palette(mapped)


def preview(runner, raw, scheme="tonal-spot", mode="dark", contrast=0):
    if not isinstance(raw,str) or not raw or len(raw)>4096 or '\x00' in raw: raise ValueError('Choose an image first')
    path=Path(raw).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES or path.stat().st_size>50*1024*1024: raise ValueError('Choose an image file no larger than 50 MiB')
    if scheme not in PALETTE_SCHEMES or mode not in ('dark','light') or type(contrast) not in (int,float) or not -1 <= contrast <= 1: raise ValueError('Invalid Material palette options')
    version=runner.run('matugen','--version')
    match=re.search(r'\b(\d+)\.',version)
    if not match or int(match[1]) not in (3,4): raise ValueError('Wallpaper palettes require Matugen 3 or 4')
    with tempfile.TemporaryDirectory(prefix='lme-matugen-') as folder:
        config=Path(folder)/'config.toml';config.write_text('[config]\n\n[templates]\n')
        args=['image',str(path),'-m',mode,'-t','scheme-'+scheme,'--contrast',str(contrast),'-c',str(config),'--json','hex','--dry-run']
        # Matugen 4 otherwise prompts for a source color and fails without a terminal.
        if int(match[1])>=4: args+=['--source-color-index=0','--old-json-output']
        output=runner.run('matugen',*args,timeout=35)
    return {'colors':colors_from_json(output,mode),'path':str(path),'paletteScheme':scheme,'paletteMode':mode,'paletteContrast':contrast}


def follow_wallpaper_palette(host, message, raw):
    """P1-1: after a successful wallpaper apply, regenerate the Material palette
    when the user enabled wallpaper-following theming. Never fails the apply;
    appends the outcome to the wallpaper action's message instead."""
    prefs = host.preferences.values
    if prefs.get('wallpaperPaletteAuto') is not True or prefs.get('paletteSource') != 'wallpaper': return message
    if not isinstance(raw, str) or not raw: return message
    try:
        result = preview(host.runner, raw, prefs.get('paletteScheme','tonal-spot'),
                         prefs.get('paletteMode','dark'), prefs.get('paletteContrast',0))
        colors = validate_palette(result.get('colors'))
        host.palette_preview = result
        host.preferences.update({'wallpaperPalette': colors, 'paletteSource': 'wallpaper', 'accent': colors['accent']})
        palette_sinks.request_sync()
        return message + ' (palette updated)'
    except Exception as error:
        return message + ' (palette unchanged: ' + str(error)[:120] + ')'
