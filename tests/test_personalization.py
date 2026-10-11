"""Element theming, concurrent edits, binary aliases and native liquid controls."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from test_backend import backend, Fixture
from desktop_features import APPEARANCE_KEYS, appearance_profile


class PersonalizationCase(Fixture, unittest.TestCase):
    def test_tokens_fonts_and_bar_bounds_reject_malformed_preferences(self):
        for key, value in [('themeOverrides', {'buttonFill': '#ABCDEF', 'barFill': '#80223344'}), ('fontOverrides', {'body': 'Roboto', 'bar': 'DejaVu Sans'}), ('barEdge', 'bottom'), ('barEdgeMargin', 0), ('barSideMargin', 160), ('barHeight', 64), ('fontSize', 20)]:
            self.preferences.set(key, value)
        self.assertEqual(self.preferences.values['themeOverrides']['buttonFill'], '#abcdef')
        for key, value in [('themeOverrides', {'missing': '#112233'}), ('themeOverrides', {'buttonFill': 'red'}), ('themeOverrides', {'barFill': 3}), ('fontOverrides', {'heading': 'bad\nname'}), ('fontOverrides', {'unknown': 'Roboto'}), ('barEdge', 'left'), ('barEdgeMargin', -1), ('barSideMargin', 161), ('barHeight', 30), ('fontSize', True)]:
            with self.assertRaises(ValueError): self.preferences.set(key, value)
        self.assertEqual(self.preferences.values['barEdge'], 'bottom')
        for token in (None, [], False):
            result = self.make_backend().handle({'action': 'setting', 'key': 'themeOverrides', 'token': token, 'value': '#112233'})
            self.assertFalse(result['ok'])

    def test_two_stale_clients_patch_tokens_without_losing_other_edits(self):
        first, second = backend.Preferences(self.preferences.path), backend.Preferences(self.preferences.path)
        first.set('themeOverrides', '#112233', token='buttonFill')
        second.set('themeOverrides', '#abcdef', token='barFill')
        first.set('fontOverrides', 'DejaVu Sans', token='body')
        second.set('themeOverrides', '', token='buttonFill')
        saved = json.loads(self.preferences.path.read_text())
        self.assertEqual(saved['themeOverrides'], {'barFill': '#abcdef'})
        self.assertEqual(saved['fontOverrides'], {'body': 'DejaVu Sans'})
        with self.assertRaises(ValueError): first.set('themeOverrides', '', token='missing')

    def test_legacy_profiles_migrate_and_profiles_include_element_and_font_edits(self):
        legacy = {'name': 'Old', 'accent': '#ff80bf', 'opacity': .8, 'density': 'compact', 'animations': True}
        normalized = appearance_profile(legacy, backend.validate_preference)
        self.assertEqual(set(normalized) - {'name'}, set(APPEARANCE_KEYS))
        self.assertEqual(normalized['themeOverrides'], {})
        live = self.make_backend(demo=True)
        for key, token, value in [('themeOverrides', 'buttonFill', '#123456'), ('fontOverrides', 'body', 'DejaVu Sans')]:
            self.assertTrue(live.handle({'action': 'setting', 'key': key, 'token': token, 'value': value})['ok'])
        live.handle({'action': 'appearanceSave', 'name': 'Personal'})
        live.handle({'action': 'appearanceApply', 'name': 'Dracula'})
        self.assertEqual(live.preferences.values['themeOverrides'], {})
        live.handle({'action': 'appearanceApply', 'name': 'Personal'})
        self.assertEqual(live.preferences.values['themeOverrides']['buttonFill'], '#123456')
        self.assertEqual(live.preferences.values['fontOverrides']['body'], 'DejaVu Sans')
        self.assertFalse(self.preferences.path.exists())

    def test_settings_launcher_supports_qs_only_and_keeps_argument_boundaries(self):
        repo = Path(__file__).resolve().parents[1]; binaries = self.root/'bin'; binaries.mkdir()
        (binaries/'dirname').symlink_to(shutil.which('dirname'))
        fake = binaries/'qs'
        fake.write_text('#!/usr/bin/python3\nimport sys,json\nif "ipc" in sys.argv:sys.exit(1)\nprint(json.dumps(sys.argv[1:]))\n');fake.chmod(0o755)
        env = {**os.environ, 'PATH': str(binaries), 'LME_SHELL_DEMO': '1'}
        for key in ('LME_QS_BINARY', 'LME_SHELL_PREVIEW'): env.pop(key, None)
        result = subprocess.run(['/bin/bash', str(repo/'scripts/settings.sh'), '--page', 'elements'], env=env, capture_output=True, text=True, timeout=4)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['--no-duplicate', '-p', str(repo/'settings-demo.qml')])
        with patch('desktop_backend.shutil.which', side_effect=lambda name: str(fake) if name == 'qs' else None), patch.dict(os.environ, LME_QS_BINARY='qs'):
            self.assertEqual(backend.CommandRunner().executable('quickshell'), str(fake))


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'opt-in private Wayland personalization and Settings launch')
class NativePersonalizationCase(unittest.TestCase):
    def test_native_color_font_edit_hover_press_reduced_motion_and_bottom_bar(self):
        repo = Path(__file__).resolve().parents[1]; entry = repo/'upgrades-demo.qml'
        with tempfile.TemporaryDirectory() as config, tempfile.TemporaryFile(mode='w+') as log:
            env = {**os.environ, 'LME_TEST_UPGRADES': '1', 'XDG_CONFIG_HOME': config}
            process = subprocess.Popen(['quickshell', '-p', str(entry)], env=env, stdout=log, stderr=log)
            def ipc(method, *args):
                return subprocess.check_output(['quickshell', '-p', str(entry), 'ipc', 'call', 'upgradesFixture', method, *args], env=env, text=True, timeout=5).strip()
            def wait(predicate, method='themeState'):
                deadline = time.monotonic()+8; state = {}
                while time.monotonic()<deadline:
                    try: state=json.loads(ipc(method))
                    except (ValueError, subprocess.CalledProcessError): pass
                    if predicate(state):return state
                    time.sleep(.08)
                if os.environ.get('LME_TEST_PERSONALIZATION_SCREENSHOT'):
                    ipc('screenshot',os.environ['LME_TEST_PERSONALIZATION_SCREENSHOT']);time.sleep(.2)
                log.seek(0);raise AssertionError(str(state)+'\n'+log.read())
            def point(name):return json.loads(ipc('position', name))
            def click(name):
                point(name);time.sleep(.06)  # Commit Flickable auto-scroll/layout before hitting the item.
                p=point(name);subprocess.run([os.environ['LME_TEST_POINTER'],str(p['x']),str(p['y'])],env=env,check=True,timeout=5)
            def type_text(text):subprocess.run(['wtype','-s','150','-M','ctrl','-k','a','-m','ctrl',text,'-k','Return'],env=env,check=True,timeout=5)
            def run(key,value,**extra):ipc('run',json.dumps({'action':'setting','key':key,'value':value,**extra}))
            try:
                wait(lambda s:s.get('ready'));ipc('navigate','settings','elements');wait(lambda s:s.get('colors')==6);time.sleep(.6)
                click('elementPreviewButton')
                p=point('elementPreviewButton')
                pointer=subprocess.Popen([str(Path(os.environ['LME_TEST_POINTER']).with_name('pointer-move')),str(p['x']),str(p['y']),'8000'],env=env)
                try:
                    wait(lambda s:s['hover'] and s['scale']>1.009)
                    subprocess.run(['wtype','-P','space'],env=env,check=True)
                    wait(lambda s:s['ripple']>.1 and s['rippleOpacity']>0)
                    subprocess.run(['wtype','-p','space'],env=env,check=True);wait(lambda s:not s['feedbackRunning'] and s['rippleOpacity']==0)
                    run('animations',False);wait(lambda s:not s['animations'] and s['scale']==1)
                    pointer.terminate();pointer.wait(timeout=5)
                    run('animations',True);wait(lambda s:s['animations']);time.sleep(.2)
                    # Saving displays a status banner and moves the page content.
                    p=point('elementPreviewButton')
                    pointer=subprocess.Popen([str(Path(os.environ['LME_TEST_POINTER']).with_name('pointer-move')),str(p['x']),str(p['y']),'8000'],env=env)
                    wait(lambda s:s['hover'] and s['scale']>1.009)
                finally: pointer.terminate();pointer.wait(timeout=5)
                wait(lambda s:not s['status'])
                click('elementGroup');subprocess.run(['wtype','-s','150','-k','Home','-k','Down','-k','Down','-k','Return'],env=env,check=True)
                time.sleep(.3)  # Qt's combo popup closes before the next pointer target.
                click('element-buttonFill');type_text('#113355');wait(lambda s:s['buttonFill']=='#113355')
                click('element-buttonFill');type_text('#xyz');time.sleep(.2);self.assertEqual(json.loads(ipc('themeState'))['buttonFill'],'#113355')
                click('font-body');type_text('DejaVu Sans');wait(lambda s:s['bodyFont']=='DejaVu Sans' and s['barFont']=='DejaVu Sans')
                run('fontOverrides','Roboto',token='bar');wait(lambda s:s['barFont']=='Roboto')
                run('barEdge','bottom');run('barEdgeMargin',28);run('barSideMargin',64);run('barHeight',48)
                ipc('navigate','desktop','appearance');state=wait(lambda s:bool(s['bar']))
                self.assertEqual(state['bar']['x'],64);self.assertEqual(state['bar']['height'],48)
                self.assertEqual(state['bar']['y'],state['bar']['screenHeight']-28-48)
                for height in (36,64):
                    run('barHeight',height);state=wait(lambda s:s['bar']['height']==height)
                    self.assertGreaterEqual(state['bar']['viewportHeight'],30,'Bar modules must fit without vertical clipping')
                run('barHeight',48);wait(lambda s:s['bar']['height']==48)
                run('motionSpeed',.5);wait(lambda s:s['panel']['progress']==1)
                open_panel=json.loads(ipc('themeState'))['panel'];ipc('panel','')
                closing=wait(lambda s:s['panel']['active'] and not s['panel']['shown'])['panel']
                self.assertEqual((closing['x'],closing['y']),(open_panel['x'],open_panel['y']))
                ipc('panel','control');wait(lambda s:s['panel']['shown'] and s['panel']['progress']==1)
                ipc('panel','');wait(lambda s:not s['panel']['active'])
                ipc('panel','control');wait(lambda s:s['panel']['progress']==1)
                run('animations',False);ipc('panel','');wait(lambda s:not s['panel']['active'] and s['panel']['progress']==0)
                run('animations',True);ipc('panel','power');wait(lambda s:s['panel']['progress']==1)
                ipc('confirmPower');time.sleep(.1);p=point('Confirm shut down')
                pointer=subprocess.Popen([str(Path(os.environ['LME_TEST_POINTER']).with_name('pointer-move')),str(p['x']),str(p['y']),'3000'],env=env)
                try:
                    power=wait(lambda s:s['power'].get('hover'))['power'];time.sleep(.2)
                    color=json.loads(ipc('themeState'))['power']['color']
                    self.assertGreater(int(color[1:3],16),int(color[3:5],16),'Danger confirmation must retain its red palette while hovered')
                finally:pointer.terminate();pointer.wait(timeout=5)
                log.seek(0);text=log.read()
                for problem in ('TypeError','ReferenceError','Binding loop','Unable to assign','Failed to load configuration'):self.assertNotIn(problem,text)
            finally:
                subprocess.run(['wtype','-p','space'],env=env,check=False)
                process.terminate();process.wait(timeout=5)

    def test_real_shell_under_gpt_symlink_opens_reuses_and_reopens_settings(self):
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);config=root/'config';(config/'quickshell').mkdir(parents=True);(config/'quickshell/gpt').symlink_to(repo,target_is_directory=True)
            (config/'lme-shell').mkdir();(config/'lme-shell/settings.json').write_text(json.dumps({'weatherAutoLocation':False,'clipboardEnabled':False}))
            runtime=root/'runtime';runtime.mkdir(mode=0o700);binaries=root/'bin';binaries.mkdir()
            niri=binaries/'niri';niri.write_text('#!/usr/bin/python3\nimport sys\nprint("niri 26.04" if sys.argv[1:]==["--version"] else "[]")\n');niri.chmod(0o755)
            env={**os.environ,'XDG_CONFIG_HOME':str(config),'XDG_RUNTIME_DIR':str(runtime),'XDG_STATE_HOME':str(root/'state'),'XDG_DATA_HOME':str(root/'data'),'WAYLAND_DISPLAY':str(Path(os.environ['XDG_RUNTIME_DIR'])/os.environ['WAYLAND_DISPLAY']),'PATH':str(binaries)+os.pathsep+os.environ['PATH'],'LME_SHELL_DEMO':'0'}
            for key in ('LME_SHELL_PREVIEW','LME_SHELL_SETTINGS','LME_SHELL_ENTRY','LME_QS_BINARY'):env.pop(key,None)
            with (root/'shell.log').open('w+') as log:
                process=subprocess.Popen(['quickshell','-c','gpt'],env=env,stdout=log,stderr=log)
                def root_ipc(*args):return subprocess.run(['quickshell','-c','gpt','ipc','call','shell',*args],env=env,capture_output=True,text=True,timeout=5)
                def settings_ipc(*args):return subprocess.run(['quickshell','-p',str(repo/'settings.qml'),'ipc','call','settings',*args],env=env,capture_output=True,text=True,timeout=5)
                def windows():
                    tree=json.loads(subprocess.check_output(['swaymsg','-t','get_tree'],env=env,text=True));found=[]
                    def visit(node):
                        if node.get('name')=='LME Shell Settings':found.append(node)
                        for child in node.get('nodes',[])+node.get('floating_nodes',[]):visit(child)
                    visit(tree);return found
                def wait(predicate):
                    deadline=time.monotonic()+9
                    while time.monotonic()<deadline:
                        if predicate():return
                        time.sleep(.1)
                    log.seek(0);raise AssertionError('Settings launch did not settle\n'+log.read())
                try:
                    wait(lambda:root_ipc('toggle','settings').returncode==0)
                    wait(lambda:len(windows())==1);first=windows()[0]['pid']
                    self.assertEqual(settings_ipc('openPage','elements').returncode,0)
                    self.assertEqual(root_ipc('toggle','settings').returncode,0);time.sleep(.3)
                    self.assertEqual([w['pid'] for w in windows()],[first])
                    subprocess.run(['swaymsg','[pid='+str(first)+']','kill'],env=env,check=True,capture_output=True)
                    wait(lambda:not windows());self.assertEqual(root_ipc('toggle','settings').returncode,0);wait(lambda:len(windows())==1)
                    log.seek(0);text=log.read()
                    for problem in ('TypeError','ReferenceError','Binding loop','Unable to assign','Failed to load configuration','Settings could not be opened'):self.assertNotIn(problem,text)
                finally:
                    subprocess.run(['quickshell','-p',str(repo/'settings.qml'),'kill'],env=env,capture_output=True)
                    process.terminate();process.wait(timeout=5)
