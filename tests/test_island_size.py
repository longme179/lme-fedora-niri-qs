"""Island limits remain strict during spring resizing and fit the viewport."""
import os
import unittest
from test_backend import Fixture, backend
from settings_transfer import document, validate_document
import test_local_qml as qml_tests


class IslandSizeCase(Fixture, unittest.TestCase):
    def test_limits_validate_persist_transfer_and_round_trip_through_profiles(self):
        values = dict(activityCompactMaxWidth=600,activityPopupMaxWidth=800,activityPopupMaxHeight=720)
        self.preferences.update(values)
        restored = backend.Preferences(self.preferences.path)
        for kind in ('preset','backup'):
            result=validate_document(document(restored.values,kind),backend.validate_preference,backend.DEFAULT_PREFERENCES)
            self.assertEqual({k:result[k] for k in values},values)
        live=self.make_backend()
        self.assertTrue(live.handle(dict(action='appearanceSave',name='Wide Island'))['ok'])
        self.preferences.set('activityPopupMaxWidth',460)
        self.assertTrue(live.handle(dict(action='appearanceApply',name='Wide Island'))['ok'])
        self.assertEqual(self.preferences.values['activityPopupMaxWidth'],800)
        self.preferences.set('activityPopupMaxHeight',0)
        for key,value in [('activityCompactMaxWidth',119),('activityPopupMaxWidth',399),('activityPopupMaxHeight',319),
                          ('activityPopupMaxHeight',2161),('activityPopupMaxWidth',True),('activityPopupMaxWidth',float('inf'))]:
            with self.assertRaises(ValueError): self.preferences.set(key,value)


@unittest.skipUnless(os.environ.get('LME_TEST_MOTION_UI')=='1','private QML motion checks')
class IslandSizeQmlCase(unittest.TestCase):
    run_qml=qml_tests.LocalQmlCase.run_qml

    def test_limits_live_resize_small_viewport_bottom_edge_and_reduced_motion(self):
        result=self.run_qml('import "qml/panels"\nimport "qml/bar"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property bool bounded: true
    property var checks: ({})
    function setting(key,value) { ShellState.run("setting",{key,value}); }
    FloatingWindow { implicitWidth: 1000; implicitHeight: 900
        Item { id: viewport; width: 1000; height: 900; ActivityIsland { id: island } }
        ActivityButton { id: pill; y: 850; budget: 1000 }
    }
    FrameAnimation { running: true; onTriggered: {
        if (island.mounted && (island.width>island.expandedWidth+.01 || island.height>island.expandedHeight+.01 || island.width<0 || island.height<0)) fixture.bounded=false;
    } }
    Timer { interval: 60; running: true; repeat: true; onTriggered: {
        if (++fixture.ticks>180) { fixture.finish({timeout:fixture.phase}); return; }
        if (!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { fixture.setting("activityCompactMaxWidth",120); fixture.setting("activityPopupMaxWidth",800); fixture.setting("activityPopupMaxHeight",400); ShellState.activityOpen=true; fixture.phase++; }
        else if(fixture.phase===1 && island.progress===1 && Math.abs(island.width-800)<.1 && Math.abs(island.height-400)<.1) {
            fixture.checks.custom=pill.implicitWidth<=120 && island.expandedHeight===400;
            fixture.setting("activityPopupMaxWidth",400); fixture.setting("activityPopupMaxHeight",0); fixture.phase++;
        } else if(fixture.phase===2 && Math.abs(island.width-400)<.1 && Math.abs(island.height-island.expandedHeight)<.1) {
            fixture.checks.resized=island.height>400; viewport.width=320; viewport.height=270;
            fixture.setting("barEdgeMargin",64); fixture.setting("barEdge","bottom"); fixture.phase++;
        } else if(fixture.phase===3 && Math.abs(island.width-island.expandedWidth)<.1 && Math.abs(island.height-island.expandedHeight)<.1 && ShellState.preferences.barEdge==="bottom") {
            fixture.checks.viewport=island.x>=0 && island.y>=0 && island.x+island.width<=viewport.width && island.y+island.height<=viewport.height;
            fixture.setting("animations",false); fixture.setting("activityPopupMaxHeight",320); fixture.phase++;
        } else if(fixture.phase===4 && ShellState.preferences.animations===false) {
            fixture.checks.reduced=island.width===island.expandedWidth && island.height===island.expandedHeight;
            ShellState.closePanels(); fixture.phase++;
        } else if(fixture.phase===5 && !island.mounted) {
            fixture.checks.bounded=fixture.bounded; fixture.finish(fixture.checks);
        }
    } }
''')
        self.assertEqual(result,dict(custom=True,resized=True,viewport=True,reduced=True,bounded=True))
