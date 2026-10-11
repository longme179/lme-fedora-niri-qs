"""Bounded, unprivileged helpers for desktop preferences and local content."""
from __future__ import annotations

import ast
import json
import math
import operator
from pathlib import Path
import re

MOTION_DEFAULTS = {"motionPreset": "expressive", "motionSpeed": 1.0, "motionBounce": .35}
THEME_SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'config/theme-tokens.json').read_text())
THEME_DEFAULTS = {"themeOverrides": {}, "fontOverrides": {}, "fontSize": 14}
APPEARANCE_KEYS = ("accent", "opacity", "density", "animations", *MOTION_DEFAULTS, *THEME_DEFAULTS)
DRACULA_PROFILE = {"name": "Dracula", "accent": "#9580ff", "opacity": .90,
                   "density": "comfortable", "animations": True, **MOTION_DEFAULTS, **THEME_DEFAULTS}
CONTROL_MODULES = ("weather", "charging", "wifi", "bluetooth", "microphone", "dnd", "stayAwake", "motion", "nightLight", "sliders", "powerProfile", "media", "resources", "capture", "overview")
DEFAULT_CONTROL_LAYOUT = [{"id": key, "enabled": True, "size": "half" if key in {"wifi", "bluetooth", "microphone", "dnd", "stayAwake", "motion", "nightLight"} else "full"} for key in CONTROL_MODULES]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def appearance_profile(value, validate):
    if not isinstance(value, dict) or set(value) - {"name", *APPEARANCE_KEYS} or not {"name", "accent", "opacity", "density", "animations"} <= set(value):
        raise ValueError("Invalid appearance profile")
    name = value["name"]
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40 or any(ord(c) < 32 for c in name):
        raise ValueError("Use a profile name between 1 and 40 characters")
    defaults = {**MOTION_DEFAULTS, **THEME_DEFAULTS}
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
    if key not in ('themeOverrides', 'fontOverrides') or not isinstance(token, str) or not isinstance(value, str):
        raise ValueError('Invalid theme token update')
    validated = theme_overrides({token: value or ('Roboto' if key == 'fontOverrides' else '#000000')}, fonts=key == 'fontOverrides')
    return validated if value else {}


def control_layout(value):
    # Preserve saved layouts from before the Night Light tile existed.
    if isinstance(value, list) and len(value) == len(CONTROL_MODULES) - 1 and all(isinstance(item, dict) and isinstance(item.get('id'), str) for item in value) and {item['id'] for item in value} == set(CONTROL_MODULES) - {'nightLight'}:
        value = [*value, {'id': 'nightLight', 'enabled': True, 'size': 'half'}]
    if not isinstance(value, list) or len(value) != len(CONTROL_MODULES):
        raise ValueError("The layout must include every control module exactly once")
    result, seen = [], set()
    for item in value:
        if (not isinstance(item, dict) or set(item) != {"id", "enabled", "size"}
                or not isinstance(item["id"], str) or item["id"] not in CONTROL_MODULES or item["id"] in seen
                or type(item["enabled"]) is not bool or item["size"] not in ("half", "full")):
            raise ValueError("Invalid control module")
        seen.add(item["id"])
        result.append(dict(item))
    return result


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
