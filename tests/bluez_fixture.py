"""Private-bus BlueZ service; never used against the machine's system bus."""
import json
import os
import signal
from gi.repository import Gio, GLib

V = GLib.Variant
bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
loop = GLib.MainLoop()
ADAPTER = '/org/bluez/hci0'
DEVICE = ADAPTER + '/dev_AA_BB_CC_DD_EE_FF'
objects = {ADAPTER: {'org.bluez.Adapter1': {'Alias': V('s', 'Test adapter'), 'Powered': V('b', True), 'Discovering': V('b', False)}},
           DEVICE: {'org.bluez.Device1': {'Alias': V('s', 'Test headset'), 'Address': V('s', 'AA:BB:CC:DD:EE:FF'), 'Paired': V('b', False), 'Connected': V('b', False)}}}
objects['/org/bluez/hci1'] = {'org.bluez.Adapter1': {'Alias': V('s', 'Other adapter'), 'Powered': V('b', True), 'Discovering': V('b', False)}}
objects['/org/bluez/hci1/dev_11_22_33_44_55_66'] = {'org.bluez.Device1': {'Alias': V('s', 'Other keyboard'), 'Paired': V('b', True), 'Connected': V('b', False)}}
mode = 'confirm'; owner = ''; agent_path = ''; pairing = None

def log(name, data=None):
    if os.environ.get('LME_BLUEZ_EVENTS'):
        with open(os.environ['LME_BLUEZ_EVENTS'], 'a') as output: output.write(json.dumps([name, data]) + '\n')

def changed(path, iface, key, value):
    objects[path][iface][key] = value
    bus.emit_signal(None, path, 'org.freedesktop.DBus.Properties', 'PropertiesChanged', V('(sa{sv}as)', (iface, {key: value}, [])))

def call(conn, sender, path, interface, method, parameters, invocation):
    global owner, agent_path, mode, pairing
    args = parameters.unpack(); log(method, args)
    if method == 'GetManagedObjects': invocation.return_value(V('(a{oa{sa{sv}}})', (objects,))); return
    if method == 'RegisterAgent': owner, agent_path = sender, args[0]
    elif method == 'UnregisterAgent': owner = ''; agent_path = ''
    elif method == 'StartDiscovery': changed(path, 'org.bluez.Adapter1', 'Discovering', V('b', True))
    elif method == 'StopDiscovery': changed(path, 'org.bluez.Adapter1', 'Discovering', V('b', False))
    elif method == 'Connect': changed(DEVICE, 'org.bluez.Device1', 'Connected', V('b', True))
    elif method == 'SetMode': mode = args[0]
    elif method == 'Drop':
        bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'ReleaseName', V('(s)', ('org.bluez',)), None, Gio.DBusCallFlags.NONE, 2000, None)
    elif method == 'Claim':
        bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'RequestName', V('(su)', ('org.bluez', 0)), None, Gio.DBusCallFlags.NONE, 2000, None)
    elif method == 'CancelPairing':
        if pairing: pairing.return_dbus_error('org.bluez.Error.AuthenticationCanceled', 'Canceled'); pairing = None
    elif method == 'Pair':
        pairing = invocation
        types = {'pin': ('RequestPinCode', '(o)', (DEVICE,)), 'passkey': ('RequestPasskey', '(o)', (DEVICE,)),
                 'confirm': ('RequestConfirmation', '(ou)', (DEVICE, 12345)), 'authorize': ('RequestAuthorization', '(o)', (DEVICE,)),
                 'service': ('AuthorizeService', '(os)', (DEVICE, '0000110b-0000-1000-8000-00805f9b34fb')),
                 'display-pin': ('DisplayPinCode', '(os)', (DEVICE, '0123')),
                 'display-passkey': ('DisplayPasskey', '(ouq)', (DEVICE, 12345, 2))}
        if mode == 'wait': return
        method_name, signature, values = types[mode]
        def done(connection, result):
            global pairing
            try:
                value = connection.call_finish(result).unpack(); log('AgentReply', value)
                if pairing and not mode.startswith('display'):
                    changed(DEVICE, 'org.bluez.Device1', 'Paired', V('b', True))
                    pairing.return_value(V('()', ())); pairing = None
            except GLib.Error as exc:
                if pairing: pairing.return_dbus_error('org.bluez.Error.AuthenticationRejected', str(exc)); pairing = None
        bus.call(owner, agent_path, 'org.bluez.Agent1', method_name, V(signature, values), None, Gio.DBusCallFlags.NONE, 10000, None, done)
        return
    invocation.return_value(V('()', ()))

interfaces = {
'/': '<interface name="org.freedesktop.DBus.ObjectManager"><method name="GetManagedObjects"><arg type="a{oa{sa{sv}}}" direction="out"/></method></interface>',
'/org/bluez': '<interface name="org.bluez.AgentManager1"><method name="RegisterAgent"><arg type="o" direction="in"/><arg type="s" direction="in"/></method><method name="UnregisterAgent"><arg type="o" direction="in"/></method></interface>',
ADAPTER: '<interface name="org.bluez.Adapter1"><method name="StartDiscovery"/><method name="StopDiscovery"/></interface>',
DEVICE: '<interface name="org.bluez.Device1"><method name="Pair"/><method name="CancelPairing"/><method name="Connect"/></interface>',
'/test': '<interface name="org.lme.BlueZTest"><method name="SetMode"><arg type="s" direction="in"/></method><method name="Drop"/><method name="Claim"/></interface>'}
interfaces['/org/bluez/hci1'] = interfaces[ADAPTER]
for path, xml in interfaces.items():
    for interface in Gio.DBusNodeInfo.new_for_xml('<node>'+xml+'</node>').interfaces:
        bus.register_object(path, interface, call, None, None)
bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'RequestName', V('(su)', ('org.bluez', 0)), None, Gio.DBusCallFlags.NONE, 2000, None)
print(bus.get_unique_name(), flush=True)
GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (loop.quit(), False)[1])
loop.run()
