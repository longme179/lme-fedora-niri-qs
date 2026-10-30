"""CLI wiring in copied hosts/private Wayland; shortened timings are not GPU evidence."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from release_session_fixture import ReleaseWorld


@unittest.skipUnless(os.environ.get('LME_TEST_MEMORY_WORKLOAD')=='1','private Wayland memory workload')
class NativeWorkloadCase(unittest.TestCase):
    def call(self, world, entry, target, method, *args):
        reply = subprocess.run(['quickshell','-p',str(world.root/entry),'ipc','call',target,method,*args],
            env=world.env,capture_output=True,text=True,timeout=5)
        if reply.returncode or reply.stderr.strip(): raise ValueError(reply.stderr)
        return reply.stdout.strip()

    def wait(self, predicate, process, seconds=25):
        deadline = time.monotonic()+seconds
        while time.monotonic()<deadline and process.poll() is None:
            try:
                value = predicate()
                if value: return value
            except (ValueError,subprocess.SubprocessError): pass
            time.sleep(.1)
        self.fail('Private host readiness deadline expired')

    @contextmanager
    def world(self):
        with tempfile.TemporaryDirectory(prefix='memory-native-') as raw, tempfile.TemporaryFile(mode='w+') as log:
            world = ReleaseWorld(Path(raw),'smoked')
            prefs = json.loads(world.settings.read_text()); prefs.update(animations=False,peripheralBatteryAlerts=False)
            world.settings.write_text(json.dumps(prefs))
            world.env.update(QT_QUICK_BACKEND='software',LME_WORKLOAD_OWNER_SENTINEL='main-owner')
            path = world.root/'qml/settings/SettingsApplication.qml'
            text = path.read_text().replace('function startupPending()', '''function workloadOwner(): string { return Quickshell.env("LME_WORKLOAD_OWNER_SENTINEL"); }
        function workloadClose(): void { if (view.item) (view.item as SettingsView).closeRequested(); }
        function startupPending()''',1)
            path.write_text(text)
            main = subprocess.Popen(['quickshell','-p',str(world.root/'shell.qml')],env=world.env,stdout=log,stderr=log)
            try:
                def ready():
                    value = json.loads(self.call(world,'shell.qml','clipboardSlice','state'))
                    return value if value['ready'] and value['workerReady'] else None
                self.wait(ready,main)
                yield world,main
            finally:
                subprocess.run(['quickshell','-p',str(world.root/'settings.qml'),'kill'],env=world.env,capture_output=True,timeout=5)
                if main.poll() is None: main.terminate(); main.wait(timeout=8)
            log.seek(0); output = log.read()
            for error in ('ReferenceError','TypeError','Binding loop','Failed to load configuration'):
                self.assertNotIn(error,output)

    def open_settings(self, world, main):
        self.call(world,'shell.qml','shell','toggle','settings')
        self.wait(lambda:self.call(world,'settings.qml','settings','openPage','appearance')=='true',main)

    def arguments(self, world):
        return [sys.executable,str(world.root/'scripts/memory_workload.py'),'--checkout',str(world.root),
                '--theme','smoked','--dwell','.1','--settle','.2','--output',str(world.home/'workload.json')]

    def test_unchanged_hosts_gear_route_keeps_owner_environment_and_normal_close(self):
        with self.world() as (world,main):
            self.open_settings(world,main)
            self.assertEqual(self.call(world,'settings.qml','settings','workloadOwner'),'main-owner')
            self.assertEqual(self.call(world,'settings.qml','settings','startupPending'),'false')
            self.call(world,'settings.qml','settings','workloadClose')
            def gone():
                reply = subprocess.run(['quickshell','-p',str(world.root/'settings.qml'),'list','--json'],
                    env=world.env,capture_output=True,text=True,timeout=5)
                return not reply.stdout.strip() or reply.stdout.startswith('No running instances') or json.loads(reply.stdout)==[]
            self.wait(gone,main)

    def test_existing_settings_refuses_without_closing_user_panel(self):
        with self.world() as (world,main):
            self.open_settings(world,main)
            self.call(world,'shell.qml','shell','toggle','control')
            reply = subprocess.run(self.arguments(world),env=world.env,capture_output=True,text=True,timeout=30)
            report = json.loads((world.home/'workload.json').read_text())
            self.assertEqual(reply.returncode,1)
            self.assertIn('close Settings',report['error'])
            self.assertEqual(report['samples'],[])
            self.assertTrue(json.loads(self.call(world,'shell.qml','clipboardSlice','state'))['panelOpen'])

    def test_cli_48_cycles_settings_owner_and_normal_exit_are_complete(self):
        with self.world() as (world,main), tempfile.TemporaryFile(mode='w+') as log:
            before = world.settings.read_bytes()
            caller = dict(world.env,LME_WORKLOAD_OWNER_SENTINEL='caller-not-owner')
            process = subprocess.Popen(self.arguments(world)+['--wait-close'],env=caller,stdout=log,stderr=log)
            try:
                def prompted():
                    log.seek(0); return 'Close Settings with its X now' in log.read()
                self.wait(prompted,process,seconds=100)
                self.assertEqual(self.call(world,'settings.qml','settings','workloadOwner'),'main-owner')
                self.call(world,'settings.qml','settings','workloadClose')
                process.wait(timeout=20)
                report = json.loads((world.home/'workload.json').read_text())
                self.assertIsNone(report['error'])
                self.assertEqual([s['label'] for s in report['samples']],
                    ['steady','warm-24','warm-48','Settings-open','Settings-closed'])
                self.assertTrue(all(s['memory']['complete'] for s in report['samples']))
                self.assertTrue(report['settings_exit_confirmed'])
                self.assertEqual(report['completed_cycles'],48)
                self.assertEqual(process.returncode,int(not all(s['within_budget'] for s in report['samples'])))
                self.assertEqual(world.settings.read_bytes(),before)
                self.assertNotIn('caller-not-owner',json.dumps(report))
            finally:
                if process.poll() is None: process.terminate(); process.wait(timeout=8)


if __name__=='__main__': unittest.main()
