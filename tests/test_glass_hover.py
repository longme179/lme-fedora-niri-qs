"""Passive glass lighting follows real pointer events and releases its motion drivers."""
import os
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import test_local_qml as qml_tests


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'private OpenGL hover checks')
class GlassHoverCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_pointer_entry_inertia_exit_geometry_input_and_idle_release(self):
        result=self.run_qml('import QtTest\nimport QtQuick.Window\nimport "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    property int phase:0
    property int ticks:0
    property int age:0
    property int frames:0
    property int idleStart:0
    property int presses:0
    property bool retainedVelocity:false
    property bool recordedRetarget:false
    property bool disabledHeld:false
    property real exitX:0
    property real targetBeforeMove:0
    property var checks:({})
    FloatingWindow { id:window;implicitWidth:800;implicitHeight:600;color:"#243545"
        Item { id:group;x:100;y:100;width:500;height:300
            LiquidButton { id:button;x:40;y:40;width:360;height:96;text:"Interactive glass";onClicked:fixture.presses++ }
        }
        TestCase { id:mouse;when:false }
    }
    readonly property var glass:mouse.findChild(button,"glassMaterial")
    readonly property var lightX:mouse.findChild(button,"glassLightX")
    readonly property var lightY:mouse.findChild(button,"glassLightY")
    Connections { target:button.Window.window; function onAfterAnimating() { fixture.frames++; } }
    Connections { target:fixture.lightX; function onTargetChanged() {
        if(fixture.phase===4 && !fixture.recordedRetarget && fixture.lightX.target<fixture.lightX.value) {
            fixture.recordedRetarget=true;fixture.retainedVelocity=fixture.lightX.velocity>0;
        }
    }}
    Timer { interval:30;running:true;repeat:true;onTriggered: {
        if(++fixture.ticks>400) { fixture.finish({timeout:fixture.phase,checks:fixture.checks,x:fixture.lightX.value,target:fixture.lightX.target});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});fixture.phase++; }
        else if(fixture.phase===1 && Theme.liquidGlass) { mouse.mouseMove(button,30,48);fixture.phase++; }
        else if(fixture.phase===2 && fixture.glass.hasPointer && fixture.glass.hoverAmount>.9) {
            fixture.checks.entry=Math.abs(fixture.lightX.value-30)<3 && Math.abs(fixture.lightY.value-48)<3;
            mouse.mouseMove(button,290,48);fixture.phase++;
        } else if(fixture.phase===3 && fixture.lightX.value>65 && fixture.lightX.value<260 && fixture.lightX.velocity>0) {
            fixture.checks.inertia=true;fixture.phase=4;mouse.mouseMove(button,45,48);
        } else if(fixture.phase===4 && fixture.lightX.target<65) {
            fixture.checks.retarget=fixture.retainedVelocity;
            fixture.targetBeforeMove=fixture.lightX.target;group.x+=16;fixture.phase++;
        } else if(fixture.phase===5 && fixture.lightX.target<fixture.targetBeforeMove-10 && !fixture.lightX.running && !fixture.lightY.running) {
            fixture.checks.mapping=Math.abs(fixture.lightX.target-(fixture.targetBeforeMove-16/button.scale))<2;
            fixture.idleStart=fixture.frames;fixture.age=0;fixture.phase++;
        } else if(fixture.phase===6 && ++fixture.age>18) {
            fixture.checks.idle=!fixture.lightX.driver.running && !fixture.lightY.driver.running && fixture.frames-fixture.idleStart<4;
            mouse.mouseClick(button,button.width/2,button.height/2);
            fixture.checks.input=fixture.presses===1;fixture.age=0;fixture.phase++;
        } else if(fixture.phase===7 && !fixture.lightX.running && !fixture.lightY.running && ++fixture.age>8) {
            mouse.mouseMove(button,70,48);fixture.phase++;
        } else if(fixture.phase===8 && fixture.lightX.target<90 && !fixture.lightX.running && !fixture.lightY.running) {
            fixture.exitX=fixture.glass.lightPosition.x;mouse.mouseMove(window.contentItem,5,5);
            fixture.checks.noCenterJump=Math.abs(fixture.glass.lightPosition.x-fixture.exitX)<2;
            fixture.phase++;
        } else if(fixture.phase===9 && fixture.glass.hoverAmount===0) {
            fixture.checks.exit=!fixture.glass.hasPointer && !fixture.lightX.driver.running && !fixture.lightY.driver.running;
            ShellState.run("setting",{key:"springMotion",value:false});mouse.mouseMove(button,80,48);fixture.phase++;
        } else if(fixture.phase===10 && fixture.glass.hasPointer && !Theme.springMotion) {
            fixture.checks.direct=fixture.lightX.value===fixture.lightX.target && !fixture.lightX.running;
            ShellState.run("setting",{key:"animations",value:false});fixture.phase++;
        } else if(fixture.phase===11 && !Theme.animations) {
            fixture.checks.reduced=fixture.glass.hoverAmount===0 && !fixture.glass.lightEnabled && !fixture.lightX.driver.running;
            ShellState.run("setting",{key:"animations",value:true});ShellState.run("setting",{key:"springMotion",value:true});fixture.phase++;
        } else if(fixture.phase===12 && fixture.glass.hoverAmount>.5) {
            mouse.mouseMove(button,60,48);fixture.phase++;
        } else if(fixture.phase===13 && fixture.glass.hasPointer && !fixture.lightX.running && !fixture.lightY.running) {
            const x=fixture.glass.lightPosition.x;button.enabled=false;
            fixture.disabledHeld=Math.abs(fixture.glass.lightPosition.x-x)<2;fixture.phase++;
        } else if(fixture.phase===14 && fixture.glass.hoverAmount===0) {
            fixture.checks.disabled=fixture.disabledHeld && !fixture.glass.hasPointer && !fixture.lightX.driver.running;
            button.enabled=true;mouse.mouseMove(button,100,48);fixture.phase++;
        } else if(fixture.phase===15 && fixture.glass.hoverAmount>.5) {
            group.visible=false;fixture.phase++;
        } else if(fixture.phase===16 && !fixture.glass.active) {
            fixture.checks.hidden=!fixture.lightX.driver.running && !fixture.lightY.driver.running && GlassState.backdrops.length===0;
            fixture.finish(fixture.checks);
        }
    }}
''', {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
        self.assertEqual(result,dict(entry=True,inertia=True,retarget=True,mapping=True,idle=True,input=True,noCenterJump=True,exit=True,direct=True,reduced=True,disabled=True,hidden=True))

    def test_rendered_glint_moves_across_the_rim_without_washing_out_the_body(self):
        try:
            from PIL import Image, ImageChops, ImageStat
        except ImportError:
            self.skipTest('Pillow is required for rendered pixels')
        if not shutil.which('grim'): self.skipTest('grim is required for rendered pixels')
        with tempfile.TemporaryDirectory() as directory:
            result=self.run_qml('import Quickshell.Io\nimport "qml/components"', '''
    property int phase:0
    property int age:0
    FloatingWindow { fullscreen:true;color:"#21303c"
        Image { id:source;source:"assets/wallpapers/liquid-dracula.png";visible:false }
        GlassOptics { anchors.centerIn:parent;width:320;height:200
            src:source;sourceAvailable:0;clear:1;tintAmount:0;bezel:8;frost:.9;rim:.38
            topLeftRadius:32;topRightRadius:32;bottomLeftRadius:32;bottomRightRadius:32
            hover:fixture.phase===0 ? 0 : 1
            cursorPos:Qt.point(fixture.phase===2 ? width-8 : 8,height/2)
            opacity:fixture.phase===3 ? .5 : 1
        }
        Text { anchors.centerIn:parent;text:"Readable";color:"white";font.pixelSize:28;font.bold:true }
    }
    Process { id:shot;onExited:code=> {
        if(code!==0) { fixture.finish({error:code});return; }
        fixture.age=0;if(++fixture.phase===4) fixture.finish({captured:4});
    }}
    Timer { interval:60;repeat:true;running:true;onTriggered: {
        if(!shot.running && ++fixture.age>=4) { shot.command=["grim",DIR+"/"+fixture.phase+".png"];shot.running=true; }
    }}
'''.replace('DIR',json.dumps(directory)), {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
            self.assertEqual(result,dict(captured=4))
            images=[Image.open(Path(directory)/f'{i}.png').convert('RGB') for i in range(4)]
            x,y=(images[0].width-320)//2,(images[0].height-200)//2
            left=(x,y+70,x+6,y+130);right=(x+314,y+70,x+320,y+130)
            def level(image,box): return sum(ImageStat.Stat(image.crop(box)).mean)
            self.assertGreater(level(images[1],left),level(images[2],left)+15)
            self.assertGreater(level(images[2],right),level(images[1],right)+15)
            for image in images:
                self.assertEqual(image.getpixel((x,y)),(33,48,60),'rounded corners must remain clear')
                body=image.getpixel((x+160,y+45))
                self.assertLess(max(abs(a-b) for a,b in zip(body,(33,48,60))),12,'no opaque hover wash')
                white=sum(min(image.getpixel((a,b)))>245 for b in range(y+80,y+120) for a in range(x+70,x+250))
                self.assertGreater(white,300,'foreground text must remain white')
            expected=Image.blend(images[1],Image.new('RGB',images[1].size,'#21303c'),.5)
            diff=ImageChops.difference(images[3],expected).crop((x,y,x+320,y+60))
            self.assertLess(max(ImageStat.Stat(diff).mean),1.5,'reflection must follow group opacity')

    def test_bevel_has_depth_on_bright_apps_and_preserves_clear_body_and_group_opacity(self):
        try:
            from PIL import Image, ImageChops, ImageStat
        except ImportError:
            self.skipTest('Pillow is required for rendered pixels')
        if not shutil.which('grim'): self.skipTest('grim is required for rendered pixels')
        with tempfile.TemporaryDirectory() as directory:
            result=self.run_qml('import Quickshell.Io\nimport "qml/components"', '''
    property int phase:0
    property int age:0
    FloatingWindow { fullscreen:true;color:"#21303c"
        Repeater { model:["#f4f4f4","#18232f"]
            Rectangle { required property int index;required property string modelData
                x:200+index*800;y:120;width:650;height:480;color:modelData
                GlassOptics { x:100;y:80;width:420;height:320
                    sourceAvailable:0;clear:1;tintAmount:0;bezel:8;frost:.9
                    rim:fixture.phase===0 ? 0 : .38
                    brightness:fixture.phase===2 ? 0 : 1
                    opacity:fixture.phase===3 ? .5 : 1
                    topLeftRadius:56;topRightRadius:8;bottomLeftRadius:56;bottomRightRadius:8
                }
            }
        }
    }
    Process { id:shot;onExited:code=> {
        if(code!==0) { fixture.finish({captureError:code});return; }
        fixture.age=0;if(++fixture.phase===4) fixture.finish({captured:4});
    }}
    Timer { interval:60;repeat:true;running:true;onTriggered: {
        if(!shot.running && ++fixture.age>=4) { shot.command=["grim",DIR+"/"+fixture.phase+".png"];shot.running=true; }
    }}
'''.replace('DIR',json.dumps(directory)), {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
            self.assertEqual(result,dict(captured=4))
            images=[Image.open(Path(directory)/f'{i}.png').convert('RGB') for i in range(4)]
            for x,background in ((300,(244,244,244)),(1100,(24,35,47))):
                self.assertEqual(images[1].getpixel((x+210,300)),background,'the glass body must stay transparent')
                self.assertEqual(images[1].getpixel((x+2,202)),background,'large rounded corners must stay clear')
                self.assertEqual(images[2].getpixel((x+210,300)),(0,0,0),'zero brightness must remain opaque black')
                expected=Image.blend(images[1],images[0],.5)
                diff=ImageChops.difference(images[3],expected).crop((x,200,x+420,520))
                self.assertLess(max(ImageStat.Stat(diff).mean),1.5,'the bevel must follow group opacity')
            bright_inner=[sum(images[1].getpixel((310+i,360))) for i in range(-2,3)]
            self.assertLess(min(bright_inner),3*244-20,'bright backdrops need a shallow dark inner bevel')
            dark_edge=[sum(images[1].getpixel((1310,200+i))) for i in range(5)]
            self.assertGreater(max(dark_edge),sum((24,35,47))+35,'dark backdrops need a visible refractive rim')
