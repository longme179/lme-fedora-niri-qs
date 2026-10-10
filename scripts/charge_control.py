#!/usr/bin/python3 -I
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read and change kernel charge controls. The privileged CLI accepts modes only."""
import argparse
import json
import os
from pathlib import Path
import re
import stat

HELPER_PATH = Path('/usr/local/libexec/lme-shell-charge')


def trusted_helper(path=HELPER_PATH):
    try:
        if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
            return False
        for item in (path, *path.parents):
            info = item.stat()
            if info.st_uid != 0 or info.st_mode & 0o022:
                return False
        return True
    except OSError:
        return False


class ChargeControl:
    def __init__(self, sysfs=Path('/sys')):
        self.sysfs = Path(sysfs)

    @staticmethod
    def read(path):
        try:
            return path.read_text().strip()
        except (OSError, UnicodeError):
            return ''

    def discover(self):
        batteries = [p for p in sorted((self.sysfs / 'class/power_supply').glob('*'))
                     if self.read(p / 'type') == 'Battery']
        for battery in batteries:
            end = battery / 'charge_control_end_threshold'
            if self.read(end).isdigit() and 1 <= int(self.read(end)) <= 100:
                return 'threshold', end
        for battery in batteries:
            types = battery / 'charge_types'
            text = self.read(types)
            if 'Standard' in text and 'Long Life' in text and re.search(r'\[(Standard|Long Life)\]', text):
                return 'charge-types', types
        for device in sorted((self.sysfs / 'bus/platform/devices').glob('VPC2004:*')):
            path = device / 'conservation_mode'
            if self.read(path) in ('0', '1'):
                return 'ideapad', path
        return '', None

    def state(self):
        kind, path = self.discover()
        base = {'available': path is not None, 'kind': kind, 'mode': '', 'limitPercent': None,
                'supports85': kind == 'threshold', 'writable': False,
                'reason': 'No charge-control interface is exposed by this kernel/firmware.'}
        if path is None:
            return base
        base.update(writable=os.access(path, os.W_OK), reason='')
        value = self.read(path)
        if kind == 'threshold':
            limit = int(value)
            base.update(limitPercent=limit, mode='max' if limit == 100 else 'conservation')
        elif kind == 'charge-types':
            base['mode'] = 'conservation' if '[Long Life]' in value else 'max'
        else:
            base['mode'] = 'conservation' if value == '1' else 'max'
        if kind != 'threshold':
            base['reason'] = 'Conservation uses a fixed firmware limit; this interface cannot set an exact 85%.'
        return base

    def set_mode(self, limit):
        if type(limit) is not int or limit not in (85, 100):
            raise ValueError('Choose conservation (85) or maximum charge (100).')
        kind, path = self.discover()
        if path is None:
            raise ValueError(self.state()['reason'])
        changes = []
        def write(target, value):
            old = self.read(target)
            target.write_text(str(value) + '\n')
            changes.append((target, old))
        try:
            if kind == 'threshold':
                # Explicit percentages must not be overridden by firmware's
                # separate Long Life mode. Preserve the start threshold unless
                # it would be invalid with the requested stop threshold.
                types = path.parent / 'charge_types'
                if '[Long Life]' in self.read(types):
                    write(types, 'Standard')
                    if '[Standard]' not in self.read(types):
                        raise ValueError('The driver did not disable its fixed Long Life mode.')
                start = path.parent / 'charge_control_start_threshold'
                value = self.read(start)
                if value.isdigit() and int(value) >= limit:
                    write(start, max(0, limit - 5))
                write(path, limit)
                if self.read(path) != str(limit):
                    raise ValueError('The driver did not confirm the requested charge threshold.')
            elif kind == 'charge-types':
                desired = 'Long Life' if limit == 85 else 'Standard'
                write(path, desired)
                # Real sysfs lists available types and brackets the selected one.
                if f'[{desired}]' not in self.read(path):
                    raise ValueError('The driver did not confirm the requested charge mode.')
            else:
                desired = '1' if limit == 85 else '0'
                write(path, desired)
                if self.read(path) != desired:
                    raise ValueError('The firmware did not confirm conservation mode.')
        except (OSError, ValueError):
            for target, old in reversed(changes):
                try:
                    # Enum sysfs files return the choice list; restore the
                    # selected enum, not the entire list.
                    selected = re.search(r'\[(Standard|Long Life)\]', old)
                    target.write_text((selected.group(1) if selected else old) + '\n')
                except OSError:
                    pass
            raise
        return self.state()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('85', '100', 'status'))
    args = parser.parse_args()
    controller = ChargeControl()
    try:
        if args.mode == 'status':
            result = controller.state()
        else:
            if os.geteuid() != 0:
                raise PermissionError('Changing charge limits needs administrator authentication.')
            result = controller.set_mode(int(args.mode))
        print(json.dumps(result))
        return 0
    except (OSError, ValueError) as error:
        parser.exit(1, f'Charge control: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
