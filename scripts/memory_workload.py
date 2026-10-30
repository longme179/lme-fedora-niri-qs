#!/usr/bin/env python3
"""Opt-in timed laptop workload; inclusive PSS checkpoints, no runtime integration."""
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
from memory_report import collect, read_identity

PANELS = ('clipboard', 'control', 'activity', 'notifications', 'launcher', 'power')
CORE = {'Quickshell', 'backend', 'clipboard worker'}


def timing(value):
    number = float(value)
    if not math.isfinite(number) or not .1 <= number <= 30: raise ValueError('Timing must be between 0.1 and 30 seconds')
    return number


def same_process(pid, started):
    folder = Path('/proc')/str(pid)
    try:
        return read_identity(folder)[1] == started and (folder/'stat').read_text().rsplit(')',1)[1].split()[0] not in ('Z','X')
    except FileNotFoundError: return False
    except OSError: return True  # Unreadable does not confirm exit.


class Session:
    def __init__(self, root, binary, extra):
        self.root, self.binary, self.extra = root.resolve(), binary, extra
        self.main = self.settings = self.baseline = self.stream = None
        self.settings_core = set()
        self.report = dict(version=1, samples=[], error=None, ownership_review_required=True)

    def save(self):
        if self.stream is None: return
        self.stream.seek(0); json.dump(self.report, self.stream, indent=2)
        self.stream.write('\n'); self.stream.truncate(); self.stream.flush(); os.fsync(self.stream.fileno())

    def qs(self, *args):
        if not self.binary: raise ValueError('Quickshell not found; use --quickshell PATH')
        result = subprocess.run([self.binary, *args], capture_output=True, text=True, timeout=5)
        if result.returncode or result.stderr.strip(): raise ValueError('Quickshell request failed: '+result.stderr.strip()[-300:])
        return result.stdout.strip()

    def instances(self):
        text = self.qs('list','--all','--json')
        value = [] if text.startswith('No running instances') else json.loads(text)
        if not isinstance(value, list) or any(not isinstance(v,dict) or not isinstance(v.get('id'),str)
                or not v['id'] or type(v.get('pid')) is not int or v['pid']<=0
                or not isinstance(v.get('config_path'),str) for v in value): raise ValueError('Invalid instance inventory')
        return [{key:v[key] for key in ('id','pid','config_path')} for v in value]

    def ipc(self, instance, target, method, *args):
        return self.qs('ipc','--id',instance['id'],'call',target,method,*args)

    def command(self, method, *args):
        if self.ipc(self.main,'shell',method,*args): raise ValueError('Unexpected IPC reply; workload stopped')

    def verify(self, report, expected):
        if not report['complete'] or report['pss_kib'] is None: raise ValueError('Incomplete memory inventory; review the report')
        if report['checkouts'] != [str(self.root)]: raise ValueError('Other/unresolved checkouts require ownership review')
        core = {(v['pid'],v['role'],read_identity(Path('/proc')/str(v['pid']))[1])
                for v in report['processes'] if v['role'] in CORE}
        if {pid for pid,role,_ in core if role=='Quickshell'} != {v['pid'] for v in expected}:
            raise ValueError('Instance PIDs do not match the memory inventory')
        counts = Counter(role for _,role,_ in core)
        if counts['backend'] != len(expected) or counts['clipboard worker']>1: raise ValueError('Unexpected backend/history ownership')
        if self.baseline is not None:
            extras = core-self.baseline
            wanted = Counter({'Quickshell':1,'backend':1}) if self.settings else Counter()
            if not self.baseline<=core or Counter(role for _,role,_ in extras)!=wanted:
                raise ValueError('Persistent process identity changed; repeat with a stable session')
            if self.settings: self.settings_core = extras
        return core

    def attach(self):
        instances = self.instances()
        if len(instances)!=1 or Path(instances[0]['config_path']).resolve()!=self.root/'shell.qml':
            raise ValueError('Start one main shell from this checkout; close Settings/other instances first')
        panels = {v['id'] for v in load_catalog(self.root).get('panel',[])}
        if not {'clipboard','notifications'}<=panels: raise ValueError('Enable Clipboard and Notifications for this workload')
        status = json.loads(self.ipc(instances[0],'shell','mediaStatus'))
        if not isinstance(status,dict) or status.get('demo') is not False: raise ValueError('A live shell is required; demo/preview is not a GPU measurement')
        report = collect(extra=self.extra)
        self.report['preflight'] = report
        core = self.verify(report, instances)
        self.main, self.baseline = instances[0], core
        self.report['main_instance'] = self.main
        self.save()

    def measure(self, label, limit):
        expected = [self.main]+([self.settings] if self.settings else [])
        if {(v['id'],v['pid']) for v in self.instances()} != {(v['id'],v['pid']) for v in expected}:
            raise ValueError('Instance ownership changed during workload')
        report = collect(extra=self.extra)
        record = dict(label=label, budget_mb=limit, within_budget=None, memory=report)
        self.report['samples'].append(record)
        self.verify(report, expected)
        record['pss_mb'] = round(report['pss_kib']*1024/1_000_000,2)
        record['within_budget'] = report['pss_kib']*1024 <= limit*1_000_000
        self.save()
        print(f"{label}: {record['pss_mb']:.2f} MB inclusive PSS; {len(report['processes'])} PIDs; "
              f"{'WITHIN' if record['within_budget'] else 'OVER'} {limit} MB",flush=True)

    def open_settings(self):
        if self.instances()!=[self.main]: raise ValueError('Close Settings/other instances before continuing')
        self.command('toggle','settings')  # Same owner/environment as clicking Gear.
        deadline = time.monotonic()+30
        while time.monotonic()<deadline:
            found = [v for v in self.instances() if Path(v['config_path']).resolve()==self.root/'settings.qml']
            if len(found)>1: raise ValueError('Multiple Settings instances appeared')
            if found:
                try:
                    pending = self.ipc(found[0],'settings','startupPending')
                    if pending=='false' and self.ipc(found[0],'settings','openPage','appearance')=='true':
                        self.settings = found[0]; self.report['settings_instance'] = self.settings; return
                except subprocess.TimeoutExpired: pass  # Readiness may retry; toggles never do.
            time.sleep(.2)
        raise ValueError('Settings did not confirm a visible window within 30 seconds')

    def exercise(self, dwell, settle):
        self.command('close'); time.sleep(settle); self.measure('steady',400)
        for index in range(48):
            self.command('toggle',PANELS[index%len(PANELS)]); time.sleep(dwell)
            self.command('close'); time.sleep(dwell)
            self.report['completed_cycles'] = index+1
            if (index+1)%6==0: self.save(); print(f'Sent {index+1}/48 timed cycles',flush=True)
            if index+1 in (24,48): time.sleep(settle); self.measure('warm-'+str(index+1),400)
        self.open_settings(); time.sleep(settle); self.measure('Settings-open',500)
        values = {v['label']:v['memory']['pss_kib'] for v in self.report['samples']}
        self.report['warm_delta_mb'] = round((values['warm-48']-values['warm-24'])*1024/1_000_000,2)
        self.save()
        print(f"warm-48 minus warm-24: {self.report['warm_delta_mb']:+.2f} MB (not a leak verdict)",flush=True)

    def wait_closed(self, settle):
        deadline = time.monotonic()+120
        print('Close Settings with its X now; waiting up to 120s for Settings/backend exit.',flush=True)
        while time.monotonic()<deadline:
            if self.settings['id'] not in {v['id'] for v in self.instances()} and not any(
                    same_process(pid,started) for pid,_,started in sorted(self.settings_core)):
                self.settings = None
                time.sleep(settle); self.measure('Settings-closed',400)
                self.report['settings_exit_confirmed'] = True; self.save(); return
            time.sleep(.5)
        raise ValueError('Settings/backend exit unconfirmed after 120s; no process was killed')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--theme',required=True,choices=('liquid','smoked'),help='Your observed theme; does not change it')
    parser.add_argument('--dwell',type=timing,default=2.,help='Seconds open AND closed per cycle (default 2)')
    parser.add_argument('--settle',type=timing,default=5.,help='Seconds before each sample (default 5)')
    parser.add_argument('--pid',type=int,action='append',default=[],help='Additional reviewed helper PID')
    parser.add_argument('--quickshell',help='Override the deployment/runtime executable')
    parser.add_argument('--output',type=Path,help='New private JSON file; never overwritten')
    parser.add_argument('--wait-close',action='store_true',help='Wait for normal Settings close and sample again')
    args = parser.parse_args(argv)
    if any(pid<=0 for pid in args.pid): parser.error('Helper PIDs must be positive')
    managed = Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'lme-shell/deployment/bin/quickshell'
    binary = args.quickshell or os.environ.get('LME_QS_BINARY') or (str(managed) if os.access(managed,os.X_OK) else None)
    binary = shutil.which(binary) if binary else (shutil.which('quickshell') or shutil.which('qs'))
    output = args.output or Path(tempfile.mkdtemp(prefix='lme-memory-'))/'report.json'
    session = Session(args.checkout,binary,args.pid)
    try:
        with os.fdopen(os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'w') as stream:
            os.fchmod(stream.fileno(),0o600); session.stream = stream
            session.report.update(created_utc=datetime.now(timezone.utc).isoformat(),
                theme_user_reported=args.theme,dwell_seconds=args.dwell,settle_seconds=args.settle)
            session.save()
            print(f'Report: {output}\n48 timed cycles (~{96*args.dwell+4*args.settle:.0f}s plus startup). '
                  'Avoid other input; opening Notifications marks them read.',flush=True)
            try:
                session.attach(); session.exercise(args.dwell,args.settle)
                if args.wait_close: session.wait_closed(args.settle)
            except (OSError,ValueError,subprocess.SubprocessError,KeyboardInterrupt) as error:
                session.report['error'] = str(error) or 'Interrupted by user'
                print('INCOMPLETE: '+session.report['error'],file=sys.stderr)
            finally:
                if session.main:
                    try: session.command('close')
                    except (OSError,ValueError,subprocess.SubprocessError) as error:
                        session.report['error'] = session.report['error'] or str(error)
                        print('INCOMPLETE: final panel close failed: '+str(error),file=sys.stderr)
                session.save()
    except OSError as error:
        print('Unable to create/save a new report: '+str(error),file=sys.stderr); return 1
    print('Review helper ownership and actual GPU/visuals; Settings is never killed.',flush=True)
    return int(bool(session.report['error']) or not session.report['samples']
               or not all(v['within_budget'] for v in session.report['samples']))


if __name__=='__main__': raise SystemExit(main())
