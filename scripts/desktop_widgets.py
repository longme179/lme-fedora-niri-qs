"""Validated desktop widget records and atomic per-widget patches."""
# SPDX-License-Identifier: GPL-3.0-or-later
import math
import re

FIELDS = {'type','output','x','y','width','height','enabled','interactive'}


def widgets(value, partial=False):
    if not isinstance(value, dict) or len(value) > 12: raise ValueError('Use at most 12 desktop widgets')
    result = {}
    for key, record in value.items():
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',key): raise ValueError('Invalid widget identifier')
        if not isinstance(record,dict) or set(record)-FIELDS or not partial and set(record)!=FIELDS: raise ValueError('Invalid desktop widget fields')
        for field, item in record.items():
            if field == 'type' and item not in ('clock','notes','media'): raise ValueError('Unknown desktop widget')
            if field == 'output' and (not isinstance(item,str) or not 1 <= len(item) <= 128 or any(ord(c)<32 for c in item)): raise ValueError('Choose a display')
            if field in ('enabled','interactive') and type(item) is not bool: raise ValueError('Widget switches must be boolean')
            if field in ('x','y') and (type(item) not in (int,float) or not math.isfinite(item) or not 0 <= item <= 1): raise ValueError('Widget positions must be normalized')
            if field in ('width','height') and (type(item) is not int or not 180 <= item <= 1200): raise ValueError('Widget size must be between 180 and 1200')
        result[key] = dict(record)
    return result


def widget_patch(token, value):
    widgets({token: {}}, partial=True)
    return {} if value == '' else widgets({token: value}, partial=True)


def merge(current, delta, token):
    result = {key: dict(value) for key,value in current.items()}
    if token in delta: result[token] = {**result.get(token, {}), **delta[token]}
    else: result.pop(token, None)
    return widgets(result)
