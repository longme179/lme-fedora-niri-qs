"""Refractive selection reuses the shared material and existing moving plate."""
import os
import unittest
import test_local_qml as qml_tests
from test_backend import Fixture, backend
from settings_transfer import document, validate_document


class LensPreferencesCase(Fixture, unittest.TestCase):
    def test_switch_is_validated_persistent_and_portable(self):
        self.assertTrue(self.preferences.values['glassSelection'])
        self.preferences.set('glassSelection', False)
        self.assertFalse(backend.Preferences(self.preferences.path).values['glassSelection'])
        values=validate_document(document(self.preferences.values,'preset'),backend.validate_preference,backend.DEFAULT_PREFERENCES)
        self.assertFalse(values['glassSelection'])
        before=self.preferences.path.read_bytes()
        for value in (None,0,'true',[],{}):
            with self.assertRaises(ValueError): self.preferences.set('glassSelection',value)
        self.assertEqual(self.preferences.path.read_bytes(),before)


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI')=='1','private OpenGL selection checks')
class LensQmlCase(unittest.TestCase):
    run_qml=qml_tests.LocalQmlCase.run_qml

    def test_travel_reversal_press_reduced_motion_and_teardown(self):
        result=self.run_qml('import QtTest\nimport "qml/components"\nimport "qml/services"\nimport "qml/theme"','''
    property int phase:0
    property int ticks:0
    property int choice:0
    property var checks:({})
    FloatingWindow { id:window;implicitWidth:700;implicitHeight:400
        Item { x:50;y:80;width:560;height:80
            StretchIndicator { id:indicator;targetItem:fixture.choice===0 ? first : second }
            LiquidButton { id:first;x:20;width:190;text:"First";selected:fixture.choice===0;selectionFill:false }
            LiquidButton { id:second;x:280;width:140;text:"Second";selected:fixture.choice===1;selectionFill:false }
        }
        TestCase { id:mouse;when:false }
    }
    readonly property var lens:mouse.findChild(indicator,"glassMaterial")
    Timer { interval:30;repeat:true;running:true;onTriggered: {
        if(++fixture.ticks>300) { fixture.finish({timeout:fixture.phase,checks:fixture.checks});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { fixture.checks.smoked=!fixture.lens.active;ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});fixture.phase++; }
        else if(fixture.phase===1 && fixture.lens.active && !indicator.moving) {
            fixture.checks.shared=GlassState.backdrops.length===1 && !mouse.findChild(first,"glassMaterial").active;
            fixture.choice=1;fixture.phase++;
        } else if(fixture.phase===2 && indicator.x>50 && indicator.x<250 && fixture.lens.pressAmount>.1) {
            fixture.checks.travels=fixture.lens.active && fixture.lens.parent===indicator;
            const x=indicator.x;fixture.choice=0;
            fixture.checks.reversal=Math.abs(x-indicator.x)<.01;fixture.phase++;
        } else if(fixture.phase===3 && !indicator.moving && fixture.lens.pressAmount<.001) {
            first.down=true;fixture.phase++;
        } else if(fixture.phase===4 && fixture.lens.pressAmount>.9) {
            fixture.checks.press=true;first.down=false;
            ShellState.run("setting",{key:"glassSelection",value:false});fixture.phase++;
        } else if(fixture.phase===5 && !fixture.lens.active) {
            fixture.checks.disabled=mouse.findChild(first,"glassMaterial").active;
            ShellState.run("setting",{key:"glassSelection",value:true});fixture.phase++;
        } else if(fixture.phase===6 && fixture.lens.active) {
            ShellState.run("setting",{key:"animations",value:false});fixture.phase++;
        } else if(fixture.phase===7 && !Theme.animations) {
            fixture.choice=1;fixture.phase++;
        } else if(fixture.phase===8 && Math.abs(indicator.x-second.x)<.01) {
            fixture.checks.reduced=!indicator.moving && fixture.lens.pressAmount===0;
            window.visible=false;fixture.phase++;
        } else if(fixture.phase===9 && !GlassState.backdrops.length) {
            fixture.checks.released=true;fixture.finish(fixture.checks);
        }
    }}
''',{'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
        self.assertEqual(result,dict(smoked=True,shared=True,travels=True,reversal=True,press=True,disabled=True,reduced=True,released=True))
