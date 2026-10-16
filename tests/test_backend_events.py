"""Real backend loop/child lifecycle; the niri command boundary is simulated."""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from test_backend import Fixture, backend


class BackendEventCase(Fixture, unittest.TestCase):
    def test_stream_recovers_from_startup_failure_and_eof_without_blocking_commands(self):
        state_path = self.root / 'niri.json'
        events_path = self.root / 'events.jsonl'
        values = {'online': False, 'fail_start': True, 'version': 1}
        def update(**changes):
            values.update(changes); backend.write_json(state_path, values)
        update()
        niri = self.put('niri', f'''#!{sys.executable}
import json, os, time
from pathlib import Path
with Path({str(events_path)!r}).open('a') as log:
    log.write(json.dumps(dict(kind='started', pid=os.getpid(), at=time.monotonic()))+'\\n')
version = None
while True:
    current = json.loads(Path({str(state_path)!r}).read_text())['version']
    if current != version:
        print('{{}}', flush=True)
        version = current
    time.sleep(.01)
''')
        niri.chmod(0o755)
        harness = self.put('backend.py', f'''import json, sys, time
from pathlib import Path
sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
from test_backend import backend as b
class Runner:
    def available(self, name): return name == 'niri'
    def executable(self, name):
        with Path({str(events_path)!r}).open('a') as log:
            log.write(json.dumps(dict(kind='attempt', at=time.monotonic()))+'\\n')
        if json.loads(Path({str(state_path)!r}).read_text())['fail_start']:
            raise b.CommandError('Fixture startup failure')
        return {str(niri)!r}
    def run(self, name, *args, **kwargs):
        state = json.loads(Path({str(state_path)!r}).read_text())
        if not state['online']: raise b.CommandError('Fixture compositor is offline')
        if args == ('msg', '--json', 'workspaces'): return '[]'
        if args == ('msg', '--json', 'windows'): return json.dumps([dict(id=state['version'])])
        raise b.CommandError('Unexpected command')
original = b.DesktopBackend
def isolated(**kwargs):
    kwargs.update(runner=Runner(), preferences=b.Preferences(Path({str(self.preferences.path)!r})),
                  apps=b.Applications([]), proc=Path({str(self.root / 'proc')!r}),
                  sysfs=Path({str(self.root / 'sys')!r}), weather_fetch=False, manage_idle=False)
    return original(**kwargs)
b.DesktopBackend = isolated
raise SystemExit(b.main(['--interval', '30']))
''')
        def events(kind):
            return [e for line in events_path.read_text().splitlines() if (e := json.loads(line))['kind'] == kind] if events_path.exists() else []
        with tempfile.TemporaryFile(mode='w+') as log:
            process = subprocess.Popen([sys.executable, str(harness)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
            selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
            buffer = b''; latest = {}
            def until(predicate, timeout=8):
                nonlocal buffer, latest
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if predicate(): return
                    self.assertIsNone(process.poll(), 'Backend exited unexpectedly')
                    if not selector.select(.05): continue
                    data = os.read(process.stdout.fileno(), 65536)
                    self.assertTrue(data, 'Backend closed its output')
                    buffer += data
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        latest = json.loads(line)
                log.seek(0); self.fail(str(latest) + '\n' + log.read())
            def send(request):
                process.stdin.write(json.dumps(request).encode() + b'\n'); process.stdin.flush()
            try:
                until(lambda: bool(latest))
                self.assertFalse(latest['niri']['available']); self.assertEqual(events('attempt'), [])
                update(online=True)
                send({'action': 'refresh'})
                until(lambda: bool(events('attempt')))
                self.assertTrue(latest['niri']['available'])
                update(fail_start=False)
                send({'action': 'calculate', 'query': '2+2'})
                until(lambda: latest['lastResult']['action'] == 'calculate', timeout=2)
                self.assertEqual(latest['lastResult']['message'], '4')
                self.assertEqual(events('started'), [])
                until(lambda: len(events('started')) == 1)
                attempts = events('attempt')
                self.assertGreaterEqual(attempts[1]['at'] - attempts[0]['at'], 4.5)
                first = events('started')[0]
                os.kill(first['pid'], signal.SIGTERM)
                until(lambda: len(events('started')) == 2)
                second = events('started')[1]
                self.assertGreaterEqual(second['at'] - first['at'], 4.5)
                self.assertFalse(Path('/proc', str(first['pid'])).exists(), 'Exited stream was not reaped')
                update(version=99)
                until(lambda: latest['niri']['windows'] == [{'id': 99}], timeout=2)
                process.stdin.close(); process.wait(timeout=4)
                self.assertEqual(process.returncode, 0)
                self.assertFalse(Path('/proc', str(second['pid'])).exists(), 'Live stream survived backend shutdown')
            finally:
                if not process.stdin.closed: process.stdin.close()
                if process.poll() is None: process.kill(); process.wait(timeout=3)
                process.stdout.close(); selector.close()
                for child in events('started'):
                    path = Path('/proc', str(child['pid']))
                    try:
                        if str(niri).encode() in (path / 'cmdline').read_bytes(): os.kill(child['pid'], signal.SIGKILL)
                    except FileNotFoundError: pass
