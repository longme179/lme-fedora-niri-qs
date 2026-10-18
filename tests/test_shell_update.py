"""Real local Git remotes; no network, checkout resets or installed-shell changes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
from shell_update import ShellUpdate


@unittest.skipUnless(shutil.which('git'), 'Git is required')
class ShellUpdateCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        environment = patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1'})
        environment.start(); self.addCleanup(environment.stop)
        self.remote = self.root/'origin.git'
        self.source = self.root/'author'
        self.client = self.root/'installed shell'
        self.git(self.root, 'init', '--bare', '--initial-branch=main', str(self.remote))
        self.git(self.root, 'init', '--initial-branch=main', str(self.source))
        (self.source/'shell.qml').write_text('version one\n')
        self.commit(self.source)
        self.git(self.source, 'remote', 'add', 'origin', str(self.remote))
        self.git(self.source, 'push', '-u', 'origin', 'main')
        self.git(self.root, 'clone', str(self.remote), str(self.client))
        self.updater = ShellUpdate(self.client, self.root/'state')

    @staticmethod
    def git(repo, *args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def commit(self, repo):
        self.git(repo, 'add', '.')
        self.git(repo, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'Test update')
        return self.git(repo, 'rev-parse', 'HEAD')

    def publish(self):
        (self.source/'shell.qml').write_text('version two\n')
        target = self.commit(self.source)
        self.git(self.source, 'push')
        return target

    def wait(self):
        deadline = time.monotonic()+10
        value = {}
        while time.monotonic() < deadline:
            value = self.updater.read()
            if value.get('stage') not in ('checking', 'updating', None):
                if self.updater.worker: self.updater.worker.wait(timeout=3)
                return value
            time.sleep(.03)
        self.fail(str(value))

    def test_check_then_detached_fast_forward_preserves_preferences_and_skips_hooks(self):
        original = self.git(self.client, 'rev-parse', 'HEAD')
        target = self.publish()
        prefs = self.root/'settings.json'; prefs.write_text('{"opacity":0.8}')
        hook = self.client/'.git/hooks/post-merge'
        hook.write_text('#!/bin/sh\nprintf unexpected > '+str(self.root/'hook-ran')+'\n'); hook.chmod(0o755)
        self.assertEqual(self.updater.inspect()['current'], original)
        self.updater.launch('check')
        value = self.wait()
        self.assertEqual(value['stage'], 'available', value)
        self.assertTrue(value['canUpdate'])
        self.assertEqual(self.git(self.client, 'rev-parse', 'HEAD'), original)
        self.updater.launch('update')
        value = self.wait()
        self.assertEqual(value['stage'], 'updated', value)
        self.assertEqual(value['current'], target)
        self.assertEqual(self.git(self.client, 'rev-parse', 'HEAD'), target)
        self.assertEqual(prefs.read_text(), '{"opacity":0.8}')
        self.assertFalse((self.root/'hook-ran').exists())
        self.assertEqual(self.updater.perform('update')['stage'], 'current')

    def test_dirty_tracked_untracked_and_non_main_checkouts_are_blocked(self):
        original = self.git(self.client, 'rev-parse', 'HEAD')
        for name in ('shell.qml', 'personal-script.sh'):
            path = self.client/name; previous = path.read_text() if path.exists() else None
            path.write_text('my changes')
            value = self.updater.launch('update')
            self.assertEqual(value['stage'], 'blocked')
            self.assertIn('Local changes', value['message'])
            self.assertEqual(path.read_text(), 'my changes')
            if previous is None: path.unlink()
            else: path.write_text(previous)
        self.git(self.client, 'checkout', '-b', 'personal')
        self.assertEqual(self.updater.inspect()['stage'], 'blocked')
        self.assertEqual(self.git(self.client, 'rev-parse', 'HEAD'), original)

    def test_local_commits_and_divergence_are_never_reset_or_rebased(self):
        (self.client/'local.txt').write_text('personal commit')
        original = self.commit(self.client)
        self.publish()
        self.updater.launch('update')
        value = self.wait()
        self.assertEqual(value['stage'], 'error', value)
        self.assertIn('commits outside', value['message'])
        self.assertEqual(self.git(self.client, 'rev-parse', 'HEAD'), original)
        self.assertEqual((self.client/'local.txt').read_text(), 'personal commit')

    def test_edits_during_fetch_are_preserved(self):
        self.publish()
        original_git = self.updater.git
        def concurrent_edit(*args, **kwargs):
            result = original_git(*args, **kwargs)
            if args[0] == 'fetch': (self.client/'shell.qml').write_text('edit made while fetching')
            return result
        with patch.object(self.updater, 'git', side_effect=concurrent_edit), self.assertRaisesRegex(ValueError, 'Local changes'):
            self.updater.perform('update')
        self.assertEqual((self.client/'shell.qml').read_text(), 'edit made while fetching')

    def test_lock_and_interrupted_state_recovery_and_corrupt_status(self):
        current = self.updater.local()
        fd = self.updater.lock()
        try:
            self.updater.write(self.updater.state('updating', 'Working', current=current))
            self.assertEqual(self.updater.launch('check')['stage'], 'updating')
            self.assertEqual(self.updater.inspect()['stage'], 'updating')
        finally: os.close(fd)
        self.assertEqual(self.updater.inspect()['stage'], 'error')
        self.assertIn('interrupted', self.updater.read()['message'])
        for content in ('[1,2]', 'not json'):
            self.updater.path.write_text(content)
            self.assertEqual(self.updater.inspect()['stage'], 'idle')

    def test_network_failure_and_zip_installation_report_errors(self):
        self.git(self.client, 'remote', 'set-url', 'origin', str(self.root/'missing.git'))
        original = self.updater.local()
        self.updater.launch('check')
        value = self.wait()
        self.assertEqual(value['stage'], 'error', value)
        self.assertEqual(self.git(self.client, 'rev-parse', 'HEAD'), original)
        folder = self.root/'zip'; folder.mkdir()
        self.assertIn('ZIP/source', ShellUpdate(folder, self.root/'zip-state').inspect()['message'])

    def test_git_errors_redact_credentials(self):
        response = subprocess.CompletedProcess([], 1, '', 'fatal: https://person:secret@github.com/example/repo failed')
        with patch('shell_update.subprocess.run', return_value=response), self.assertRaises(ValueError) as error:
            self.updater.git('fetch')
        self.assertNotIn('secret', str(error.exception))
        with patch('shell_update.subprocess.run', side_effect=FileNotFoundError), self.assertRaisesRegex(ValueError, 'Install git'):
            self.updater.git('status')

    @unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'private Wayland update controls')
    def test_update_buttons_and_worker_survive_the_settings_process_exiting(self):
        project = Path(__file__).resolve().parents[1]
        shutil.copytree(project/'qml', self.source/'qml')
        shutil.copytree(project/'scripts', self.source/'scripts', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in ('config', 'assets'): (self.source/name).symlink_to(project/name, target_is_directory=True)
        (self.source/'.gitignore').write_text('__pycache__/\n*.pyc\n')
        (self.source/'ui.qml').write_text('''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import "qml/settings"
import "qml/services"
ShellRoot {
    FloatingWindow { implicitWidth:1100;implicitHeight:950;color:"#20232a"
        AboutPage { id:page;width:1040;anchors.centerIn:parent }
        TestCase { id:mouse;when:false }
    }
    IpcHandler { target:"fixture"
        function state():string { return JSON.stringify({ready:UpdateState.ready,busy:UpdateState.busy,stage:UpdateState.state.stage,
            canUpdate:mouse.findChild(page,"applyUpdate").enabled,message:UpdateState.state.message}); }
        function click(name:string):void { const button=mouse.findChild(page,name);mouse.mouseClick(button,button.width/2,button.height/2); }
    }
}
''')
        self.commit(self.source); self.git(self.source, 'push')
        self.git(self.client, 'pull', '--ff-only')
        entry = self.client/'ui.qml'
        target = self.publish()
        marker = self.root/'fetch-started'
        real_git = shutil.which('git')
        shim = self.root/'bin/git'; shim.parent.mkdir()
        shim.write_text('#!/usr/bin/env python3\nimport os,sys,time\n'
                        'if "fetch" in sys.argv:\n'
                        f'    open({str(marker)!r},"w").close();time.sleep(.5)\n'
                        f'os.execv({real_git!r},[{real_git!r},*sys.argv[1:]])\n')
        shim.chmod(0o755)
        env = dict(os.environ, PATH=str(shim.parent)+os.pathsep+os.environ['PATH'],
                   QT_QPA_PLATFORM='wayland', QT_QUICK_BACKEND='software', LME_SHELL_DEMO='0',
                   LME_SHELL_BACKEND_DEMO='1', LME_SHELL_SETTINGS='1',
                   XDG_CONFIG_HOME=str(self.root/'ui-config'), XDG_STATE_HOME=str(self.root/'ui-state'),
                   XDG_DATA_HOME=str(self.root/'ui-data'), DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(self.root/'no-bus'))
        with (self.root/'ui.log').open('w+') as log:
            process = subprocess.Popen(['quickshell', '-p', str(entry)], env=env, stdout=log, stderr=log)
            def ipc(method, *args):
                return subprocess.check_output(['quickshell', '-p', str(entry), 'ipc', 'call', 'fixture', method, *args],
                                               env=env, text=True, stderr=subprocess.DEVNULL, timeout=4).strip()
            def wait(predicate):
                deadline = time.monotonic()+10
                while time.monotonic() < deadline:
                    try:
                        state = json.loads(ipc('state'))
                        if predicate(state): return state
                    except (ValueError, subprocess.CalledProcessError): pass
                    time.sleep(.04)
                log.seek(0); self.fail(log.read())
            worker = ShellUpdate(self.client, self.root/'ui-state/lme-shell')
            try:
                wait(lambda s:s['ready'] and not s['busy'])
                ipc('click', 'checkUpdates')
                wait(lambda s:s['stage'] == 'available' and s['canUpdate'])
                marker.unlink()
                ipc('click', 'applyUpdate')
                wait(lambda s:s['busy'] and marker.exists())
                process.terminate(); process.wait(timeout=5)
                deadline = time.monotonic()+10
                while time.monotonic() < deadline and worker.read().get('stage') in ('checking', 'updating'):
                    time.sleep(.04)
                self.assertEqual(worker.read().get('stage'), 'updated', worker.read())
                self.assertEqual(self.git(self.client, 'rev-parse', 'HEAD'), target)
                log.seek(0)
                output = log.read()
                for error in ('TypeError', 'ReferenceError', 'Unable to assign', 'Binding loop', 'Failed to load configuration'):
                    self.assertNotIn(error, output)
            finally:
                if process.poll() is None: process.terminate();process.wait(timeout=5)
