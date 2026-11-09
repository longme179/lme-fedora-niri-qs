"""On-demand NetworkManager I/O; no secrets, monitor, executor or saved shell state.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: wifi; Phase 3 graph).
"""
import hashlib
import json
import re
import time

from command_runner import CommandError
from network_inventory import DEVICE_FIELDS, LIST_FIELDS, PROFILE_FIELDS, candidates, connections, inventory
from network_plans import active_for, hotspot_plan, select


class NetworkFailure(CommandError):
    def __init__(self, message, state=None):
        super().__init__(message); self.state = state


class Cancelled(CommandError): pass


def safe_error(error):
    value = str(error).lower()
    if any(s in value for s in ('secret', 'password', 'authentication')):
        return 'NetworkManager needs credentials or an authentication agent. Use Advanced network settings.'
    if any(s in value for s in ('not authorized', 'permission', 'not permitted')):
        return 'NetworkManager denied permission. Check the session agent or Advanced network settings.'
    if 'plugin' in value or 'vpn service' in value:
        return 'The VPN plugin is unavailable. Install its NetworkManager plugin and use Advanced network settings.'
    if 'timed out' in value or 'timeout' in value:
        return 'Network operation timed out. Refresh the observed state before retrying.'
    return 'NetworkManager could not complete the operation. Refresh or use Advanced network settings.'


class NetworkProfiles:
    def __init__(self, capabilities):
        self.cap = capabilities

    def command(self, deadline, tool, *args, mutation=False, cancel=None):
        if cancel is not None and cancel.is_set(): raise Cancelled('Activation cancelled')
        remaining = deadline-time.monotonic()
        if remaining <= 0: raise CommandError('Network operation timed out')
        def observe(stdout, stderr):
            if cancel is not None and cancel.is_set(): raise Cancelled('Activation cancelled')
        try:
            return self.cap.wifi.run(tool, *args, timeout=min(18 if mutation else 2, remaining),
                max_output=1024*1024, **({'observe': observe} if mutation and cancel is not None else {}))
        except Cancelled: raise
        except CommandError as error: raise NetworkFailure(safe_error(error)) from None

    def epoch(self, deadline):
        def call(method, *args):
            raw = self.command(deadline, 'busctl', '--system', '--json=short', 'call',
                'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', method, *args)
            value = json.loads(raw)
            data = value.get('data') if isinstance(value, dict) else None
            if not isinstance(value, dict) or value.get('type') != 's' or not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], str):
                raise ValueError('NetworkManager identity is unavailable')
            return data[0]
        bus, owner = call('GetId'), call('GetNameOwner', 's', 'org.freedesktop.NetworkManager')
        if not re.fullmatch(r'[0-9a-fA-F]{32}', bus) or not re.fullmatch(r':[0-9]+\.[0-9]+', owner):
            raise ValueError('NetworkManager identity is unavailable')
        return hashlib.sha256((bus+'/'+owner).encode()).hexdigest()

    def read(self, deadline):
        if not all(self.cap.available(tool) for tool in ('nmcli', 'busctl')):
            raise NetworkFailure('Install NetworkManager/nmcli and systemd busctl to manage connections')
        server = self.epoch(deadline)
        radio = self.command(deadline, 'nmcli', '-t', '-f', 'WIFI-HW,WIFI', 'general')
        devices = self.command(deadline, 'nmcli', '-t', '-m', 'multiline', '-f', DEVICE_FIELDS, 'device', 'show')
        rows = connections(self.command(deadline, 'nmcli', '-t', '-f', LIST_FIELDS, 'connection', 'show'), self.cap.split)
        ids = candidates(rows)
        details = self.command(deadline, 'nmcli', '-t', '-m', 'multiline', '-f', ','.join(PROFILE_FIELDS),
            'connection', 'show', *(arg for ident in ids for arg in ('uuid', ident))) if ids else ''
        model = inventory(server, devices, rows, details, radio, self.cap.split)
        if self.epoch(deadline) != server: raise ValueError('NetworkManager changed during inspection; refresh')
        model['checkedAt'] = int(time.time()*1000)
        return model

    def inspect(self, action, request):
        model = None
        try:
            model = self.read(time.monotonic()+10)
            if action == 'networkHotspotPlan': model['hotspotPlan'] = hotspot_plan(model, request)
            if action == 'networkEdit':
                if model['serverId'] != request['serverId'] or not any(p['uuid'] == request['uuid'] for p in model['profiles']):
                    raise ValueError('Saved connection changed; refresh before editing')
                self.cap.spawn([self.cap.executable('nm-connection-editor'), '--edit='+request['uuid']])
            return dict(state=model, message='Network editor opened' if action == 'networkEdit' else 'Network connections refreshed')
        except (CommandError, ValueError, OSError, RecursionError) as error:
            raise NetworkFailure(str(error) if isinstance(error, (NetworkFailure, ValueError)) else safe_error(error), model) from None

    def stop_attempt(self, model, profile, device, before, deadline):
        for active in active_for(model, profile, device):
            siblings = [a for a in model['active'] if a['path'] == active['path']]
            if active['path'] in before or len(siblings) != 1: continue
            self.command(deadline, 'nmcli', '--wait', '5', 'connection', 'down', 'apath', active['path'], mutation=True)

    def change(self, action, request, cancel):
        model = None; attempted = False; before = set(); profile = device = None
        deadline = time.monotonic()+40
        try:
            if cancel.is_set(): raise Cancelled('Activation cancelled')
            model = self.read(min(deadline, time.monotonic()+10))
            profile, device = select(model, request, disconnect=action == 'networkDisconnect')
            existing = active_for(model, profile, device)
            if action == 'networkDisconnect':
                matching = [a for a in existing if a['path'] == request['activePath']]
                if len(matching) != 1 or len([a for a in model['active'] if a['path'] == request['activePath']]) != 1:
                    raise ValueError('Activation changed or spans multiple adapters; refresh or use Advanced settings')
                args = ('connection', 'down', 'apath', request['activePath'])
            else:
                if any(a['uuid'] == profile['uuid'] and a not in existing for a in model['active']):
                    raise ValueError('This profile is active on another adapter; disconnect it explicitly first')
                if action == 'networkHotspotStart':
                    plan = hotspot_plan(model, request)
                    if plan['token'] != request['planToken']: raise ValueError('Wi-Fi or hotspot settings changed; review a fresh warning')
                elif profile['kind'] == 'hotspot': raise ValueError('Review the hotspot warning before starting it')
                if any(a['state'] == 'activated' for a in existing):
                    return dict(state=model, message='Connection is already active (NetworkManager)')
                if existing: raise ValueError('This profile is still changing; wait or stop its reported activation')
                args = ('connection', 'up', 'uuid', profile['uuid'])
                if profile['kind'] != 'wireguard': args += ('ifname', device['interface'])
            before = {a['path'] for a in existing}
            if cancel.is_set(): raise Cancelled('Activation cancelled')
            attempted = True
            self.command(deadline, 'nmcli', '--wait', '15', *args, mutation=True, cancel=cancel)
            if cancel.is_set(): raise Cancelled('Activation cancelled')
            model = self.read(min(deadline, time.monotonic()+10))
            if model['serverId'] != request['serverId']: raise ValueError('NetworkManager changed before confirmation; refresh')
            actual = active_for(model, profile, device)
            if action == 'networkDisconnect':
                if any(a['path'] == request['activePath'] for a in model['active']): raise ValueError('Unable to confirm disconnection; showing observed state')
                message = 'Selected connection disconnected'
            else:
                if not any(a['state'] == 'activated' for a in actual): raise ValueError('Unable to confirm activation; showing observed state')
                if action == 'networkHotspotStart':
                    current = next((p for p in model['profiles'] if p['uuid'] == profile['uuid']), None)
                    if not current or current['kind'] != 'hotspot' or current['settings']['ipv4.method'] != 'shared' or current['security'] not in ('wpa-psk', 'sae'):
                        self.stop_attempt(model, profile, device, before, deadline)
                        model = self.read(min(deadline, time.monotonic()+10))
                        raise ValueError('Hotspot settings changed during activation; check the observed state before retrying')
                    message = 'Hotspot active; Internet access is not verified'
                else: message = 'Connection active (NetworkManager)'
            model['notice'] = message
            return dict(state=model, message=message)
        except Cancelled:
            try:
                model = self.read(time.monotonic()+10)
                if attempted:
                    if model['serverId'] != request['serverId']: raise ValueError('NetworkManager changed during cancellation; check actual connections')
                    self.stop_attempt(model, profile, device, before, time.monotonic()+8)
                    model = self.read(time.monotonic()+10)
                    if any(a['path'] not in before for a in active_for(model, profile, device)):
                        raise ValueError('Cancellation could not confirm disconnection; use Advanced network settings')
                message = 'Activation cancelled.' + (' Previous Wi-Fi may need reconnecting.' if attempted and action == 'networkHotspotStart' else '')
                model['notice'] = message
                return dict(state=model, message=message)
            except (CommandError, ValueError, OSError) as error:
                raise NetworkFailure(str(error) if isinstance(error, (ValueError, NetworkFailure)) else safe_error(error), model) from None
        except (CommandError, ValueError, OSError, RecursionError) as error:
            if attempted:
                try: model = self.read(min(deadline, time.monotonic()+10))
                except (CommandError, ValueError, OSError, RecursionError): model = None
            raise NetworkFailure(str(error) if isinstance(error, (NetworkFailure, ValueError)) else safe_error(error), model) from None
