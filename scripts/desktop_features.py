"""Bounded, unprivileged helpers for desktop preferences and local content."""
from __future__ import annotations

import ast
import json
import math
import operator
from pathlib import Path
import re

MOTION_DEFAULTS = {"springMotion": True, "shapeMorph": True, "animatedTabs": True, "pointerRipple": True, "mediaWave": True, "mediaShapes": True, "motionPreset": "expressive", "motionSpeed": 1.0, "motionBounce": .35}
THEME_SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'config/theme-tokens.json').read_text())
THEME_DEFAULTS = {"themeOverrides": {}, "fontOverrides": {}, "fontSize": 14, "activityCompactMaxWidth": 300, "activityPopupMaxWidth": 460, "activityPopupMaxHeight": 0}
PALETTE_DOCUMENT = json.loads((Path(__file__).resolve().parents[1] / 'config/palettes.json').read_text())
PALETTE_CATALOG = PALETTE_DOCUMENT['palettes']
PALETTE_IDS = {p['id'] for p in PALETTE_CATALOG}
PALETTE_SCHEMES = tuple(PALETTE_DOCUMENT['schemes'])
PALETTE_DEFAULTS = {"paletteSource": "dracula", "palettePreset": "lme-dracula", "paletteScheme": "tonal-spot", "paletteMode": "dark", "paletteContrast": 0.0, "wallpaperPalette": {}}
from settings_schema import appearance_keys
APPEARANCE_KEYS = appearance_keys()
DRACULA_PROFILE = {"name": "Dracula", "accent": "#9580ff", "opacity": .90,
                   "density": "comfortable", "animations": True, **MOTION_DEFAULTS, **THEME_DEFAULTS, **PALETTE_DEFAULTS}
CONTROL_CATALOG = json.loads((Path(__file__).resolve().parents[1] / 'config/control-grid.json').read_text())
CONTROL_TILES = CONTROL_CATALOG['tiles']
CONTROL_MODULES = tuple(item['id'] for item in [*CONTROL_CATALOG['cards'], *CONTROL_TILES])
DEFAULT_CONTROL_LAYOUT = [{'id': item['id'], 'enabled': True, 'size': item.get('size', 'full' if item.get('cols', 0) >= 4 else 'half')}
                          for item in [*CONTROL_CATALOG['cards'], *CONTROL_TILES]]
CONTROL_SPANS = {tile['id']: tile['cols'] for tile in CONTROL_TILES}
DEFAULT_CONTROL_GRID = {'columns': 4, 'rows': max(8, 1 + max(tile['row'] for tile in CONTROL_TILES)), 'tiles': [{key: tile[key] for key in ('id', 'col', 'row')} for tile in CONTROL_TILES]}
LEGACY_CONTROL_MODULES = {'weather', 'charging', 'wifi', 'bluetooth', 'microphone', 'dnd', 'stayAwake', 'motion', 'nightLight',
                          'sliders', 'powerProfile', 'media', 'resources', 'capture', 'overview'}
LEGACY_GRID_IDS = set(CONTROL_SPANS) - {'volume', 'micLevel', 'brightness', 'powerProfile', 'settings', 'power', 'batterySaver'}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def appearance_profile(value, validate):
    if not isinstance(value, dict) or set(value) - {"name", "connectedPopups", *APPEARANCE_KEYS} or not {"name", "accent", "opacity", "density", "animations"} <= set(value):
        raise ValueError("Invalid appearance profile")
    name = value["name"]
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40 or any(ord(c) < 32 for c in name):
        raise ValueError("Use a profile name between 1 and 40 characters")
    defaults = {**MOTION_DEFAULTS, **THEME_DEFAULTS, **PALETTE_DEFAULTS}
    return {"name": name.strip(), **{key: validate(key, value.get(key, defaults.get(key))) for key in APPEARANCE_KEYS}}


def theme_overrides(value, fonts=False):
    keys = {item['key'] for item in THEME_SCHEMA['fonts']} if fonts else {key for group in THEME_SCHEMA['colors'] for key in group['tokens']}
    if not isinstance(value, dict) or set(value) - keys: raise ValueError('Unknown theme element')
    result = {}
    for key, item in value.items():
        if not isinstance(item, str): raise ValueError('Theme values must be text')
        if fonts:
            if not 1 <= len(item.strip()) <= 80 or not item.isprintable(): raise ValueError('Use a font family name between 1 and 80 characters')
            result[key] = item.strip()
        else:
            if not re.fullmatch(r'#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})', item): raise ValueError('Use #RRGGBB or #AARRGGBB')
            result[key] = item.lower()
    return result


def theme_token(key, token, value):
    if key == 'barIslandStyles':
        if token not in ('left', 'center', 'right'): raise ValueError('Unknown bar island')
        return bar_island_styles({token: value}) if value != '' else {}
    if key not in ('themeOverrides', 'fontOverrides') or not isinstance(token, str) or not isinstance(value, str):
        raise ValueError('Invalid theme token update')
    validated = theme_overrides({token: value or ('Roboto' if key == 'fontOverrides' else '#000000')}, fonts=key == 'fontOverrides')
    return validated if value else {}


def bar_corners(value):
    if not isinstance(value, dict) or set(value) != {'topLeft', 'topRight', 'bottomLeft', 'bottomRight'} or not all(type(v) is int and -1 <= v <= 32 for v in value.values()):
        raise ValueError('Use four corner radii between -1 (automatic) and 32 px')
    return dict(value)


def bar_island_styles(value):
    if not isinstance(value, dict) or set(value) - {'left', 'center', 'right'}: raise ValueError('Unknown bar island')
    result = {}
    for zone, style in value.items():
        if not isinstance(style, dict) or set(style) - {'corners', 'borderWidth', 'borderColor', 'fillColor'}: raise ValueError('Unknown island style')
        normalized = dict(style)
        if 'corners' in style: normalized['corners'] = bar_corners(style['corners'])
        if 'borderWidth' in style and (type(style['borderWidth']) is not int or not 0 <= style['borderWidth'] <= 4): raise ValueError('Island borders must be 0–4 px')
        for key in ('borderColor', 'fillColor'):
            if key in style:
                if not isinstance(style[key], str) or style[key] and not re.fullmatch(r'#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})', style[key]): raise ValueError('Use #RRGGBB or #AARRGGBB')
                normalized[key] = style[key].lower()
        result[zone] = normalized
    return result


def control_layout(value):
    if not isinstance(value, list) or len(value) > len(CONTROL_MODULES):
        raise ValueError("The layout must include every control module exactly once")
    result, seen = [], set()
    for item in value:
        if (not isinstance(item, dict) or set(item) != {'id', 'enabled', 'size'}
                or not isinstance(item['id'], str) or item['id'] not in {*CONTROL_MODULES, 'sliders'} or item['id'] in seen
                or type(item['enabled']) is not bool or item['size'] not in ('half', 'full')):
            raise ValueError('Invalid control module')
        seen.add(item['id']); result.append(dict(item))
    if seen in (set(CONTROL_MODULES) - {'nightLight'}, set(CONTROL_MODULES) - {'nightLight', 'batterySaver'}, LEGACY_CONTROL_MODULES - {'nightLight'}):
        result.append({'id': 'nightLight', 'enabled': True, 'size': 'half'}); seen.add('nightLight')
    if seen == LEGACY_CONTROL_MODULES:
        actions_enabled = next(item['enabled'] for item in result if item['id'] == 'capture')
        migrated = []
        for item in result:
            ids = ('volume', 'micLevel', 'brightness') if item['id'] == 'sliders' else ('capture', 'captureScreen', 'captureArea', 'captureWindow') if item['id'] == 'capture' else (item['id'],)
            migrated.extend({**item, 'id': id} for id in ids)
        result = [*migrated, {'id': 'settings', 'enabled': actions_enabled, 'size': 'half'}, {'id': 'power', 'enabled': actions_enabled, 'size': 'half'}]
    if {item['id'] for item in result} == set(CONTROL_MODULES) - {'batterySaver'}:
        result.append({'id': 'batterySaver', 'enabled': True, 'size': 'half'})
    if {item['id'] for item in result} != set(CONTROL_MODULES):
        raise ValueError('The layout must include every control module exactly once')
    return result


def control_grid(value):
    if (not isinstance(value, dict) or set(value) != {'columns', 'rows', 'tiles'}
            or type(value['columns']) is not int or value['columns'] not in (4, 8)
            or type(value['rows']) is not int or not 4 <= value['rows'] <= 32):
        raise ValueError('Choose 4 or 8 columns and 4–32 rows')
    if not isinstance(value['tiles'], list): raise ValueError('Include every quick control exactly once')
    occupied, seen, result = set(), set(), []
    for tile in value['tiles']:
        if (not isinstance(tile, dict) or set(tile) != {'id', 'col', 'row'}
                or not isinstance(tile['id'], str) or tile['id'] not in CONTROL_SPANS or tile['id'] in seen
                or type(tile['col']) is not int or type(tile['row']) is not int
                or not 0 <= tile['col'] <= value['columns'] - CONTROL_SPANS[tile['id']] or not 0 <= tile['row'] < value['rows']):
            raise ValueError('Quick controls must fit within the canvas')
        cells = {(tile['row'], col) for col in range(tile['col'], tile['col'] + CONTROL_SPANS[tile['id']])}
        if occupied & cells: raise ValueError('Quick controls cannot overlap')
        occupied |= cells; seen.add(tile['id']); result.append(dict(tile))
    if seen not in (set(CONTROL_SPANS), set(CONTROL_SPANS) - {'batterySaver'}, LEGACY_GRID_IDS): raise ValueError('Include every quick control exactly once')
    rows = value['rows']
    # Add new controls in vacant cells, growing downward without shifting saved positions.
    for tile in CONTROL_TILES:
        if tile['id'] in seen: continue
        placed = False
        while not placed:
            for row in range(rows):
                for col in range(value['columns'] - tile['cols'] + 1):
                    cells = {(row, x) for x in range(col, col + tile['cols'])}
                    if not occupied & cells:
                        result.append({'id': tile['id'], 'col': col, 'row': row}); occupied |= cells; placed = True; break
                if placed: break
            if not placed:
                if rows == 32: raise ValueError('No space remains for new controls')
                rows += 1
    return {**value, 'rows': rows, 'tiles': result}


def wallpaper_library(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Choose a wallpaper folder first")
    directory = Path(raw).expanduser().resolve()
    if not directory.is_dir():
        raise ValueError("Wallpaper folder does not exist")
    entries, visited, truncated = [], 0, False
    # Do not follow directory symlinks or traverse an unbounded home tree.
    for path in directory.rglob("*"):
        visited += 1
        if visited > 10000 or len(entries) >= 500:
            truncated = True
            break
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES and path.resolve().is_relative_to(directory):
            entries.append({"path": str(path.resolve()), "name": path.name, "url": path.resolve().as_uri()})
    entries.sort(key=lambda item: (item["name"].casefold(), item["path"]))
    return {"entries": entries, "folder": str(directory), "truncated": truncated, "error": ""}


def calculate(raw):
    """Arithmetic only: no eval, calls, attributes or unbounded exponents."""
    if not isinstance(raw, str) or not 1 <= len(raw) <= 160:
        raise ValueError("Enter a short arithmetic expression")
    try:
        tree = ast.parse(raw.replace("×", "*").replace("÷", "/").replace("^", "**"), mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise ValueError("Invalid expression") from exc
    if len(list(ast.walk(tree))) > 60:
        raise ValueError("Expression is too complex")
    binary = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
              ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and type(node.op) in binary:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and (abs(right) > 12 or abs(left) > 1e12):
                raise ValueError("Exponent is too large")
            value = binary[type(node.op)](left, right)
        else:
            raise ValueError("Only numbers and arithmetic operators are supported")
        if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e15:
            raise ValueError("Result is outside the supported range")
        return value
    try:
        result = visit(tree.body)
    except (ZeroDivisionError, OverflowError) as exc:
        raise ValueError("Cannot divide by zero or overflow") from exc
    return format(result, ".12g")
