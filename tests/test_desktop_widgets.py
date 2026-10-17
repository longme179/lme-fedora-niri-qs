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
            const corner=fixture.find(widget.contentItem,"desktopResize-clock-a");
            pointer.mousePress(corner,10,10);pointer.mouseMove(corner,65,60);pointer.mouseRelease(corner,65,60);fixture.phase++;
        }else if(fixture.phase===5 && DesktopState.widgets["clock-a"].width>320){
            fixture.checks.resized=true;DesktopState.patch("clock-a",{interactive:false});DesktopState.editing=false;fixture.phase++;
        }else if(fixture.phase===6 && DesktopState.widgets["clock-a"].interactive===false){
            fixture.checks.clickthrough=widget.mask.item===null;
            fixture.checks.returned=widget.WlrLayershell.layer===WlrLayer.Bottom;
            fixture.finish(fixture.checks);
        }
    }}
''',{'QT_QPA_PLATFORM':'wayland'})
        self.assertEqual(result,dict(below=True,overlay=True,moved=True,resized=True,clickthrough=True,returned=True))
