"""A private-bus MPRIS player for optional native integration checks."""
import signal
from gi.repository import Gio, GLib

ROOT = 'org.mpris.MediaPlayer2'
PLAYER = ROOT + '.Player'
PATH = '/org/mpris/MediaPlayer2'
V = GLib.Variant
values = {
    ROOT: {'Identity': V('s', 'LME Test Player'), 'DesktopEntry': V('s', 'lme-test'),
           'CanQuit': V('b', False), 'CanRaise': V('b', False), 'HasTrackList': V('b', False),
           'SupportedUriSchemes': V('as', ['file']), 'SupportedMimeTypes': V('as', ['audio/ogg'])},
    PLAYER: {'PlaybackStatus': V('s', 'Playing'), 'LoopStatus': V('s', 'None'),
             'Rate': V('d', 1.0), 'Shuffle': V('b', False), 'Volume': V('d', .5), 'Position': V('x', 0),
             'MinimumRate': V('d', 1.0), 'MaximumRate': V('d', 1.0),
             'Metadata': V('a{sv}', {'xesam:title': V('s', 'Native track'), 'xesam:artist': V('as', ['Test Artist']),
                                    'mpris:trackid': V('o', '/track/1'), 'mpris:length': V('x', 120000000)}),
             **{name: V('b', True) for name in ['CanGoNext', 'CanGoPrevious', 'CanPlay', 'CanPause', 'CanSeek', 'CanControl']}}
}
xml = '<node>'
for interface, props in values.items():
    xml += f'<interface name="{interface}">' + ''.join(f'<property name="{k}" type="{v.get_type_string()}" access="read"/>' for k, v in props.items())
    if interface == PLAYER:
        xml += ''.join(f'<method name="{name}"/>' for name in ['PlayPause', 'Next', 'Previous', 'Play', 'Pause', 'Stop'])
    xml += '</interface>'
xml += '</node>'
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
loop = GLib.MainLoop()

def call(conn, sender, path, interface, method, args, invocation):
    props = values[PLAYER]
    if method in ['PlayPause', 'Play', 'Pause', 'Stop']:
        status = 'Paused' if props['PlaybackStatus'].unpack() == 'Playing' else 'Playing'
        props['PlaybackStatus'] = V('s', status if method == 'PlayPause' else {'Play': 'Playing', 'Pause': 'Paused', 'Stop': 'Stopped'}[method])
        name = 'PlaybackStatus'
    else:
        props['Metadata'] = V('a{sv}', {'xesam:title': V('s', 'Next track' if method == 'Next' else 'Previous track'), 'xesam:artist': V('as', ['Test Artist']), 'mpris:trackid': V('o', '/track/2')})
        name = 'Metadata'
    bus.emit_signal(None, PATH, 'org.freedesktop.DBus.Properties', 'PropertiesChanged', V('(sa{sv}as)', (PLAYER, {name: props[name]}, [])))
    invocation.return_value(V('()', ()))

for iface in Gio.DBusNodeInfo.new_for_xml(xml).interfaces:
    bus.register_object(PATH, iface, call, lambda conn, sender, path, interface, name: values[interface][name], None)
bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'RequestName', V('(su)', ('org.mpris.MediaPlayer2.lmeTest', 0)), V('(u)', (0,)).get_type(), Gio.DBusCallFlags.NONE, -1, None)
GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (loop.quit(), False)[1])
loop.run()
