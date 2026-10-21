"""Read the bundled, data-only feature catalog; stdlib, no registration side effects."""
from functools import lru_cache
import json
from pathlib import Path
import re
import signal
import sys

KINDS = {'bar': 'id', 'settingsPage': 'key', 'controlTab': 'id', 'panel': 'id', 'bootstrap': 'id', 'gesture': 'id'}
FIELDS = {
    'bar': {'id', 'title', 'detail', 'icon', 'entry', 'after'},
    'settingsPage': {'key', 'title', 'icon', 'description', 'keywords', 'entry', 'after'},
    'controlTab': {'id', 'title', 'entry', 'refresh', 'markRead', 'after'},
    'panel': {'id', 'entry', 'centered', 'scrim'},
    'bootstrap': {'id', 'entry'},
    'gesture': {'id', 'title', 'after'},
}


class CatalogError(ValueError):
    """An invalid bundled catalog must not shadow legacy registrations."""


def empty_catalog():
    return {'version': 1, **{kind: [] for kind in KINDS}, 'preferences': {}, 'preferenceMetadata': {},
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
        if isinstance(error, CatalogError): raise
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
    validate_positions(data, legacy or {})
    return data


def validate_positions(data, legacy):
    for kind, entries in data['all'].items():
        key = KINDS[kind]; anchors = {item[key]: item.get('after') for item in entries}
        known = set(legacy.get(kind, ())) | set(anchors)
        for ident, after in anchors.items():
            if after is None: continue
            identifier(after)
            if kind in legacy and after not in known: raise CatalogError(f'Missing {kind} anchor: {after}')
            visited = {ident}
            while after in anchors:
                if after in visited: raise CatalogError(f'Cyclic {kind} position: {ident}')
                visited.add(after); after = anchors[after]


def legacy_ids(root):
    """Read the existing registrations until their owners leave the legacy lists."""
    root = Path(root); result = {}
    sources = [('bar', 'qml/bar/BarRegistry.qml', 'legacyModules'),
        ('settingsPage', 'qml/settings/SettingsRegistry.qml', 'legacyPages'),
        ('gesture', 'qml/bar/BarGestures.qml', 'legacyActions'),
        ('panel', 'qml/services/ShellState.qml', 'legacyPanels')]
    for kind, source, field in sources:
        path = root/source
        if not path.exists(): continue
        match = re.search(r'\b' + field + r':\s*\[(.*?)\]', path.read_text(), re.S)
        if not match: raise CatalogError(f'Missing legacy registration field: {field}')
        pattern = r'"([A-Za-z][A-Za-z0-9_-]*)"' if kind == 'panel' else r'\b' + KINDS[kind] + r': "([A-Za-z][A-Za-z0-9_-]*)"'
        result[kind] = re.findall(pattern, match[1])
    path = root/'config/control-grid.json'
    if path.exists(): result['controlTab'] = [item['id'] for item in document(path)['tabs']]
    return result


def load_catalog(root=None, *, legacy=None, setting_keys=()):
    root = (Path(root) if root is not None else Path(__file__).resolve().parents[1]).resolve()
    index = document(resource(root, 'config/features.json', '.json'))
    shape(index, {'version', 'features'}, {'version', 'features'})
    if type(index['version']) is not int or index['version'] != 1 or not isinstance(index['features'], list):
        raise CatalogError('Unsupported feature catalog version or index')
    result = empty_catalog()
    for record in index['features']:
        shape(record, {'id', 'descriptor', 'enabled', 'startup'}, {'id', 'descriptor', 'enabled'})
        ident = identifier(record['id'])
        if type(record['enabled']) is not bool: raise CatalogError('Invalid enabled flag')
        if ident in result['ids']['features']: raise CatalogError(f'Duplicate feature ID: {ident}')
        result['ids']['features'].append(ident)
        descriptor = document(resource(root, record['descriptor'], '.json'))
        shape(descriptor, {'id', 'sources', 'preferences', 'preferenceMetadata', *KINDS}, {'id'})
        if descriptor['id'] != ident: raise CatalogError(f'Descriptor ID does not match index: {ident}')
        startup = record.get('startup', {})
        shape(startup, set(KINDS), set())
        for kind, item in startup.items():
            if kind in descriptor and descriptor[kind] != item:
                raise CatalogError(f'Conflicting startup metadata: {ident}/{kind}')
            descriptor[kind] = item
        sources = descriptor.get('sources', [])
        if not isinstance(sources, list): raise CatalogError('Invalid sources')
        for source in sources: resource(root, source)
        metadata = descriptor.get('preferenceMetadata', {})
        if not isinstance(metadata, dict): raise CatalogError('Invalid preference metadata')
        for key, definition in metadata.items():
            identifier(key)
            shape(definition, {'type', 'default', 'min', 'max'}, {'type', 'default'})
            if key in result['preferenceMetadata']: raise CatalogError(f'Duplicate metadata key: {key}')
            result['preferenceMetadata'][key] = definition
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
            required = {id_key} | ({'entry'} if kind != 'gesture' else set()) | ({'title'} if kind not in ('panel', 'bootstrap') else set()) | ({'icon'} if kind in ('bar', 'settingsPage') else set())
            shape(item, FIELDS[kind], required)
            item_id = identifier(item[id_key])
            if item_id in result['ids'][kind]: raise CatalogError(f'Duplicate {kind} ID: {item_id}')
            for key, value in item.items():
                if key in ('refresh', 'markRead', 'centered'):
                    if type(value) is not bool: raise CatalogError(f'Invalid tab flag: {key}')
                elif key == 'scrim':
                    if type(value) not in (int, float) or not 0 <= value <= 1: raise CatalogError('Invalid panel scrim')
                elif not isinstance(value, str) or not value:
                    raise CatalogError(f'Invalid {kind} field: {key}')
            if 'entry' in item: resource(root, item['entry'], '.qml')
            result['ids'][kind].append(item_id)
            result['all'][kind].append(dict(item, enabled=record['enabled']))
            if record['enabled']: result[kind].append(dict(item))
    return validate_legacy(result, legacy, setting_keys)


def bounded(operation):
    def expired(*_): raise CatalogError('Validation timed out; using legacy entries')
    previous = signal.signal(signal.SIGALRM, expired)
    timer = signal.setitimer(signal.ITIMER_REAL, 3)
    try:
        return operation()
    finally:
        signal.setitimer(signal.ITIMER_REAL, *timer)
        signal.signal(signal.SIGALRM, previous)


@lru_cache(maxsize=1)
def catalog():
    """Only process owners cache; explicit fixture reads remain independent."""
    return bounded(load_catalog)


def page_keys():
    """Admission only; backend validation gates QML resource loading separately."""
    index = document(Path(__file__).resolve().parents[1] / 'config/features.json')
    shape(index, {'version', 'features'}, {'version', 'features'})
    if type(index['version']) is not int or index['version'] != 1 or not isinstance(index['features'], list):
        raise CatalogError('Unsupported feature catalog version or index')
    keys = []
    for record in index['features']:
        shape(record, {'id', 'descriptor', 'enabled', 'startup'}, {'id', 'descriptor', 'enabled'})
        if type(record['enabled']) is not bool: raise CatalogError('Invalid enabled flag')
        startup = record.get('startup', {})
        shape(startup, set(KINDS), set())
        page = startup.get('settingsPage', {})
        if not isinstance(page, dict): raise CatalogError('Invalid settings page')
        if page and record['enabled']: keys.append(identifier(page.get('key')))
    return keys


def canonical_index(index):
    """One compact record per line; startup page keys remain literal and first."""
    records = []
    for value in index['features']:
        record = dict(id=value['id'], **{key: item for key, item in value.items() if key != 'id'})
        if 'settingsPage' in record.get('startup', {}):
            page = record['startup']['settingsPage']
            record['startup'] = dict(record['startup'], settingsPage=dict(
                key=page['key'], **{key: item for key, item in page.items() if key != 'key'}))
        records.append(json.dumps(record, separators=(',', ':'), ensure_ascii=True))
    return '{"version":1,"features":[' + ('\n'+',\n'.join(records)+'\n' if records else '') + ']}\n'


def check_admission(data):
    path = Path(__file__).resolve().parents[1] / 'config/features.json'
    index = document(path)
    keys = {record.get('startup', {}).get('settingsPage', {}).get('key') for record in index['features']}
    if any(page['key'] not in keys for page in data['all']['settingsPage']):
        raise CatalogError('Settings pages require startup keys in the index')
    validate_legacy(data, legacy_ids(path.parents[1]))
    if path.read_text(encoding='utf-8') != canonical_index(index):
        raise CatalogError('Noncanonical feature index: require compact records on separate lines and literal first page keys')


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        if args and args[0] == '--page' and len(args) >= 2:
            page, legacy = args[1], args[2:]
            if page in legacy: return 0
            try: keys = bounded(page_keys)
            except CatalogError as error:
                print(f'Feature catalog: {error}', file=sys.stderr)
                keys = []
            if page not in keys:
                print(f'Error: unknown settings page: {page}', file=sys.stderr)
                return 2
        elif args == ['--check']:
            bounded(lambda: check_admission(catalog()))
        elif args:
            raise CatalogError('Unsupported catalog arguments')
        else:
            print(json.dumps(catalog(), separators=(',', ':')))
    except CatalogError as error:
        print(f'Feature catalog: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
