"""Floating glass samples niri window geometry without waking unrelated probes."""
import os
import shutil
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
        self.assertEqual(live.runner.calls, [('niri', '--version'), ('niri', 'msg', '--json', 'workspaces'), ('niri', 'msg', '--json', 'windows')])
        live.runner.calls.clear()
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


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class GeometryHelperCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_anchors_first_then_id_then_title(self):
        # Offscreen helper tests guard the anchored cases without a
        # layer-shell backend: anchors always win, a niri IPC id disambiguates
        # duplicate titles, and the shell-owned title is single-match only.
        result = self.run_qml('import "qml/components/GlassGeometry.js" as GlassGeometry', '''
    property var checks: ({})
    Timer {
        interval: 80; running: true
        onTriggered: {
            const out = {width: 1920, height: 1080};
            const host = {width: 800, height: 600};
            const win = {width: 800, height: 600};
            const spaces = [{id: 1, output: "eDP-1"}];
            const a = {id: 7, title: "Same", workspace_id: 1, layout: {tile_pos_in_workspace_view: [10, 20], window_offset_in_tile: [1, 2]}};
            const b = {id: 8, title: "Same", workspace_id: 1, layout: {tile_pos_in_workspace_view: [300, 400], window_offset_in_tile: [5, 5]}};
            const windows = [a, b];
            const anchored = GlassGeometry.resolve({left: true, top: false, right: false, bottom: false}, {left: 14, top: 22, right: 0, bottom: 0}, win, host, out, windows, spaces, "eDP-1", [7], "Same");
            fixture.checks.anchored = anchored.x === 14 && anchored.y === (1080 - 600) / 2;
            const byId = GlassGeometry.resolve(null, null, win, host, out, windows, spaces, "eDP-1", [8], "Same");
            fixture.checks.byId = byId.x === 305 && byId.y === 405;
            const byTitle = GlassGeometry.resolve(null, null, win, host, out, [a], spaces, "eDP-1", [], "Same");
            fixture.checks.byTitle = byTitle.x === 11 && byTitle.y === 22;
            const dupTitle = GlassGeometry.resolve(null, null, win, host, out, windows, spaces, "eDP-1", [], "Same");
            fixture.checks.dupCentered = dupTitle.x === (1920 - 800) / 2 && dupTitle.y === (1080 - 600) / 2;
            const emptyLayout = {id: 9, title: "Same", workspace_id: 1, layout: {tile_pos_in_workspace_view: [], window_offset_in_tile: []}};
            const safe = GlassGeometry.resolve(null, null, win, host, out, [emptyLayout], spaces, "eDP-1", [9], "Same");
            fixture.checks.safe = Number.isFinite(safe.x) && Number.isFinite(safe.y);
            const wrongOut = GlassGeometry.resolve(null, null, win, host, out, [a], spaces, "DP-9", [7], "Same");
            fixture.checks.wrongOutCentered = wrongOut.x === (1920 - 800) / 2;
            const anchoredRight = GlassGeometry.resolve({left: false, top: false, right: true, bottom: true}, {left: 0, top: 0, right: 30, bottom: 40}, win, host, out, windows, spaces, "eDP-1", [7], "Same");
            fixture.checks.anchoredRight = anchoredRight.x === 1920 - 800 - 30 && anchoredRight.y === 1080 - 600 - 40;
            fixture.finish(fixture.checks);
        }
    }
''')
        self.assertEqual(result, dict(anchored=True, byId=True, byTitle=True, dupCentered=True,
            safe=True, wrongOutCentered=True, anchoredRight=True))


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
