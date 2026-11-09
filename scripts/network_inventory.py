"""Bounded, secret-free nmcli normalization; identifiers are never display labels.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: wifi; Phase 3 graph).
"""
# GOTCHA: nmcli output/terse formatting varies; parse defensively and never expose secrets in labels.
import json
import hashlib
import re

BASE = '/org/freedesktop/NetworkManager/'
UUID = re.compile(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}')
PROFILE_FIELDS = ('connection.uuid', 'connection.id', 'connection.type', 'connection.interface-name',
    'connection.master', 'connection.slave-type', '802-11-wireless.mode',
    '802-11-wireless-security.key-mgmt', 'ipv4.method', 'ipv4.addresses', 'ipv4.gateway', 'ipv4.dns',
    'ipv6.method', 'ipv6.addresses', 'ipv6.gateway', 'ipv6.dns')
LIST_FIELDS = 'UUID,TYPE,NAME,DEVICE,STATE,ACTIVE-PATH,SLAVE'
DEVICE_FIELDS = 'GENERAL,WIFI-PROPERTIES,WIRED-PROPERTIES,CONNECTIONS,IP4,IP6'
TYPES = {'vpn': 'vpn', 'wireguard': 'wireguard', '802-3-ethernet': 'ethernet',
         'ethernet': 'ethernet', '802-11-wireless': 'wifi', 'wifi': 'wifi'}


def text(value):
    if not isinstance(value, str) or len(value) > 4096: raise ValueError('Invalid NetworkManager value')
    return '' if value == '--' else value


def label(value): return ' '.join(text(value).split())[:160]


def uuid(value):
    if not isinstance(value, str) or not UUID.fullmatch(value): raise ValueError('Invalid saved connection UUID')
    return value.lower()


def interface(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.:-]{0,62}', value):
        raise ValueError('Unsupported network interface name')
    return value


def path(value, kind):
    if not isinstance(value, str) or len(value) > 256 or not re.fullmatch(re.escape(BASE+kind+'/')+r'[0-9]+', value):
        raise ValueError('Invalid NetworkManager object identity')
    return value


def key_value(line):
    # Multiline rows are KEY:VALUE with colon-free keys, but nmcli's escaping of colons in
    # multiline values changed across versions: <=1.4x printed `key:v\\:al`, >=1.5x prints the
    # raw `key:v:al` (verified on 1.56.1). Split at the first unescaped colon; in the value
    # only the legacy `\\:` escape is folded to `:` — raw backslashes stay literal, so both
    # spellings converge without eating modern names' backslashes.
    cut = -1
    for index, character in enumerate(line):
        if character == ':':
            backslashes = 0; probe = index - 1
            while probe >= 0 and line[probe] == '\\': backslashes += 1; probe -= 1
            if backslashes % 2 == 0: cut = index; break
    if cut < 0: return [line]
    value = []
    index = cut + 1
    while index < len(line):
        if line[index] == '\\' and index + 1 < len(line) and line[index + 1] == ':':
            value.append(':'); index += 2
        else:
            value.append(line[index]); index += 1
    return [line[:cut], ''.join(value)]


def blocks(raw, first):
    result = []
    for line in raw.splitlines():
        if not line.strip(): continue
        fields = key_value(line)
        if len(fields) != 2: raise ValueError('Invalid NetworkManager property row')
        key, value = fields; value = text(value)
        if key == first: result.append({})
        if not result or key in result[-1]: raise ValueError('Ambiguous NetworkManager property block')
        result[-1][key] = value
    return result


def connections(raw, split):
    result = []
    for line in raw.splitlines():
        fields = split(line)
        if len(fields) != 7 or len(result) >= 256: raise ValueError('Invalid or oversized connection listing')
        ident, kind, name, devices, state, active, slave = map(text, fields)
        result.append(dict(uuid=uuid(ident), type=kind, name=label(name), interfaces=devices,
                           state=state, path=path(active, 'ActiveConnection') if active else '', slave=slave))
    return result


def candidates(rows):
    ids = list(dict.fromkeys(row['uuid'] for row in rows if row['type'] in TYPES and not row['slave']))
    if len(ids) > 128: raise ValueError('Too many saved profiles to inspect safely')
    return ids


def devices(raw, radio, split):
    values = blocks(raw, 'GENERAL.DEVICE')
    if len(values) > 64: raise ValueError('Network device inventory exceeds 64 objects')
    enabled = split(radio.strip())
    if len(enabled) != 2 or any(v not in ('enabled', 'disabled') for v in enabled):
        raise ValueError('Invalid Wi-Fi radio state')
    result = []
    for v in values:
        ident = path(v.get('GENERAL.DBUS-PATH'), 'Devices'); name = interface(v.get('GENERAL.DEVICE'))
        try: state = int(v.get('GENERAL.STATE', '').split()[0])
        except (ValueError, IndexError): raise ValueError('Invalid network device state') from None
        compatible = []
        for key, value in v.items():
            if key.startswith('CONNECTIONS.AVAILABLE-CONNECTIONS') and value:
                compatible.append(uuid(value.split('|', 1)[0].strip()))
        addresses = lambda family, field: [label(value) for key, value in v.items()
            if key.startswith(family+'.'+field+'[') and value]
        result.append(dict(id=ident, interface=name, kind=v.get('GENERAL.TYPE', ''), state=state,
            managed=v.get('GENERAL.NM-MANAGED') == 'yes', connected=state == 100,
            activeUuid=uuid(v['GENERAL.CON-UUID']) if v.get('GENERAL.CON-UUID') else '',
            activePath=path(v['GENERAL.CON-PATH'], 'ActiveConnection') if v.get('GENERAL.CON-PATH') else '',
            connection=label(v.get('GENERAL.CONNECTION', '')), compatible=list(dict.fromkeys(compatible)),
            ap=v.get('WIFI-PROPERTIES.AP') == 'yes', radio=all(v == 'enabled' for v in enabled),
            carrier=None if not v.get('WIRED-PROPERTIES.CARRIER') else v['WIRED-PROPERTIES.CARRIER'] == 'yes',
            ip4=addresses('IP4', 'ADDRESS'), ip6=addresses('IP6', 'ADDRESS'),
            dns4=addresses('IP4', 'DNS'), dns6=addresses('IP6', 'DNS'),
            gateway4=label(v.get('IP4.GATEWAY', '')), gateway6=label(v.get('IP6.GATEWAY', ''))))
    if len({d['id'] for d in result}) != len(result) or len({d['interface'] for d in result}) != len(result):
        raise ValueError('Ambiguous network devices')
    return result


def inventory(server, device_raw, rows, detail_raw, radio_raw, split):
    devs = devices(device_raw, radio_raw, split); details = blocks(detail_raw, 'connection.uuid')
    wanted = set(candidates(rows)); found = {}; profiles = []
    for p in details:
        ident = uuid(p.get('connection.uuid'))
        if ident not in wanted: continue
        if ident in found:
            if found[ident] != p: raise ValueError('Conflicting saved connection details')
            continue
        found[ident] = p
        kind = TYPES.get(p.get('connection.type'))
        if any(TYPES.get(row['type']) != kind for row in rows if row['uuid'] == ident):
            raise ValueError('Saved connection types changed during inspection; refresh')
        if not kind or p.get('connection.master') or p.get('connection.controller') or p.get('connection.slave-type') or p.get('connection.port-type'): continue
        mode = p.get('802-11-wireless.mode', '')
        if kind == 'wifi':
            if mode != 'ap': continue
            kind = 'hotspot'
        bound = p.get('connection.interface-name', '')
        if bound: interface(bound)
        settings = {key: label(p.get(key, '')) for key in PROFILE_FIELDS if key.startswith(('ipv4.', 'ipv6.'))}
        compatible = []
        for d in devs:
            if not d['managed']: continue
            if kind == 'vpn': eligible = d['connected'] and d['kind'] in ('wifi', 'ethernet', 'bridge', 'bond', 'vlan')
            else: eligible = ident in d['compatible'] and d['kind'] == ('wifi' if kind == 'hotspot' else 'ethernet') and (not bound or bound == d['interface'])
            if eligible: compatible.append(d['id'])
        if kind == 'wireguard': compatible = ['virtual/'+ident] if bound else []
        profiles.append(dict(uuid=ident, name=label(p.get('connection.id', '')), kind=kind,
            interface=bound, compatible=compatible, settings=settings, mode=mode,
            security=p.get('802-11-wireless-security.key-mgmt', '')))
    if set(found) != wanted: raise ValueError('Saved connections changed during inspection')
    if len(profiles) > 64: raise ValueError('Connection inventory exceeds 64 profiles')
    ids = {p['uuid'] for p in profiles}; active = []
    for row in rows:
        if row['uuid'] not in ids or not row['path']: continue
        interfaces = [interface(s.strip()) for s in row['interfaces'].split(',') if s.strip()]
        for name in interfaces or ['']:
            d = next((d for d in devs if d['interface'] == name), None)
            active.append(dict(uuid=row['uuid'], deviceId=d['id'] if d else '', interface=name,
                               path=row['path'], state=row['state']))
    if len(active) > 128 or len({(a['path'], a['deviceId']) for a in active}) != len(active):
        raise ValueError('Ambiguous or oversized active connections')
    model = dict(available=True, serverId=server, devices=devs, profiles=profiles, active=active,
                 error='', notice='', hotspotPlan=None)
    # Leave room for the bounded operation/retry identifiers installed by the owner.
    if len(json.dumps(model, ensure_ascii=True).encode()) > 126*1024: raise ValueError('Network metadata exceeds 128 KiB')
    return model


def demo_inventory():
    profiles = []; devs = []
    for index, (name, kind) in enumerate((('Work VPN', 'vpn'), ('Desk Ethernet', 'ethernet'), ('Phone sharing', 'hotspot'), ('Work WireGuard', 'wireguard')), 1):
        ident = '00000000-0000-0000-0000-'+f'{index:012d}'
        profiles.append(dict(uuid=ident, name=name, kind=kind, interface='wg-demo' if kind == 'wireguard' else '',
            compatible=['virtual/'+ident] if kind == 'wireguard' else [BASE+'Devices/'+('1' if kind == 'hotspot' else '2')],
            settings={'ipv4.method': 'shared' if kind == 'hotspot' else 'auto', 'ipv4.addresses': '', 'ipv4.gateway': '', 'ipv4.dns': '', 'ipv6.method': 'auto'},
            mode='ap' if kind == 'hotspot' else '', security='wpa-psk' if kind == 'hotspot' else ''))
    for i, kind, name in ((1, 'wifi', 'wlan-demo'), (2, 'ethernet', 'eth-demo')):
        devs.append(dict(id=BASE+'Devices/'+str(i), interface=name, kind=kind, state=100, managed=True, connected=True,
            activeUuid='00000000-0000-0000-0000-000000000099' if i == 1 else profiles[1]['uuid'],
            activePath=BASE+'ActiveConnection/'+str(i), connection='Home Wi-Fi' if i == 1 else 'Desk Ethernet',
            compatible=[p['uuid'] for p in profiles], ap=i == 1, radio=True, carrier=True,
            ip4=['192.0.2.2/24'], ip6=[], dns4=['192.0.2.1'], dns6=[], gateway4='192.0.2.1', gateway6=''))
    return dict(available=True, serverId=hashlib.sha256(b'demo-network-manager').hexdigest(), profiles=profiles, devices=devs,
        active=[dict(uuid=profiles[1]['uuid'], deviceId=devs[1]['id'], interface=devs[1]['interface'], path=BASE+'ActiveConnection/2', state='activated')],
        error='', notice='Demo data; no NetworkManager commands are executed.', hotspotPlan=None)
