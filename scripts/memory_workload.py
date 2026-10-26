#!/usr/bin/env python3
"""Explicitly exercise a running LME session; save PSS checkpoints, leave Settings open."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from feature_catalog import load_catalog
from memory_report import collect

PANELS = ('clipboard', 'control', 'activity', 'notifications', 'launcher', 'power')
CORE = {'Quickshell', 'backend', 'clipboard worker'}


def timing(value):
    number = float(value)
    if not math.isfinite(number) or not .1 <= number <= 30:
        raise ValueError('Timing must be between 0.1 and 30 seconds')
    return number


def running(pid):
    try:
        lines = (Path('/proc')/str(pid)/'status').read_text().splitlines()
        return not any(line.startswith('State:') and line.split()[1] in ('Z', 'X') for line in lines)
    except FileNotFoundError: return False
    except OSError: return True  # Unreadable is not confirmed exit.


class Session:
    def __init__(self, root, binary, extra):
        self.root, self.binary, self.extra = root.resolve(), binary, extra
        self.main = self.settings = self.baseline = None
        self.report = dict(version=1, samples=[], error=None, ownership_review_required=True)

    def qs(self, *args):
        result = subprocess.run([self.binary, *args], capture_output=True, text=True, timeout=5)
        if result.returncode: raise ValueError('Quickshell command failed: '+result.stderr.strip())
        return result.stdout.strip()

    def instances(self):
        value = json.loads(self.qs('list', '--all', '--json'))
        if not isinstance(value, list) or any(not isinstance(v, dict) or
                not isinstance(v.get('id'), str) or not v['id'] or
                type(v.get('pid')) is not int or v['pid'] <= 0 or
                not isinstance(v.get('config_path'), str) for v in value):
            raise ValueError('Invalid Quickshell instance inventory')
        return value

    def ipc(self, instance, target, method, *args):
        return self.qs('ipc', '--id', instance['id'], 'call', target, method, *args)

    def command(self, method, *args):
        if self.ipc(self.main, 'shell', method, *args):
            raise ValueError('Unexpected IPC reply; workload stopped')

    def attach(self):
        instances = self.instances()
        if len(instances) != 1 or Path(instances[0]['config_path']).resolve() != self.root/'shell.qml':
            raise ValueError('Start exactly one main shell from --checkout; close Settings/other instances first')
        panels = {v['id'] for v in load_catalog(self.root).get('panel', [])}
        if not {'clipboard', 'notifications'} <= panels:
            raise ValueError('Clipboard and Notifications must be enabled in the catalog for this workload')
        status = json.loads(self.ipc(instances[0], 'shell', 'mediaStatus'))
        if not isinstance(status, dict) or status.get('demo') is not False:
            raise ValueError('A live shell is required; demo/preview is not a laptop GPU measurement')
        self.main = instances[0]
        self.report['media_status'] = status
        self.report['main_instance'] = instances[0]

    def measure(self, label, limit):
        current = self.instances()
        expected = [self.main] + ([self.settings] if self.settings else [])
        if {(v['id'], v['pid']) for v in current} != {(v['id'], v['pid']) for v in expected}:
            raise ValueError('Instance ownership changed; repeat after the session is stable')
        report = collect(extra=self.extra)
        record = dict(label=label, budget_mb=limit, within_budget=None, memory=report)
        self.report['samples'].append(record)
        if not report['complete'] or report['pss_kib'] is None:
            raise ValueError('Incomplete memory inventory; see the saved report')
        if report['checkouts'] != [str(self.root)]:
            raise ValueError('Other/unresolved checkouts are present; review ownership')
        if {v['pid'] for v in report['processes'] if v['role'] == 'Quickshell'} != {v['pid'] for v in expected}:
            raise ValueError('Instance PIDs do not match the memory inventory')
        core = {(v['pid'], v['role']) for v in report['processes'] if v['role'] in CORE}
        if self.baseline is None:
            counts = Counter(role for _, role in core)
            if counts['Quickshell'] != 1 or counts['backend'] != 1 or counts['clipboard worker'] > 1:
                raise ValueError('Expected one main Quickshell/backend and at most one history worker')
            self.baseline = core
        additions = core-self.baseline
        expected_additions = Counter({'Quickshell': 1, 'backend': 1}) if self.settings else Counter()
        if not self.baseline <= core or Counter(role for _, role in additions) != expected_additions:
            raise ValueError('Persistent process ownership changed; repeat after the session is stable')
        record['within_budget'] = report['pss_kib']*1024 <= limit*1_000_000
        record['pss_mb'] = round(report['pss_kib']*1024/1_000_000, 2)
        counts = dict(Counter(v['role'] for v in report['processes']))
        print(f"{label}: {record['pss_mb']:.2f} MB inclusive PSS; {len(report['processes'])} PIDs; "
              f"{'WITHIN' if record['within_budget'] else 'OVER'} {limit} MB; {counts}", flush=True)

    def open_settings(self):
        if self.instances() != [self.main]: raise ValueError('Close Settings/other instances before continuing')
        self.settings_process = subprocess.Popen([str(self.root/'scripts/settings.sh'), '--page', 'appearance'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic()+25
        while time.monotonic() < deadline:
            matches = [v for v in self.instances() if Path(v['config_path']).resolve() == self.root/'settings.qml']
            if len(matches) == 1:
                self.settings = matches[0]
                if (self.ipc(self.settings, 'settings', 'startupPending') == 'false' and
                        self.ipc(self.settings, 'settings', 'openPage', 'appearance') == 'true'):
                    return
            if self.settings_process.poll() not in (None, 0):
                raise ValueError('Settings launch failed; inspect the Quickshell log')
            time.sleep(.2)
        raise ValueError('Settings did not confirm a visible window within 25 seconds')

    def exercise(self, dwell, settle):
        self.command('close'); time.sleep(settle); self.measure('steady', 400)
        for index in range(48):
            self.command('toggle', PANELS[index % len(PANELS)])
            time.sleep(dwell)
            self.command('close'); time.sleep(dwell)
            self.report['completed_cycles'] = index+1
            if (index+1) % 6 == 0: print(f'Sent {index+1}/48 timed cycles', flush=True)
            if index+1 in (24, 48):
                time.sleep(settle); self.measure('warm-'+str(index+1), 400)
        self.open_settings(); time.sleep(settle); self.measure('Settings-open', 500)
        values = {v['label']: v['memory']['pss_kib'] for v in self.report['samples']}
        self.report['warm_delta_mb'] = round((values['warm-48']-values['warm-24'])*1024/1_000_000, 2)
        print(f"warm-48 minus warm-24: {self.report['warm_delta_mb']:+.2f} MB (not a leak verdict)", flush=True)

    def wait_closed(self, settle):
        last = self.report['samples'][-1]['memory']['processes']
        created = {v['pid'] for v in last if v['role'] in CORE}-{pid for pid, _ in self.baseline}
        deadline = time.monotonic()+120
        print('Close Settings with its X now; waiting up to 120s for Settings and its backend to exit.', flush=True)
        while time.monotonic() < deadline:
            child = getattr(self, 'settings_process', None)
            if child is not None: child.poll()
            if (self.settings['id'] not in {v['id'] for v in self.instances()} and
                    not any(running(pid) for pid in created)):
                self.settings = None
                time.sleep(settle); self.measure('Settings-closed', 400)
                self.report['settings_exit_confirmed'] = True
                return
            time.sleep(.5)
        raise ValueError('Could not confirm Settings/backend exit within 120s; no process was killed')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, default=Path.cwd())
    parser.add_argument('--theme', required=True, choices=('liquid', 'smoked'), help='Your observed active theme')
    parser.add_argument('--dwell', type=timing, default=2., help='Seconds open AND closed per cycle (default 2)')
    parser.add_argument('--settle', type=timing, default=5., help='Seconds before each sample (default 5)')
    parser.add_argument('--pid', type=int, action='append', default=[], help='Additional reviewed helper PID')
    parser.add_argument('--output', type=Path, help='New private JSON file; never overwritten')
    parser.add_argument('--wait-close', action='store_true', help='Wait for normal X close and measure Settings-closed')
    args = parser.parse_args(argv)
    if any(pid <= 0 for pid in args.pid): parser.error('Helper PIDs must be positive')
    output = args.output or Path(tempfile.mkdtemp(prefix='lme-memory-'))/'report.json'
    session = Session(args.checkout, shutil.which('quickshell') or shutil.which('qs') or 'quickshell', args.pid)
    try:
        with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as file:
            try:
                session.report.update(created_utc=datetime.now(timezone.utc).isoformat(),
                    theme_user_reported=args.theme, dwell_seconds=args.dwell, settle_seconds=args.settle,
                    software_forced_in_caller=os.environ.get('LIBGL_ALWAYS_SOFTWARE') == '1')
                print(f'Timed 48-cycle workload (~{96*args.dwell+4*args.settle:.0f}s plus startup). '
                      'Avoid other input; Notifications become read.', flush=True)
                print('Report: '+str(output), flush=True)
                session.attach(); session.exercise(args.dwell, args.settle)
                if args.wait_close: session.wait_closed(args.settle)
            except (OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt) as error:
                session.report['error'] = str(error) or 'Interrupted by user'
                print('INCOMPLETE: '+session.report['error'], file=sys.stderr)
            finally:
                if session.main:
                    try: session.command('close')
                    except (OSError, ValueError, subprocess.SubprocessError) as error:
                        session.report['error'] = session.report['error'] or str(error)
                json.dump(session.report, file, indent=2); file.write('\n')
    except OSError as error:
        print('Cannot create a new report: '+str(error), file=sys.stderr); return 1
    print('Review helper ownership and actual GPU/visuals.', flush=True)
    if session.settings: print('Settings is left open; close it with X.', flush=True)
    return int(bool(session.report['error']) or not session.report['samples'] or
               not all(v['within_budget'] for v in session.report['samples']))


if __name__ == '__main__': raise SystemExit(main())
