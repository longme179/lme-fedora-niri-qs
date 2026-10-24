#!/usr/bin/env python3
"""One-shot Linux memory inventory; read-only, stdlib, no runtime integration."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from collections import defaultdict, deque
import json
import os
from pathlib import Path
import re

SCRIPTS = {'desktop_backend.py', 'clipboard.py', 'audio_visualizer.py', 'bluetooth_agent.py',
           'lyrics.py', 'display_control.py', 'idle_control.py', 'detached_log.py',
           'managed_command.py', 'shell_update.py', 'night_light.py'}
MARKER = b"LME shell's unprivileged JSON-lines backend"


def read_identity(folder):
    fields = (folder/'stat').read_text().rsplit(')', 1)[1].split()
    return int(fields[1]), int(fields[19])


def read_memory(folder):
    values = {}
    for line in (folder/'smaps_rollup').read_text().splitlines():
        parts = line.split()
        if parts and parts[0] in ('Pss:', 'Rss:'):
            if len(parts)!=3 or parts[2]!='kB' or int(parts[1])<0: raise ValueError('Invalid memory counter')
            values[parts[0][:-1].lower()+'_kib'] = int(parts[1])
    return values


def script_arg(argv):
    if Path(argv[0]).suffix=='.py': return argv[0]
    if not re.fullmatch(r'python(?:\d+(?:\.\d+)*)?', Path(argv[0]).name): return None
    index = 1
    while index<len(argv):
        value = argv[index]
        if value.startswith(('-c','-m')): return None
        if value=='--': return argv[index+1] if index+1<len(argv) else None
        if not value.startswith('-'): return value
        index += 2 if value in ('-X','-W','--check-hash-based-pycs') else 1
    return None


def resolve(folder, value):
    path = Path(value)
    if not path.is_absolute(): path = (folder/'cwd').resolve(strict=True)/path
    return path.resolve()


def checkout(path):
    root = path.parent.parent if path.parent.name=='scripts' else path.parent
    try:
        if not path.is_file() or not (root/'shell.qml').is_file(): return None
        with (root/'scripts/desktop_backend.py').open('rb') as source:
            return str(root) if MARKER in source.read(512) else None
    except OSError:
        return None


def collect(proc=Path('/proc'), uid=None, extra=()):
    proc = Path(proc); uid = os.getuid() if uid is None else uid
    records = {}; roles = {}; roots = {}; issues = []; quickshells = set()
    for folder in proc.iterdir():
        if not folder.name.isdecimal() or int(folder.name)==os.getpid(): continue
        pid = int(folder.name)
        try:
            if folder.stat().st_uid!=uid: continue
            parent, started = read_identity(folder)
            with (folder/'cmdline').open('rb') as stream:
                argv = [os.fsdecode(arg) for arg in stream.read(65536).split(b'\0') if arg]
            if not argv: continue
            records[pid] = dict(parent=parent, started=started)
            if Path(argv[0]).name in ('quickshell','qs'):
                quickshells.add(pid)
                entries = [argv[i+1] for i,value in enumerate(argv[:-1]) if value in ('-p','--path')]
                for value in entries:
                    path = resolve(folder,value)
                    if path.is_dir(): path = path/'shell.qml'
                    if path.name in ('shell.qml','settings.qml','settings-demo.qml') and (root:=checkout(path)):
                        roles[pid], roots[pid] = 'Quickshell', root
            elif (value:=script_arg(argv)) and Path(value).name in SCRIPTS:
                path = resolve(folder,value); root = checkout(path)
                if root:
                    roles[pid] = {'desktop_backend.py':'backend','clipboard.py':'clipboard worker',
                        'detached_log.py':'Launchpad relay'}.get(path.name,path.stem+' helper')
                    roots[pid] = root
                else: issues.append(f'PID {pid}: unresolved LME-named script; review or add --pid')
        except (OSError,ValueError,IndexError):
            issues.append(f'PID {pid}: process metadata unavailable or changed')
    for pid in tuple(roles):
        parent = records[pid]['parent']; visited = set()
        while parent in records and parent not in visited:
            visited.add(parent)
            if parent in quickshells:
                roles[parent], roots[parent] = 'Quickshell', roots[pid]
                break
            parent = records[parent]['parent']
    for pid in extra:
        if pid not in records: issues.append(f'PID {pid}: requested process unavailable for this user')
        else: roles.setdefault(pid,'explicit helper')
    children = defaultdict(list)
    for pid,record in records.items(): children[record['parent']].append(pid)
    pending = deque(roles)
    while pending:
        parent = pending.popleft()
        for pid in children[parent]:
            if pid in roles: continue
            roles[pid] = 'job payload' if roles[parent] in ('Launchpad relay','job payload') else 'helper descendant (review)'
            if parent in roots: roots[pid] = roots[parent]
            pending.append(pid)
    rows = []
    for pid in sorted(roles):
        folder = proc/str(pid); record = records[pid]
        values = dict(pss_kib=None,rss_kib=None)
        try:
            identity = record['parent'],record['started']
            if read_identity(folder)!=identity: raise ValueError('PID changed')
            sampled = read_memory(folder)
            if read_identity(folder)!=identity: raise ValueError('PID changed')
            values.update(sampled)
            if None in values.values(): issues.append(f'PID {pid}: PSS/RSS counters unavailable')
        except (OSError,ValueError,IndexError):
            issues.append(f'PID {pid}: memory unreadable or process changed/exited')
        rows.append(dict(pid=pid,parent=record['parent'],role=roles[pid],checkout=roots.get(pid),**values))
    unattributed = sorted(quickshells-roles.keys())
    complete = bool(rows) and not issues and not unattributed
    def total(field, selected):
        return None if any(row[field] is None for row in selected) else sum(row[field] for row in selected)
    return dict(version=1,complete=complete,processes=rows,issues=issues,
        unattributed_quickshell=unattributed,checkouts=sorted(set(roots.values())),
        pss_kib=total('pss_kib',rows) if complete else None,
        rss_kib=total('rss_kib',rows) if complete else None,
        measured_pss_kib=sum(row['pss_kib'] or 0 for row in rows),
        shell_pss_kib=total('pss_kib',[row for row in rows if row['role']!='job payload']) if rows else None,
        payload_pss_kib=total('pss_kib',[row for row in rows if row['role']=='job payload']))


def render(report):
    def size(value): return '?' if value is None else str(value)
    def mb(value): return 'unavailable' if value is None else f'{value*1024/1_000_000:.2f} MB'
    lines = ['LME memory inventory: '+('complete snapshot; review ownership' if report['complete'] else 'INCOMPLETE'),
        '    PID    PPID    PSS KiB    RSS KiB  Role']
    for row in report['processes']:
        lines.append(f"{row['pid']:7} {row['parent']:7} {size(row['pss_kib']):>10} {size(row['rss_kib']):>10}  {row['role']}")
    lines += ['Selected shell/helpers PSS: '+mb(report['shell_pss_kib']),
        'Launchpad payload PSS: '+mb(report['payload_pss_kib']),
        'Inclusive PSS: '+mb(report['pss_kib']),
        'Measured PSS subtotal (may be partial): '+mb(report['measured_pss_kib']),
        'Summed RSS: '+mb(report['rss_kib'])+'; shared pages are double-counted.',
        'Checkouts: '+json.dumps(report['checkouts']),
        'Unattributed Quickshell PIDs: '+json.dumps(report['unattributed_quickshell'])]
    lines += report['issues']
    lines.append('Review all instances/shared helpers and reparented jobs; --pid adds missing roots. This is not release approval.')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    def positive(value):
        number = int(value)
        if number<=0: raise argparse.ArgumentTypeError('PID must be positive')
        return number
    parser.add_argument('--pid',type=positive,action='append',default=[],help='Include an additional current-user root and descendants (repeatable)')
    parser.add_argument('--json',action='store_true',help='Print the same inventory as JSON; no command arguments or environment')
    parser.add_argument('--label',default='',help='Scenario label, for example steady or Settings-open')
    args = parser.parse_args(argv)
    try: report = collect(extra=args.pid)
    except OSError as error:
        parser.exit(1,'Unable to read process inventory: '+str(error)+'\n')
    report['label'] = args.label
    print(json.dumps(report,indent=2) if args.json else 'Scenario: '+json.dumps(args.label)+'\n'+render(report))
    return 0 if report['complete'] else 1


if __name__=='__main__': raise SystemExit(main())
