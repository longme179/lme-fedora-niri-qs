"""Desktop geometry validation, independent edits and native layer/input checks."""
import copy
import os
import unittest
from test_backend import backend, Fixture
from settings_transfer import document, validate_document
import test_local_qml as qml_tests

RECORD = dict(type='clock',output='primary',x=.2,y=.3,width=320,height=220,enabled=True,interactive=True)


class DesktopWidgetCase(Fixture,unittest.TestCase):
    def test_validation_and_portable_configuration(self):
        self.preferences.set('desktopWidgets',{'one':RECORD})
        result=validate_document(document(self.preferences.values,'preset'),backend.validate_preference,backend.DEFAULT_PREFERENCES)
        self.assertEqual(result['desktopWidgets'],{'one':RECORD})
        for field,value in [('x',float('nan')),('x',True),('y',2),('width',True),('height',0),('type','shell'),('output','\n'),('enabled',1)]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.preferences.set('desktopWidgets',{'one':dict(RECORD,**{field:value})})
        with self.assertRaises(ValueError):self.preferences.set('desktopWidgets',{str(i):RECORD for i in range(13)})

    def test_atomic_widget_patches_preserve_other_fields_and_other_writers(self):
        self.preferences.set('desktopWidgets',{'one':RECORD,'two':dict(RECORD,type='notes')})
        stale=backend.Preferences(self.preferences.path)
        self.preferences.set('desktopWidgets',{'width':500},token='one')
        stale.set('desktopWidgets',{'x':.8,'y':.9},token='one')
        saved=backend.Preferences(self.preferences.path).values['desktopWidgets']
        self.assertEqual(saved['one']['width'],500)
        self.assertEqual(saved['one']['x'],.8)
        self.assertEqual(saved['two']['type'],'notes')
        self.preferences.set('desktopWidgets','',token='one')
        with self.assertRaises(ValueError):stale.set('desktopWidgets',{'x':.5},token='one')
        self.assertEqual(set(backend.Preferences(self.preferences.path).values['desktopWidgets']),{'two'})

    def test_demo_widget_patch_and_delete_are_isolated(self):
        live=self.make_backend(demo=True)
        self.assertTrue(live.handle(dict(action='setting',key='desktopWidgets',token='clock-a',value=RECORD))['ok'])
        self.assertTrue(live.handle(dict(action='setting',key='desktopWidgets',token='clock-a',value={'x':.8}))['ok'])
        self.assertEqual(live.preferences.values['desktopWidgets']['clock-a']['width'],320)
        self.assertFalse(self.preferences.path.exists())
        self.assertTrue(live.handle(dict(action='setting',key='desktopWidgets',token='clock-a',value=''))['ok'])
        self.assertEqual(live.preferences.values['desktopWidgets'],{})


@unittest.skipUnless(os.environ.get('LME_TEST_DESKTOP_UI')=='1','requires private Wayland')
class DesktopWidgetQmlCase(unittest.TestCase):
    run_qml=qml_tests.LocalQmlCase.run_qml

    def test_native_widgets_move_resize_clickthrough_and_edit_layer(self):
        result=self.run_qml('import QtTest\nimport Quickshell.Wayland\nimport "qml/panels"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property var checks: ({})
    property var initial: null
    property var resizeOrigin: []
    DesktopWidgetWindow { id: widget; widgetId:"clock-a"; screenInfo:Quickshell.screens[0] }
    TestCase { id: pointer; when:false }
    function find(item,name) { if(item.objectName===name)return item;for(const child of item.children || []){const found=find(child,name);if(found)return found;}return null; }
    Timer { interval:100;repeat:true;running:true;onTriggered:{
        if(++fixture.ticks>100){fixture.finish({timeout:fixture.phase,record:DesktopState.widgets["clock-a"],checks:fixture.checks,draft:widget.draftWidth,width:widget.width});return;}
        if(!ShellState.backendReady || ShellState.pendingActions.setting)return;
        if(fixture.phase===0){
            ShellState.run("setting",{key:"desktopEnabled",value:true});fixture.phase++;
        }else if(fixture.phase===1){
            ShellState.run("setting",{key:"desktopWidgets",token:"clock-a",value:{type:"clock",output:"primary",x:.2,y:.3,width:320,height:220,enabled:true,interactive:true}});fixture.phase++;
        }else if(fixture.phase===2 && DesktopState.widgets["clock-a"]){
            fixture.checks.below=widget.WlrLayershell.layer===WlrLayer.Bottom;
            fixture.initial=DesktopState.widgets["clock-a"];DesktopState.editing=true;fixture.phase++;
        }else if(fixture.phase===3){
            fixture.checks.overlay=widget.WlrLayershell.layer===WlrLayer.Overlay;
            const grip=fixture.find(widget.contentItem,"desktopDrag-clock-a");
            pointer.mousePress(grip,12,12);pointer.mouseMove(grip,65,40);pointer.mouseRelease(grip,65,40);fixture.phase++;
        }else if(fixture.phase===4 && DesktopState.widgets["clock-a"].x!==fixture.initial.x){
            fixture.checks.moved=true;
            fixture.resizeOrigin=[widget.margins.left,widget.margins.top];
            const corner=fixture.find(widget.contentItem,"desktopResize-clock-a");
            pointer.mousePress(corner,10,10);pointer.mouseMove(corner,65,60);pointer.mouseRelease(corner,65,60);fixture.phase++;
        }else if(fixture.phase===5 && DesktopState.widgets["clock-a"].width>320){
            fixture.checks.resized=true;DesktopState.patch("clock-a",{interactive:false});DesktopState.editing=false;fixture.phase++;
        }else if(fixture.phase===6 && DesktopState.widgets["clock-a"].interactive===false && widget.width===DesktopState.widgets["clock-a"].width && widget.height===DesktopState.widgets["clock-a"].height){
            fixture.checks.anchored=Math.abs(widget.margins.left-fixture.resizeOrigin[0])<=1 && Math.abs(widget.margins.top-fixture.resizeOrigin[1])<=1;
            fixture.checks.clickthrough=widget.mask.item===null;
            fixture.checks.returned=widget.WlrLayershell.layer===WlrLayer.Bottom;
            fixture.finish(fixture.checks);
        }
    }}
''',{'QT_QPA_PLATFORM':'wayland'})
        self.assertEqual(result,dict(below=True,overlay=True,moved=True,resized=True,anchored=True,clickthrough=True,returned=True))

    def test_resize_stays_anchored_and_small_viewports_preserve_valid_saved_sizes(self):
        result=self.run_qml('import "qml/panels"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property var origin: []
    property var checks: ({})
    QtObject { id: dimensions; property int width: 1920; property int height: 1080 }
    DesktopWidgetWindow {
        id: widget; widgetId: "one"; screenInfo: dimensions; screen: Quickshell.screens[0]
    }
    Timer { interval: 120; repeat: true; running: true; onTriggered: {
        if (++fixture.ticks>70) { fixture.finish({timeout:fixture.phase}); return; }
        if (!ShellState.backendReady || ShellState.pendingActions.setting) return;
        const card=widget.contentItem.children[0];
        if (fixture.phase===0) {
            ShellState.run("setting",{key:"desktopWidgets",value:{one:{type:"clock",output:"primary",x:.2,y:.3,width:320,height:220,enabled:true,interactive:true}}}); fixture.phase++;
        } else if (fixture.phase===1 && widget.width===320) {
            fixture.origin=[widget.margins.left,widget.margins.top]; card.resizeBy(100,80); fixture.phase++;
        } else if (fixture.phase===2 && widget.width===420 && widget.height===300) {
            widget.commit(); fixture.phase++;
        } else if (fixture.phase===3 && widget.record.width===420) {
            fixture.checks.anchored=Math.abs(widget.margins.left-fixture.origin[0])<=1 && Math.abs(widget.margins.top-fixture.origin[1])<=1;
            dimensions.height=180; fixture.phase++;
        } else if (fixture.phase===4 && widget.height<180) {
            card.moveBy(20,0); widget.commit(); fixture.phase++;
        } else if (fixture.phase===5) {
            fixture.checks.moveSaved=ShellState.lastResult.ok;
            fixture.checks.keptSize=widget.record.width===420 && widget.record.height===300;
            card.resizeBy(0,10); widget.commit(); fixture.phase++;
        } else if (fixture.phase===6) {
            fixture.checks.smallResizeSaved=ShellState.lastResult.ok && widget.record.height>=180;
            dimensions.height=1080; fixture.phase++;
        } else if (fixture.phase===7) { fixture.checks.restoredSize=widget.height===widget.record.height; fixture.finish(fixture.checks); }
    } }
''',{'QT_QPA_PLATFORM':'wayland'})
        self.assertEqual(result,dict(anchored=True,moveSaved=True,keptSize=True,smallResizeSaved=True,restoredSize=True))

    def test_canvas_retains_instances_and_layout_through_visibility_and_output_changes(self):
        result=self.run_qml('import QtTest\nimport "qml/panels"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property var original: null
    property var checks: ({})
    DesktopCanvas { id: canvas }
    TestResult { id: probe }
    function corner() { return probe.findChild(canvas,"desktopResize-one"); }
    Timer { interval: 120; repeat: true; running: true; onTriggered: {
        if (++fixture.ticks>80) { fixture.finish({timeout:fixture.phase}); return; }
        if (!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if (fixture.phase===0) {
            ShellState.run("setting",{key:"desktopEnabled",value:true}); fixture.phase++;
        } else if (fixture.phase===1) {
            ShellState.run("setting",{key:"desktopWidgets",value:{one:{type:"clock",output:"primary",x:.2,y:.3,width:320,height:220,enabled:true,interactive:true}}}); fixture.phase++;
        } else if (fixture.phase===2 && fixture.corner()) {
            fixture.original=fixture.corner(); DesktopState.patch("one",{x:.7}); fixture.phase++;
        } else if (fixture.phase===3 && DesktopState.widgets.one.x===.7) {
            fixture.checks.stable=fixture.corner()===fixture.original;
            DesktopState.patch("one",{enabled:false}); fixture.phase++;
        } else if (fixture.phase===4 && !fixture.corner()) {
            fixture.checks.hidden=true; DesktopState.patch("one",{enabled:true,output:"unplugged-output"}); fixture.phase++;
        } else if (fixture.phase===5 && DesktopState.widgets.one.output==="unplugged-output") {
            fixture.checks.disconnected=!fixture.corner() && DesktopState.widgets.one.x===.7;
            DesktopState.patch("one",{output:"primary"}); fixture.phase++;
        } else if (fixture.phase===6 && fixture.corner()) {
            fixture.checks.returned=DesktopState.widgets.one.x===.7;
            DesktopState.editing=true; ShellState.run("setting",{key:"desktopEnabled",value:false}); fixture.phase++;
        } else if (fixture.phase===7 && !DesktopState.enabled && !fixture.corner()) {
            fixture.checks.disabled=!DesktopState.editing;
            ShellState.run("setting",{key:"desktopEnabled",value:true}); fixture.phase++;
        } else if (fixture.phase===8 && fixture.corner()) {
            fixture.checks.restored=DesktopState.widgets.one.x===.7;
            DesktopState.patch("one",""); fixture.phase++;
        } else if (fixture.phase===9 && !fixture.corner() && !DesktopState.widgets.one) fixture.finish(fixture.checks);
    } }
''',{'QT_QPA_PLATFORM':'wayland'})
        self.assertEqual(result,dict(stable=True,hidden=True,disconnected=True,returned=True,disabled=True,restored=True))

    def test_setting_update_does_not_reset_geometry_during_a_pointer_gesture(self):
        result=self.run_qml('import QtTest\nimport "qml/panels"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property var held: []
    DesktopWidgetWindow { id: widget; widgetId:"one"; screenInfo:Quickshell.screens[0] }
    TestCase { id: pointer; when:false }
    Timer { interval:120; repeat:true; running:true; onTriggered: {
        if (++fixture.ticks>60) { fixture.finish({timeout:fixture.phase}); return; }
        if (!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if (fixture.phase===0) {
            DesktopState.editing=true;
            ShellState.run("setting",{key:"desktopWidgets",value:{one:{type:"clock",output:"primary",x:.2,y:.3,width:320,height:220,enabled:true,interactive:true}}}); fixture.phase++;
        } else if (fixture.phase===1 && widget.width===320) {
            const grip=pointer.findChild(widget.contentItem,"desktopDrag-one");
            pointer.mousePress(grip,12,12); widget.draftX=460; widget.draftY=350;
            fixture.held=[widget.draftX,widget.draftY]; DesktopState.patch("one",{interactive:false}); fixture.phase++;
        } else if (fixture.phase===2 && widget.record.interactive===false) {
            const kept=widget.draftX===fixture.held[0] && widget.draftY===fixture.held[1];
            const grip=pointer.findChild(widget.contentItem,"desktopDrag-one");
            const pressed=grip.pressed; pointer.mouseRelease(grip,12,12);
            fixture.finish({kept,pressed});
        }
    } }
''',{'QT_QPA_PLATFORM':'wayland'})
        self.assertEqual(result,dict(kept=True,pressed=True))
