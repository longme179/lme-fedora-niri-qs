"""Synchronous audio, backlight and Bluetooth operations with host-owned read-back."""
from dataclasses import dataclass
import re
from typing import Callable

from backend_actions import ActionSpec


@dataclass(frozen=True)
class AudioCapabilities:
    run: Callable
    percentage: Callable
    bluetooth: Callable
    set_bluetooth: Callable
    demo_controls: Callable


def provide(capabilities):
    def volume(request):
        if 'delta' in request:
            delta = capabilities.percentage(request['delta'], -100)
            capabilities.run('wpctl', 'set-volume', '--limit', '1.0', '@DEFAULT_AUDIO_SINK@', f"{abs(delta)}%{'+' if delta >= 0 else '-'}")
            return 'Volume adjusted'
        value = capabilities.percentage(request.get('value'))
        capabilities.run('wpctl', 'set-volume', '--limit', '1.0', '@DEFAULT_AUDIO_SINK@', f'{value}%')
        return f'Volume {value}%'

    def mute(request):
        capabilities.run('wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@', 'toggle')
        return 'Mute toggled'

    def mic_volume(request):
        value = capabilities.percentage(request.get('value'))
        capabilities.run('wpctl', 'set-volume', '--limit', '1.0', '@DEFAULT_AUDIO_SOURCE@', f'{value}%')
        return f'Microphone {value}%'

    def mic_mute(request):
        capabilities.run('wpctl', 'set-mute', '@DEFAULT_AUDIO_SOURCE@', 'toggle')
        return 'Microphone mute toggled'

    def brightness(request):
        value = capabilities.percentage(request.get('value'), 1)
        capabilities.run('brightnessctl', '--class=backlight', 'set', f'{value}%')
        return f'Brightness {value}%'

    def bluetooth_device(request):
        path, connected = request.get('path'), request.get('connected')
        state = capabilities.bluetooth()
        if (not isinstance(path, str) or not re.fullmatch(r'/org/bluez/hci[0-9]+/dev_(?:[A-Fa-f0-9]{2}_){5}[A-Fa-f0-9]{2}', path)
                or type(connected) is not bool or not any(item['path'] == path for item in state['devices'])):
            raise ValueError('Unknown Bluetooth device or state')
        capabilities.run('busctl', '--system', 'call', 'org.bluez', path, 'org.bluez.Device1', 'Connect' if connected else 'Disconnect', timeout=15.0)
        return 'Bluetooth device ' + ('connected' if connected else 'disconnected')

    def demo(action, request):
        system = capabilities.demo_controls()
        if action == 'volume':
            system['audio']['volume'] = max(0, min(100, system['audio']['volume'] + capabilities.percentage(request['delta'], -100))) if 'delta' in request else capabilities.percentage(request.get('value'))
        elif action == 'mute': system['audio']['muted'] = not system['audio']['muted']
        elif action == 'micVolume': system['microphone']['volume'] = capabilities.percentage(request.get('value'))
        elif action == 'micMute': system['microphone']['muted'] = not system['microphone']['muted']
        elif action == 'brightness': system['brightness']['percent'] = capabilities.percentage(request.get('value'), 1)
        elif action == 'bluetoothToggle': system['bluetooth']['enabled'] = not system['bluetooth']['enabled']
        elif action == 'bluetoothDevice':
            device = next((item for item in system['bluetooth']['devices'] if item['path'] == request.get('path')), None)
            if not device or type(request.get('connected')) is not bool: raise ValueError('Unknown Bluetooth device or state')
            device['connected'] = request['connected']

    handlers = {'volume': volume, 'mute': mute, 'micVolume': mic_volume, 'micMute': mic_mute,
                'brightness': brightness, 'bluetoothToggle': lambda request: capabilities.set_bluetooth(not capabilities.bluetooth()['enabled']),
                'bluetoothDevice': bluetooth_device}
    return tuple(ActionSpec(name, {'shell'}, live, lambda request, name=name: demo(name, request))
                 for name, live in handlers.items()), lambda: {}
