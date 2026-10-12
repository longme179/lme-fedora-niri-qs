"""Isolated Matugen preview: never executes the user's theme templates."""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import re
import tempfile
from desktop_features import IMAGE_SUFFIXES, THEME_SCHEMA

ROLES={'background':'background','panel':'surface_container','surface':'surface_container_high','text':'on_surface','muted':'on_surface_variant','border':'outline',
       'purple':'primary','pink':'secondary','cyan':'tertiary','red':'error','primaryContainer':'primary_container','secondaryContainer':'secondary_container',
       'tertiaryContainer':'tertiary_container','surfaceContainer':'surface_container','surfaceContainerHigh':'surface_container_high','onPrimary':'on_primary','accent':'primary'}
ALLOWED={k for group in THEME_SCHEMA['colors'] for k in group['tokens']} | {'accent'}


def validate_palette(value):
    if not isinstance(value,dict) or not set(value)<=ALLOWED or not all(isinstance(c,str) and re.fullmatch(r'#[0-9a-fA-F]{6}',c) for c in value.values()):
        raise ValueError('Invalid wallpaper palette')
    return {k:c.lower() for k,c in value.items()}


def colors_from_json(raw):
    start=raw.find('{')
    if start<0 or len(raw)>1024*1024: raise ValueError('Matugen returned no valid color document')
    data=json.loads(raw[start:]);colors=data.get('colors')
    if not isinstance(colors,dict): raise ValueError('Matugen returned no colors')
    mapped={}
    for role,source in ROLES.items():
        value=colors.get(source)
        if isinstance(value,dict): value=value.get('dark')
        if not isinstance(value,str): raise ValueError('Matugen is missing dark role '+source)
        mapped[role]=value
    return validate_palette(mapped)


def preview(runner, raw):
    if not isinstance(raw,str) or not raw or len(raw)>4096 or '\x00' in raw: raise ValueError('Choose an image first')
    path=Path(raw).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES or path.stat().st_size>50*1024*1024: raise ValueError('Choose an image file no larger than 50 MiB')
    version=runner.run('matugen','--version')
    match=re.search(r'\b(\d+)\.',version)
    if not match or int(match[1]) not in (3,4): raise ValueError('Wallpaper palettes require Matugen 3 or 4')
    with tempfile.TemporaryDirectory(prefix='lme-matugen-') as folder:
        config=Path(folder)/'config.toml';config.write_text('[config]\n\n[templates]\n')
        args=['image',str(path),'-m','dark','-t','scheme-tonal-spot','-c',str(config),'--json','hex','--dry-run']
        if int(match[1])>=4: args.append('--old-json-output')
        output=runner.run('matugen',*args,timeout=35)
    return {'colors':colors_from_json(output),'path':str(path)}
