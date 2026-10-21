"""Read the bundled, data-only feature catalog; stdlib, no registration side effects."""
from functools import lru_cache
import json
from pathlib import Path
import re
import sys

KINDS = {'bar': 'id', 'settingsPage': 'key', 'controlTab': 'id'}
FIELDS = {
    'bar': {'id', 'title', 'detail', 'icon', 'entry'},
    'settingsPage': {'key', 'title', 'icon', 'description', 'keywords', 'entry'},
    'controlTab': {'id', 'title', 'entry', 'refresh', 'markRead'},
}


class CatalogError(ValueError):
    """An invalid bundled catalog must not shadow legacy registrations."""


def empty_catalog():
    return {'version': 1, **{kind: [] for kind in KINDS}, 'preferences': {},
            'ids': {'features': [], **{kind: [] for kind in KINDS}},
            'all': {kind: [] for kind in KINDS}}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', value):
        raise CatalogError(f'Invalid identifier: {value!r}')
    return value


def shape(value, fields, required):
    if not isinstance(value, dict) or set(value) - fields or not required <= set(value):
        raise CatalogError('Invalid catalog fields')


def resource(root, value, suffix=None):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or any(part in ('', '.', '..') for part in value.split('/'))):
        raise CatalogError(f'Invalid resource path: {value!r}')
    try:
        path = (root / value).resolve(strict=True)
        path.relative_to(root)
        if not path.is_file() or suffix and path.suffix != suffix:
            raise ValueError('Wrong resource type')
    except (OSError, ValueError, RuntimeError) as error:
        raise CatalogError(f'Missing or escaping resource: {value}') from error
    return path


def pairs(items):
    value = {}
    for key, item in items:
        if key in value: raise CatalogError(f'Duplicate JSON key: {key}')
        value[key] = item
    return value


def nonfinite(value):
    raise CatalogError(f'Invalid JSON number: {value}')


def document(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite)
    except (OSError, ValueError) as error:
        raise CatalogError(str(error)) from error


def validate_legacy(data, legacy=None, setting_keys=()):
    for kind, ids in (legacy or {}).items():
        collision = set(data['ids'].get(kind, ())) & set(ids)
        if collision: raise CatalogError(f'Duplicate {kind} ID in legacy: {sorted(collision)[0]}')
    collision = set(data['preferences']) & set(setting_keys)
    if collision: raise CatalogError(f'Duplicate setting in legacy: {sorted(collision)[0]}')
    return data


def load_catalog(root=None, *, legacy=None, setting_keys=()):
    root = (Path(root) if root is not None else Path(__file__).resolve().parents[1]).resolve()
    index = document(resource(root, 'config/features.json', '.json'))
    shape(index, {'version', 'features'}, {'version', 'features'})
    if type(index['version']) is not int or index['version'] != 1 or not isinstance(index['features'], list):
        raise CatalogError('Unsupported feature catalog version or index')
    result = empty_catalog()
    for record in index['features']:
        shape(record, {'id', 'descriptor', 'enabled'}, {'id', 'descriptor', 'enabled'})
        ident = identifier(record['id'])
        if type(record['enabled']) is not bool: raise CatalogError('Invalid enabled flag')
        if ident in result['ids']['features']: raise CatalogError(f'Duplicate feature ID: {ident}')
        result['ids']['features'].append(ident)
        descriptor = document(resource(root, record['descriptor'], '.json'))
        shape(descriptor, {'id', 'sources', 'preferences', *KINDS}, {'id'})
        if descriptor['id'] != ident: raise CatalogError(f'Descriptor ID does not match index: {ident}')
        sources = descriptor.get('sources', [])
        if not isinstance(sources, list): raise CatalogError('Invalid sources')
        for source in sources: resource(root, source)
        preferences = descriptor.get('preferences', {})
        if not isinstance(preferences, dict): raise CatalogError('Invalid preference fragment')
        for key, definition in preferences.items():
            identifier(key)
            if key in result['preferences']: raise CatalogError(f'Duplicate setting key: {key}')
            shape(definition, {'type', 'default', 'min', 'max', 'portable', 'appearance', 'validator'}, {'type', 'default'})
            if definition['type'] not in ('boolean', 'integer', 'number', 'string', 'object', 'array'):
                raise CatalogError(f'Invalid setting type: {key}')
            result['preferences'][key] = definition
        for kind, id_key in KINDS.items():
            if kind not in descriptor: continue
            item = descriptor[kind]
            required = {id_key, 'title', 'entry'} | ({'icon'} if kind != 'controlTab' else set())
            shape(item, FIELDS[kind], required)
            item_id = identifier(item[id_key])
            if item_id in result['ids'][kind]: raise CatalogError(f'Duplicate {kind} ID: {item_id}')
            for key, value in item.items():
                if key in ('refresh', 'markRead'):
                    if type(value) is not bool: raise CatalogError(f'Invalid tab flag: {key}')
                elif not isinstance(value, str) or not value:
                    raise CatalogError(f'Invalid {kind} field: {key}')
            resource(root, item['entry'], '.qml')
            result['ids'][kind].append(item_id)
            result['all'][kind].append(dict(item, enabled=record['enabled']))
            if record['enabled']: result[kind].append(dict(item))
    return validate_legacy(result, legacy, setting_keys)


@lru_cache(maxsize=1)
def catalog():
    """Only process owners cache; explicit fixture reads remain independent."""
    return load_catalog()


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        data = catalog()
        if args and args[0] == '--page' and len(args) >= 2:
            page, legacy = args[1], args[2:]
            validate_legacy(data, {'settingsPage': legacy})
            if page not in legacy and page not in [item['key'] for item in data['settingsPage']]:
                print(f'Error: unknown settings page: {page}', file=sys.stderr)
                return 2
        elif args:
            raise CatalogError('Unsupported catalog arguments')
        else:
            print(json.dumps(data, separators=(',', ':')))
    except CatalogError as error:
        print(f'Feature catalog: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
