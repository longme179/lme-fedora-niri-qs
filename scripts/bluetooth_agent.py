#!/usr/bin/python3
"""On-demand BlueZ discovery and KeyboardDisplay agent, using JSON lines and Gio.

The main backend retains power/connect controls. This process owns its discovery
session and Pair calls; it never replaces another application's default agent.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import re
import signal
import sys
import uuid

AGENT_PATH = '/org/lme/Shell/BluetoothAgent'
AGENT_XML = '''<node><interface name="org.bluez.Agent1">
<method name="Release"/><method name="Cancel"/>
<method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
<method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
<method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
<method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/></method>
<method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
<method name="RequestAuthorization"><arg type="o" direction="in"/></method>
<method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
</interface></node>'''


def response_value(kind, value):
    if kind == 'pin':
        if not isinstance(value, str) or not 1 <= len(value.encode('utf-8')) <= 16 or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('Enter a PIN of 1–16 bytes')
        return '(s)', (value,)
    if kind == 'passkey':
        if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,6}', value):
            raise ValueError('Enter a numeric passkey of up to 6 digits')
        return '(u)', (int(value),)
    return '()', ()


class BluetoothAgent:
    def __init__(self, bus, loop, emit):
        self.bus, self.loop, self.emit = bus, loop, emit
        self.objects = {}; self.owner = ''; self.preferred = ''; self.adapter = ''
        self.ready = False; self.error = ''; self.scanning = False; self.scan_pending = False
        self.pairing = ''; self.pair_generation = 0; self.scan_requested = False; self.prompt = {}; self.invocation = None
        self.scan_timer = 0; self.prompt_timer = 0; self.generation = 0; self.closing = False
        bus.register_object(AGENT_PATH, Gio.DBusNodeInfo.new_for_xml(AGENT_XML).interfaces[0], self.agent_call, None, None)
        bus.signal_subscribe('org.freedesktop.DBus', 'org.freedesktop.DBus', 'NameOwnerChanged', '/org/freedesktop/DBus', 'org.bluez', Gio.DBusSignalFlags.NONE, self.owner_changed)
        bus.signal_subscribe('org.bluez', None, None, None, None, Gio.DBusSignalFlags.NONE, self.changed)
        self.initialize()

    def call(self, path, interface, method, signature='()', args=(), callback=None):
        generation = self.generation
        def done(bus, result):
            try: reply = bus.call_finish(result); error = None
            except GLib.Error as exc: reply, error = None, str(exc)
            if generation != self.generation: return
            if callback: callback(reply, error)
            elif error: self.error = error; self.publish()
        self.bus.call('org.bluez', path, interface, method, GLib.Variant(signature, args), None,
                      Gio.DBusCallFlags.NONE, 120000 if method == 'Pair' else 10000, None, done)

    def initialize(self):
        try:
            self.owner = self.bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'GetNameOwner', GLib.Variant('(s)', ('org.bluez',)), None, Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
            self.objects = self.bus.call_sync('org.bluez', '/', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects', None, None, Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
            self.bus.call_sync('org.bluez', '/org/bluez', 'org.bluez.AgentManager1', 'RegisterAgent', GLib.Variant('(os)', (AGENT_PATH, 'KeyboardDisplay')), None, Gio.DBusCallFlags.NONE, 3000, None)
            self.ready = True; self.error = ''; self.select_adapter()
        except GLib.Error as exc:
            self.ready = False; self.error = 'BlueZ unavailable: ' + str(exc)
        self.publish()

    def owner_changed(self, bus, sender, path, iface, name, params):
        _, old, new = params.unpack()
        self.generation += 1; self.ready = False; self.objects = {}; self.owner = new
        self.cancel_prompt(); self.pairing = ''; self.scanning = False; self.scan_pending = False
        self.stop_timer('scan_timer')
        if new: self.initialize()
        else: self.error = 'Bluetooth service disconnected'; self.publish()

    def changed(self, bus, sender, path, iface, name, params):
        if iface == 'org.freedesktop.DBus.ObjectManager' and name == 'InterfacesAdded':
            object_path, interfaces = params.unpack(); self.objects.setdefault(object_path, {}).update(interfaces)
        elif iface == 'org.freedesktop.DBus.ObjectManager' and name == 'InterfacesRemoved':
            object_path, interfaces = params.unpack()
            for key in interfaces: self.objects.get(object_path, {}).pop(key, None)
        elif iface == 'org.freedesktop.DBus.Properties' and name == 'PropertiesChanged':
            target, changes, invalidated = params.unpack()
            relevant = {'org.bluez.Adapter1': {'Powered', 'Alias', 'Discovering'},
                        'org.bluez.Device1': {'Alias', 'Name', 'Address', 'Paired', 'Connected'}}
            if not (set(changes) | set(invalidated)) & relevant.get(target, set()): return
            props = self.objects.setdefault(path, {}).setdefault(target, {}); props.update(changes)
            for key in invalidated: props.pop(key, None)
        else: return
        self.select_adapter()
        if self.adapter and not self.objects.get(self.adapter, {}).get('org.bluez.Adapter1', {}).get('Powered'):
            self.cancel_pairing(); self.stop_scan()
        self.publish()

    def select_adapter(self):
        adapters = [path for path, interfaces in self.objects.items() if 'org.bluez.Adapter1' in interfaces]
        selected = self.preferred if self.preferred in adapters else next(iter(sorted(adapters)), '')
        if selected != self.adapter:
            self.cancel_pairing(); self.stop_scan(); self.adapter = selected

    def devices(self):
        result = []
        for path, interfaces in self.objects.items():
            props = interfaces.get('org.bluez.Device1')
            if props is not None and path.startswith(self.adapter + '/dev_'):
                result.append(dict(path=path, name=props.get('Alias') or props.get('Name') or props.get('Address', 'Bluetooth device'),
                                   address=props.get('Address', ''), paired=bool(props.get('Paired')), connected=bool(props.get('Connected'))))
        return sorted(result, key=lambda d: (not d['connected'], not d['paired'], d['name'].casefold(), d['path']))

    def publish(self):
        if not self.closing:
            self.emit(dict(ready=self.ready, adapter=self.adapter, devices=self.devices(), scanning=self.scanning,
                           scanPending=self.scan_pending, pairing=self.pairing, request=self.prompt, error=self.error))

    def stop_timer(self, name):
        timer = getattr(self, name)
        if timer: GLib.source_remove(timer); setattr(self, name, 0)

    def stop_scan(self):
        self.scan_requested = False
        self.stop_timer('scan_timer')
        if self.scanning:
            self.call(self.adapter, 'org.bluez.Adapter1', 'StopDiscovery', callback=lambda reply, error: None)
        self.scanning = False

    def scan(self, enabled):
        if type(enabled) is not bool: raise ValueError('Scan state must be boolean')
        if not enabled: self.stop_scan(); self.publish(); return
        if not self.ready or not self.adapter: raise ValueError('No Bluetooth adapter available')
        if not self.objects[self.adapter]['org.bluez.Adapter1'].get('Powered'): raise ValueError('Turn Bluetooth on before scanning')
        if self.scan_pending or self.scanning: return
        self.error = ''; self.scan_pending = True; self.scan_requested = True
        adapter = self.adapter
        def started(reply, error):
            self.scan_pending = False
            if not error:
                if self.closing or not self.scan_requested or adapter != self.adapter:
                    self.call(adapter, 'org.bluez.Adapter1', 'StopDiscovery', callback=lambda r, e: None); self.publish(); return
                self.scanning = True
                self.scan_timer = GLib.timeout_add_seconds(60, self.scan_expired)
            else: self.error = error
            self.publish()
        self.call(adapter, 'org.bluez.Adapter1', 'StartDiscovery', callback=started); self.publish()

    def scan_expired(self):
        self.scan_timer = 0; self.stop_scan(); self.publish(); return False

    def cancel_prompt(self):
        self.stop_timer('prompt_timer')
        if self.invocation:
            self.invocation.return_dbus_error('org.bluez.Error.Canceled', 'Pairing canceled')
        self.invocation = None; self.prompt = {}

    def cancel_pairing(self):
        self.pair_generation += 1
        self.cancel_prompt()
        if self.pairing:
            self.call(self.pairing, 'org.bluez.Device1', 'CancelPairing', callback=lambda r, e: None)
        self.pairing = ''

    def pair(self, path):
        if not self.ready: raise ValueError('BlueZ is not ready')
        if self.pairing: raise ValueError('Finish or cancel the current pairing first')
        if path not in [device['path'] for device in self.devices()]: raise ValueError('Choose a device on the selected adapter')
        self.error = ''; self.pairing = path; self.pair_generation += 1
        pair_generation = self.pair_generation
        def paired(reply, error):
            if self.pairing != path or self.pair_generation != pair_generation: return
            self.cancel_prompt(); self.pairing = ''
            if error: self.error = error
            else: self.call(path, 'org.bluez.Device1', 'Connect')
            self.publish()
        self.call(path, 'org.bluez.Device1', 'Pair', callback=paired); self.publish()

    def agent_call(self, bus, sender, path, interface, method, params, invocation):
        if sender != self.owner:
            invocation.return_dbus_error('org.bluez.Error.Rejected', 'Only BlueZ may call this agent'); return
        args = params.unpack()
        if method in ('Cancel', 'Release'):
            self.cancel_prompt()
            if method == 'Release': self.ready = False; self.error = 'Bluetooth agent released'
            invocation.return_value(GLib.Variant('()', ())); self.publish(); return
        device = args[0]
        if device != self.pairing:
            invocation.return_dbus_error('org.bluez.Error.Rejected', 'Pairing was not requested in this shell'); return
        kinds = {'RequestPinCode': 'pin', 'RequestPasskey': 'passkey', 'RequestConfirmation': 'confirm',
                 'RequestAuthorization': 'authorize', 'AuthorizeService': 'service',
                 'DisplayPinCode': 'display-pin', 'DisplayPasskey': 'display-passkey'}
        if method not in kinds:
            invocation.return_dbus_error('org.bluez.Error.Rejected', 'Unsupported pairing request'); return
        display = method.startswith('Display')
        if self.invocation:
            invocation.return_dbus_error('org.bluez.Error.Rejected', 'Another pairing request is pending'); return
        previous_token = self.prompt.get('token') if display and self.prompt.get('kind') == kinds[method] else None
        self.prompt = dict(token=previous_token or uuid.uuid4().hex, kind=kinds[method], path=device,
                           name=next((d['name'] for d in self.devices() if d['path'] == device), device),
                           code=(str(args[1]) if method == 'DisplayPinCode' else f'{args[1]:06d}') if method in ('DisplayPinCode', 'DisplayPasskey', 'RequestConfirmation') else '',
                           entered=int(args[2]) if method == 'DisplayPasskey' else 0, service=args[1] if method == 'AuthorizeService' else '')
        if display: invocation.return_value(GLib.Variant('()', ()))
        else: self.invocation = invocation
        self.stop_timer('prompt_timer'); self.prompt_timer = GLib.timeout_add_seconds(60, self.prompt_expired)
        self.publish()

    def prompt_expired(self):
        self.prompt_timer = 0; self.cancel_pairing(); self.error = 'Bluetooth pairing timed out'; self.publish(); return False

    def reply(self, request):
        if not self.prompt or request.get('token') != self.prompt['token']: raise ValueError('This pairing request is no longer active')
        if type(request.get('accept')) is not bool: raise ValueError('Pairing decision must be boolean')
        if not request['accept']: self.cancel_pairing(); self.publish(); return
        if self.invocation:
            signature, values = response_value(self.prompt['kind'], request.get('value', ''))
            self.error = ''
            self.invocation.return_value(GLib.Variant(signature, values)); self.invocation = None
            self.stop_timer('prompt_timer'); self.prompt = {}
        self.publish()

    def command(self, request):
        try:
            if not isinstance(request, dict) or not isinstance(request.get('action'), str): raise ValueError('Expected a Bluetooth action')
            action = request['action']
            if action == 'watch':
                preferred = request.get('adapter', '')
                if not isinstance(preferred, str) or not re.fullmatch(r'|/org/bluez/hci[0-9]+', preferred): raise ValueError('Invalid Bluetooth adapter')
                self.preferred = preferred; self.select_adapter()
            elif action == 'scan': self.scan(request.get('enabled'))
            elif action == 'pair': self.pair(request.get('path'))
            elif action == 'reply': self.reply(request)
            elif action == 'cancel': self.cancel_pairing()
            elif action == 'close': self.close(); return
            else: raise ValueError('Unknown Bluetooth action')
        except (ValueError, TypeError) as exc: self.error = str(exc)
        self.publish()

    def close(self):
        if self.closing: return False
        self.closing = True; self.cancel_pairing(); self.stop_scan()
        if self.ready:
            self.call('/org/bluez', 'org.bluez.AgentManager1', 'UnregisterAgent', '(o)', (AGENT_PATH,), lambda r, e: self.loop.quit())
            GLib.timeout_add(1500, self.loop.quit)
        else: self.loop.quit()
        return False


def main():
    global Gio, GLib
    def emit(value): print(json.dumps(value, ensure_ascii=False), flush=True)
    try:
        import gi
        from gi.repository import Gio, GLib
    except ImportError:
        emit({'error': 'Bluetooth pairing needs python3-gobject-base (Gio/GLib). Install it with DNF.', 'ready': False}); return 1
    loop = GLib.MainLoop()
    try: agent = BluetoothAgent(Gio.bus_get_sync(Gio.BusType.SYSTEM, None), loop, emit)
    except GLib.Error as exc: emit({'error': 'Cannot connect to the system bus: ' + str(exc), 'ready': False}); return 1
    pending = bytearray()
    os.set_blocking(sys.stdin.fileno(), False)
    def read(channel, condition):
        try: data = os.read(sys.stdin.fileno(), 65536)
        except BlockingIOError: return True
        if not data: agent.close(); return False
        pending.extend(data)
        while b'\n' in pending:
            line, _, rest = pending.partition(b'\n'); pending[:] = rest
            try:
                if len(line) > 65536: raise ValueError('Bluetooth request is too large')
                agent.command(json.loads(line))
            except (ValueError, UnicodeError) as exc: agent.error = str(exc); agent.publish()
        if len(pending) > 65536: agent.error = 'Bluetooth request is too large'; agent.publish(); agent.close(); return False
        return True
    GLib.io_add_watch(sys.stdin, GLib.IO_IN | GLib.IO_HUP, read)
    for sig in (signal.SIGTERM, signal.SIGINT): GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, agent.close)
    loop.run()
    return 0


if __name__ == '__main__': raise SystemExit(main())
