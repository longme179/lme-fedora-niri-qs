"""Glass preference boundaries, concurrent writers and opt-in compositor settings."""
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from test_backend import Fixture, backend
import liquid_glass
from liquid_glass import DEFAULTS, CONTROLS, MARKER
from settings_transfer import document, validate_document
import test_local_qml as qml_tests


def frosted_snippet(passes=3, offset='3.0'):
    return (MARKER + '// Include AFTER generic background-effect rules; later rules win.\n'
            '// With xray on, only the wallpaper is blurred; with xray off, app windows are blurred too.\n'
            'layer-rule {\n'
            '    match namespace="^lme-(bar|overlay|authentication|desktop|notifications|osd)$"\n'
            '    background-effect {\n'
            '        xray true\n'
            '    }\n'
            '}\n'
            'window-rule {\n'
            '    match app-id="^lme-shell-settings$"\n'
            '    // Keep niri\'s focus-ring backing from filling the transparent window.\n'
            '    draw-border-with-background false\n'
            '    background-effect {\n'
            '        xray true\n'
            '    }\n'
            '}\n'
            f'blur {{\n    passes {passes}\n    offset {offset}\n}}\n')


class GlassControlsCase(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        patcher = patch('liquid_glass.probe_niri_version', return_value=(26, 4))
        patcher.start(); self.addCleanup(patcher.stop)
    def test_partial_edits_reload_merge_export_and_reset_without_touching_material(self):
        self.preferences.set('accent', '#12ab34')
        other = backend.Preferences(self.preferences.path)
        self.preferences.set('liquidGlass', '#ccAABBCC', token='tint')
        other.set('liquidGlass', 1.8, token='edgeWidth')
        saved = backend.Preferences(self.preferences.path).values
        self.assertEqual(saved['liquidGlass']['tint'], '#ccaabbcc')
        self.assertEqual(saved['liquidGlass']['edgeWidth'], 1.8)
        for kind in ('preset', 'backup'):
            result = validate_document(document(saved, kind), backend.validate_preference, backend.DEFAULT_PREFERENCES)
            self.assertEqual(result['liquidGlass'], saved['liquidGlass'])
        other.set('liquidGlass', {})
        self.assertEqual(other.values['liquidGlass'], DEFAULTS)
        self.assertEqual(other.values['accent'], '#12ab34')

    def test_invalid_inputs_do_not_change_disk_or_known_good_preferences(self):
        self.preferences.set('liquidGlass', {'rim':1.8})
        original = self.preferences.path.read_bytes()
        for key, control in CONTROLS.items():
            bad = ('red', '#abcdefg', '#aabbccdde', None, True, {}) if key == 'tint' else (True, None, '1', math.nan, math.inf, 10**400, control['min']-.1, control['max']+.1)
            for value in bad:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.preferences.set('liquidGlass', value, token=key)
        for value in ({'passes':1.5}, {'unknown':1}, [], None):
            with self.subTest(value=value), self.assertRaises(ValueError): self.preferences.set('liquidGlass', value)
        self.assertEqual(self.preferences.path.read_bytes(), original)

    def test_only_explicit_apply_writes_owned_snippet_and_demo_never_writes(self):
        live = self.make_backend(); live.settings_only = True
        result = live.handle(dict(action='setting', key='liquidGlass', token='passes', value=3))
        self.assertTrue(result['ok'], result)
        path = self.preferences.path.parent/'liquid-blur.kdl'
        self.assertFalse(path.exists())
        result = live.handle(dict(action='glassBlurApply'))
        self.assertTrue(result['ok'], result)
        self.assertEqual(path.read_text(), frosted_snippet(3))
        self.assertIn('compositor-wide', result['message'])
        path.write_text('my own configuration')
        self.assertFalse(live.handle(dict(action='glassBlurApply'))['ok'])
        self.assertEqual(path.read_text(), 'my own configuration')
        path.unlink(); target = self.root/'protected'; target.write_text('keep')
        path.symlink_to(target)
        self.assertFalse(live.handle(dict(action='glassBlurApply'))['ok'])
        self.assertEqual(target.read_text(), 'keep')
        path.unlink()
        preview = self.make_backend(demo=True)
        self.assertTrue(preview.handle(dict(action='glassBlurApply'))['ok'])
        self.assertFalse(path.exists())

    def test_demo_tokens_follow_the_same_validation_without_persisting(self):
        live = self.make_backend(demo=True)
        self.assertTrue(live.handle(dict(action='setting', key='liquidGlass', token='rim', value=1.8))['ok'])
        self.assertEqual(live.preferences.values['liquidGlass']['rim'], 1.8)
        self.assertFalse(live.handle(dict(action='setting', key='liquidGlass', token='rim', value=20))['ok'])
        self.assertFalse(self.preferences.path.exists())

    def test_grain_round_trips_through_settings_save(self):
        self.assertEqual(DEFAULTS['grain'], 0.004)
        self.preferences.set('liquidGlass', 0.02, token='grain')
        saved = backend.Preferences(self.preferences.path).values
        self.assertEqual(saved['liquidGlass']['grain'], 0.02)
        for bad in (-0.1, 0.09, 'grain'):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                self.preferences.set('liquidGlass', bad, token='grain')

    def test_material_presets_write_only_existing_keys(self):
        presets = {
            'Clear': {'tint': '#f0081420', 'opacity': 0.65, 'blur': 1, 'rim': 1, 'edgeWidth': 1, 'grain': 0.004, 'passes': 2, 'offset': 3},
            'Frosted': {'tint': '#f0182436', 'opacity': 0.9, 'blur': 3, 'rim': 0.8, 'edgeWidth': 0.5, 'grain': 0.01, 'passes': 1, 'offset': 2},
            'Vivid': {'tint': '#f00a1a28', 'opacity': 0.55, 'blur': 1.5, 'rim': 1.6, 'edgeWidth': 1.5, 'grain': 0.002, 'passes': 3, 'offset': 4.5},
        }
        for name, values in presets.items():
            with self.subTest(preset=name):
                self.preferences.set('liquidGlass', dict(values))
                saved = backend.Preferences(self.preferences.path).values['liquidGlass']
                for key, expected in values.items():
                    self.assertEqual(saved[key], expected if key != 'tint' else expected.lower())
                self.assertNotIn('materialPreset', saved)


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1' and shutil.which('quickshell'), 'private glass settings controls')
class GlassControlsQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_hex_slider_picker_reset_and_smoked_restoration(self):
        result = self.run_qml('import QtTest\nimport "qml/settings"\nimport "qml/services"\nimport "qml/theme"', '''
    FloatingWindow { implicitWidth:800;implicitHeight:1000
        Flickable { id:view;anchors.fill:parent;contentHeight:page.implicitHeight;clip:true
            LiquidGlassSettings { id:page;width:parent.width }
        }
        TestCase { id:mouse;when:false }
    }
    property int phase:0
    property int ticks:0
    property var checks:({})
    Timer { interval:80;running:true;repeat:true;onTriggered: {
        if(++fixture.ticks>120) { fixture.finish({timeout:fixture.phase,checks:fixture.checks});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting || !Object.keys(Theme.glassControls).length) return;
        const hex=mouse.findChild(page,"glassTint"), apply=mouse.findChild(page,"glassTintApply");
        if(fixture.phase===0) { ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});fixture.phase++; }
        else if(fixture.phase===1 && Theme.liquidGlass) {
            fixture.checks.defaults=Theme.glass.rim===1 && Theme.glass.edgeWidth===1 && Theme.panelOpacity===.65;
            hex.text="not a color";mouse.mouseClick(apply,apply.width/2,apply.height/2);
            fixture.checks.invalid=!!mouse.findChild(page,"glassTintError").text && Theme.glass.tint==="#f0081420";
            hex.text="#bb223344";mouse.mouseClick(apply,apply.width/2,apply.height/2);fixture.phase++;
        } else if(fixture.phase===2 && Theme.glass.tint==="#bb223344") {
            fixture.checks.color=Theme.glassBase.toString()==="#bb223344" && Theme.text.toString()==="#ffffff";
            const slider=mouse.findChild(page,"glass-rim");
            view.contentY=Math.max(0,slider.mapToItem(page,0,0).y-200);fixture.phase++;
        } else if(fixture.phase===3) {
            const slider=mouse.findChild(page,"glass-rim");
            mouse.mouseClick(slider,slider.width*.8,slider.height/2);fixture.phase++;
        } else if(fixture.phase===4 && Theme.glass.rim>1.5) {
            fixture.checks.slider=true;view.contentY=0;fixture.phase++;
        } else if(fixture.phase===5) {
            const choose=mouse.findChild(page,"glassTintPicker");mouse.mouseClick(choose,choose.width/2,choose.height/2);fixture.phase++;
        } else if(fixture.phase===6) {
            const popup=mouse.findChild(page,"glassColorPicker");
            if(!popup || !popup.opened) return;
            fixture.checks.picker=popup.selectedColor.toString()==="#bb223344";
            popup.chosen("#cc445566");popup.close();fixture.phase++;
        } else if(fixture.phase===7 && Theme.glass.tint==="#cc445566") {
            view.contentY=Math.max(0,page.implicitHeight-view.height);fixture.phase++;
        } else if(fixture.phase===8) {
            if(mouse.findChild(page,"glassColorPicker").visible) return;
            const reset=mouse.findChild(page,"glassReset");mouse.mouseClick(reset,reset.width/2,reset.height/2);fixture.phase++;
        } else if(fixture.phase===9 && Theme.glass.tint==="#f0081420" && Theme.glass.rim===1) {
            fixture.checks.reset=Theme.panelOpacity===.65;
            ShellState.run("setting",{key:"surfaceStyle",value:"smoked"});fixture.phase++;
        } else if(fixture.phase===10 && !Theme.liquidGlass) {
            fixture.checks.smoked=!page.visible && Theme.panelOpacity===.9 && Theme.accent.toString()==="#9580ff";
            fixture.finish(fixture.checks);
        }
    }}
''', {'QT_QPA_PLATFORM':'wayland'})
        self.assertEqual(result, dict(defaults=True, invalid=True, color=True, slider=True, picker=True, reset=True, smoked=True))

    def test_shader_controls_change_pixels_without_dimming_foreground_text(self):
        try:
            from PIL import Image, ImageChops, ImageStat
        except ImportError:
            self.skipTest('Pillow is required for rendered pixels')
        if not shutil.which('grim'): self.skipTest('grim is required for rendered pixels')
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            image=Image.new('RGB',(320,240))
            image.putdata([((x*13)%256,(y*19)%256,((x+y)*7)%256) for y in range(240) for x in range(320)])
            image.save(folder/'source.png')
            result=self.run_qml('import Quickshell.Io\nimport "qml/components"', '''
    property int phase:0
    property int age:0
    readonly property var variants:[{}, {rim:0}, {frost:0}, {frost:4}, {bezel:20}, {rim:2}, {frost:1}, {bezel:3}, {saturation:0.2}, {opacity:.5}]
    readonly property var variant:variants[Math.min(phase,variants.length-1)]
    FloatingWindow { fullscreen:true;color:"#dddddd"
        Image { id:source;source:DIR+"/source.png";visible:false;mipmap:true }
        GlassOptics { anchors.centerIn:parent;width:320;height:240
            opacity:fixture.variant.opacity ?? 1
            src:source;sourceAvailable:1;clear:1;tintAmount:0
            topLeftRadius:36;topRightRadius:36;bottomLeftRadius:36;bottomRightRadius:36
            frost:fixture.variant.frost ?? 2.2;bezel:fixture.variant.bezel ?? 8;dispersion:.02;rim:fixture.variant.rim ?? .45;saturation:fixture.variant.saturation ?? 1
        }
        Text { anchors.centerIn:parent;text:"WHITE";font.pixelSize:28;font.bold:true;color:"white" }
    }
    Process { id:shot;onExited:code=> {
        if(code!==0) { fixture.finish({captureError:code});return; }
        fixture.age=0;
        if(++fixture.phase===fixture.variants.length) fixture.finish({captured:fixture.phase});
    }}
    Timer { interval:70;repeat:true;running:true;onTriggered: {
        if(!shot.running && ++fixture.age>=4) { shot.command=["grim",DIR+"/"+fixture.phase+".png"];shot.running=true; }
    }}
'''.replace('DIR',json.dumps(directory)), {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
            self.assertEqual(result,dict(captured=10))
            base=Image.open(folder/'0.png').convert('RGB')
            x,y=(base.width-320)//2,(base.height-240)//2
            for index in range(1,9):
                current=Image.open(folder/f'{index}.png').convert('RGB')
                diff=ImageChops.difference(base,current).crop((x,y,x+320,y+240))
                self.assertGreater(sum(ImageStat.Stat(diff).sum),1000,f'control {index} had no visible effect')
                bright=sum(min(current.getpixel((a,b)))>250 for b in range(y+90,y+150) for a in range(x+80,x+240))
                self.assertGreater(bright,300,'foreground text must remain white')
            half=Image.open(folder/'9.png').convert('RGB')
            expected=Image.blend(base,Image.new('RGB',base.size,'#dddddd'),.5)
            diff=ImageChops.difference(half,expected).crop((x,y,x+320,y+60))
            self.assertLess(max(ImageStat.Stat(diff).mean),1.5,'group opacity must respect the background during fades')
