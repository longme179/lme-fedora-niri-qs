"""Fresh profile/device selection and explicit hotspot confirmation; no I/O."""
import hashlib
import json
import re

from network_inventory import interface, path, uuid

ACTIONS = ('networkRefresh', 'networkConnect', 'networkDisconnect', 'networkHotspotPlan', 'networkHotspotStart', 'networkEdit')
MUTATIONS = frozenset(('networkConnect', 'networkDisconnect', 'networkHotspotStart', 'networkEdit'))


def validate(action, request):
    if action == 'networkRefresh': return
    uuid(request.get('uuid'))
    if not isinstance(request.get('serverId'), str) or not re.fullmatch(r'[0-9a-f]{64}', request['serverId']):
        raise ValueError('Refresh network connections before retrying')
    if action != 'networkEdit':
        device = request.get('deviceId')
        if isinstance(device, str) and device.startswith('virtual/'): uuid(device[8:])
        else: path(device, 'Devices')
    if action == 'networkDisconnect': path(request.get('activePath'), 'ActiveConnection')
    if action == 'networkHotspotStart' and (request.get('confirmed') is not True or
        not isinstance(request.get('planToken'), str) or not re.fullmatch(r'[0-9a-f]{64}', request['planToken'])):
        raise ValueError('Review and confirm the hotspot warning first')


def select(model, request, *, disconnect=False):
    if model['serverId'] != request['serverId']: raise ValueError('NetworkManager changed; refresh connections')
    profile = next((p for p in model['profiles'] if p['uuid'] == uuid(request['uuid'])), None)
    if not profile: raise ValueError('Saved connection disappeared or is unsupported; refresh')
    ident = request.get('deviceId')
    if ident == 'virtual/'+profile['uuid'] and profile['kind'] == 'wireguard':
        interface(profile['interface'])
        return profile, dict(id=ident, interface=profile['interface'], activePath='', activeUuid='', connection='', state=30)
    device = next((d for d in model['devices'] if d['id'] == ident), None)
    if not device: raise ValueError('The selected network adapter disappeared; refresh')
    if not disconnect:
        if device['id'] not in profile['compatible']: raise ValueError('This profile is not compatible with the selected adapter')
        if 40 <= device['state'] < 100: raise ValueError('This adapter is still changing; stop its connection or wait')
        if profile['kind'] == 'ethernet' and device['carrier'] is False: raise ValueError('Connect the Ethernet cable first')
    return profile, device


def active_for(model, profile, device):
    return [a for a in model['active'] if a['uuid'] == profile['uuid'] and
        (a['deviceId'] == device['id'] or profile['kind'] == 'wireguard' and a['interface'] == profile['interface'])]


def hotspot_plan(model, request):
    profile, device = select(model, request)
    if any(a['uuid'] == profile['uuid'] and a['deviceId'] != device['id'] for a in model['active']):
        raise ValueError('This hotspot profile is active on another adapter; stop it explicitly first')
    if profile['kind'] != 'hotspot' or profile['mode'] != 'ap' or profile['settings']['ipv4.method'] != 'shared' or profile['security'] not in ('wpa-psk', 'sae'):
        raise ValueError('Choose a saved WPA-PSK/SAE hotspot with shared IPv4 in Advanced network settings')
    if not device.get('ap') or not device.get('radio'):
        raise ValueError('This adapter must support AP mode with hardware/software Wi-Fi enabled')
    identity = dict(server=model['serverId'], profile=profile,
        device={k: device[k] for k in ('id', 'interface', 'activePath', 'activeUuid', 'managed', 'ap', 'radio')})
    token = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    other = [d['interface'] for d in model['devices'] if d['id'] != device['id'] and d['connected'] and d['kind'] in ('wifi', 'ethernet', 'bridge', 'bond', 'vlan')]
    return dict(token=token, uuid=profile['uuid'], deviceId=device['id'], name=profile['name'], interface=device['interface'],
        disconnectWifi=bool(device['activePath'] and device['activeUuid'] != profile['uuid']),
        previousConnection=device['connection'], uplinks=other,
        warning='NetworkManager applies this profile\'s shared IP, DHCP/NAT, routes and firewall policy. Internet access is not verified.')
