"""Exercise actual Settings backend selector ownership across theme changes."""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import unittest

from test_backend import Fixture


class EventStreamCase(Fixture, unittest.TestCase):
    def test_style_switches_eof_reconnect_and_shutdown_reap_streams(self):
        marker = self.root / "streams"
        eof = self.root / "eof"
        niri = self.put("niri", "#!" + sys.executable + "\n" + f'''
import os,pathlib,time
with pathlib.Path({str(marker)!r}).open('a') as stream: stream.write(str(os.getpid())+'\\n')
while not pathlib.Path({str(eof)!r}).exists() or pathlib.Path({str(eof)!r}).read_text()!=str(os.getpid()): time.sleep(.02)
''')
        niri.chmod(0o700)
        self.preferences.set("surfaceStyle", "liquid")
        repo = Path(__file__).resolve().parents[1]
        harness = self.put("harness.py", f'''
import sys
from pathlib import Path
sys.path.insert(0,{str(repo / 'scripts')!r})
import desktop_backend as b
class Runner:
    def available(self,name): return name=='niri'
    def executable(self,name): return {str(niri)!r}
    def close(self): pass
    def run(self,name,*args,**kwargs):
        if name=='niri': return '[]'
        raise b.CommandError('Unavailable')
original=b.DesktopBackend
def make(**kwargs):
    kwargs.update(runner=Runner(),preferences=b.Preferences(Path({str(self.preferences.path)!r})),weather_fetch=False,manage_idle=False)
    return original(**kwargs)
b.DesktopBackend=make
raise SystemExit(b.main(['--settings','--interval','30']))
''')
        env = dict(os.environ, XDG_CONFIG_HOME=str(self.root / "config"), XDG_STATE_HOME=str(self.root / "state"),
                   XDG_CACHE_HOME=str(self.root / "cache"), XDG_RUNTIME_DIR=str(self.root / "runtime"))
        buffer = b""
        with (self.root / "backend.log").open("w+") as log:
            process = subprocess.Popen([sys.executable, str(harness)], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=log, env=env, start_new_session=True)
            def frame():
                nonlocal buffer
                deadline = time.monotonic() + 8
                while b"\n" not in buffer:
                    self.assertTrue(select.select([process.stdout], [], [], max(0, deadline-time.monotonic()))[0], "No backend reply")
                    data = os.read(process.stdout.fileno(), 65536)
                    self.assertTrue(data, (self.root / "backend.log").read_text())
                    buffer += data
                line, buffer = buffer.split(b"\n", 1)
                return json.loads(line)
            def request(**payload):
                process.stdin.write(json.dumps(payload).encode() + b"\n"); process.stdin.flush()
                result = frame()
                self.assertTrue(result["lastResult"]["ok"], result["lastResult"])
                return result
            def pids():
                return [int(value) for value in marker.read_text().split()] if marker.exists() else []
            def wait_for(condition):
                deadline = time.monotonic() + 8
                while not condition() and time.monotonic() < deadline: time.sleep(.02)
                self.assertTrue(condition(), (self.root / "backend.log").read_text())
            try:
                self.assertEqual(frame()["preferences"]["surfaceStyle"], "liquid")
                wait_for(lambda: len(pids()) == 1)
                for cycle in range(3):
                    old = pids()[-1]
                    request(action="setting", key="surfaceStyle", value="smoked")
                    wait_for(lambda: not Path(f"/proc/{old}").exists())
                    request(action="setting", key="surfaceStyle", value="liquid")
                    wait_for(lambda: len(pids()) == cycle + 2)
                old = pids()[-1]
                eof.write_text(str(old))
                wait_for(lambda: len(pids()) == 5)
                self.assertFalse(Path(f"/proc/{old}").exists(), "EOF child was not reaped")
                self.assertEqual(request(action="refresh")["preferences"]["surfaceStyle"], "liquid")
                process.stdin.close()
                self.assertEqual(process.wait(timeout=4), 0, (self.root / "backend.log").read_text())
                self.assertTrue(all(not Path(f"/proc/{pid}").exists() for pid in pids()))
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=4)
                process.stdout.close()
                if not process.stdin.closed: process.stdin.close()
