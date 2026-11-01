"""Wi-Fi operations; the host retains network sampling and worker publication."""
from dataclasses import dataclass
import copy
from threading import Event
import time
from typing import Callable

from backend_actions import ActionSpec, PreparedWork
from command_runner import CommandError
from wifi_auth import connect
from network_profiles import NetworkProfiles
from network_inventory import BASE, demo_inventory
from network_plans import ACTIONS as CONNECTION_ACTIONS, MUTATIONS as CONNECTION_MUTATIONS, active_for, hotspot_plan, select, validate

ACTIONS = ('wifiScan', 'wifiConnect', 'wifiSaved', 'wifiDisconnect', 'wifiForget')
MUTATIONS = frozenset((*ACTIONS[1:], 'wifiToggle')) | CONNECTION_MUTATIONS


def busy(action, pending):
    # One selected-adapter controller; radio/profile writes also affect other adapters.
    return action in MUTATIONS and bool(MUTATIONS.intersection(pending))


def toggle(run, pending):
    if busy('wifiToggle', pending): raise ValueError('This operation is already running')
    status = run('nmcli', 'radio', 'wifi')
    run('nmcli', 'radio', 'wifi', 'off' if status.strip() == 'enabled' else 'on')
    return 'Wi-Fi toggled'


@dataclass(frozen=True)
class WifiCapabilities:
    network: Callable
    run: Callable
    demo_network: Callable


def perform(capabilities, action, request, *, pending=()):
    if busy(action, pending): raise ValueError('This operation is already running')
    state = capabilities.network(details=True)
    if not state["available"]: raise CommandError("NetworkManager is unavailable")
    interface = request.get("device") or state.get("device")
    if not isinstance(interface, str) or interface != state.get("device") or not interface:
        raise ValueError("No Wi-Fi adapter is available")
    run = capabilities.run
    if action == "wifiScan":
        run("nmcli", "--wait", "15", "device", "wifi", "rescan", "ifname", interface, timeout=18)
        return "Wi-Fi scan completed"
    if action == "wifiDisconnect":
        run("nmcli", "--wait", "15", "device", "disconnect", interface, timeout=18)
        return "Wi-Fi disconnected"
    if action in {"wifiSaved", "wifiForget"}:
        ident = request.get("uuid")
        if not isinstance(ident, str) or not any(n["uuid"] == ident for n in state.get("saved", [])):
            raise ValueError("Saved network is no longer available")
        if action == "wifiForget":
            run("nmcli", "connection", "delete", "uuid", ident)
            return "Saved network removed"
        args = ("connection", "up", "uuid", ident, "ifname", interface)
    else:
        network = next((n for n in state["networks"] if n.get("bssid") == request.get("bssid")), None)
        if not network: raise ValueError("Network is no longer visible; scan again")
        if network.get("enterprise"): raise ValueError("Enterprise Wi-Fi needs a certificate or account. Use Advanced network settings.")
        args = ("device", "wifi", "connect", network["bssid"], "ifname", interface)
    password = request.get("password", "")
    if not isinstance(password, str) or len(password) > 128 or any(c in password for c in "\r\n\x00"):
        raise ValueError("Invalid Wi-Fi password")
    if action == 'wifiConnect':
        security = str(network.get('security', '')).upper()
        if password and 'WPA' in security and 'WPA3' not in security and 'SAE' not in security:
            raw = password.encode('utf-8')
            if not (8 <= len(raw) <= 63 or len(raw) == 64 and all(c in b'0123456789abcdefABCDEF' for c in raw)):
                raise ValueError('WPA/WPA2 passwords need 8–63 bytes or 64 hexadecimal digits.')
    return connect(run, args, interface, password)


def provide(capabilities):
    def demo(action, request):
        if action in {"wifiConnect", "wifiSaved"}:
            capabilities.demo_network().update(connected=True, ssid=request.get("ssid", "Home Wi-Fi"))
        elif action == "wifiDisconnect":
            capabilities.demo_network().update(connected=False, ssid="")

    complete = lambda value: None
    specs = tuple(ActionSpec(action, {'shell'},
        lambda request, action=action: perform(capabilities, action, request),
        lambda request, action=action: demo(action, request), execution='worker', complete=complete)
        for action in ACTIONS)
    return specs, lambda: {}


@dataclass(frozen=True)
class ConnectionsCapabilities:
    wifi: WifiCapabilities
    available: Callable
    pending: Callable
    split: Callable
    spawn: Callable
    executable: Callable


def provide_connections(cap):
    old, project = provide(cap.wifi)
    domain = NetworkProfiles(cap); state = {}; current = None
    def install(action, value):
        nonlocal current
        if isinstance(value, Exception):
            observed = getattr(value, 'state', None)
            model = dict(observed or dict(available=False, devices=[], profiles=[], active=[], hotspotPlan=None), error=str(value)[:400])
        else: model = value['state']
        previous = state.get('value', {}).get('lastRequest', {})
        hint = {k: current[k] for k in ('serverId', 'action', 'uuid', 'deviceId')} if current and action in CONNECTION_MUTATIONS else previous
        if hint and hint.get('serverId') == model.get('serverId'): model['lastRequest'] = hint
        state['value'] = model
        if action in CONNECTION_MUTATIONS: current = None

    def prepare(action, request):
        nonlocal current
        validate(action, request)
        pending = cap.pending()
        if any(name in pending for name in CONNECTION_ACTIONS) or busy(action, pending):
            raise ValueError('This operation is already running')
        if action in CONNECTION_MUTATIONS:
            current = dict(serverId=request['serverId'], action=action, uuid=request['uuid'], deviceId=request.get('deviceId', ''), cancel=Event(), done=Event())
            attempt = current
            def operation():
                try:
                    return domain.inspect(action, request) if action == 'networkEdit' else domain.change(action, request, attempt['cancel'])
                finally: attempt['done'].set()
        else: operation = lambda: domain.inspect(action, request)
        return PreparedWork(operation)

    def cancel(request):
        if current is None or current['action'] not in ('networkConnect', 'networkHotspotStart'):
            raise ValueError('No network activation is running')
        if current['done'].is_set(): return 'Activation already finished; check observed connections'
        current['cancel'].set()
        return 'Cancellation requested; waiting for the observed outcome'

    def demo(action, request):
        validate(action, request)
        model = copy.deepcopy(state.get('value') or demo_inventory())
        if action == 'networkHotspotPlan': model['hotspotPlan'] = hotspot_plan(model, request)
        elif action != 'networkRefresh':
            if action == 'networkEdit':
                if request['serverId'] != model['serverId'] or not any(p['uuid'] == request['uuid'] for p in model['profiles']):
                    raise ValueError('Saved connection disappeared; refresh')
            else:
                profile, device = select(model, request, disconnect=action == 'networkDisconnect')
                if action == 'networkDisconnect':
                    if not any(a['path'] == request['activePath'] for a in active_for(model, profile, device)):
                        raise ValueError('Activation changed; refresh')
                    model['active'] = [a for a in model['active'] if a['path'] != request['activePath']]
                else:
                    if action == 'networkHotspotStart':
                        if hotspot_plan(model, request)['token'] != request['planToken']: raise ValueError('Review a fresh hotspot warning')
                        cap.wifi.demo_network().update(wifiConnected=False, ssid='Hotspot')
                    elif profile['kind'] == 'hotspot': raise ValueError('Review the hotspot warning first')
                    if profile['kind'] != 'vpn': model['active'] = [a for a in model['active'] if a['deviceId'] != device['id']]
                    model['active'].append(dict(uuid=profile['uuid'], deviceId=device['id'], interface=device['interface'],
                        path=BASE+'ActiveConnection/'+str(20+len(model['active'])), state='activated'))
        model.update(checkedAt=int(time.time()*1000), error='')
        state['value'] = model

    specs = tuple(ActionSpec(action, {'shell'}, lambda request: None,
        lambda request, action=action: demo(action, request), execution='worker',
        prepare=lambda request, action=action: prepare(action, request),
        complete=lambda value, action=action: install(action, value), presentation=lambda value: value['message'])
        for action in CONNECTION_ACTIONS)
    def projection():
        if not state and current is None: return project()
        operation = {k: current[k] for k in ('action', 'uuid', 'deviceId')} if current else {}
        if current: operation.update(cancellable=current['action'] in ('networkConnect', 'networkHotspotStart'), cancelling=current['cancel'].is_set())
        return {**project(), 'networkConnections': {**state.get('value', {}), 'operation': operation}}
    return (*old, *specs, ActionSpec('networkCancel', {'shell'}, cancel, lambda request: None)), projection
