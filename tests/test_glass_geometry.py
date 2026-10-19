"""Floating glass samples niri window geometry without waking unrelated probes."""
import os
import unittest
import test_local_qml as qml_tests
from test_backend import Fixture, FakeRunner


class GeometryBackendCase(Fixture, unittest.TestCase):
    def test_settings_reads_only_niri_and_only_while_liquid(self):
        live = self.make_backend(FakeRunner(available={'niri'}))
        live.settings_only = True
        live.snapshot()
        self.assertEqual(live.runner.calls, [])
        self.preferences.set('surfaceStyle', 'liquid')
        live.snapshot()
        self.assertEqual(live.runner.calls, [('niri', 'msg', '--json', 'workspaces'), ('niri', 'msg', '--json', 'windows')])
        live.runner.calls.clear()
        self.preferences.set('surfaceStyle', 'smoked')
        self.assertFalse(live.snapshot()['niri']['available'])
        self.assertEqual(live.runner.calls, [])
        demo = self.make_backend(demo=True)
        demo.settings_only = True
        self.preferences.set('surfaceStyle', 'liquid')
        demo.snapshot()
        self.assertEqual(demo.runner.calls, [])


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'private Wayland geometry checks')
class GeometryQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_native_origin_updates_and_ambiguous_missing_geometry_falls_back(self):
        result = self.run_qml('import "qml/components"\nimport "qml/services"', '''
    property int phase:0
    property int ticks:0
    FloatingWindow { id:window;title:"Geometry probe";implicitWidth:800;implicitHeight:600
        GlassPanel { anchors.fill:parent }
    }
    function publish(windows) {
        ShellState.accept(JSON.stringify(Object.assign({},ShellState.snapshot,{niri:{available:true,
            workspaces:[{id:1,idx:1,output:window.screen.name}],windows:windows}})));
    }
    Timer { interval:40;running:true;repeat:true;onTriggered: {
        if(++fixture.ticks>180) { fixture.finish({timeout:fixture.phase});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});fixture.phase++; }
        else if(fixture.phase===1 && GlassState.backdrops.length) {
            const backdrop=GlassState.backdrops[0];
            const entry={title:window.title,workspace_id:1,layout:{tile_pos_in_workspace_view:[123,241],window_offset_in_tile:[3,3]}};
            fixture.publish([entry]);
            const moved=backdrop.windowOrigin.x===126 && backdrop.windowOrigin.y===244;
            entry.layout.tile_pos_in_workspace_view=[321,145];fixture.publish([entry]);
            const updated=backdrop.windowOrigin.x===324 && backdrop.windowOrigin.y===148;
            fixture.publish([entry,entry]);
            const ambiguous=backdrop.windowOrigin.x===(backdrop.outputWidth-window.width)/2;
            entry.layout.tile_pos_in_workspace_view=[];fixture.publish([entry]);
            const safe=Number.isFinite(backdrop.windowOrigin.x) && Number.isFinite(backdrop.windowOrigin.y);
            fixture.publish([]);
            fixture.finish({moved,updated,ambiguous,safe,missing:backdrop.windowOrigin.x===(backdrop.outputWidth-window.width)/2});
        }
    }}
''', {'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
        self.assertEqual(result,dict(moved=True,updated=True,ambiguous=True,safe=True,missing=True))
