"""Palette data, isolated Matugen options, profiles and native live theming."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unittest
from test_backend import backend, Fixture, FakeRunner
from desktop_features import PALETTE_CATALOG, PALETTE_SCHEMES, appearance_profile
from wallpaper_palette import ROLES, preview


class PaletteCase(Fixture, unittest.TestCase):
    def test_catalog_roles_are_complete_and_light_dark_text_is_readable(self):
        self.assertEqual(len(PALETTE_CATALOG), 36)
        self.assertEqual(len({p['id'] for p in PALETTE_CATALOG}), 36)
        self.assertTrue({'rose-pine','gruvbox','cat-latte','nord','palenight'} <= {p['id'] for p in PALETTE_CATALOG})
        def lum(hexcode):
            rgb = [int(hexcode[i:i+2],16)/255 for i in (1,3,5)]
            return sum(w*(c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4) for w,c in zip((.2126,.7152,.0722),rgb))
        for palette in PALETTE_CATALOG:
            colors = palette['colors']
            self.assertTrue(all(re.fullmatch(r'#[0-9a-f]{6}',v) for v in colors.values()), palette['id'])
            for surface in ('background','panel','surface'):
                x,y = sorted((lum(colors[surface]),lum(colors['text'])))
                self.assertGreaterEqual((y+.05)/(x+.05),4.5,palette['id']+': '+surface)

    def test_apply_preserves_manual_styles_and_profiles_export_restore_preset(self):
        live = self.make_backend()
        live.preferences.update({'themeOverrides':{'buttonFill':'#123456'},'barIslandStyles':{'left':{'borderWidth':0}},'fontOverrides':{'body':'Roboto'}})
        self.assertTrue(live.handle({'action':'palettePreset','id':'rose-pine'})['ok'])
        self.assertEqual(live.preferences.values['themeOverrides'], {'buttonFill':'#123456'})
        self.assertEqual(live.preferences.values['barIslandStyles']['left']['borderWidth'], 0)
        self.assertEqual(live.preferences.values['paletteSource'], 'preset')
        self.assertTrue(live.handle({'action':'appearanceSave','name':'Rose glass'})['ok'])
        live.handle({'action':'appearanceApply','name':'Dracula'})
        live.handle({'action':'appearanceApply','name':'Rose glass'})
        self.assertEqual(live.preferences.values['palettePreset'],'rose-pine')
        self.assertEqual(live.preferences.values['paletteSource'],'preset')
        for key,value in [('palettePreset','missing'),('paletteMode','auto'),('paletteScheme','unknown'),('paletteContrast',float('nan')),('paletteContrast',2)]:
            with self.assertRaises(ValueError): backend.validate_preference(key,value)

    def test_matugen_options_and_mode_match_preview_and_preserve_isolation(self):
        path=self.put('wallpaper.png','test image path')
        class Runner(FakeRunner):
            def run(self,name,*args,**kwargs):
                self.calls.append((name,*args))
                if '--version' in args: return 'matugen 4.2.0'
                config=Path(args[args.index('-c')+1])
                self.assert_config=config.read_text()
                return json.dumps({'colors':{key:{'dark':'#112233','light':'#445566'} for key in ROLES.values()}})
        runner=Runner(available={'matugen'})
        result=preview(runner,str(path),'expressive','light',.5)
        self.assertEqual(result['colors']['accent'],'#445566')
        self.assertEqual(result['paletteScheme'],'expressive')
        self.assertIn('[templates]',runner.assert_config)
        for arg in ('--dry-run','--old-json-output','scheme-expressive','light','0.5'):self.assertIn(arg,runner.calls[-1])
        live=self.make_backend();live.palette_preview=result
        self.assertFalse(live.handle({'action':'paletteApply','path':str(path)})['ok'])
        live.preferences.update({'paletteScheme':'expressive','paletteMode':'light','paletteContrast':.5})
        self.assertTrue(live.handle({'action':'paletteApply','path':str(path)})['ok'])


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'opt-in native palette UI')
class PaletteUiCase(unittest.TestCase):
    def test_preview_does_not_apply_and_dark_light_switch_keeps_override(self):
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for name in ('qml','scripts','config'):(root/name).symlink_to(repo/name,target_is_directory=True)
            entry=root/'shell.qml'
            entry.write_text('''//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/components"
import "qml/services"
import "qml/theme"
ShellRoot {
    Component.onCompleted: Quickshell.watchFiles = false
    FloatingWindow { fullscreen: true; color: Theme.background
        PalettePicker { id: picker; width: 600; anchors.centerIn: parent }
    }
    IpcHandler {
        target: "paletteTest"
        function choose(id: string): void { picker.chosenId = id; }
        function state(): string {
            const button=picker.children.find(c => c.children && c.children.some(b => b.objectName === "applyPalettePreset")).children.find(b => b.objectName === "applyPalettePreset");
            const point=button.mapToGlobal(button.width/2,button.height/2);
            return JSON.stringify({ready:ShellState.backendReady,count:Theme.paletteCatalog.length,chosen:picker.chosenId,
                applied:ShellState.preferences.palettePreset,background:Theme.background.toString(),text:Theme.text.toString(),button:Theme.buttonFill.toString(),x:Math.round(point.x),y:Math.round(point.y)});
        }
        function override(): void { ShellState.run("setting",{key:"themeOverrides",token:"buttonFill",value:"#123456"}); }
    }
}''')
            env=dict(os.environ,LME_SHELL_DEMO='1',XDG_CONFIG_HOME=str(root/'home'),XDG_STATE_HOME=str(root/'state'),XDG_DATA_HOME=str(root/'data'))
            with (root/'gui.log').open('w+') as log:
                process=subprocess.Popen(['quickshell','-p',str(entry)],env=env,stdout=log,stderr=log)
                def ipc(method,*args):return subprocess.run(['quickshell','-p',str(entry),'ipc','call','paletteTest',method,*args],env=env,capture_output=True,text=True,timeout=4).stdout.strip()
                def wait(predicate):
                    deadline=time.monotonic()+6
                    while time.monotonic()<deadline:
                        try:state=json.loads(ipc('state'))
                        except ValueError:state={}
                        if state.get('ready') and state.get('count')==36 and predicate(state):return state
                        time.sleep(.05)
                    log.seek(0);self.fail(str(state)+'\n'+log.read())
                try:
                    initial=wait(lambda s:True)
                    ipc('override');wait(lambda s:s['button']=='#123456')
                    for ident in ('rose-pine','cat-latte','gruvbox'):
                        ipc('choose',ident);state=wait(lambda s:s['chosen']==ident)
                        self.assertEqual(state['background'],initial['background'])
                        subprocess.run([os.environ['LME_TEST_POINTER'],str(state['x']),str(state['y'])],env=env,check=True,timeout=5)
                        expected=next(p['colors']for p in PALETTE_CATALOG if p['id']==ident)
                        state=wait(lambda s:s['applied']==ident and s['background']==expected['background'])
                        self.assertEqual(state['text'],expected['text']);self.assertEqual(state['button'],'#123456')
                        initial=state
                    log.seek(0);output=log.read()
                    for problem in ('TypeError','ReferenceError','Binding loop','Unable to assign','Failed to load configuration'):self.assertNotIn(problem,output)
                finally:process.terminate();process.wait(timeout=5)
