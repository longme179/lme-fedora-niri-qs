"""Glass material hover light and simple rendering stay responsive without a backdrop.
Contract: test_glass_hover.py covers glass_hover behavior/contracts; check imports for fixtures/helpers under test.
"""
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
            fixture.checks.hidden=!fixture.lightX.driver.running && !fixture.lightY.driver.running;
            fixture.finish(fixture.checks);
        }
    }}
''', {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
        self.assertEqual(result,dict(entry=True,inertia=True,retarget=True,mapping=True,idle=True,input=True,noCenterJump=True,exit=True,direct=True,reduced=True,disabled=True,hidden=True))

    def test_simple_glass_renders_without_backdrop(self):
        try:
            from PIL import Image, ImageStat
        except ImportError:
            self.skipTest('Pillow is required for rendered pixels')
        if not shutil.which('grim'): self.skipTest('grim is required for rendered pixels')
        with tempfile.TemporaryDirectory() as directory:
            result=self.run_qml('import Quickshell.Io\nimport "qml/components"', '''
    property int phase:0
    property int age:0
    FloatingWindow { fullscreen:true;color:"#21303c"
        GlassOptics { anchors.centerIn:parent;width:320;height:200
            tintColor:"#f0081420"; tintAmount:0.175; panelOpacity:0.8; grain:0.008; rim:1; bezel:8
            topLeftRadius:32;topRightRadius:32;bottomLeftRadius:32;bottomRightRadius:32
        }
        Text { anchors.centerIn:parent;text:"Readable";color:"white";font.pixelSize:28;font.bold:true }
    }
    Process { id:shot;onExited:code=> fixture.finish({captured:code===0}) }
    Timer { interval:60;repeat:true;running:true;onTriggered: {
        if(!shot.running && ++fixture.age>=4) { shot.command=["grim",DIR+"/g.png"];shot.running=true; }
    }}
'''.replace('DIR',json.dumps(directory)), {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
            self.assertTrue(result.get('captured'), result)
            image=Image.open(Path(directory)/'g.png').convert('RGB')
            x,y=(image.width-320)//2,(image.height-200)//2
            self.assertEqual(image.getpixel((x,y)),(33,48,60),'rounded corners must remain clear')
            body=image.getpixel((x+160,y+100))
            self.assertNotEqual(body,(33,48,60),'tint should affect the body')
            white=sum(min(image.getpixel((a,b)))>240 for b in range(y+80,y+120) for a in range(x+90,x+230))
            self.assertGreater(white,250,'foreground text must remain readable')
