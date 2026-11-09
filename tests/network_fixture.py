"""Secret-free nmcli fixtures: never access the real system bus or adapters.
Contract: network_fixture.py covers network_fixture behavior/contracts; check imports for fixtures/helpers under test.
"""
import copy
import json
import threading

from test_backend import FakeRunner

PREFIX = '/org/freedesktop/NetworkManager/'
DEV = [PREFIX+'Devices/'+str(i) for i in (1, 2, 3)]
UUIDS = ['00000000-0000-0000-0000-'+f'{i:012d}' for i in range(1, 9)]


def data():
    def profile(index, kind, name, interface='', **props):
        return {'connection.uuid': UUIDS[index], 'connection.id': name, 'connection.type': kind,
            'connection.interface-name': interface, 'connection.master': '', 'connection.slave-type': '',
            'ipv4.method': 'auto', 'ipv4.addresses': '', 'ipv4.gateway': '', 'ipv4.dns': '',
            'ipv6.method': 'auto', 'ipv6.addresses': '', 'ipv6.gateway': '', 'ipv6.dns': '', **props}
    profiles = [profile(0, 'vpn', 'Work: VPN'), profile(1, '802-3-ethernet', 'Office', 'enp1s0'),
        profile(2, '802-3-ethernet', 'Office', 'enp2s0'),
        profile(3, 'wireguard', 'WireGuard', 'wg0'),
        profile(4, '802-11-wireless', 'Share Wi-Fi', 'wlp1s0', **{'802-11-wireless.mode': 'ap',
            '802-11-wireless-security.key-mgmt': 'wpa-psk', 'ipv4.method': 'shared'}),
        profile(5, '802-11-wireless', 'Home', 'wlp1s0', **{'802-11-wireless.mode': 'infrastructure'}),
        profile(6, '802-3-ethernet', 'Bridge port', 'enp1s0', **{'connection.master': 'br0', 'connection.slave-type': 'bridge'})]
    devices = []
    for path, interface, kind, active in zip(DEV, ('wlp1s0', 'enp1s0', 'enp2s0'), ('wifi', 'ethernet', 'ethernet'), (UUIDS[5], UUIDS[1], '')):
        devices.append({'GENERAL.DEVICE': interface, 'GENERAL.DBUS-PATH': path,
            'GENERAL.TYPE': kind, 'GENERAL.NM-MANAGED': 'yes',
            'GENERAL.STATE': '100 (connected)' if active else '30 (disconnected)',
            'GENERAL.CON-UUID': active, 'GENERAL.CONNECTION': 'Home' if kind == 'wifi' else 'Office',
            'GENERAL.CON-PATH': PREFIX+'ActiveConnection/'+('1' if kind == 'wifi' else '2') if active else '',
            'GENERAL.HWADDR': 'AA:BB:CC:DD:EE:F' + ('1' if kind == 'wifi' else '2'),
            'WIFI-PROPERTIES.AP': 'yes' if kind == 'wifi' else '', 'WIRED-PROPERTIES.CARRIER': 'yes',
            'CONNECTIONS.AVAILABLE-CONNECTIONS[1]': (UUIDS[4] if kind == 'wifi' else active or UUIDS[2])+' | Saved profile',
            'IP4.ADDRESS[1]': '192.0.2.2/24', 'IP4.GATEWAY': '192.0.2.1', 'IP4.DNS[1]': '192.0.2.1',
            'IP6.ADDRESS[1]': '2001:db8::10/64', 'IP6.GATEWAY': 'fe80::1', 'IP6.DNS[1]': '2001:db8::53'})
    return dict(bus='a'*32, owner=':1.25', radio=['enabled', 'enabled'], profiles=profiles, devices=devices,
        active=[dict(uuid=UUIDS[5], device=DEV[0], path=PREFIX+'ActiveConnection/1', state='activated'),
                dict(uuid=UUIDS[1], device=DEV[1], path=PREFIX+'ActiveConnection/2', state='activated')])


def escape(value):
    return str(value).replace('\\', '\\\\').replace(':', '\\:')


def device_text(state):
    # nmcli >= 1.5x prints multiline values RAW (verified on 1.56.1: HWADDR/IPv6 colons are
    # not escaped), so the fixture mirrors that; key_value accepts this and the legacy
    # escaped spelling (test_native_inventory pins their equivalence).
    return '\n\n'.join('\n'.join(key+':'+str(value) for key, value in d.items()) for d in state['devices'])


def profile_text(state):
    return '\n\n'.join('\n'.join(key+':'+str(value) for key, value in p.items()) for p in state['profiles'])


def connection_text(state):
    rows = []
    for p in state['profiles']:
        active = [a for a in state['active'] if a['uuid'] == p['connection.uuid']]
        for a in active or [{}]:
            device = next((d['GENERAL.DEVICE'] for d in state['devices'] if d['GENERAL.DBUS-PATH'] == a.get('device')), '')
            rows.append(':'.join(map(escape, [p['connection.uuid'], p['connection.type'], p['connection.id'],
                device, a.get('state', ''), a.get('path', ''), p['connection.slave-type']])))
    return '\n'.join(rows)


class NetworkRunner(FakeRunner):
    def __init__(self):
        super().__init__(available={'nmcli', 'busctl', 'nm-connection-editor'})
        self.model = data(); self.options = []; self.writes = []; self.fail = None
        self.apply = True; self.started = threading.Event(); self.release = threading.Event(); self.block = False

    def run(self, name, *args, **kwargs):
        self.calls.append((name, *args)); self.options.append(kwargs)
        if name == 'busctl':
            return json.dumps(dict(type='s', data=[self.model['bus'] if args[-1] == 'GetId' else self.model['owner']]))
        if 'up' in args or 'down' in args:
            self.writes.append(args); self.started.set()
            if self.block and 'up' in args:
                while not self.release.wait(.01):
                    if kwargs.get('observe'): kwargs['observe'](b'', b'')
            if self.fail: raise self.fail
            if self.apply: self.mutate(args)
            return 'Connection operation completed'
        if args[-1] == 'general': return ':'.join(self.model['radio'])
        if args[-2:] == ('device', 'show'): return device_text(self.model)
        if 'connection' in args and 'show' in args:
            return profile_text(self.model) if 'uuid' in args else connection_text(self.model)
        raise AssertionError((name, args))

    def mutate(self, args):
        if 'down' in args:
            path = args[-1]
            self.model['active'] = [a for a in self.model['active'] if a['path'] != path]
            for d in self.model['devices']:
                if d['GENERAL.CON-PATH'] == path:
                    d.update({'GENERAL.CON-PATH': '', 'GENERAL.CON-UUID': '', 'GENERAL.STATE': '30 (disconnected)'})
            return
        uuid = args[args.index('uuid')+1]
        p = next(p for p in self.model['profiles'] if p['connection.uuid'] == uuid)
        interface = args[args.index('ifname')+1] if 'ifname' in args else p['connection.interface-name']
        if p['connection.type'] == 'wireguard' and not any(d['GENERAL.DEVICE'] == interface for d in self.model['devices']):
            self.model['devices'].append({'GENERAL.DEVICE': interface, 'GENERAL.DBUS-PATH': PREFIX+'Devices/9',
                'GENERAL.TYPE': 'wireguard', 'GENERAL.NM-MANAGED': 'yes', 'GENERAL.STATE': '30 (disconnected)'})
        d = next(d for d in self.model['devices'] if d['GENERAL.DEVICE'] == interface)
        path = PREFIX+'ActiveConnection/'+str(10+len(self.writes))
        if p['connection.type'] != 'vpn':
            self.model['active'] = [a for a in self.model['active'] if a['device'] != d['GENERAL.DBUS-PATH']]
            d.update({'GENERAL.CON-PATH': path, 'GENERAL.CON-UUID': uuid, 'GENERAL.STATE': '100 (connected)'})
        self.model['active'].append(dict(uuid=uuid, device=d['GENERAL.DBUS-PATH'], path=path, state='activated'))

    def clone(self): return copy.deepcopy(self.model)
