"""Static catalog vocabulary and navigation compatibility validation."""
KINDS = {'bar': 'id', 'settingsPage': 'key', 'controlTab': 'id', 'agendaTab': 'id', 'panel': 'id', 'bootstrap': 'id', 'gesture': 'id'}
FIELDS = {
    'bar': {'id', 'title', 'detail', 'icon', 'entry', 'after'},
    'settingsPage': {'key', 'title', 'icon', 'description', 'keywords', 'entry', 'after'},
    'controlTab': {'id', 'title', 'entry', 'refresh', 'markRead', 'after', 'legacyIndex'},
    'agendaTab': {'id', 'title', 'entry', 'after', 'legacyIndex', 'setting', 'fallback'},
    'panel': {'id', 'entry', 'centered', 'scrim'},
    'bootstrap': {'id', 'entry', 'contexts'},
    'gesture': {'id', 'title', 'after'},
}

def validate_indices(data, navigation, error):
    for kind, field in [('controlTab', 'tabs'), ('agendaTab', 'agendaTabs')]:
        seen = set()
        for item in navigation.get(field, []) + data['all'][kind]:
            if 'legacyIndex' not in item: continue
            value = item['legacyIndex']
            if type(value) is not int or not 0 <= value <= 2147483647 or value in seen:
                raise error(f'Invalid or duplicate {kind} legacyIndex: {value!r}')
            seen.add(value)


def validate_contexts(value, error):
    allowed = {'live-main', 'demo', 'preview', 'settings'}
    if (not isinstance(value, list) or not value or any(type(item) is not str or item not in allowed for item in value)
            or len(set(value)) != len(value)):
        raise error('Invalid bootstrap contexts')
