"""Measurement-only full replacement in a copied checkout; no product conversion."""
import json
import re

from catalog_measurement import synthetic


def replace_legacy(root):
    metadata = synthetic(root, compact=True)
    fixture = json.loads((root/'tests/fixtures/catalog-legacy.json').read_text())
    path = root/'config/features.json'; index = json.loads(path.read_text())
    groups = {'bar': ('bars', 'id'), 'settingsPage': ('pages', 'key'), 'controlTab': ('tabs', 'id')}
    positions = dict.fromkeys(groups, 0)
    for record in index['features']:
        for kind, (source, key) in groups.items():
            if kind not in record['startup']: continue
            old = fixture[source][positions[kind]]; positions[kind] += 1
            record['startup'][kind][key] = old[key]
    path.write_text(json.dumps(index))
    # Remove registrations, retain the actual factories so first-frame work stays comparable.
    for relative, name in [('qml/bar/BarRegistry.qml', 'legacyModules'), ('qml/settings/SettingsRegistry.qml', 'legacyPages')]:
        path = root/relative
        text, count = re.subn(r'(readonly property var '+name+r': )\[.*?\n    \]', r'\1[]', path.read_text(), flags=re.S)
        assert count == 1, relative
        path.write_text(text)
    path = root/'config/control-grid.json'; data = json.loads(path.read_text()); data['tabs'] = []
    path.write_text(json.dumps(data))
    path = root/'scripts/desktop_backend.py'
    text, count = re.subn(r'BAR_MODULES = \{.*?\}', 'BAR_MODULES = set()', path.read_text(), count=1, flags=re.S)
    assert count == 1
    path.write_text(text)
    for relative, expression in [('qml/bar/BarModule.qml', 'catalogEntry.entry ? catalogComponent : '),
                                  ('qml/settings/SettingsView.qml', 'root.currentPage.entry ? catalogPage : ')]:
        path = root/relative; text = path.read_text(); assert expression in text
        path.write_text(text.replace(expression, '', 1))
    path = root/'scripts/settings.sh'
    text, count = re.subn(r'^    utilities\|appearance\|.*\) ;;\n', '', path.read_text(), count=1, flags=re.M)
    assert count == 1
    path.write_text(text)
    metadata['json_bytes'] = (root/'config/features.json').stat().st_size + sum((root/item['descriptor']).stat().st_size for item in index['features'])
    return dict(metadata, mode='replace', total_bars=19, total_pages=16, total_tabs=6,
        limits='Registration/projection cost only. Copied host legacy arrays are removed; original IDs and '
        'bar/Settings factories remain for comparable first-frame work. CLI legacy admission is removed too, '
        'so Settings takes the index-only lookup path. Neither mode models migrated feature bootstrap, '
        'schema consumption, workers, tab factories or real GPU/hardware.')
