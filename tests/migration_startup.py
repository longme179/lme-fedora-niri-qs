"""Migration smoke checks and process/cache-cold startup measurements; stdlib only."""
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import tempfile
import time
import unittest

REPO = Path(os.environ['LME_GATE_REPO'])
OUTPUT = Path(os.environ['LME_GATE_OUTPUT'])


def windows(pid):
    tree = json.loads(subprocess.check_output(['swaymsg', '-t', 'get_tree'], text=True, timeout=3))
    found = []
    def visit(node):
        if node.get('pid') == pid and node.get('visible') and node.get('window_rect', {}).get('width', 0) > 0:
            found.append(node)
        for child in node.get('nodes', []) + node.get('floating_nodes', []): visit(child)
    visit(tree)
    return found


def wait(predicate, process, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None: raise AssertionError('Launched process exited: ' + str(process.returncode))
        if predicate(): return
        time.sleep(.02)
    raise AssertionError('No mapped window/condition before startup deadline')


def stop(process):
    if process.poll() is None:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)


class Launch:
    def __init__(self, kind, name, cache_path=None):
        self.kind, self.name = kind, name
        self.cache_path = cache_path

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix='startup-', dir=OUTPUT)
        root = Path(self.temp.name)
        self.env = dict(os.environ)
        for name in ('CONFIG', 'STATE', 'CACHE', 'DATA'):
            path = root / name.lower(); path.mkdir()
            self.env['XDG_' + name + '_HOME'] = str(path)
        if self.cache_path is not None:
            self.env['XDG_CACHE_HOME'] = str(self.cache_path)
        # Absolute socket keeps this launch isolated while using the private compositor.
        runtime = root/'runtime'; runtime.mkdir(mode=0o700)
        self.env['XDG_RUNTIME_DIR'] = str(runtime)
        self.env['WAYLAND_DISPLAY'] = str(Path(os.environ['XDG_RUNTIME_DIR'])/os.environ['WAYLAND_DISPLAY'])
        config = Path(self.env['XDG_CONFIG_HOME'])/'quickshell'; config.mkdir()
        (config/'migration-checkout').symlink_to(REPO, target_is_directory=True)
        self.env.pop('LME_SHELL_PREVIEW', None)
        self.env.pop('LME_SETTINGS_PAGE', None)
        if self.kind == 'preview':
            self.env['LME_SHELL_DEMO'] = '1'
            self.entry = REPO/'shell.qml'
            self.argv = ['./scripts/start.sh', '--preview', '--config', 'migration-checkout']
        else:
            demo = self.kind == 'settings-demo'
            self.env.update(LME_SHELL_DEMO='1' if demo else '0', LME_SHELL_BACKEND_DEMO='1')
            self.entry = REPO/('settings-demo.qml' if demo else 'settings.qml')
            self.argv = ['./scripts/settings.sh'] + (['--demo'] if demo else []) + ['--page', 'appearance']
        self.env['QSG_INFO'] = '1'
        self.log = (OUTPUT/(self.name+'.log')).open('w+')
        started = time.monotonic()
        self.process = subprocess.Popen(self.argv, cwd=REPO, env=self.env, stdout=self.log, stderr=self.log, start_new_session=True)
        try: wait(lambda: windows(self.process.pid), self.process)
        except BaseException:
            stop(self.process); self.log.close(); self.temp.cleanup(); raise
        self.elapsed = time.monotonic() - started
        return self

    def ipc(self, method, *args):
        target = 'shell' if self.kind == 'preview' else 'settings'
        config = ['-c', 'migration-checkout'] if self.kind == 'preview' else ['-p', str(self.entry)]
        return subprocess.check_output(['quickshell', *config, 'ipc', 'call', target, method, *args],
                                       env=self.env, text=True, timeout=5).strip()

    def __exit__(self, *_):
        stop(self.process)
        self.log.seek(0); self.text = self.log.read(); self.log.close()
        self.temp.cleanup()


class SmokeCase(unittest.TestCase):
    def clean_log(self, launch):
        for bad in ('TypeError', 'ReferenceError', 'Binding loop', 'Failed to load configuration'):
            self.assertNotIn(bad, launch.text)

    def test_preview_alias_panels_and_clean_exit(self):
        with Launch('preview', 'G1-preview') as launch:
            for panel in ('clipboard', 'control', 'activity', 'power'):
                launch.ipc('toggle', panel); time.sleep(.4)
                launch.ipc('close'); time.sleep(.4)
            self.assertTrue(windows(launch.process.pid))
        self.clean_log(launch)

    def test_standalone_demo_settings_open_close_reopen(self):
        for index in range(2):
            with Launch('settings-demo', 'G1-settings-'+str(index)) as launch:
                self.assertEqual(launch.ipc('openPage', 'clipboard'), 'true')
                self.assertEqual(launch.ipc('openPage', 'appearance'), 'true')
            self.clean_log(launch)


def measure(count):
    result = {'method': 'Fresh process and fresh XDG config/state/data/cache/runtime per run; monotonic launch-to-first-visible mapped Sway window, polled every 20ms. OS page cache not dropped; no warm-up exclusion.', 'runs': count}
    for kind in ('preview', 'settings'):
        values = []
        for index in range(count):
            with Launch(kind, 'cold-'+kind+'-'+str(index)) as launch:
                values.append(round(launch.elapsed, 6))
        result[kind] = {'seconds': values, 'median_seconds': statistics.median(values)}
    return result
