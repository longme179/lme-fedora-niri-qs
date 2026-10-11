import copy
import json
import io
import os
from pathlib import Path
import signal
import tempfile
import time
import unittest
from unittest.mock import patch

from test_backend import backend, Fixture, FakeRunner
from idle_control import main as idle_main, DEFAULT_IDLE_PROFILES, IdleControl, idle_command, validate_profiles, secure_lock
from niri_keybinds import read_keybinds, nodes
from system_monitor import SystemMonitor


class LaptopCase(Fixture, unittest.TestCase):
    def test_monitor_deltas_pid_reuse_network_resets_and_bounded_history(self):
        proc = self.root / 'monitor-proc'; (proc/'net').mkdir(parents=True)
        def write(cpu, idle, ticks, born, received, sent):
            (proc/'stat').write_text(f'cpu {cpu} 0 0 {idle} 0 0 0 0\ncpu0 {cpu} 0 0 {idle} 0 0 0 0\n')
            (proc/'net/dev').write_text(f'wlp1s0: {received} 0 0 0 0 0 0 0 {sent} 0 0 0 0 0 0 0\nlo: 999 0 0 0 0 0 0 0 999 0\n')
            directory = proc/'42'; directory.mkdir(exist_ok=True)
            fields = ['0']*22; fields[0]='S'; fields[11]=str(ticks); fields[19]=str(born); fields[21]='100'
            (directory/'stat').write_text('42 (app (worker)) '+' '.join(fields))
        clock = [0.0]
        monitor = SystemMonitor(proc, lambda: clock[0]); system={'cpu':50,'memoryPercent':30}
        write(100,100,100,1,1000,2000)
        first = monitor.sample(system)
        self.assertIsNone(first['cores'][0]['percent']); self.assertIsNone(first['processes'][0]['cpu'])
        clock[0]=2; write(200,200,100+os.sysconf('SC_CLK_TCK'),1,3000,3000)
        state = monitor.sample(system)
        self.assertEqual(state['cores'][0]['percent'],50)
        self.assertEqual(state['processes'][0]['name'],'app (worker)')
        self.assertEqual(state['processes'][0]['cpu'],50)
        self.assertEqual(state['processes'][0]['memoryBytes'],100*os.sysconf('SC_PAGE_SIZE'))
        self.assertEqual(state['interfaces'][0]['download'],1000)
        clock[0]=4; write(300,300,999,2,1,1)
        state=monitor.sample(system)
        self.assertIsNone(state['processes'][0]['cpu']); self.assertEqual(state['interfaces'][0]['download'],0)
        for i in range(65): clock[0]+=2; monitor.sample(system)
        self.assertEqual(len(monitor.history),60)

    def test_monitor_is_on_demand_and_settings_cannot_start_it(self):
        live=self.make_backend()
        with patch.object(live.monitor, 'sample') as sample:
            live.snapshot(); sample.assert_not_called()
            self.assertTrue(live.handle({'action':'monitor','enabled':True})['ok'])
        with patch.object(live.monitor, 'sample') as sample:
            live.snapshot(); sample.assert_called_once()
            live.handle({'action':'monitor','enabled':False}); live.snapshot(); self.assertEqual(sample.call_count,1)
        for invalid in ['true',1,None]: self.assertFalse(live.handle({'action':'monitor','enabled':invalid})['ok'])
        live.settings_only=True
        self.assertFalse(live.handle({'action':'monitor','enabled':True})['ok'])

    def test_demo_actions_are_isolated_and_version_gates_blur(self):
        runner=FakeRunner(available=backend.TOOLS); live=self.make_backend(runner,demo=True)
        for request in [{'action':'monitor','enabled':True},{'action':'monitor','enabled':False}, {'action':'keybindRefresh'}, {'action':'platformRefresh'}, {'action':'idleRefresh'},{'action':'idleInhibit','value':True}]:
            self.assertTrue(live.handle(request)['ok'],request)
        self.assertEqual(runner.calls,[]); self.assertEqual(runner.spawns,[]); self.assertFalse(self.preferences.path.exists())
        for version, expected in [('niri 25.11',False),('niri 26.04 (abcdef)',True),('niri 26.08',True),('unknown',False)]:
            runner=FakeRunner(responses={('niri','--version'):version}); state=self.make_backend(runner).compositor_features()
            self.assertEqual(state['popupBlurSupported'],expected)

    def test_ac_source_uses_adapter_online_not_full_battery_status(self):
        supplies=self.root/'sys/class/power_supply'; (supplies/'AC').mkdir(parents=True)
        (supplies/'AC/type').write_text('Mains'); (supplies/'AC/online').write_text('0')
        (supplies/'BAT0').mkdir(exist_ok=True); (supplies/'BAT0/type').write_text('Battery'); (supplies/'BAT0/status').write_text('Full')
        self.assertFalse(self.make_backend().ac_online())
        (supplies/'AC/online').write_text('1'); self.assertTrue(self.make_backend().ac_online())

    def test_settings_reads_live_idle_status_without_starting_another_daemon(self):
        path=str(Path(backend.__file__).resolve().parents[1]/"shell.qml")
        state={'source':'ac','running':True,'available':True,'paused':True,'error':'Example error'}
        runner=FakeRunner(responses={('quickshell','-p',path,'ipc','call','shell','idleStatus'):json.dumps(state)})
        live=self.make_backend(runner); live.settings_only=True
        self.assertTrue(live.handle({'action':'idleRefresh'})['ok']); self.assertEqual(live.idle_state,state)
        self.assertEqual(runner.spawns,[])

    def test_profiles_validate_and_preserve_existing_preferences(self):
        profiles=copy.deepcopy(DEFAULT_IDLE_PROFILES); profiles['battery']['display']=2
        self.preferences.set('idleProfiles',profiles)
        self.assertEqual(backend.Preferences(self.preferences.path).values['idleProfiles'],profiles)
        self.assertFalse(self.preferences.values['idleEnabled'])
        for value in [None,{},dict(profiles,extra={})]:
            with self.assertRaises(ValueError): validate_profiles(value)
        for value in [True,-1,241,'3']:
            invalid=copy.deepcopy(profiles); invalid['battery']['lock']=value
            with self.assertRaises(ValueError): validate_profiles(invalid)
        invalid=copy.deepcopy(profiles); invalid['battery']['lock']=20
        with self.assertRaises(ValueError): validate_profiles(invalid)
        self.assertEqual(self.preferences.values['idleProfiles'],profiles)

    def test_idle_commands_sources_pause_and_owned_cleanup(self):
        runner=FakeRunner(available={'swayidle','niri','swaylock','systemctl'})
        argv=idle_command(DEFAULT_IDLE_PROFILES['battery'], True, runner)
        self.assertEqual(argv[:2],['/usr/bin/swayidle','-w'])
        self.assertIn('180',argv); self.assertIn('300',argv); self.assertIn('900',argv)
        self.assertIn('before-sleep',argv); self.assertTrue(any('sleep --lock' in a for a in argv))
        class Child:
            pid=99999
            def poll(self): return None
            def wait(self,**kwargs): return 0
        prefs=copy.deepcopy(backend.DEFAULT_PREFERENCES); prefs['idleEnabled']=True
        control=IdleControl(runner)
        with patch('idle_control.subprocess.Popen',return_value=Child()) as popen, patch('idle_control.os.killpg') as kill:
            self.assertTrue(control.sync(prefs,False)['running']); control.sync(prefs,False); self.assertEqual(popen.call_count,1)
            self.assertEqual(control.sync(prefs,True)['source'],'ac'); self.assertEqual(popen.call_count,2)
            control.paused=True; self.assertFalse(control.sync(prefs,True)['running']); self.assertEqual(popen.call_count,2)
            self.assertEqual(kill.call_count,2)
            control.close()
        unavailable=IdleControl(FakeRunner()); state=unavailable.sync(prefs,False)
        self.assertFalse(state['running']); self.assertIn('Install',state['error'])
        live=self.make_backend(); live.manage_idle=False; live.preferences.set('idleEnabled',True)
        with patch.object(live.idle_control,'sync') as sync: live.snapshot(); sync.assert_not_called()

    def test_suspend_waits_for_lock_and_reports_failure_without_sleep(self):
        runner=FakeRunner(available={'systemctl','swaylock'})
        live=self.make_backend(runner)
        with patch.object(backend, 'secure_lock',side_effect=RuntimeError('Lock failed')):
            ack=live.handle({'action':'suspend'}); self.assertTrue(ack['pending'])
            end=time.monotonic()+2
            while not live.feature_jobs['suspend'].done() and time.monotonic()<end: time.sleep(.01)
            live.finish_features(); self.assertFalse(live.last_result['ok']); self.assertIn('Lock failed',live.last_result['message'])
            self.assertNotIn(('systemctl','suspend'),runner.calls)
        with patch.object(backend, 'secure_lock') as lock:
            self.assertEqual(live.lock_session(suspend=True),'Suspend requested after locking')
            lock.assert_called_once(); self.assertEqual(runner.calls[-1],('systemctl','suspend'))
        with patch('sys.argv',['idle_control.py','sleep','--lock']), patch('idle_control.secure_lock',side_effect=RuntimeError('Lock failed')), patch('idle_control.subprocess.run') as sleep, patch('sys.stderr',io.StringIO()):
            self.assertEqual(idle_main(),1); sleep.assert_not_called()

    def test_backend_sigterm_stops_its_idle_child(self):
        import subprocess
        tools=self.root/'idle-tools'; tools.mkdir(); marker=self.root/'idle-pid'
        fake=tools/'swayidle'; fake.write_text('#!/usr/bin/python3\nimport os,pathlib,time\npathlib.Path('+repr(str(marker))+').write_text(str(os.getpid()))\ntime.sleep(60)\n'); fake.chmod(0o755)
        fake=tools/'niri'; fake.write_text('#!/usr/bin/python3\nimport sys\nprint("niri 25.11" if "--version" in sys.argv else "[]")\n'); fake.chmod(0o755)
        profiles={key:{'display':1,'lock':0,'suspend':0} for key in ['ac','battery']}
        self.preferences.update({'idleEnabled':True,'idleProfiles':profiles,'idleLockBeforeSleep':False,'weatherAutoLocation':False})
        config=self.root/'session-config'; backend.Preferences(config/'lme-shell/settings.json').update(self.preferences.values)
        with tempfile.TemporaryFile(mode='w+') as log:
            env={**os.environ,'PATH':str(tools),'XDG_CONFIG_HOME':str(config),'XDG_RUNTIME_DIR':str(self.root/'runtime'),'NIRI_SOCKET':'test-only'}
            process=subprocess.Popen([os.sys.executable,str(Path(backend.__file__).resolve()),'--interval','0.5'],env=env,stdin=subprocess.PIPE,stdout=log,stderr=log)
            pid=None
            try:
                end=time.monotonic()+5
                while not marker.exists() and process.poll() is None and time.monotonic()<end: time.sleep(.05)
                self.assertTrue(marker.exists()); pid=int(marker.read_text())
                process.terminate(); process.wait(timeout=5)
                self.assertEqual(process.returncode,0)
                with self.assertRaises(ProcessLookupError): os.kill(pid,0)
            finally:
                if process.poll() is None: process.kill(); process.wait(timeout=3)
                if process.stdin: process.stdin.close()
                if pid:
                    try: os.kill(pid,signal.SIGTERM)
                    except ProcessLookupError: pass

    def test_secure_lock_ready_handshake_reuses_locker_and_detects_failure(self):
        tools=self.root/'tools'; tools.mkdir()
        locker=tools/'swaylock'
        locker.write_text('#!/usr/bin/python3\nimport os,sys,time\nfd=int(sys.argv[sys.argv.index("--ready-fd")+1]); os.write(fd,b"1"); os.close(fd); time.sleep(30)\n'); locker.chmod(0o755)
        with patch.dict(os.environ,{'PATH':str(tools)+':'+os.environ.get('PATH',''),'XDG_RUNTIME_DIR':str(self.root/'runtime')}):
            try:
                secure_lock(); state=json.loads((self.root/'runtime/lme-shell/session-lock.json').read_text())
                secure_lock(); self.assertEqual(json.loads((self.root/'runtime/lme-shell/session-lock.json').read_text()),state)
            finally:
                if 'state' in locals(): os.kill(state['pid'],signal.SIGTERM)
            # Remove stale identity so the failed process must be attempted.
            (self.root/'runtime/lme-shell/session-lock.json').unlink()
            locker.write_text('#!/usr/bin/python3\nimport sys\nprint("Denied by compositor",file=sys.stderr)\nsys.exit(1)\n'); locker.chmod(0o755)
            with self.assertRaisesRegex(RuntimeError,'not confirmed'): secure_lock()

    def test_keybind_parser_includes_comments_raw_strings_disabled_and_errors(self):
        config=self.root/'config.kdl'; included=self.root/'keys.kdl'
        config.write_text('''/* outside /* nested */ comment */
input { keyboard { xkb { layout "us"; }; }; }
include "keys.kdl"
binds {
  Mod+A hotkey-overlay-title="Open {app}; // title" { spawn "app" "a}b"; }
  /- Mod+B { spawn "hidden"; }
  Mod+C /- hotkey-overlay-title="Hidden label" { spawn r#"say \"hi\" {x}"#; }
}
include "missing.kdl"
''')
        included.write_text('include "config.kdl"\nbinds { Mod+Tab { toggle-overview; }; }')
        result=read_keybinds(str(config))
        self.assertEqual([b['key'] for b in result['bindings']],['Mod+Tab','Mod+A','Mod+C'])
        self.assertEqual(result['bindings'][1]['title'],'Open {app}; // title')
        self.assertEqual(result['bindings'][1]['line'],5)
        self.assertIn('say "hi" {x}',result['bindings'][2]['action'])
        self.assertIn('missing.kdl',result['errors'][0])
        self.assertEqual(config.read_text().count('binds'),1)
        for text in ['binds { Mod+A { spawn "app"; }','/* unclosed','binds { Mod+A { spawn "unclosed; } }']:
            with self.assertRaises(ValueError): nodes(text)
        escaped = nodes(r'binds { Mod+A hotkey-overlay-title="C:\\stuff \s \u{1f600}" { spawn "app"; }; }')
        self.assertEqual(escaped[0]['children'][0]['props']['hotkey-overlay-title'], 'C:\\stuff   😀')
        config.write_text('bad {'); self.assertTrue(read_keybinds(str(config))['errors'])
        self.assertEqual(read_keybinds(str(self.root/'absent'))['bindings'],[])


class NativeIdleCase(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('LME_TEST_IDLE_NATIVE') == '1', 'requires private Wayland idle session')
    def test_swayidle_receives_idle_and_resume_without_touching_hardware(self):
        import subprocess
        import shutil
        self.assertIsNotNone(shutil.which('swayidle'))
        pointer=os.environ['LME_TEST_POINTER']
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
            root=Path(directory); calls=root/'calls'; fake=root/'niri'
            fake.write_text('#!/usr/bin/python3\nimport pathlib,sys\np=pathlib.Path('+repr(str(calls))+'); p.open("a").write(sys.argv[-1]+"\\n")\n'); fake.chmod(0o755)
            runner=FakeRunner(available={'swayidle','niri'})
            runner.executable=lambda name: shutil.which('swayidle') if name == 'swayidle' else str(fake)
            argv=idle_command({'display':1,'lock':0,'suspend':0},False,runner)
            argv[argv.index('timeout')+1]='1'  # Test-only timeout; production preferences stay in minutes.
            argv=[os.sys.executable,str(Path(backend.__file__).with_name('idle_control.py')),'--parent',str(os.getpid()),'client',*argv]
            env={**os.environ,'XDG_CONFIG_HOME':directory}
            child=subprocess.Popen(argv,env=env,stdout=log,stderr=log)
            def wait(action):
                end=time.monotonic()+5
                while time.monotonic()<end:
                    if calls.exists() and action in calls.read_text(): return
                    if child.poll() is not None: break
                    time.sleep(.05)
                log.seek(0); self.fail('No '+action+' from native idle notifier: '+log.read())
            try:
                wait('power-off-monitors')
                subprocess.run([pointer,'300','300'],check=True,timeout=4)
                wait('power-on-monitors')
                self.assertEqual(calls.read_text().splitlines()[:2],['power-off-monitors','power-on-monitors'])
                end=time.monotonic()+4
                while calls.read_text().splitlines().count('power-off-monitors') < 2 and time.monotonic()<end: time.sleep(.05)
                self.assertGreaterEqual(calls.read_text().splitlines().count('power-off-monitors'),2)
                child.terminate(); child.wait(timeout=4)
                self.assertGreaterEqual(calls.read_text().splitlines().count('power-on-monitors'),2)
            finally:
                child.terminate(); child.wait(timeout=4)

    @unittest.skipUnless(os.environ.get('LME_TEST_IDLE_NATIVE') == '1', 'requires private Quickshell session')
    def test_quickshell_shutdown_does_not_leave_an_idle_daemon(self):
        import subprocess
        import sys
        import shutil
        qs=shutil.which('quickshell')
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryFile(mode='w+') as log:
            root=Path(temporary); tools=root/'tools'; tools.mkdir(); marker=root/'idle-pid'
            fake=tools/'swayidle'; fake.write_text('#!/usr/bin/python3\nimport os,pathlib,time\npathlib.Path('+repr(str(marker))+').write_text(str(os.getpid()))\ntime.sleep(30)\n'); fake.chmod(0o755)
            fake=tools/'niri'; fake.write_text('#!/usr/bin/python3\nimport sys\nprint("niri 25.11" if "--version" in sys.argv else "[]")\n'); fake.chmod(0o755)
            config=root/'config'
            backend.Preferences(config/'lme-shell/settings.json').update({'idleEnabled':True,'idleLockBeforeSleep':False,'weatherAutoLocation':False,'idleProfiles':{key:{'display':1,'lock':0,'suspend':0} for key in ['ac','battery']}})
            fixture=root/'shell.qml'
            command=json.dumps([sys.executable,str(Path(backend.__file__).resolve())])
            fixture.write_text('import QtQuick\nimport Quickshell\nimport Quickshell.Io\nShellRoot { Process { running: true; stdinEnabled: true; command: '+command+'; stdout: SplitParser {} } }')
            env={**os.environ,'PATH':str(tools),'XDG_CONFIG_HOME':str(config),'NIRI_SOCKET':'test-only'}
            shell=subprocess.Popen([qs,'-p',str(fixture)],env=env,stdout=log,stderr=log)
            pid=None
            try:
                end=time.monotonic()+6
                while not marker.exists() and shell.poll() is None and time.monotonic()<end: time.sleep(.05)
                log.seek(0); self.assertTrue(marker.exists(), log.read()); pid=int(marker.read_text())
                subprocess.run([qs,'-p',str(fixture),'kill'],env=env,capture_output=True,check=True,timeout=4)
                shell.wait(timeout=5)
                end=time.monotonic()+3
                while time.monotonic()<end:
                    try: os.kill(pid,0)
                    except ProcessLookupError: break
                    # An orphan can briefly be a zombie until init reaps it.
                    if Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0] == 'Z': break
                    time.sleep(.05)
                else: self.fail('Quickshell shutdown left its idle daemon running')
            finally:
                if shell.poll() is None: shell.terminate(); shell.wait(timeout=3)
                if pid:
                    try: os.kill(pid,signal.SIGTERM)
                    except ProcessLookupError: pass
