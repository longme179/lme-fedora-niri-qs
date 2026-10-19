"""Reversible glass theming, shared backdrop lifetime and real shader rendering."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
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
            fixture.checks.neutral=Theme.text.toString()==="#ffffff" && Theme.accent.toString()==="#d7e7f5" && Theme.panelOpacity===.65 && bar.fill===Theme.barFill && bar.border.width===1;
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
        const smoked=ShellState.popupBlurEnabled && ShellState.barBlurEnabled && !ShellState.liquidBlurEnabled;
        apply("liquid",true,true);
        const liquid=!ShellState.popupBlurEnabled && ShellState.liquidBlurEnabled && ShellState.barBlurEnabled && ShellState.preferences.popupBlur===true;
        apply("smoked",true,true);
        const restored=ShellState.popupBlurEnabled && ShellState.barBlurEnabled;
        apply("liquid",false,true);
        const local=ShellState.liquidBlurEnabled && !ShellState.popupBlurEnabled && ShellState.preferences.popupBlur===false;
        apply("smoked",false,true);
        const disabled=!ShellState.popupBlurEnabled && !ShellState.liquidBlurEnabled && ShellState.preferences.popupBlur===false;
        apply("smoked",true,false);
        const unsupported=!ShellState.popupBlurEnabled && !ShellState.barBlurEnabled;
        apply("liquid",true,false);
        fixture.finish({smoked:smoked,liquid:liquid,restored:restored,local:local,disabled:disabled,
            unsupported:unsupported && !ShellState.liquidBlurEnabled});
    }}
''', {'LME_SHELL_DEMO':'0','LME_SHELL_BACKEND_DEMO':'1'})
        self.assertEqual(result, dict(smoked=True, liquid=True, restored=True, local=True, disabled=True, unsupported=True))

    def test_local_region_tracks_parent_transforms_corners_reparenting_and_visibility(self):
        result=self.run_qml('import "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    FloatingWindow { id:window;implicitWidth:700;implicitHeight:500
        Item { id:group;x:20;y:30
            Rectangle { id:panel;x:40;y:50;width:200;height:100;radius:20;topLeftRadius:0;topRightRadius:30
                transform:[Translate { id:shift;x:12;y:7 },Scale { id:stretch;xScale:1.2;yScale:.8 }]
            }
        }
        Item { id:other;x:310;y:90 }
    }
    SurfaceBlurRegion { id:region;surface:panel;popup:true }
    property int ticks:0
    property int phase:0
    property var checks:({})
    function aligned() {
        const bounds=panel.mapToItem(window.contentItem,0,0,panel.width,panel.height);
        return region.x===Math.floor(bounds.x) && region.y===Math.floor(bounds.y)
            && region.width===Math.ceil(bounds.x+bounds.width)-region.x && region.height===Math.ceil(bounds.y+bounds.height)-region.y;
    }
    Timer { interval:80;running:true;repeat:true;onTriggered: {
        if(++fixture.ticks>90) { fixture.finish({timeout:fixture.phase});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { fixture.checks.smoked=region.width===0;ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});fixture.phase++; }
        else if(fixture.phase===1 && region.active) {
            fixture.checks.initial=fixture.aligned() && region.topLeftRadius===0 && region.topRightRadius===24 && region.radius===16;
            fixture.checks.window=region.hostWindow===window && GlassState.popupsFor(window).length===1;
            group.x=95;group.y=110;shift.x=40;stretch.xScale=.8;stretch.yScale=1.1;fixture.phase++;
        } else if(fixture.phase===2) {
            fixture.checks.moved=fixture.aligned() && region.radius===16;
            group.visible=false;fixture.phase++;
        } else if(fixture.phase===3) {
            fixture.checks.hidden=!region.active && region.width===0 && GlassState.popupRegions.length===0;
            panel.parent=other;fixture.phase++;
        } else if(fixture.phase===4) {
            fixture.checks.reparented=region.active && fixture.aligned() && GlassState.popupRegions.length===1;
            other.opacity=0;fixture.phase++;
        } else if(fixture.phase===5) {
            fixture.checks.transparent=region.width===0 && GlassState.popupRegions.length===0;
            other.opacity=1;ShellState.run("setting",{key:"surfaceStyle",value:"smoked"});fixture.phase++;
        } else if(fixture.phase===6 && !Theme.liquidGlass) {
            fixture.checks.released=region.width===0 && GlassState.popupRegions.length===0;
            fixture.finish(fixture.checks);
        }
    }}
''')
        self.assertEqual(result,dict(smoked=True,initial=True,window=True,moved=True,hidden=True,reparented=True,transparent=True,released=True))


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'private Wayland glass checks')
class LiquidNativeCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_real_shell_uses_panel_masks_and_popup_regions_without_blurring_the_screen(self):
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('qml','scripts','config','assets'):
                (root/name).symlink_to(repo/name,target_is_directory=True)
            source=(repo/'shell.qml').read_text()
            # Private Sway lacks the protocol; test actual region selection independently of capability guards.
            source=source.replace('ShellState.liquidBlurEnabled','Theme.liquidGlass').replace('ShellState.popupBlurEnabled','(!Theme.liquidGlass && ShellState.preferences.popupBlur !== false)')
            source=source.replace('target: "shell"','''target: "shell"
        function fixtureState(): string {
            const region=overlay.BackgroundEffect.blurRegion;
            return JSON.stringify({ready:ShellState.backendReady,liquid:Theme.liquidGlass,
                local:region===glassPopupBlur,full:region===popupBlurRegion,visible:overlay.visible,
                scrim:liquidScrim.visible,bottom:Theme.barBottom,editing:!!(panelLoader.item && panelLoader.item.editing),
                panel:panelLoader.progress,island:activityIsland.progress,width:overlay.screen.width,height:overlay.screen.height,
                nativeWidth:overlay.width,nativeHeight:overlay.height,
                areas:glassPopupBlur.regions.map(r=>({x:r.x+overlay.viewport.x,y:r.y+overlay.viewport.y,width:r.width,height:r.height,radius:r.radius})),
                popups:GlassState.popupsFor(overlay).length,registered:GlassState.popupRegions.length});
        }
        function fixtureStyle(style:string): void { ShellState.run("setting",{key:"surfaceStyle",value:style}); }
        function fixtureBottom(): void { ShellState.run("setting",{key:"barEdge",value:"bottom"}); }
        function fixtureEditTarget(): string {
            function find(item) {if(!item) return null;if(item.objectName==="controlEdit") return item;for(const child of item.children || []) {const found=find(child);if(found) return found;}return null;}
            const button=find(panelLoader.item),point=button.mapToItem(overlay.contentItem,button.width/2,button.height/2);
            return JSON.stringify({x:point.x+overlay.viewport.x,y:point.y+overlay.viewport.y});
        }
        function fixtureMenu(open:bool): string {
            function find(item) {
                if(!item) return null;
                if(item.popup && item.textAt) return item;
                for(const child of item.children || []) { const found=find(child);if(found) return found; }
                return null;
            }
            const combo=find(panelLoader.item);
            if(!combo) return "{}";
            if(open) combo.popup.open();else combo.popup.close();
            const menu=combo.popup,point=menu.parent.mapToItem(overlay.contentItem,menu.x,menu.y);
            return JSON.stringify({x:point.x+overlay.viewport.x,y:point.y+overlay.viewport.y,width:menu.width,height:menu.height,
                dx:menu.travelX,dy:menu.travelY,viewport:overlay.viewport});
        }''',1)
            entry=root/'shell.qml';entry.write_text(source)
            env=dict(os.environ,LME_SHELL_DEMO='1',XDG_CONFIG_HOME=str(root/'home'),XDG_DATA_HOME=str(root/'data'),XDG_STATE_HOME=str(root/'state'))
            with (root/'gui.log').open('w+') as log:
                process=subprocess.Popen(['quickshell','-p',str(entry)],env=env,stdout=log,stderr=log)
                def ipc(method,*args):
                    return subprocess.check_output(['quickshell','-p',str(entry),'ipc','call','shell',method,*args],env=env,text=True,timeout=4).strip()
                def wait(predicate):
                    deadline=time.monotonic()+7
                    state={}
                    while time.monotonic()<deadline:
                        try: state=json.loads(ipc('fixtureState'))
                        except (ValueError,subprocess.CalledProcessError): pass
                        if predicate(state):return state
                        time.sleep(.04)
                    log.seek(0);self.fail(str(state)+'\n'+log.read())
                try:
                    wait(lambda s:s.get('ready'));ipc('toggle','control')
                    wait(lambda s:s.get('full') and s.get('panel')==1)
                    ipc('fixtureStyle','liquid')
                    state=wait(lambda s:s.get('local') and s['areas'][1]['width']>300)
                    panel=state['areas'][1]
                    self.assertLess(state['nativeWidth'],state['width']*.8)
                    self.assertGreater(panel['x'],state['width']*.3)
                    self.assertLess(panel['width'],state['width']*.7)
                    self.assertLessEqual(panel['height'],state['height'])
                    self.assertGreater(panel['radius'],0)
                    self.assertEqual(state['areas'][0]['width'],0)
                    self.assertTrue(state['scrim'])
                    pointer=os.environ.get('LME_TEST_POINTER')
                    if pointer and Path(pointer).is_file():
                        point=json.loads(ipc('fixtureEditTarget'))
                        for editing in (True,False):
                            subprocess.run([pointer,str(round(point['x'])),str(round(point['y']))],env=env,check=True,timeout=5)
                            wait(lambda s:s.get('editing') is editing)
                    ipc('fixtureMenu','true')
                    state=wait(lambda s:s.get('popups')==1 and len(s['areas'])==3)
                    self.assertGreater(state['areas'][2]['width'],0)
                    flight=json.loads(ipc('fixtureMenu','true'))
                    if flight['dx']<0:
                        self.assertLess(flight['x']+flight['dx']+flight['width'],0)
                        self.assertEqual(flight['viewport']['x'],0)
                    elif flight['dx']>0:
                        self.assertGreater(flight['x']+flight['dx'],state['width'])
                        self.assertEqual(flight['viewport']['x']+flight['viewport']['width'],state['width'])
                    elif flight['dy']<0:
                        self.assertLess(flight['y']+flight['dy']+flight['height'],0)
                        self.assertEqual(flight['viewport']['y'],0)
                    else:
                        self.assertGreater(flight['y']+flight['dy'],state['height'])
                        self.assertEqual(flight['viewport']['y']+flight['viewport']['height'],state['height'])
                    ipc('fixtureMenu','false');wait(lambda s:s.get('registered')==0)
                    if pointer and Path(pointer).is_file():
                        subprocess.run([pointer,'20','500'],env=env,check=True,timeout=5)
                    else: ipc('close')
                    wait(lambda s:not s.get('visible') and not s.get('scrim') and all(r['width']==0 for r in s['areas']))
                    ipc('toggle','activity')
                    state=wait(lambda s:s.get('local') and s.get('island')==1 and s['areas'][0]['width']>300)
                    self.assertEqual(state['areas'][1]['width'],0)
                    self.assertLess(state['nativeWidth'],state['width']*.7)
                    self.assertLess(state['areas'][0]['width'],state['width']*.7)
                    top=state['areas'][0]['y']
                    ipc('fixtureBottom')
                    wait(lambda s:s.get('bottom') and s['areas'][0]['y']>top+50)
                    ipc('toggle','launcher')
                    wait(lambda s:s.get('panel')==1 and s['areas'][0]['width']==0 and s['areas'][1]['width']>300)
                    ipc('fixtureStyle','smoked');wait(lambda s:s.get('full') and not s.get('local'))
                    ipc('close');wait(lambda s:not s.get('visible') and s.get('registered')==0)
                    log.seek(0);output=log.read()
                    for problem in ('TypeError','ReferenceError','Unable to assign','Binding loop','Failed to load configuration','non-NOTIFYable'):
                        self.assertNotIn(problem,output)
                finally:process.terminate();process.wait(timeout=6)

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

    def test_glass_tiles_and_tabs_stay_translucent_white_text_and_input_restore_their_colors(self):
        result = self.run_qml('import QtTest\nimport "qml/components"\nimport "qml/panels"\nimport "qml/services"\nimport "qml/theme"', '''
    FloatingWindow { implicitWidth:1000;implicitHeight:1000
        ControlCenter { id:center;anchors.fill:parent }
        LabelText { id:label;text:"White label";color:fixture.labelColor }
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
            fixture.checks.frosted=fixture.plate(wifi).color.a<=.12 && fixture.plate(power).color.a<.1
                && Theme.panelFill.a>.9 && Theme.panelFill.a*Theme.panelOpacity<.7 && Theme.cardFill.a<.1 && Theme.surface.a<.1;
            const indicator=mouse.findChild(center,"controlTabIndicator");
            fixture.checks.selection=indicator.fill.a<.3 && indicator.targetItem.palette.buttonText===Theme.text;
            const text=fixture.labels(center);
            fixture.checks.white=text.length>35 && text.every(item=>item.style===Text.Normal && item.color.toString()==="#ffffff")
                && label.color.toString()==="#ffffff" && lateLabel.item.color.toString()==="#ffffff";
            mouse.mouseClick(entry,entry.width/2,entry.height/2);
            mouse.keyClick(Qt.Key_A,Qt.ControlModifier);
            for(const key of [Qt.Key_1,Qt.Key_2,Qt.Key_3]) mouse.keyClick(key);
            fixture.checks.input=entry.text==="123" && entry.color.toString()==="#ffffff" && entry.background.color.a>.3 && entry.background.color.r<.15;
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
        self.assertEqual(result, dict(normal=True, frosted=True, selection=True, white=True, input=True, restored=True, binding=True))

    def test_white_glyphs_render_without_an_outline_and_restore_the_smoked_color(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow is required for rendered pixels')
        if not shutil.which('grim'):
            self.skipTest('grim is required for rendered pixels')
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_qml('import Quickshell.Io\nimport "qml/components"\nimport "qml/services"', '''
    FloatingWindow { color:"black";implicitWidth:900;implicitHeight:700
        LabelText { id:label;anchors.centerIn:parent;text:"Glass text 0123";color:"black";font.pixelSize:24 }
    }
    property int phase:0
    property int ticks:0
    property bool white:false
    Process { id:shot;command:["grim",SHOTS+"/liquid.png"];onExited:code=> {
        if(fixture.phase===1) { fixture.white=label.style===Text.Normal && label.color.toString()==="#ffffff";ShellState.run("setting",{key:"surfaceStyle",value:"smoked"});fixture.phase++; }
        else fixture.finish({captured:code===0,white:fixture.white,restored:label.color.toString()==="#000000"});
    }}
    Timer { interval:100;repeat:true;running:true;onTriggered: {
        if(++fixture.ticks>90) { fixture.finish({timeout:fixture.phase});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});fixture.phase++; }
        else if(fixture.phase===1 && fixture.ticks>8 && !shot.running) shot.running=true;
        else if(fixture.phase===2 && fixture.ticks>12 && !shot.running) { shot.command=["grim",SHOTS+"/smoked.png"];fixture.phase++;shot.running=true; }
    }}
'''.replace('SHOTS',json.dumps(directory)), {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
            self.assertEqual(result, dict(captured=True, white=True, restored=True))
            def bright_pixels(name):
                image=Image.open(Path(directory)/name).convert('RGB')
                x,y=image.width//2,image.height//2
                pixels=image.load()
                return sum(min(pixels[col,row])>95 for row in range(y-30,y+30) for col in range(x-150,x+150))
            self.assertGreater(bright_pixels('liquid.png'), 600, 'Liquid must render filled white glyphs')
            self.assertEqual(bright_pixels('smoked.png'), 0, 'Smoked typography must retain its previous rendering')

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
            result = self.run_qml('import Quickshell.Io\nimport QtQuick.Window\nimport "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    FloatingWindow { color:"#21c548"; implicitWidth:1000; implicitHeight:800
        // Isolate texture/refraction from whatever pointer position the preceding UI test left.
        GlassMaterial { id:glass;enabled:false;anchors.centerIn:parent;width:400;height:300;radius:50;topLeftRadius:-1;topRightRadius:-1;bottomLeftRadius:-1;bottomRightRadius:-1 }
    }
    property int ticks:0
    property int phase:0
    property bool encoded:false
    property bool cropped:false
    property int frames:0
    property int readyFrame:-1
    property int errorFrame:-1
    Connections { target:glass.Window.window; function onFrameSwapped() { fixture.frames++; } }
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
        else if(fixture.phase===1 && glass.backdrop && glass.backdrop.status===Image.Ready && fixture.ticks>12 && !shot.running) {
            if(fixture.readyFrame<0) { fixture.readyFrame=fixture.frames;glass.Window.window.update(); }
            else if(fixture.frames>fixture.readyFrame) shot.running=true;
        }
        else if(fixture.phase===2 && glass.backdrop.status===Image.Error && !shot.running) {
            // Image status changes before its new uniforms reach the native surface.
            if(fixture.errorFrame<0) { fixture.errorFrame=fixture.frames;glass.Window.window.update(); }
            else if(fixture.frames>fixture.errorFrame) { shot.command=["grim",MISSING];shot.running=true;fixture.phase++; }
        }
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
