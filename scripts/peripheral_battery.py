"""Normalize BlueZ and kernel device batteries without extra hardware probes."""
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


def kernel_batteries(sysfs, read):
    result = []
    for path in sorted((sysfs / 'class/power_supply').glob('*')):
        if read(path / 'type') != 'Battery' or read(path / 'scope') != 'Device' or read(path / 'present') == '0':
            continue
        props = dict(line.split('=', 1) for line in (read(path / 'device/uevent') or '').splitlines() if '=' in line)
        serial = read(path / 'serial_number') or props.get('HID_UNIQ', '')
        name = read(path / 'model_name') or props.get('HID_NAME') or path.name
        try: level = percentage(float(read(path / 'capacity') or 'nan'))
        except ValueError: level = None
        status = read(path / 'status')
        result.append(dict(id=identity(serial, 'power_supply:' + (serial or path.name)), name=name, kind=kind(name),
                           percentage=level, connected=True,
                           charging=True if status == 'Charging' else False if status in ('Discharging', 'Not charging', 'Full') else None))
    return result


def merge_batteries(bluetooth, kernel):
    # A disconnected BlueZ record takes precedence over a lingering HID sysfs node.
    disconnected = {device['id'] for device in bluetooth if not device['connected']}
    result = {}
    for device in bluetooth:
        if device['connected']:
            result[device['id']] = {key: device[key] for key in ('id', 'name', 'kind', 'percentage', 'connected', 'charging')}
    for device in kernel:
        if device['id'] in disconnected and device['id'] not in result: continue
        if device['id'] not in result: result[device['id']] = dict(device)
        else:
            for key in ('percentage', 'charging'):
                if result[device['id']][key] is None: result[device['id']][key] = device[key]
    return sorted(result.values(), key=lambda item: (item['name'].casefold(), item['id']))
