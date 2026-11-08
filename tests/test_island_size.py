"""Island limits remain strict during spring resizing and fit the viewport."""
import os
from pathlib import Path
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
        } else if(fixture.phase===5 && (island.dormant || !island.mounted)) {
            fixture.checks.bounded=fixture.bounded; fixture.finish(fixture.checks);
        }
    } }
''')
        self.assertEqual(result,dict(custom=True,resized=True,viewport=True,reduced=True,bounded=True))


class IslandFlightSourceCase(unittest.TestCase):
    """The island morph must reverse with the flight and the warm pass must
    render at open geometry (first-open jank + the open+ESC stuck look)."""

    def sources(self):
        repo = Path(__file__).resolve().parents[1]
        return {
            'island': (repo / 'qml/panels/ActivityIsland.qml').read_text(),
            'loader': (repo / 'qml/components/SlideLoader.qml').read_text(),
            'shell': (repo / 'shell.qml').read_text(),
            'elasticity': (repo / 'qml/components/PopupElasticity.qml').read_text(),
        }

    def test_size_springs_follow_the_flight_instead_of_the_mount_state(self):
        source = self.sources()['island']
        # A close mid-expansion must retarget compact immediately: the island
        # shrinks with the exit instead of still growing while it leaves.
        self.assertIn('target: root.mounted && (root.shown || root.warmupActive) ? root.expandedWidth : root.compactWidth', source)
        self.assertIn('target: root.mounted && (root.shown || root.warmupActive) ? root.expandedHeight : 30', source)
        # The old latch (expanded until park) is exactly the ESC-race regression.
        self.assertNotIn('target: root.mounted && !root.dormant ? root.expandedWidth : root.compactWidth', source)

    def test_warm_pass_renders_the_tree_at_open_geometry_then_rewinds(self):
        source = self.sources()['island']
        # Dormant trees are invisible, which would skip the warm render entirely.
        self.assertIn('visible: mounted && (!dormant || warmupActive)', source)
        # Springs would still be mid-expansion during the few forced frames, so
        # the pass snaps to the open geometry and rewinds to the compact park.
        self.assertRegex(source, r'onWarmupActiveChanged: \{[\s\S]*?widthSpring\.snapTo\(root\.expandedWidth\)[\s\S]*?heightSpring\.snapTo\(root\.expandedHeight\)')
        self.assertRegex(source, r'else \{ widthSpring\.snapTo\(root\.compactWidth\); heightSpring\.snapTo\(30\); \}')

    def test_loader_defers_and_retires_the_warm_pass_correctly(self):
        source = self.sources()['loader']
        # A busy stage defers the pass instead of dropping it for the session.
        self.assertIn('if (panelOpen || activityOpen) return;', source)
        self.assertNotIn('if (panelOpen || activityOpen) { controlWarmupPending = false; return; }', source)
        # A real open during the pass parks first (full entrance flight) and
        # retires the warm-up because the tree renders live anyway.
        self.assertRegex(source, r'function move\(to\) \{[\s\S]*?if \(warmupActive\) \{ warmupPark\(\); opacity = 1; layer\.enabled = false; warmupActive = false; controlWarmupPending = false; controlWarmupDone = true; \}')
        self.assertRegex(source, r'onLoaded: \{[\s\S]*?controlWarmupPending = false; controlWarmupDone = true;')
        # Jelly elasticity keeps its layer live for the invisible pass.
        elasticity = self.sources()['elasticity']
        self.assertRegex(elasticity, r'property bool warmup: false')
        self.assertRegex(elasticity, r'rendering: engaged && \(warmup \|\| shape\.running \|\| Math\.abs\(strain\) > \.00002\)')

    def test_shell_wires_the_island_warmup_as_viewport_only(self):
        source = self.sources()['shell']
        # The overlay surface must stay a quiet 1x1 sliver during the pass.
        self.assertIn('(activityIsland.visible && !activityIsland.warmupActive)', source)
        # The viewport reserves the island frame for the invisible render.
        self.assertIn('if (activityIsland.mounted && !activityIsland.dormant || activityIsland.warmupActive) {', source)
        # The prewarm mounts the island dormant after the control center settles,
        # and measurement suites can opt out of the startup burst entirely.
        self.assertRegex(source, r'Timer \{\s*interval: 6500[\s\S]*?LME_SHELL_NO_PREWARM[\s\S]*?activityIsland\.retainedContent = activityIsland\.content; activityIsland\.mounted = true;')
        # Load and park hooks start the pass; an all-closed stage retries deferred ones.
        self.assertRegex(source, r'function onLoaded\(\) \{ Qt\.callLater\(\(\) => activityIsland\.startControlWarmup\(ShellState\.panelOpen, ShellState\.activityOpen\)\); \}')


@unittest.skipUnless(os.environ.get('LME_TEST_MOTION_UI') == '1', 'private QML motion checks')
class IslandFlightQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_midflight_close_reverses_the_morph_and_parks_quickly(self):
        result = self.run_qml('import "qml/panels"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property int frames: 0
    property int closeFrame: 0
    property real peakWidth: 0
    property real exitWidth: -1
    property var checks: ({})
    FloatingWindow { implicitWidth: 1000; implicitHeight: 900
        Item { width: 1000; height: 900; ActivityIsland { id: island } }
    }
    FrameAnimation { running: true; onTriggered: {
        fixture.frames++;
        if (island.mounted && !island.dormant && island.shown) fixture.peakWidth = Math.max(fixture.peakWidth, island.width);
        if (fixture.phase === 2 && fixture.exitWidth < 0 && fixture.frames > fixture.closeFrame + 10) fixture.exitWidth = island.width;
    } }
    Timer { interval: 60; running: true; repeat: true; onTriggered: {
        if (++fixture.ticks > 240) { fixture.finish({timeout: fixture.phase}); return; }
        if (!ShellState.backendReady) return;
        if (fixture.phase === 0) { ShellState.activityOpen = true; fixture.phase++; }
        else if (fixture.phase === 1 && island.item && island.progress > .05 && island.progress < .95) { ShellState.closePanels(); fixture.closeFrame = fixture.frames; fixture.phase++; }
        else if (fixture.phase === 2 && island.dormant) {
            fixture.checks.reversed = fixture.exitWidth >= 0 && fixture.exitWidth < fixture.peakWidth - 40;
            fixture.checks.quick = (fixture.frames - fixture.closeFrame) * 17 < 1500;
            fixture.checks.parked = island.mounted && island.dormant && !island.visible;
            fixture.checks.rewound = Math.abs(island.width - island.compactWidth) < 1 && Math.abs(island.height - 30) < 1;
            fixture.finish(fixture.checks);
        }
    } }
''')
        self.assertEqual(result, dict(reversed=True, quick=True, parked=True, rewound=True))

    def test_control_warmup_renders_expanded_and_leaves_a_clean_park(self):
        result = self.run_qml('import "qml/panels"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property var warm: ({})
    property var checks: ({})
    FloatingWindow { implicitWidth: 1000; implicitHeight: 900
        Item { width: 1000; height: 900; ActivityIsland { id: island } }
    }
    // The warm pass lasts only a few frames; sample it per frame or the
    // polling timer can miss the whole window.
    FrameAnimation { running: true; onTriggered: {
        if (fixture.phase === 1 && island.warmupActive) {
            fixture.warm = {width: island.width, height: island.height, opacity: island.opacity, visible: island.visible};
            fixture.phase = 2;
        }
    } }
    Timer { interval: 60; running: true; repeat: true; onTriggered: {
        if (++fixture.ticks > 240) { fixture.finish({timeout: fixture.phase}); return; }
        if (!ShellState.backendReady) return;
        if (fixture.phase === 0) { island.controlWarmupPending = true; island.dormant = true; island.retainedContent = island.content; island.mounted = true; fixture.phase++; }
        else if (fixture.phase === 2 && !island.warmupActive && island.controlWarmupDone) {
            fixture.checks.warmGeometry = fixture.warm.width > island.compactWidth + 200 && fixture.warm.height > 200;
            fixture.checks.invisible = fixture.warm.opacity === 0 && fixture.warm.visible === true;
            fixture.checks.restored = island.opacity === 1 && !island.visible && island.dormant;
            fixture.checks.rewound = Math.abs(island.width - island.compactWidth) < 1 && Math.abs(island.height - 30) < 1;
            ShellState.activityOpen = true; fixture.phase++;
        } else if (fixture.phase === 3 && island.progress === 1 && Math.abs(island.width - island.expandedWidth) < 5) {
            fixture.checks.reopen = Math.abs(island.height - island.expandedHeight) < 5;
            ShellState.closePanels(); fixture.phase++;
        } else if (fixture.phase === 4 && island.dormant) {
            fixture.finish(fixture.checks);
        }
    } }
''')
        self.assertEqual(result, dict(warmGeometry=True, invisible=True, restored=True, rewound=True, reopen=True))
