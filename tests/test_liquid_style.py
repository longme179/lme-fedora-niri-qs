"""Reversible glass theming, shared backdrop lifetime and real shader rendering."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from test_backend import Fixture, backend
from settings_transfer import document, validate_document
import test_local_qml as qml_tests


class LiquidPreferenceCase(Fixture, unittest.TestCase):
    def test_style_is_validated_persistent_portable_and_independent_of_profiles(self):
        self.assertEqual(self.preferences.values['surfaceStyle'], 'smoked')
        for style in ('liquid', 'smoked'):
            self.preferences.set('surfaceStyle', style)
            saved = backend.Preferences(self.preferences.path).values
            self.assertEqual(saved['surfaceStyle'], style)
            for kind in ('preset', 'backup'):
                restored = validate_document(document(saved, kind), backend.validate_preference, backend.DEFAULT_PREFERENCES)
                self.assertEqual(restored['surfaceStyle'], style)
        for value in ('', 'glass', None, 1, True, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.preferences.set('surfaceStyle', value)
        live = self.make_backend()
        self.assertTrue(live.handle(dict(action='appearanceSave', name='Personal'))['ok'])
        self.preferences.set('surfaceStyle', 'liquid')
        self.assertTrue(live.handle(dict(action='appearanceApply', name='Personal'))['ok'])
        self.assertEqual(self.preferences.values['surfaceStyle'], 'liquid')


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is required')
class LiquidThemeCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_neutral_roles_bypass_saved_colors_and_restore_them_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lme-shell/settings.json'
            prefs = backend.Preferences(path)
            prefs.update(dict(accent='#12ab34', opacity=.98, paletteSource='wallpaper',
                              wallpaperPalette={'panel': '#bf1234'}, themeOverrides={'barFill': '#ff1122', 'text': '#aabbcc'},
                              fontOverrides={'body': 'DejaVu Sans'}, fontSize=17, motionPreset='jelly-v2',
                              barIslandStyles={'left': {'fillColor': '#11cc33', 'borderColor': '#dd1111', 'borderWidth': 4, 'corners': {'topLeft': 0, 'topRight': 16, 'bottomLeft': 8, 'bottomRight': 16}}},
                              barCorners={'topLeft': 0, 'topRight': 16, 'bottomLeft': 8, 'bottomRight': 16}))
            result = self.run_qml('import "qml/services"\nimport "qml/theme"\nimport "qml/bar"', '''
    FloatingWindow { implicitWidth:600; implicitHeight:300; BarSurface { id:bar; zone:"left"; width:500; height:48 } }
    property int phase:0
    property int ticks:0
    property string saved:""
    property var checks:({})
    Timer { interval:80; running:true; repeat:true; onTriggered: {
        if(++fixture.ticks>100) { fixture.finish({timeout:fixture.phase}); return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting || !Theme.catalog.colors.length) return;
        if(fixture.phase===0) {
            fixture.saved=JSON.stringify(ShellState.preferences);
            fixture.checks.before=Theme.accent.toString()==="#12ab34" && Theme.panel.toString()==="#bf1234" && bar.fill.toString()==="#11cc33";
            fixture.checks.collapsed=Theme.barCornerRadius("topLeft",-16,"left")===0 && Theme.barCornerRadius("topRight",0,"left")===0;
            ShellState.run("setting",{key:"surfaceStyle",value:"liquid"}); fixture.phase++;
        } else if(fixture.phase===1 && Theme.liquidGlass) {
            fixture.checks.neutral=Theme.text.toString()==="#000000" && Theme.accent.toString()==="#d7e7f5" && Theme.panelOpacity===.55 && bar.fill===Theme.barFill && bar.border.width===1;
            fixture.checks.allRoles=Theme.catalog.colors.every(group=>group.tokens.every(key=>!!Theme.glassColors[key]));
            fixture.checks.kept=Theme.fontFamily==="DejaVu Sans" && Theme.bodySize===17 && Theme.motionPreset==="jelly-v2" && bar.topLeftRadius===0 && bar.topRightRadius===16;
            ShellState.run("setting",{key:"surfaceStyle",value:"smoked"}); fixture.phase++;
        } else if(fixture.phase===2 && !Theme.liquidGlass) {
            fixture.checks.restored=JSON.stringify(ShellState.preferences)===fixture.saved && Theme.text.toString()==="#aabbcc" && Theme.accent.toString()==="#12ab34" && Theme.panelOpacity===.98 && bar.fill.toString()==="#11cc33" && bar.border.width===4;
            fixture.checks.noGpu=GlassState.backdrops.length===0;
            fixture.finish(fixture.checks);
        }
    }}
''', {'XDG_CONFIG_HOME': directory})
            self.assertEqual(result, dict(before=True, collapsed=True, neutral=True, allRoles=True, kept=True, restored=True, noGpu=True))
            self.assertEqual(backend.Preferences(path).values, prefs.values)

    def test_liquid_pauses_only_global_blur_and_preserves_the_saved_preference(self):
        result = self.run_qml('import "qml/services"', '''
    Timer { interval:80;running:true;repeat:true;onTriggered: {
        if(!ShellState.backendReady) return;
        const saved=Object.assign({},ShellState.preferences,{surfaceStyle:"smoked",popupBlur:true,barBlur:true});
        function apply(style,popup,supported) {
            ShellState.snapshot=Object.assign({},ShellState.snapshot,{
                platform:{popupBlurSupported:supported},
                preferences:Object.assign({},saved,{surfaceStyle:style,popupBlur:popup})
            });
        }
        apply("smoked",true,true);
        const smoked=ShellState.popupBlurEnabled && ShellState.barBlurEnabled;
        apply("liquid",true,true);
        const liquid=!ShellState.popupBlurEnabled && ShellState.barBlurEnabled && ShellState.preferences.popupBlur===true;
        apply("smoked",true,true);
        const restored=ShellState.popupBlurEnabled && ShellState.barBlurEnabled;
        apply("liquid",false,true);apply("smoked",false,true);
        const disabled=!ShellState.popupBlurEnabled && ShellState.preferences.popupBlur===false;
        apply("smoked",true,false);
        fixture.finish({smoked:smoked,liquid:liquid,restored:restored,disabled:disabled,
            unsupported:!ShellState.popupBlurEnabled && !ShellState.barBlurEnabled});
    }}
''', {'LME_SHELL_DEMO':'0','LME_SHELL_BACKEND_DEMO':'1'})
        self.assertEqual(result, dict(smoked=True, liquid=True, restored=True, disabled=True, unsupported=True))


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'private Wayland glass checks')
class LiquidNativeCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_separate_windows_do_not_share_textures_and_destroyed_windows_release_them(self):
        result = self.run_qml('import "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    FloatingWindow { implicitWidth:600;implicitHeight:400; GlassPanel { anchors.fill:parent } }
    Loader { id:other;active:false;sourceComponent:Component {
        FloatingWindow { implicitWidth:500;implicitHeight:300; GlassPanel { anchors.fill:parent } }
    }}
    property int phase:0
    property int ticks:0
    property var checks:({})
    Timer { interval:80;running:true;repeat:true;onTriggered: {
        if(++fixture.ticks>100) { fixture.finish({timeout:fixture.phase,count:GlassState.backdrops.length}); return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});fixture.phase++; }
        else if(fixture.phase===1 && GlassState.backdrops.length===1) { other.active=true;fixture.phase++; }
        else if(fixture.phase===2 && GlassState.backdrops.length===2) {
            fixture.checks.separate=GlassState.backdrops[0].hostWindow!==GlassState.backdrops[1].hostWindow;
            other.active=false;fixture.phase++;
        } else if(fixture.phase===3 && GlassState.backdrops.length===1) {
            fixture.checks.destroyed=true;
            ShellState.run("setting",{key:"surfaceStyle",value:"smoked"});fixture.phase++;
        } else if(fixture.phase===4 && GlassState.backdrops.length===0) fixture.finish(fixture.checks);
    }}
''', {'QT_QPA_PLATFORM': 'wayland', 'QT_QUICK_BACKEND': 'rhi', 'QSG_RHI_BACKEND': 'opengl'})
        self.assertEqual(result, dict(separate=True, destroyed=True))

    def test_settings_switch_and_software_fallback_keep_controls_interactive(self):
        result = self.run_qml('import QtTest\nimport "qml/settings"\nimport "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    FloatingWindow { implicitWidth:900; implicitHeight:1000
        Flickable { anchors.fill:parent; contentHeight:page.implicitHeight
            AppearancePage { id:page; width:parent.width }
        }
        TestCase { id:mouse; when:false }
    }
    property int phase:0
    property int ticks:0
    property var checks:({})
    function blurPreference(item) {
        if(item.preference==="popupBlur") return item;
        for(const child of item.children || []) { const found=blurPreference(child);if(found) return found; }
        return null;
    }
    Timer { interval:100; running:true; repeat:true; onTriggered: {
        if(++fixture.ticks>100) { fixture.finish({timeout:fixture.phase}); return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        const toggle=mouse.findChild(page,"surfaceStyle");
        if(fixture.phase===0) { mouse.mouseClick(toggle,26,20); fixture.phase++; }
        else if(fixture.phase===1 && Theme.liquidGlass) {
            const material=mouse.findChild(page,"glassMaterial");
            fixture.checks.fallback=material.software && material.active && GlassState.backdrops.length===0;
            fixture.checks.enabled=toggle.enabled;
            fixture.checks.paused=!fixture.blurPreference(page).enabled && ShellState.preferences.popupBlur===true;
            mouse.mouseClick(toggle,26,20); fixture.phase++;
        } else if(fixture.phase===2 && !Theme.liquidGlass) {
            fixture.checks.restored=GlassState.backdrops.length===0 && fixture.blurPreference(page).enabled && ShellState.preferences.popupBlur===true; fixture.finish(fixture.checks);
        }
    }}
''', {'QT_QPA_PLATFORM': 'wayland'})
        self.assertEqual(result, dict(fallback=True, enabled=True, paused=True, restored=True))

    def test_glass_tiles_and_tabs_stay_clear_black_text_and_input_restore_their_colors(self):
        result = self.run_qml('import QtTest\nimport "qml/components"\nimport "qml/panels"\nimport "qml/services"\nimport "qml/theme"', '''
    FloatingWindow { implicitWidth:1000;implicitHeight:1000
        ControlCenter { id:center;anchors.fill:parent }
        LabelText { id:label;text:"Black label";color:fixture.labelColor }
        Loader { id:lateLabel;active:Theme.liquidGlass;sourceComponent:ShellText { text:"Late label";color:"red" } }
        ExpressiveField { id:entry;width:250;y:60;text:"Editable input" }
        TestCase { id:mouse;when:false }
    }
    property int phase:0
    property int ticks:0
    property int age:0
    property color labelColor:"#446688"
    property var checks:({})
    function labels(item) {
        const result=[];
        if(item.styleColor!==undefined && item.style!==undefined && item.text!==undefined) result.push(item);
        for(const child of item.children || []) result.push(...labels(child));
        return result;
    }
    function plate(item) {
        if(item.plate) return item.plate;
        for(const child of item.children || []) { const found=plate(child);if(found) return found; }
        return null;
    }
    Timer { interval:100;running:true;repeat:true;onTriggered: {
        if(++fixture.ticks>90) { fixture.finish({timeout:fixture.phase});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { fixture.checks.normal=label.style===Text.Normal && label.color.toString()==="#446688";ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});fixture.phase++; }
        else if(fixture.phase===1 && Theme.liquidGlass) {
            if(++fixture.age<5) return;
            const wifi=mouse.findChild(center,"controlTile-wifi"),power=mouse.findChild(center,"controlTile-power");
            if(!wifi || !power || !fixture.plate(wifi) || !fixture.plate(power)) return;
            fixture.checks.clear=fixture.plate(wifi).color.a<=.12 && fixture.plate(power).color.a<.04
                && Theme.panelFill.a<.04 && Theme.cardFill.a<.04 && Theme.surface.a<.04;
            const indicator=mouse.findChild(center,"controlTabIndicator");
            fixture.checks.selection=indicator.fill.a<.2 && indicator.targetItem.palette.buttonText===Theme.text;
            const text=fixture.labels(center);
            fixture.checks.black=text.length>35 && text.every(item=>item.style===Text.Normal && item.color.toString()==="#000000")
                && label.color.toString()==="#000000" && lateLabel.item.color.toString()==="#000000";
            mouse.mouseClick(entry,entry.width/2,entry.height/2);
            mouse.keyClick(Qt.Key_A,Qt.ControlModifier);
            for(const key of [Qt.Key_1,Qt.Key_2,Qt.Key_3]) mouse.keyClick(key);
            fixture.checks.input=entry.text==="123" && entry.color.toString()==="#000000" && entry.background.color.a>.6 && entry.background.color.r>.9;
            ShellState.run("setting",{key:"surfaceStyle",value:"smoked"});fixture.phase++;
        } else if(fixture.phase===2 && !Theme.liquidGlass) {
            fixture.checks.restored=label.style===Text.Normal && label.color.toString()==="#446688" && fixture.labels(center).every(item=>item.style===Text.Normal);
            fixture.labelColor="#668844";fixture.phase++;
        } else if(fixture.phase===3) {
            fixture.checks.binding=label.color.toString()==="#668844";
            fixture.finish(fixture.checks);
        }
    }}
''', {'QT_QPA_PLATFORM': 'wayland'})
        self.assertEqual(result, dict(normal=True, clear=True, selection=True, black=True, input=True, restored=True, binding=True))

    def test_black_glyphs_render_without_an_outline_and_restore_the_smoked_color(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow is required for rendered pixels')
        if not shutil.which('grim'):
            self.skipTest('grim is required for rendered pixels')
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_qml('import Quickshell.Io\nimport "qml/components"\nimport "qml/services"', '''
    FloatingWindow { color:"white";implicitWidth:900;implicitHeight:700
        LabelText { id:label;anchors.centerIn:parent;text:"Glass text 0123";color:"white";font.pixelSize:24 }
    }
    property int phase:0
    property int ticks:0
    property bool black:false
    Process { id:shot;command:["grim",SHOTS+"/liquid.png"];onExited:code=> {
        if(fixture.phase===1) { fixture.black=label.style===Text.Normal && label.color.toString()==="#000000";ShellState.run("setting",{key:"surfaceStyle",value:"smoked"});fixture.phase++; }
        else fixture.finish({captured:code===0,black:fixture.black,restored:label.color.toString()==="#ffffff"});
    }}
    Timer { interval:100;repeat:true;running:true;onTriggered: {
        if(++fixture.ticks>90) { fixture.finish({timeout:fixture.phase});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});fixture.phase++; }
        else if(fixture.phase===1 && fixture.ticks>8 && !shot.running) shot.running=true;
        else if(fixture.phase===2 && fixture.ticks>12 && !shot.running) { shot.command=["grim",SHOTS+"/smoked.png"];fixture.phase++;shot.running=true; }
    }}
'''.replace('SHOTS',json.dumps(directory)), {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
            self.assertEqual(result, dict(captured=True, black=True, restored=True))
            def dark_pixels(name):
                image=Image.open(Path(directory)/name).convert('RGB')
                x,y=image.width//2,image.height//2
                pixels=image.load()
                return sum(max(pixels[col,row])<160 for row in range(y-30,y+30) for col in range(x-150,x+150))
            self.assertGreater(dark_pixels('liquid.png'), 600, 'Liquid must render filled black glyphs')
            self.assertEqual(dark_pixels('smoked.png'), 0, 'Smoked typography must retain its previous rendering')

    def test_shared_texture_resize_motion_reversal_hidden_and_repeated_teardown(self):
        result = self.run_qml('import QtTest\nimport "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    FloatingWindow { implicitWidth:900; implicitHeight:800
        SlideLoader { id:slide; x:100; y:100; width:600; height:500; shown:false; exitToEdge:true; exitEdge:"top"
            content:GlassPanel { GlassPanel { x:25;y:25;width:180;height:120 } LiquidButton { objectName:"glassAction";x:250;y:100;text:"Still clickable";onClicked:fixture.presses++ } }
        }
        TestCase { id:mouse;when:false }
    }
    property int phase:0
    property int ticks:0
    property int age:0
    property int cycles:0
    property int presses:0
    property var shared:null
    property real initialY:0
    property var checks:({})
    function set(key,value) { ShellState.run("setting",{key:key,value:value}); }
    Timer { interval:30; running:true; repeat:true; onTriggered: {
        if(++fixture.ticks>400) { fixture.finish({timeout:fixture.phase,checks:fixture.checks}); return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { fixture.set("motionPreset","jelly-v2"); fixture.phase++; }
        else if(fixture.phase===1) { fixture.set("surfaceStyle","liquid"); fixture.phase++; }
        else if(fixture.phase===2 && Theme.liquidGlass) { slide.shown=true; fixture.phase++; }
        else if(fixture.phase===3 && GlassState.backdrops.length && ++fixture.age>5) {
            fixture.shared=GlassState.backdrops[0]; fixture.initialY=mouse.findChild(slide.item,"glassMaterial").sampleRect.y;
            fixture.checks.shared=fixture.shared.consumers===3 && fixture.shared.status===Image.Ready;
            fixture.checks.bounded=fixture.shared.sourceSize.width<=1280 && fixture.shared.sourceSize.height<=720;
            slide.shown=false; fixture.age=0; fixture.phase++;
        } else if(fixture.phase===4 && ++fixture.age>2) {
            slide.shown=true; slide.width=650;
            fixture.checks.retained=GlassState.backdrops[0]===fixture.shared && slide.mounted;
            fixture.age=0; fixture.phase++;
        } else if(fixture.phase===5 && slide.progress===1 && !slide.transitioning) {
            fixture.checks.settled=slide.offsetY===0 && slide.layer.effect!==null && !slide.layer.enabled;
            const button=mouse.findChild(slide.item,"glassAction");
            mouse.mouseClick(button,button.width/2,button.height/2);
            fixture.checks.input=fixture.presses===1;
            fixture.checks.mapped=mouse.findChild(slide.item,"glassMaterial").sampleRect.y!==fixture.initialY;
            slide.visible=false; fixture.phase++;
        } else if(fixture.phase===6 && GlassState.backdrops.length===0) {
            fixture.checks.hidden=true; slide.visible=true; fixture.phase++;
        } else if(fixture.phase===7 && GlassState.backdrops.length===1) {
            fixture.set("surfaceStyle","smoked"); fixture.phase++;
        } else if(fixture.phase===8 && !Theme.liquidGlass && GlassState.backdrops.length===0) {
            if(++fixture.cycles<10) { fixture.set("surfaceStyle","liquid"); fixture.phase=7; }
            else { fixture.checks.repeated=true; slide.shown=false; fixture.phase++; }
        } else if(fixture.phase===9 && !slide.mounted) fixture.finish(fixture.checks);
    }}
''', {'QT_QPA_PLATFORM': 'wayland', 'QT_QUICK_BACKEND': 'rhi', 'QSG_RHI_BACKEND': 'opengl'})
        self.assertEqual(result, dict(shared=True, bounded=True, retained=True, settled=True, input=True, mapped=True, hidden=True, repeated=True))

    def test_gl_shader_has_transparent_center_visible_rim_and_safe_missing_source(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow is required for rendered pixels')
        if not shutil.which('grim'):
            self.skipTest('grim is required for rendered pixels')
        with tempfile.TemporaryDirectory() as directory:
            wallpaper = Path(directory)/'glass wallpaper #1.png'
            Image.new('RGB', (400, 800), (220, 45, 150)).save(wallpaper)
            config = Path(directory)/'config'
            backend.Preferences(config/'lme-shell/settings.json').set('wallpaper', str(wallpaper))
            result = self.run_qml('import Quickshell.Io\nimport "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    FloatingWindow { color:"#21c548"; implicitWidth:1000; implicitHeight:800
        GlassMaterial { id:glass;anchors.centerIn:parent;width:400;height:300;radius:50;topLeftRadius:-1;topRightRadius:-1;bottomLeftRadius:-1;bottomRightRadius:-1 }
    }
    property int ticks:0
    property int phase:0
    property bool encoded:false
    property bool cropped:false
    Process { id:shot; command:["grim",SHOT]; onExited:code=> {
        if(fixture.phase===1) {
            fixture.encoded=decodeURIComponent(String(glass.backdrop.source)).endsWith("glass wallpaper #1.png");
            fixture.cropped=glass.backdrop.cropRect.height<.5 && glass.backdrop.cropRect.width===1;
            glass.backdrop.source="file:///missing/glass%20wallpaper%20%231.png"; fixture.phase++;
        } else fixture.finish({captured:code===0,ready:!glass.software,missing:glass.backdrop.status===Image.Error,encoded:fixture.encoded,cropped:fixture.cropped});
    }}
    Timer { interval:100;running:true;repeat:true;onTriggered: {
        if(++fixture.ticks>110) { fixture.finish({timeout:fixture.phase}); return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { ShellState.run("setting",{key:"surfaceStyle",value:"liquid"}); fixture.phase++; }
        else if(fixture.phase===1 && glass.backdrop && glass.backdrop.status===Image.Ready && fixture.ticks>12 && !shot.running) shot.running=true;
        else if(fixture.phase===2 && glass.backdrop.status===Image.Error && !shot.running) { shot.command=["grim",MISSING]; shot.running=true; fixture.phase++; }
    }}
'''.replace('SHOT', json.dumps(str(Path(directory)/'glass.png'))).replace('MISSING', json.dumps(str(Path(directory)/'missing.png'))),
                                  {'QT_QPA_PLATFORM': 'wayland', 'QT_QUICK_BACKEND': 'rhi', 'QSG_RHI_BACKEND': 'opengl', 'XDG_CONFIG_HOME': str(config)})
            self.assertEqual(result, dict(captured=True, ready=True, missing=True, encoded=True, cropped=True))
            rims = []
            for name in ('glass.png', 'missing.png'):
                image = Image.open(Path(directory)/name).convert('RGB')
                cx, cy = image.width//2, image.height//2
                center = image.getpixel((cx, cy))
                self.assertGreater(center[1], 170, 'The shader must preserve the app behind its center')
                self.assertLess(center[0], 65)
                self.assertEqual(image.getpixel((cx-196,cy-146)), (33,197,72), 'Rounded corners must leave the backdrop untouched')
                # Find a highlight along the rounded material's left edge.
                edge = [image.getpixel((cx-200+x,cy)) for x in range(5)]
                self.assertGreater(max(c[0] for c in edge), center[0]+8, 'The renderer must draw a visible rim')
                rims.append(edge)
            self.assertNotEqual(rims[0], rims[1], 'The loaded texture must affect refraction, not just allocate an image')
