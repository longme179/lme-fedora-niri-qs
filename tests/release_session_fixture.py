"""Copied real hosts, read-only probes and strictly test-owned detached jobs."""
from contextlib import contextmanager
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from clipboard_slice_fixture import World, ROOT
from memory_report import collect, read_identity

OWNER = '''
import json, shlex, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from launchpad import Launchpad
from memory_report import read_identity
jobs = Launchpad()
entry = dict(name='Release fixture', kind='command', terminal=False, cwd=sys.argv[2],
    command=shlex.join([sys.executable, '-c', 'import time; time.sleep(180)']))
items = {str(i):entry for i in range(9)}
try:
 for i in range(8):
  jobs.run(str(i), items, 'unused')
  pid = jobs.jobs[str(i)]['process'].pid
  with Path(sys.argv[3]).open('a') as file:
   file.write(json.dumps(dict(pid=pid, started=read_identity(Path('/proc')/str(pid))[1]))+'\\n')
 try: jobs.run('8', items, 'unused')
 except ValueError as error: assert str(error) == 'Up to eight Launchpad commands can run at once'
 else: raise AssertionError('Ninth job admitted')
except BaseException:
 for job in jobs.jobs.values():
  job['process'].terminate(); job['process'].wait(timeout=3)
 raise
print('eight jobs; ninth rejected', flush=True)
'''


class ReleaseWorld(World):
    def __init__(self, directory, style):
        super().__init__(directory)
        # Restore the worker: the inherited fixture's tracing trampoline is not measured.
        shutil.copy2(ROOT/'scripts/clipboard.py', self.root/'scripts/clipboard.py')
        (self.root/'scripts/clipboard_slice_actual.py').unlink()
        self.env['LME_SHELL_BACKEND_DEMO'] = '1'
        preferences = json.loads(self.settings.read_text())
        preferences.update(surfaceStyle=style, animations=True, springMotion=True,
            motionPreset='jelly-v2', desktopShapes=False, bluetoothPairing=False, lyricsOnline=False)
        self.settings.write_text(json.dumps(preferences))
        path = self.root/'shell.qml'; text = path.read_text()
        old = 'lastResult: ShellState.lastResult'
        assert text.count(old) == 1
        text = text.replace(old, old+''', release: {
            mounted: panelLoader.mounted, activityMounted: activityIsland.mounted,
            activityProgress: activityIsland.progress, pending: Object.keys(ShellState.pendingActions),
            backdrops: GlassState.backdrops.length, regions: GlassState.popupRegions.length,
            consumers: GlassState.backdrops.reduce((count, item) => count + item.consumers, 0),
            style: Theme.liquidGlass ? "liquid" : "smoked", preset: Theme.motionPreset}''')
        path.write_text(text)


def owned_process(pid, started, root):
    path = Path('/proc')/str(pid)
    try:
        return (read_identity(path)[1] == started and path.stat().st_uid == os.getuid()
                and os.fsencode(root/'scripts/detached_log.py') in (path/'cmdline').read_bytes().split(b'\0')
                and os.getpgid(pid) == pid)
    except (OSError, ValueError, IndexError): return False


@contextmanager
def detached_jobs(world):
    manifest = world.home/'release-jobs.jsonl'
    try:
        result = subprocess.run([sys.executable, '-c', OWNER, str(world.root/'scripts'),
            str(world.home), str(manifest)], env=world.env, capture_output=True, text=True, timeout=15)
        if result.returncode: raise AssertionError(result.stderr)
        records = [json.loads(line) for line in manifest.read_text().splitlines()]
        assert len(records) == 8 and result.stdout.strip() == 'eight jobs; ninth rejected'
        yield records
    finally:
        records = [json.loads(line) for line in manifest.read_text().splitlines()] if manifest.exists() else []
        for record in records:
            if owned_process(record['pid'], record['started'], world.root):
                os.kill(record['pid'], signal.SIGTERM)
        deadline = time.monotonic()+5
        while any(owned_process(r['pid'], r['started'], world.root) for r in records) and time.monotonic()<deadline:
            time.sleep(.05)
        for record in records:
            if owned_process(record['pid'], record['started'], world.root):
                os.killpg(record['pid'], signal.SIGKILL)


def sample(world, label, backends, shells, workers=1, relays=0, ui=None):
    deadline = time.monotonic()+8
    while True:
        report = collect()
        rows = [row for row in report['processes'] if row['checkout'] == str(world.root)]
        counts = Counter(row['role'] for row in rows)
        expected = dict(backend=backends, Quickshell=shells,
                       **{'clipboard worker':workers, 'Launchpad relay':relays, 'job payload':relays})
        if report['complete'] and all(counts[key] == value for key,value in expected.items()): break
        if time.monotonic() >= deadline: raise AssertionError(str((label, expected, report)))
        time.sleep(.05)
    if any(row['pss_kib'] is None or row['rss_kib'] is None for row in rows):
        raise AssertionError('Incomplete fixture counters')
    total = sum(row['pss_kib'] for row in rows)
    payload = sum(row['pss_kib'] for row in rows if row['role'] == 'job payload')
    value = dict(scenario=label, processes=len(rows), roles=dict(counts), pss_kib=total,
        shell_pss_kib=total-payload, payload_pss_kib=payload,
        ui=ui,
        rss_kib=sum(row['rss_kib'] for row in rows),
        pids=[{key:row[key] for key in ('pid','role','pss_kib','rss_kib')} for row in rows],
        outside_scope_pids=[row['pid'] for row in report['processes'] if row not in rows])
    print('RELEASE_SESSION '+json.dumps(value, sort_keys=True), flush=True)
    return rows, value
