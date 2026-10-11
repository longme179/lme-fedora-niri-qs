"""Click and keyboard checks of the actual QML components on private Wayland."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

@unittest.skipUnless(os.environ.get('LME_TEST_UPGRADE_UI') == '1', 'Enable only in a private Wayland session')
class UpgradeInterfaceCase(unittest.TestCase):
    def test_settings_launcher_wifi_notifications_and_responsive_cards(self):
        pointer = os.environ.get('LME_TEST_POINTER')
        if not pointer: raise unittest.SkipTest('Set LME_TEST_POINTER')
        repo = Path(__file__).resolve().parents[1]
        fixture = repo / 'upgrades-demo.qml'
        with tempfile.TemporaryDirectory() as config, tempfile.TemporaryFile(mode='w+') as log:
            env = dict(os.environ, LME_TEST_UPGRADES='1', XDG_CONFIG_HOME=config)
            shell = subprocess.Popen(['quickshell', '-p', str(fixture)], env=env, stdout=log, stderr=log)
            def ipc(method, *args):
                return subprocess.run(['quickshell', '-p', str(fixture), 'ipc', 'call', 'upgradesFixture', method, *args], env=env, capture_output=True, text=True, timeout=4).stdout.strip()
            def wait(predicate):
                end = time.monotonic() + 8
                while time.monotonic() < end:
                    try: state = json.loads(ipc('state'))
                    except ValueError: state = {}
                    if predicate(state): return state
                    time.sleep(.1)
                log.seek(0); raise AssertionError('UI state did not settle: ' + str(state) + '\n' + log.read())
            def click(name):
                point = json.loads(ipc('position', name)); self.assertIn('x', point, name)
                time.sleep(.06)
                subprocess.run([pointer, str(point['x']), str(point['y'])], check=True, timeout=4)
            def type_text(text):
                subprocess.run(['wtype', '-s', '200', '-M', 'ctrl', '-k', 'a', '-m', 'ctrl', text], check=True, env=env, timeout=4)
            def run(action, **data): ipc('run', json.dumps(dict(action=action, **data)))
            def show(mode, page='appearance'):
                ipc('navigate', mode, page); time.sleep(.2)
            try:
                wait(lambda s: s.get('ready'))
                run('setting', key='accent', value='#ff80bf'); wait(lambda s: s.get('preferences', {}).get('accent') == '#ff80bf')
                show('settings')
                click('appearanceProfileName'); type_text('Pink glass'); click('Save current'); wait(lambda s: len(s['preferences']['appearanceProfiles']) == 2)
                run('appearanceApply', name='Dracula'); wait(lambda s: s['preferences']['accent'] == '#9580ff')
                run('appearanceApply', name='Pink glass'); wait(lambda s: s['preferences']['accent'] == '#ff80bf')
                show('settings', 'display')
                wait(lambda s: len(s.get('displays', {}).get('outputs', [])) == 1)
                click('displayMode'); subprocess.run(['wtype', '-s', '200', '-k', 'Up', '-k', 'Return'], check=True, env=env)
                dragger = os.environ.get('LME_TEST_DRAG')
                if dragger:
                    monitor = json.loads(ipc('position', 'displayMonitor-eDP-1'))
                    subprocess.run([dragger, str(monitor['x']), str(monitor['y']), str(monitor['x']+60), str(monitor['y'])], check=True, timeout=5)
                click('Apply & test'); wait(lambda s: s['displays']['preview'].get('status') == 'pending')
                click('Keep changes'); saved = wait(lambda s: bool(s['preferences']['displayLayout']))['preferences']['displayLayout']
                self.assertEqual(saved[0]['refresh'], 60000)
                if dragger: self.assertGreater(saved[0]['x'], 0)
                show('settings', 'wallpaper'); wait(lambda s: len(s.get('library', {}).get('entries', [])) >= 1)
                show('settings', 'controlLayout')
                dragger = os.environ.get('LME_TEST_DRAG')
                if dragger:
                    start = json.loads(ipc('position', 'controlGrip-charging')); finish = json.loads(ipc('position', 'controlGrip-weather'))
                    subprocess.run([dragger, str(start['x']), str(start['y']), str(finish['x']), str(finish['y'])], check=True, timeout=5)
                    wait(lambda s: s['preferences']['controlLayout'][0]['id'] == 'charging')
                layout = wait(lambda s: s.get('ready'))['preferences']['controlLayout']
                layout = list(reversed(layout)); layout[0]['enabled'] = False; layout[1]['size'] = 'half'
                run('setting', key='controlLayout', value=layout); wait(lambda s: s['preferences']['controlLayout'] == layout)
                run('setting', key='controlWidth', value=480); wait(lambda s: s['preferences']['controlWidth'] == 480)
                show('control'); time.sleep(.2)
                click('System'); wait(lambda s: len(s.get('monitor', {}).get('processes', [])) == 3)
                click('processSearch'); type_text('firefox'); wait(lambda s: s.get('processMatches') == 1)
                click('Controls'); wait(lambda s: s.get('monitor') == {})
                show('settings', 'idle'); wait(lambda s: s.get('idle', {}).get('source') == 'battery')
                click('idle-battery-display'); subprocess.run(['wtype', '-s', '200', '-k', 'Up', '-k', 'Return'], check=True, env=env)
                wait(lambda s: s['preferences']['idleProfiles']['battery']['display'] == 2)
                show('settings', 'keybinds'); wait(lambda s: s.get('keybindMatches', 0) >= 9)
                click('keybindConfig'); type_text('/tmp/lme-demo-keybindings.kdl'); click('Use path')
                wait(lambda s: s['preferences']['niriConfigPath'] == '/tmp/lme-demo-keybindings.kdl' and s['lastResult']['action'] == 'keybindRefresh')
                click('keybindSearch'); type_text('clipboard'); wait(lambda s: s.get('keybindMatches') == 1)
                click('keybindSearch'); type_text('not a real binding'); wait(lambda s: s.get('keybindMatches') == 0)
                show('launcher'); wait(lambda s: len(s.get('results', [])) == 3)
                self.assertEqual(json.loads(ipc('fuzzy')), {'subsequence': ['Firefox'], 'typo': ['Firefox']})
                click('launcherSearch'); type_text('frfox'); wait(lambda s: len(s.get('results', [])) == 1 and s['results'][0]['name'] == 'Firefox')
                type_text('= (2+3)*4'); wait(lambda s: s.get('results') and s['results'][0]['value'] == '20')
                type_text('=1/0'); wait(lambda s: 'zero' in s.get('calculationError', ''))
                type_text(': smile'); wait(lambda s: any('😀' in r['value'] for r in s.get('results', [])))
                type_text('@ project'); wait(lambda s: s.get('results') and s['results'][0]['kind'] == 'window')
                show('wifi'); click('wifiConnect-Guest'); wait(lambda s: s.get('wifiPopup')); click('Cancel'); wait(lambda s: not s.get('wifiPopup'))
                show('notifications'); ipc('seedNotifications'); wait(lambda s: s.get('groups') == 4)
                click('Mute popups'); wait(lambda s: len(s['preferences']['notificationMutedApps']) == 1)
                ipc('dndNearExpiry'); wait(lambda s: s.get('dnd')); wait(lambda s: not s.get('dnd'))
            finally:
                shell.terminate(); shell.wait(timeout=6)
            log.seek(0)
            content = log.read()
            for error in ['ReferenceError', 'TypeError', 'QML error', 'Failed to load configuration', 'Unable to assign', 'binding loop']:
                self.assertNotIn(error, content)

    def test_motion_overshoot_reduced_motion_and_night_light_controls(self):
        ENTRY = Path(__file__).resolve().parents[1] / 'upgrades-demo.qml'
        env = os.environ.copy(); env.update(LME_TEST_UPGRADES='1', LME_SHELL_DEMO='1')
        pointer = os.environ.get('LME_TEST_POINTER'); self.assertTrue(pointer)
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryFile(mode='w+') as log:
            env['XDG_CONFIG_HOME'] = temp
            shell = subprocess.Popen(['quickshell', '-p', str(ENTRY)], env=env, stdout=log, stderr=subprocess.STDOUT)
            def ipc(*args): return subprocess.check_output(['quickshell','-p',str(ENTRY),'ipc','call','upgradesFixture',*args],text=True,env=env,timeout=5).strip()
            def run(action, **values): ipc('run', json.dumps({'action':action,**values}))
            def wait(predicate, timeout=6):
                end=time.monotonic()+timeout
                while time.monotonic()<end:
                    try:
                        state=json.loads(ipc('state'))
                        if predicate(state):return state
                    except (ValueError,subprocess.CalledProcessError):pass
                    time.sleep(.05)
                self.fail('Motion / Night Light state timed out')
            def click(name):
                p=json.loads(ipc('position',name));self.assertTrue(p,name)
                time.sleep(.06)
                p=json.loads(ipc('position',name))
                subprocess.run([pointer,str(p['x']),str(p['y'])],check=True,timeout=5)
            try:
                wait(lambda s:s['ready']);ipc('navigate','settings','appearance')
                run('setting',key='motionPreset',value='jelly');run('setting',key='motionBounce',value=.8);run('setting',key='motionSpeed',value=.5)
                wait(lambda s:s['preferences']['motionPreset']=='jelly' and s['deformation']>.05)
                click('Replay preview');samples=[];end=time.monotonic()+1.6
                while time.monotonic()<end:
                    samples.append(json.loads(ipc('state'))['motionProgress']);time.sleep(.035)
                self.assertGreater(max(samples),1.02);self.assertAlmostEqual(samples[-1],1,places=3)
                run('setting',key='animations',value=False);wait(lambda s:not s['preferences']['animations'])
                click('Replay preview');self.assertEqual(json.loads(ipc('state'))['motionProgress'],1)
                self.assertEqual(json.loads(ipc('state'))['deformation'],0)
                ipc('navigate','settings','nightLight');wait(lambda s:s.get('nightLight',{}).get('available'))
                click('nightLightMode');subprocess.run(['wtype','-s','150','-k','Down','-k','Return'],check=True,env=env)
                wait(lambda s:s['preferences']['nightLightMode']=='schedule')
                click('nightLightStart');subprocess.run(['wtype','-s','150','-M','ctrl','-k','a','-m','ctrl','21:30','-k','Return'],check=True,env=env)
                wait(lambda s:s['preferences']['nightLightStart']=='21:30')
                click('nightLightEnd');subprocess.run(['wtype','-s','150','-M','ctrl','-k','a','-m','ctrl','06:45','-k','Return'],check=True,env=env)
                wait(lambda s:s['preferences']['nightLightEnd']=='06:45')
                run('setting',key='nightLightStart',value='25:00');wait(lambda s:not s['lastResult']['ok'])
                self.assertEqual(json.loads(ipc('state'))['preferences']['nightLightStart'],'21:30')
                ipc('navigate','settings','controlLayout');click('Restore default layout')
                wait(lambda s:any(m['id']=='nightLight' and m['enabled'] for m in s['preferences']['controlLayout']))
            finally:shell.terminate();shell.wait(timeout=6)
            log.seek(0);content=log.read()
            for error in ('ReferenceError','TypeError','binding loop','Unable to assign'):self.assertNotIn(error,content)
