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

    def test_software_and_rhi_surface_deform_settle_reverse_and_release_layers(self):
        for renderer in ('software','opengl'):
            with self.subTest(renderer=renderer):
                result=self.run_qml('import "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    property int phase: 0
    property int ticks: 0
    property real peak: 0
    property bool layered: false
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
    FrameAnimation { running: true; onTriggered: {
        const fluid=fixture.effect(panel);
        fixture.peak=Math.max(fixture.peak,Math.abs(fluid.strain));
        fixture.layered=fixture.layered || panel.layer.enabled;
        fixture.finite=fixture.finite && [fluid.strain,panel.width,panel.height,panel.offsetX,panel.offsetY].every(Number.isFinite) && Math.abs(fluid.strain)<=.42;
    } }
    Timer { interval: 35; running: true; repeat: true; onTriggered: {
        const fluid=fixture.effect(panel);
        if(++fixture.ticks>340) { fixture.finish({timeout:fixture.phase,peak:fixture.peak,progress:panel.progress,rendering:fluid.rendering}); return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { fixture.setting("motionPreset","jelly-v2"); fixture.setting("motionBounce",1); fixture.phase++; }
        else if(fixture.phase===1 && Theme.motionPreset==="jelly-v2") { panel.shown=true; fixture.phase++; }
        else if(fixture.phase===2 && panel.progress===1 && !fluid.rendering) {
            fixture.checks.deformed=fixture.peak>.08;
            fixture.checks.idle=!panel.layer.enabled && fluid.strain===0;
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
            fixture.checks.closed=!panel.layer.enabled && fluid.strain===0;
            panel.shown=true; fixture.phase++;
        } else if(fixture.phase===7 && Math.abs(fluid.strain)>.02) {
            fixture.setting("motionPreset","smooth"); fixture.phase++;
        } else if(fixture.phase===8 && Theme.motionPreset==="smooth") {
            fixture.checks.switching=fluid.strain===0 && !panel.layer.enabled;
            fixture.setting("motionPreset","jelly-v2"); panel.shown=false; fixture.phase++;
        } else if(fixture.phase===9 && !panel.mounted && Theme.motionPreset==="jelly-v2") {
            panel.shown=true; fixture.phase++;
        } else if(fixture.phase===10 && Math.abs(fluid.strain)>.02) {
            fixture.setting("animations",false); fixture.phase++;
        } else if(fixture.phase===11 && !Theme.animations) {
            fixture.checks.reduced=fluid.strain===0 && !fluid.rendering && !panel.layer.enabled && panel.progress===1;
            panel.shown=false;
            fixture.checks.finite=fixture.finite;
            fixture.checks.layered=fixture.layered;
            fixture.finish(fixture.checks);
        }
    } }
''', {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'software' if renderer=='software' else '',
      'QSG_RHI_BACKEND':renderer,'LIBGL_ALWAYS_SOFTWARE':'1'})
                self.assertEqual(result,{key:True for key in ('deformed','idle','reverse','menu','closed','switching','reduced','finite')} | {'layered':renderer=='opengl'})
