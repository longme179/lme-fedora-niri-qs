"""Shared BlueZ property and peripheral battery value normalization."""
# SPDX-License-Identifier: GPL-3.0-or-later
import math
import re


def percentage(value):
    return value if type(value) in (int, float) and 0 <= value <= 100 and math.isfinite(value) else None


def identity(address, fallback):
    address = address.upper().replace('_', ':').replace('-', ':') if isinstance(address, str) else ''
    return 'bluetooth:' + address if re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', address) else fallback


def kind(value):
    value = value.casefold()
    if 'head' in value or 'earbud' in value: return 'headphones'
    if 'mouse' in value: return 'mouse'
    if 'keyboard' in value: return 'keyboard'
    return 'device'


def bluetooth_device(path, interfaces, value):
    props = interfaces['org.bluez.Device1']
    address = value(props, 'Address', '')
    name = value(props, 'Alias', '') or value(props, 'Name', '') or address or 'Bluetooth device'
    connected = value(props, 'Connected', False) is True
    battery = interfaces.get('org.bluez.Battery1', {})
    return dict(path=path, id=identity(address, 'bluez:' + path), name=name, address=address,
                kind=kind(value(props, 'Icon', '') or name), paired=value(props, 'Paired', False) is True,
                connected=connected, percentage=percentage(value(battery, 'Percentage', None)) if connected else None,
                charging=None)


