"""Velocity deformation, interrupted motion and transient GPU-layer lifecycle."""
import os
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from test_backend import Fixture, backend
from settings_transfer import document, validate_document
import test_local_qml as qml_tests


class JellyPreferencesCase(Fixture, unittest.TestCase):
    def test_new_preset_is_validated_saved_portable_and_in_appearance_profiles(self):
        self.preferences.set('motionPreset','jelly-v2')
        self.assertEqual(backend.Preferences(self.preferences.path).values['motionPreset'],'jelly-v2')
        restored=validate_document(document(self.preferences.values,'preset'),backend.validate_preference,backend.DEFAULT_PREFERENCES)
        self.assertEqual(restored['motionPreset'],'jelly-v2')
        live=self.make_backend()
        self.assertTrue(live.handle(dict(action='appearanceSave',name='Elastic'))['ok'])
        self.preferences.set('motionPreset','smooth')
        self.assertTrue(live.handle(dict(action='appearanceApply',name='Elastic'))['ok'])
        self.assertEqual(self.preferences.values['motionPreset'],'jelly-v2')
        with self.assertRaises(ValueError): self.preferences.set('motionPreset','jelly-v3')


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is required')
class JellyGeometryCase(unittest.TestCase):
    run_qml=qml_tests.LocalQmlCase.run_qml

    def test_scan_conversion_keeps_concave_cutouts_and_clips_offscreen_edges(self):
        result=self.run_qml('import "qml/components/JellyGeometry.js" as Jelly', '''
    Timer { interval:1;running:true;onTriggered: {
        const polygon=[{x:0,y:0},{x:20,y:0},{x:20,y:20},{x:40,y:20},{x:40,y:0},{x:60,y:0},{x:60,y:40},{x:0,y:40}];
        const bands=Jelly.strips(polygon,60,40);
        function contains(x,y) { return bands.some(b=>x>=b.x && x<b.x+b.width && y>=b.y && y<b.y+b.height); }
        const clipped=Jelly.strips(polygon.map(p=>({x:p.x-10,y:p.y-10})),30,20);
        const outside=Jelly.strips(polygon.map(p=>({x:p.x-100,y:p.y+100})),60,40);
        let identity=true;
        for(const p of [{x:0,y:0},{x:400,y:300},{x:131,y:57}]) for(const horizontal of [true,false]) {
            const q=Jelly.warp(p,400,300,0,horizontal,false);
            identity=identity && Math.abs(q.x-p.x)<.00001 && Math.abs(q.y-p.y)<.00001;
        }
        fixture.finish({cutout:!contains(30,10),filled:contains(10,10) && contains(50,10) && contains(30,30),
            clipped:clipped.length>0 && clipped.every(b=>b.x>=0 && b.y>=0 && b.x+b.width<=30 && b.y+b.height<=20),
            outside:outside.length===0,empty:Jelly.strips([],60,40).length===0,identity:identity});
    }}
''')
        self.assertEqual(result,{key:True for key in ('cutout','filled','clipped','outside','empty','identity')})


@unittest.skipUnless(os.environ.get('LME_TEST_MOTION_UI')=='1','private Wayland motion checks')
class JellyQmlCase(unittest.TestCase):
    run_qml=qml_tests.LocalQmlCase.run_qml

    def test_shader_renders_a_bowed_silhouette_and_fits_tight_native_bounds(self):
        try: from PIL import Image
        except ImportError: self.skipTest('Pillow is required to inspect rendered pixels')
        if not shutil.which('grim'): self.skipTest('grim is required for native renderer pixels')
        with tempfile.TemporaryDirectory() as directory:
            result=self.run_qml('import Quickshell.Io\nimport "qml/components"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property int age: 0
    property int shotIndex: 0
    function effect(item) { if(item.objectName==="popupElasticity") return item; for(const child of item.children || []) { const found=effect(child); if(found) return found; } return null; }
    FloatingWindow { implicitWidth: 1000; implicitHeight: 700; color: "#101010"
        SlideLoader { id: panel; x: 400; y: 240; width: 300; height: 200; shown: false; exitToEdge: true; exitEdge: "left"
            content: Rectangle { color: "#fe2105"; radius: 32 } }
    }
    Process { id: shot
        command: ["grim", "SHOTS" + "/" + fixture.shotIndex + ".png"]
        onExited: code => {
            if(code!==0) { fixture.finish({captureFailed:code}); return; }
            const fluid=fixture.effect(panel);
            fixture.shotIndex++; fixture.age=0;
            if(fixture.shotIndex===1) fluid.bounded=true;
            else if(fixture.shotIndex===2) fluid.velocity=0;
            else if(fixture.shotIndex===3) { fluid.horizontal=false; fluid.bounded=false; fluid.velocity=-6000; }
            else if(fixture.shotIndex===4) fluid.bounded=true;
            else if(fixture.shotIndex===5) fluid.velocity=0;
            else fixture.finish({software:fluid.software,released:!panel.layer.enabled && !fluid.rendering});
        }
    }
    Timer { interval: 30; running: true; repeat: true; onTriggered: {
        const fluid=fixture.effect(panel);
        if(++fixture.ticks>350) { fixture.finish({timeout:fixture.phase}); return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { ShellState.run("setting",{key:"motionPreset",value:"jelly-v2"}); fixture.phase++; }
        else if(fixture.phase===1 && ShellState.preferences.motionPreset==="jelly-v2") { panel.shown=true; fixture.phase++; }
        else if(fixture.phase===2 && panel.progress===1 && !fluid.rendering) { fluid.velocity=6000; fixture.phase++; }
        else if(fixture.phase===3 && !shot.running && ++fixture.age>25 && (fixture.shotIndex%3<2 || !fluid.rendering)) shot.running=true;
    } }
'''.replace('"SHOTS"',json.dumps(directory)), {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'','QSG_RHI_BACKEND':'opengl','LIBGL_ALWAYS_SOFTWARE':'1'})
            self.assertEqual(result,dict(software=False,released=True))
            def silhouette(index):
                image=Image.open(Path(directory)/f'{index}.png').convert('RGB')
                pixels=image.load()
                points=[(x,y) for y in range(image.height) for x in range(image.width) if pixels[x,y][0]>200 and pixels[x,y][1]<90 and pixels[x,y][2]<90]
                self.assertGreater(len(points),20000,'The shader must draw the panel, not just allocate a layer')
                box=(min(x for x,y in points),min(y for x,y in points),max(x for x,y in points)+1,max(y for x,y in points)+1)
                rows={y:min(x for x,cy in points if cy==y) for y in [int(box[1]+(box[3]-box[1])*q) for q in (.25,.5)]}
                return box,rows
            warped,rows=silhouette(0); bounded,_=silhouette(1); rest,_=silhouette(2)
            self.assertGreater(warped[2]-warped[0],1.05*(rest[2]-rest[0]))
            self.assertGreaterEqual(abs(list(rows.values())[0]-list(rows.values())[1]),2,'The edge must bend rather than only scale')
            self.assertGreaterEqual(bounded[0],rest[0]); self.assertGreaterEqual(bounded[1],rest[1])
            self.assertLessEqual(bounded[2],rest[2]); self.assertLessEqual(bounded[3],rest[3])
            vertical,_=silhouette(3); bounded,_=silhouette(4)
            self.assertGreater(vertical[3]-vertical[1],1.05*(rest[3]-rest[1]))
            self.assertGreaterEqual(bounded[0],rest[0]); self.assertGreaterEqual(bounded[1],rest[1])
            self.assertLessEqual(bounded[2],rest[2]); self.assertLessEqual(bounded[3],rest[3])

    def test_native_blur_mask_matches_warped_shader_pixels_and_releases_bands(self):
        try: from PIL import Image, ImageChops, ImageDraw, ImageFilter
        except ImportError: self.skipTest('Pillow is required to inspect rendered pixels')
        if not shutil.which('grim'): self.skipTest('grim is required for native renderer pixels')
        with tempfile.TemporaryDirectory() as directory:
            result=self.run_qml('import Quickshell.Io\nimport "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    property int phase:0
    property int ticks:0
    property int age:0
    property int index:0
    property var masks:[]
    function effect() { for(const child of panel.children) if(child.objectName==="popupElasticity") return child;return null; }
    FloatingWindow { id:window;fullscreen:true;color:"#101010"
        SlideLoader { id:panel;x:600;y:300;width:400;height:300;shown:false;exitToEdge:true;exitEdge:"left"
            content:Rectangle { color:"#fe2105";radius:32;topLeftRadius:0;bottomRightRadius:60 }
        }
    }
    SurfaceBlurRegion { id:region;surface:panel.item as Item;popup:true }
    Process { id:shot;command:["grim","SHOTS"+"/"+fixture.index+".png"]
        onExited:code=> {
            if(code!==0) { fixture.finish({captureFailed:code});return; }
            fixture.masks.push(region.regions.map(r=>({x:r.x,y:r.y,width:r.width,height:r.height})));
            fixture.index++;fixture.age=0;
            const fluid=fixture.effect();
            if(fixture.index===1) fluid.velocity=-9000;
            else if(fixture.index===2) { fluid.horizontal=false;fluid.velocity=9000; }
            else if(fixture.index===3) { fluid.velocity=-9000;fluid.bounded=true; }
            else { fluid.velocity=0;fixture.phase=4; }
        }
    }
    Timer { interval:30;running:true;repeat:true;onTriggered: {
        if(++fixture.ticks>300) { fixture.finish({timeout:fixture.phase});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) {
            ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});
            ShellState.run("setting",{key:"motionPreset",value:"jelly-v2"});fixture.phase++;
        } else if(fixture.phase===1 && Theme.liquidGlass && Theme.motionPreset==="jelly-v2") {panel.shown=true;fixture.phase++;}
        else if(fixture.phase===2 && panel.progress===1 && !fixture.effect().rendering) {fixture.effect().velocity=9000;fixture.phase++;}
        else if(fixture.phase===3 && !shot.running && ++fixture.age>25) shot.running=true;
        else if(fixture.phase===4 && !fixture.effect().rendering) {
            const released=region.regions.length===0 && region.width===400 && region.active;
            panel.shown=false;fixture.phase++;fixture.masks.push({released:released});
        } else if(fixture.phase===5 && !panel.mounted && !region.active) {
            fixture.finish({masks:fixture.masks,hidden:{active:region.active,bands:region.regions.length,count:region.bands.count,strips:region.strips.length,warps:region.warps.length,popups:GlassState.popupsFor(window).length}});
        }
    }}
'''.replace('"SHOTS"',json.dumps(directory)), {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl','LIBGL_ALWAYS_SOFTWARE':'1'})
            self.assertEqual(result['hidden'],dict(active=False,bands=0,count=0,strips=0,warps=0,popups=0))
            self.assertTrue(result['masks'].pop()['released'])
            for index,bands in enumerate(result['masks']):
                with self.subTest(index=index):
                    self.assertGreater(len(bands),80)
                    image=Image.open(Path(directory)/f'{index}.png').convert('RGB')
                    red=image.getchannel('R').point(lambda v:255 if v>200 else 0)
                    green=image.getchannel('G').point(lambda v:255 if v<90 else 0)
                    silhouette=ImageChops.multiply(red,green)
                    mask=Image.new('L',image.size);draw=ImageDraw.Draw(mask)
                    for b in bands:draw.rectangle((b['x'],b['y'],b['x']+b['width']-1,b['y']+b['height']-1),fill=255)
                    area=sum(silhouette.histogram()[1:])
                    self.assertGreater(area,70000)
                    overlap=sum(ImageChops.multiply(mask,silhouette).histogram()[1:])
                    self.assertGreater(overlap/area,.97,'Blur should fill the deformed plate')
                    outside=sum(ImageChops.subtract(mask,silhouette.filter(ImageFilter.MaxFilter(5))).histogram()[1:])
                    self.assertLess(outside/area,.0005,'Blur must not protrude outside the jelly silhouette')

    def test_software_and_rhi_surface_deform_settle_reverse_and_release_layers(self):
        for renderer in ('software','opengl'):
            with self.subTest(renderer=renderer):
                result=self.run_qml('import "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    property int phase: 0
    property int ticks: 0
    property real peak: 0
    property bool layered: false
    property bool masked: false
    property bool finite: true
    property var checks: ({})
    function effect(item) { if(item.objectName==="popupElasticity") return item; for(const child of item.children || []) { const found=effect(child); if(found) return found; } return null; }
    function setting(key,value) { ShellState.run("setting",{key,value}); }
    FloatingWindow { implicitWidth: 1100; implicitHeight: 800; color: "#22212c"
        Item { id: viewport; width: 1000; height: 700
            SlideLoader { id: panel; x: 300; y: 180; width: 300; height: 260; shown: false; exitToEdge: true; exitEdge: "left"
                content: GlassPanel { LabelText { anchors.centerIn: parent; text: "Elastic surface" } } }
            MotionPopup { id: menu; x: 500; y: 200; width: 240; height: 180; background: GlassPanel {} contentItem: LabelText { text: "Menu" } }
        }
    }
    SurfaceBlurRegion { id:blur;surface:panel.item as Item }
    FrameAnimation { running: true; onTriggered: {
        const fluid=fixture.effect(panel);
        fixture.peak=Math.max(fixture.peak,Math.abs(fluid.strain));
        fixture.layered=fixture.layered || panel.layer.enabled;
        fixture.masked=fixture.masked || blur.regions.length>0;
        fixture.finite=fixture.finite && [fluid.strain,panel.width,panel.height,panel.offsetX,panel.offsetY].every(Number.isFinite) && Math.abs(fluid.strain)<=.42;
    } }
    Timer { interval: 35; running: true; repeat: true; onTriggered: {
        const fluid=fixture.effect(panel);
        if(++fixture.ticks>340) { fixture.finish({timeout:fixture.phase,peak:fixture.peak,progress:panel.progress,rendering:fluid.rendering}); return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { fixture.setting("surfaceStyle","liquid"); fixture.setting("motionPreset","jelly-v2"); fixture.setting("motionBounce",1); fixture.phase++; }
        else if(fixture.phase===1 && Theme.motionPreset==="jelly-v2") { panel.shown=true; fixture.phase++; }
        else if(fixture.phase===2 && panel.progress===1 && !fluid.rendering) {
            fixture.checks.deformed=fixture.peak>.08;
            fixture.checks.idle=!panel.layer.enabled && fluid.strain===0 && blur.regions.length===0 && blur.active;
            panel.shown=false; fixture.phase++;
        } else if(fixture.phase===3 && panel.offsetX < -20) {
            const before=panel.offsetX; panel.shown=true;
            fixture.checks.reverse=panel.offsetX===before && panel.mounted;
            fixture.phase++;
        } else if(fixture.phase===4 && panel.progress===1 && !fluid.rendering) {
            menu.open(); fixture.phase++;
        } else if(fixture.phase===5 && menu.positioned && menu.progress===1 && !fixture.effect(menu.surface).rendering) {
            fixture.checks.menu=!menu.surface.layer.enabled;
            menu.close(); panel.shown=false; fixture.phase++;
        } else if(fixture.phase===6 && !panel.mounted && !menu.mounted) {
            fixture.checks.closed=!panel.layer.enabled && fluid.strain===0 && !blur.active && blur.regions.length===0;
            panel.shown=true; fixture.phase++;
        } else if(fixture.phase===7 && Math.abs(fluid.strain)>.02) {
            fixture.setting("motionPreset","smooth"); fixture.phase++;
        } else if(fixture.phase===8 && Theme.motionPreset==="smooth") {
            fixture.checks.switching=fluid.strain===0 && !panel.layer.enabled && blur.regions.length===0;
            fixture.setting("motionPreset","jelly-v2"); panel.shown=false; fixture.phase++;
        } else if(fixture.phase===9 && !panel.mounted && Theme.motionPreset==="jelly-v2") {
            panel.shown=true; fixture.phase++;
        } else if(fixture.phase===10 && Math.abs(fluid.strain)>.02) {
            fixture.setting("animations",false); fixture.phase++;
        } else if(fixture.phase===11 && !Theme.animations) {
            fixture.checks.reduced=fluid.strain===0 && !fluid.rendering && !panel.layer.enabled && panel.progress===1 && blur.regions.length===0;
            panel.shown=false;
            fixture.checks.finite=fixture.finite;
            fixture.checks.layered=fixture.layered;
            fixture.checks.masked=fixture.masked;
            fixture.finish(fixture.checks);
        }
    } }
''', {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'software' if renderer=='software' else '',
      'QSG_RHI_BACKEND':renderer,'LIBGL_ALWAYS_SOFTWARE':'1'})
                self.assertEqual(result,{key:True for key in ('deformed','idle','reverse','menu','closed','switching','reduced','finite')} | {'layered':renderer=='opengl','masked':renderer=='opengl'})
