"""White Liquid labels and glass on custom button backgrounds."""
import os
import unittest
import test_local_qml as qml_tests


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'private OpenGL button checks')
class ButtonMaterialCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_power_agenda_calendar_custom_backgrounds_brightness_and_restoration(self):
        result = self.run_qml('import QtTest\nimport "qml/components"\nimport "qml/panels"\nimport "qml/services"\nimport "qml/theme"', '''
    FloatingWindow { id:window;implicitWidth:1000;implicitHeight:900
        PowerMenu { id:power;x:12;y:12;width:440;height:430 }
        Agenda { id:agenda;x:480;y:12;width:500;height:850 }
        LiquidButton { id:selected;x:20;y:500;text:"Selected";selected:true;selectionColor:"#f5f5f5" }
        LiquidButton { id:custom;x:20;y:560;text:"Custom";background:Rectangle { radius:13;color:Theme.surface } }
        LiquidButton { id:flat;x:20;y:620;text:"Flat";flat:true;selected:true;selectionColor:"white" }
        LiquidButton { id:bare;x:200;y:620;text:"Transparent";background:Rectangle { color:"transparent" } }
        LiquidButton { id:swatch;x:20;y:680;glassBackground:false;background:Rectangle { color:"#ff0080" } }
        LiquidComboBox { id:combo;x:20;y:740;model:["One","Two"] }
        IconButton { id:closeIcon;x:220;y:740;glyph:"×";tooltip:"Close";active:true }
        LiquidButton { id:closeButton;x:280;y:740;text:"×";palette.button:Theme.surface }
        ShellText { id:plain;text:"White label";color:"red" }
        TestCase { id:probe;when:false }
    }
    property int phase:0
    property int ticks:0
    property var checks:({})
    function items(item,predicate) {
        let result=predicate(item) ? [item] : [];
        for(const child of item.children || []) result=result.concat(items(child,predicate));
        return result;
    }
    function glass(item) { return items(item,i=>i.objectName==="glassMaterial"); }
    Timer { interval:70;repeat:true;running:true;onTriggered: {
        if(++fixture.ticks>160) { fixture.finish({timeout:fixture.phase,checks:fixture.checks});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { ShellState.run("setting",{key:"animations",value:false});fixture.phase++; }
        else if(fixture.phase===1) { ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});fixture.phase++; }
        else if(fixture.phase===2 && Theme.liquidGlass && GlassState.backdrops.length===1) {
            const buttons=fixture.items(power,i=>i.actionName!==undefined);
            fixture.checks.power=buttons.length===5 && buttons.every(b=>fixture.glass(b).length===1 && fixture.glass(b)[0].active
                && fixture.glass(b)[0].parent===b.background && b.background.color.a<.1);
            fixture.checks.custom=fixture.glass(custom).length===1 && fixture.glass(custom)[0].active && fixture.glass(custom)[0].radius===13;
            fixture.checks.combo=fixture.glass(combo.background).length===1 && fixture.glass(combo.background)[0].active;
            fixture.checks.exclusions=!fixture.glass(flat)[0].active && !fixture.glass(bare)[0].active
                && !fixture.glass(swatch)[0].active && swatch.background.color.toString()==="#ff0080";
            const day=probe.findChild(agenda,"calendarDay-"+new Date().getDate());
            const label=fixture.items(day,i=>i.text===String(new Date().getDate()))[0];
            const tabs=fixture.items(agenda,i=>["Calendar","To do","Timer","Notes"].includes(i.text) && i.selected!==undefined);
            fixture.checks.selection=selected.contentItem.color.toString()==="#ffffff" && flat.contentItem.color.toString()==="#ffffff"
                && tabs.length===4 && tabs.every(b=>b.contentItem.color.toString()==="#ffffff")
                && label.color.toString()==="#ffffff" && fixture.glass(day)[0].active && plain.color.toString()==="#ffffff";
            ShellState.run("setting",{key:"liquidGlass",token:"brightness",value:.2});fixture.phase++;
        } else if(fixture.phase===3 && Theme.glass.brightness===.2) {
            fixture.checks.dimmed=selected.contentItem.color.toString()==="#ffffff" && flat.contentItem.color.toString()==="#ffffff";
            ShellState.run("setting",{key:"liquidGlass",token:"tint",value:"#ffffff"});fixture.phase++;
        } else if(fixture.phase===4 && Theme.glass.tint==="#ffffff") {
            fixture.phase++;
            probe.mouseMove(closeButton,closeButton.width/2,closeButton.height/2);
        } else if(fixture.phase===5 && closeButton.hovered) {
            const glyph=fixture.items(closeIcon,i=>i.text==="×")[0];
            const buttons=fixture.items(window.contentItem,i=>i.text!==undefined && i.selected!==undefined && i.contentItem && i.contentItem.color!==undefined);
            fixture.checks.whiteHover=glyph.color.toString()==="#ffffff" && closeButton.contentItem.color.toString()==="#ffffff"
                && buttons.length>10 && buttons.every(b=>b.contentItem.color.toString()==="#ffffff");
            window.visible=false;fixture.phase++;
        } else if(fixture.phase===6 && !GlassState.backdrops.length) {
            fixture.checks.released=true;window.visible=true;fixture.phase++;
        } else if(fixture.phase===7 && GlassState.backdrops.length===1) {
            ShellState.run("setting",{key:"surfaceStyle",value:"smoked"});fixture.phase++;
        } else if(fixture.phase===8 && !Theme.liquidGlass && !GlassState.backdrops.length) {
            fixture.checks.restored=plain.color.toString()==="#ff0000" && !fixture.glass(custom)[0].active
                && Math.abs(fixture.items(power,i=>i.actionName!==undefined)[0].background.color.a-.55)<.01;
            fixture.finish(fixture.checks);
        }
    }}
''', {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
        self.assertEqual(result, dict(power=True,custom=True,combo=True,exclusions=True,selection=True,dimmed=True,whiteHover=True,released=True,restored=True))
