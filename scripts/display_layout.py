"""Shared niri layout validation and runner-injected application; no lifecycle state."""
import math


def validate_layout(value, outputs=None):
    if not isinstance(value, list) or not 1 <= len(value) <= 16:
        raise ValueError("Choose at least one display")
    result, seen = [], set()
    for item in value:
        if not isinstance(item, dict): raise ValueError("Invalid display settings")
        name = item.get("name")
        if not isinstance(name, str) or not 1 <= len(name) <= 128 or any(ord(c) < 32 for c in name) or name in seen:
            raise ValueError("Invalid or duplicate output name")
        seen.add(name)
        for key in ("width", "height", "refresh"):
            if type(item.get(key)) is not int or not 1 <= item[key] <= 1000000:
                raise ValueError("Invalid display mode")
        scale = item.get("scale")
        if type(scale) not in (int, float) or not math.isfinite(scale) or not .5 <= scale <= 3:
            raise ValueError("Scale must be between 0.5 and 3")
        if any(type(item.get(key)) is not int or not -32768 <= item[key] <= 32768 for key in ("x", "y")):
            raise ValueError("Display coordinates must be integers between -32768 and 32768")
        if outputs is not None:
            output = next((o for o in outputs if o["name"] == name and o["enabled"]), None)
            if not output or not any(all(m[k] == item[k] for k in ("width", "height", "refresh")) for m in output["modes"]):
                raise ValueError("Display or mode is no longer available; refresh displays")
        result.append({key: item[key] for key in ("name", "width", "height", "refresh", "scale", "x", "y")})
    return result


def current_layout(outputs):
    return [{"name": o["name"], **{k: o["current"][k] for k in ("width", "height", "refresh")},
             **{k: o[k] for k in ("scale", "x", "y")}} for o in outputs if o["current"]]


def apply_layout(layout, run, best_effort=False):
    errors = []
    for item in validate_layout(layout):
        mode = f'{item["width"]}x{item["height"]}@{item["refresh"] / 1000:.3f}'
        for args in (("mode", mode), ("scale", str(item["scale"])), ("position", "set", str(item["x"]), str(item["y"]))):
            try: run("niri", "msg", "output", item["name"], *args)
            except (RuntimeError, OSError) as exc:
                if not best_effort: raise
                errors.append(str(exc))
    return errors
