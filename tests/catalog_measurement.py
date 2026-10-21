"""M0 startup method with enabled, inert descriptors in a disposable checkout."""
import json
from pathlib import Path
import shutil
import tempfile

import migration_startup as startup


def synthetic(root, compact=False):
    legacy = json.loads((root/'tests/fixtures/catalog-legacy.json').read_text())
    (root/'qml/catalog-inert.qml').write_text('import QtQuick\nItem { implicitWidth: 30; implicitHeight: 30 }\n')
    records = []
    for kind, items, id_key in [('bar', legacy['bars'], 'id'), ('settingsPage', legacy['pages'], 'key'),
                               ('controlTab', legacy['tabs'], 'id'), ('preferences', range(30), None)]:
        for number, item in enumerate(items):
            ident = 'synthetic' + kind[0].upper() + kind[1:] + str(number)
            descriptor = {'id': ident, 'sources': ['qml/catalog-inert.qml']}
            if kind == 'preferences':
                descriptor[kind] = {'syntheticPreference'+str(number):
                    {'type': 'boolean', 'default': True, 'portable': True, 'appearance': False}}
            else:
                entry = dict(item)
                for key in ('legacyIndex', 'fallback', 'refresh', 'markRead'): entry.pop(key, None)
                entry.update({id_key: ident, 'entry': 'qml/catalog-inert.qml'})
                descriptor[kind] = entry
            path = 'config/feature-' + ident + '.json'
            record = {'id': ident, 'descriptor': path, 'enabled': True}
            if compact:
                record['startup'] = {key: descriptor.pop(key) for key in ('bar', 'settingsPage', 'controlTab') if key in descriptor}
            (root/path).write_text(json.dumps(descriptor))
            records.append(record)
    (root/'config/features.json').write_text(json.dumps({'version': 1, 'features': records}))
    assert len(records) == len(legacy['bars']) + len(legacy['pages']) + len(legacy['tabs']) + 30
    return {'compact': compact, 'descriptors': len(records), 'bars': len(legacy['bars']), 'pages': len(legacy['pages']),
            'tabs': len(legacy['tabs']), 'preference_fragments': 30,
            'json_bytes': sum((root/item['descriptor']).stat().st_size for item in records)
                          + (root/'config/features.json').stat().st_size}


def measure():
    original = startup.REPO
    with tempfile.TemporaryDirectory(prefix='synthetic-', dir=startup.OUTPUT) as directory:
        root = Path(directory)/'checkout'
        shutil.copytree(original, root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        metadata = synthetic(root)
        startup.REPO = root
        try: result = startup.measure(5)
        finally: startup.REPO = original
    result['synthetic'] = metadata
    result['limits'] = ('Enabled inert entries append to legacy lists with unique IDs; the Settings sidebar therefore '
        'has extra rows. Models JSON I/O, validation, process transport and registry projections. '
        'Does not model migrated feature execution, bootstrap/workers, schema consumption, or hardware rendering. '
        'No production registration is converted.')
    return result


if __name__ == '__main__':
    result = measure()
    (startup.OUTPUT/'startup-synthetic.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Synthetic medians: '+str({key: result[key]['median_seconds'] for key in ('preview', 'settings')}), flush=True)
