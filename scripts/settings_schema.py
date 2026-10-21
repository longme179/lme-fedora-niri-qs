"""Read-only preference metadata; persistence and legacy validation stay with their owners."""
from collections.abc import Mapping
import copy
from functools import lru_cache
import json
from pathlib import Path
import re
from types import MappingProxyType

from feature_catalog import resource, pairs, nonfinite

ROOT = Path(__file__).resolve().parents[1]


def freeze(value):
    if isinstance(value, dict): return MappingProxyType({k:freeze(v) for k,v in value.items()})
    if isinstance(value, list): return tuple(freeze(v) for v in value)
    return value


def thaw(value):
    if isinstance(value, Mapping): return {k:thaw(v) for k,v in value.items()}
    if isinstance(value, tuple): return [thaw(v) for v in value]
    return copy.deepcopy(value)


def assemble(legacy, fragments):
    definitions = {}
    for fragment in [legacy['preferences'], *fragments]:
        for key, value in fragment.items():
            if key in definitions: raise ValueError('Duplicate preference owner: '+key)
            definitions[key] = value
    expected = set(legacy['order'])
    if missing := expected - definitions.keys(): raise ValueError('Missing preference owner: '+sorted(missing)[0])
    if unknown := definitions.keys() - expected: raise ValueError('Unknown preference owner: '+sorted(unknown)[0])
    return freeze({key:definitions[key] for key in legacy['order']})


def fragment_documents(root, fallback=False):
    """Read preference data without starting the backend's UI-resource validation."""
    def read(path): return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite)
    try:
        if fallback: raise ValueError('Retain known schema fragments')
        index = read(root/'config/features.json')
        if type(index['version']) is not int or index['version'] != 1: raise ValueError('Unsupported index')
        records = index['features']
        if len({r['id'] for r in records}) != len(records): raise ValueError('Duplicate feature')
        return [read(resource(root,r['descriptor'],'.json')) for r in records]
    except (OSError, ValueError, KeyError, TypeError):
        # Keep schema/data when the UI catalog falls back to legacy-only with its diagnostic.
        # shortcut: descriptors currently live in config/; extend discovery with authorized M8 moves.
        result = []
        for path in sorted((root/'config').glob('*.json')):
            try:
                value = read(resource(root,path.relative_to(root).as_posix(),'.json'))
                if isinstance(value,dict) and 'id' in value and 'preferences' in value: result.append(value)
            except (OSError,ValueError): continue
        return result


@lru_cache(maxsize=1)
def metadata():
    legacy = json.loads((ROOT/'config/preferences-legacy.json').read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite)
    fragments = [d.get('preferences',{}) for d in fragment_documents(ROOT)]
    if set(legacy['order']) - set(legacy['preferences']) - {key for f in fragments for key in f}:
        fragments = [d.get('preferences',{}) for d in fragment_documents(ROOT, fallback=True)]
    # New declared keys append; the original inventory preserves existing write/default order.
    order = list(legacy['order'])
    for fragment in fragments:
        order.extend(key for key in fragment if key not in order)
    return assemble(dict(legacy,order=order),fragments), tuple(legacy['appearanceOrder']), frozenset(legacy['preferences'])


def portable_keys():
    return frozenset(key for key,value in metadata()[0].items() if value.get('portable') is True)


def appearance_keys():
    definitions,order,_ = metadata()
    keys = [key for key,value in definitions.items() if value.get('appearance') is True]
    return tuple([key for key in order if key in keys] + [key for key in keys if key not in order])


def bar_layout():
    source = (ROOT/'qml/bar/BarRegistry.qml').read_text()
    value = re.search(r'property var defaults:\s*\((\{.*?\})\)',source).group(1)
    return json.loads(re.sub(r'(\b(?:left|center|right)):',r'"\1":',value))


class Schema:
    """Composition supplies named existing validators/resolvers; JSON never executes code."""
    def __init__(self, *, legacy_validator=None, validators=None, resolvers=None):
        self.definitions,self._appearance,self.legacy_keys = metadata()
        self._legacy = legacy_validator
        self._validators = dict(validators or {})
        self._resolvers = dict(resolvers or {})

    def defaults(self, context=None):
        # The worker needs only its fragment and never imports the desktop backend.
        keys = [k for k in self.definitions if k.startswith('clipboard')] if context == 'clipboard' else self.definitions
        home = Path(context['home']) if isinstance(context,dict) and 'home' in context else Path.home()
        builtin = {
            'recordingFolder': lambda key: str(home/'Videos/Recordings'),
            'fileSearchRoots': lambda key: [str(home/name) for name in ('Documents','Desktop','Downloads','Pictures')],
            'barLayout': lambda key: bar_layout(),
        }
        resolvers = {**builtin,**self._resolvers}
        return {key:copy.deepcopy(resolvers[definition['defaultResolver']](key)) if 'defaultResolver' in definition
                else thaw(definition['default']) for key in keys for definition in [self.definitions[key]]}

    def validate(self, key, value):
        definition = self.definitions.get(key)
        if definition is None: raise ValueError(f'Invalid preference: {key}')
        name = definition.get('validator',definition['type'])
        if name == 'legacy':
            if self._legacy is None: raise ValueError('Legacy validator is not bound')
            return self._legacy(key,value)
        if name in self._validators: return self._validators[name](value)
        if name == 'boolean' and type(value) is bool: return value
        if name == 'integer' and type(value) is int and definition['min'] <= value <= definition['max']: return value
        raise ValueError(f'Invalid preference: {key}')

    def portable_keys(self): return portable_keys()
    def appearance_keys(self): return appearance_keys()

# The Clipboard worker binds only its three validators and never imports the backend.
clipboard_schema = Schema()
