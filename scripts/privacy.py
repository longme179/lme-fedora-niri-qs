"""PipeWire capture classification, reviewed against DMS and Noctalia (MIT)."""
# SPDX-License-Identifier: GPL-3.0-or-later
import math


def flag(value):
    return value is True or value in ('true', '1', 1)


def captures(objects):
    if not isinstance(objects, list):
        raise ValueError('Invalid PipeWire snapshot')
    linked = set()
    for item in objects:
        if not isinstance(item, dict): continue
        info = item.get('info') or {}
        if item.get('type', '').endswith(':Link') and info.get('state') == 'active':
            linked.update([info.get('output-node-id'), info.get('input-node-id')])
    active = []
    for item in objects:
        if not isinstance(item, dict) or not item.get('type', '').endswith(':Node'): continue
        info = item.get('info') or {}; props = info.get('props') or {}
        if info.get('state') != 'running' and item.get('id') not in linked: continue
        media = props.get('media.class', '')
        name = props.get('application.name') or props.get('node.description') or props.get('node.name') or 'Unknown application'
        identity = ' '.join(str(props.get(key, '')) for key in ('node.name', 'media.name', 'node.description')).lower()
        screen = any(word in identity for word in ('screencast', 'screen-cast', 'screen capture', 'xdg-desktop-portal', 'niri'))
        muted = any(p.get('mute') is True for p in (info.get('params') or {}).get('Props', []) if isinstance(p, dict))
        if media == 'Stream/Input/Audio':
            # Noctalia excludes passive loopbacks and monitor-sink captures.
            if props.get('node.link-group') or flag(props.get('node.passive')) or flag(props.get('stream.capture.sink')) or muted: continue
            if any(word in identity for word in ('cava', '.monitor', 'loopback')): continue
            kind = 'microphone'
        elif media in ('Video/Source', 'Stream/Input/Video', 'Stream/Output/Video'):
            kind = 'screen' if screen else 'camera'
        else: continue
        active.append({'kind': kind, 'name': str(name)[:160], 'id': item.get('id')})
    return active
