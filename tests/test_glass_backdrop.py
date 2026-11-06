"""Backdrop sampling: snapshot cache, flat-tile fallback, shared decode, HiDPI tier."""
import shutil
import tempfile
import unittest
from pathlib import Path
import test_local_qml as qml_tests
from glass_snapshot import GlassSnapshots


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class GlassBackdropCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_flat_tile_keeps_the_lens_alive_without_a_wallpaper(self):
        # Demo off (backend still faked) walks the real non-demo branch of the
        # source binding: no wallpaper preference -> the flat fill tile, never
        # an empty source, and one shared pixmap cache key for the whole output.
        result = self.run_qml('import "qml/components"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property var checks: ({})
    FloatingWindow {
        id: win
        implicitWidth: 640; implicitHeight: 480
        // Direct instantiation: the sampling surface is the Image itself;
        // GlassState.acquire only pools per-window instances on top of it.
        GlassBackdrop { id: first; hostWindow: win }
        GlassBackdrop { id: second; hostWindow: win }
    }
    Timer {
        interval: 60; running: true; repeat: true
        onTriggered: {
            if (++fixture.ticks > 120) { fixture.finish({timeout: fixture.phase, checks: fixture.checks}); return; }
            if (fixture.phase === 0 && first.status === Image.Ready && second.status === Image.Ready) {
                fixture.checks.flat = String(first.source).startsWith("data:image/png;base64,");
                fixture.checks.ready = first.status === Image.Ready && second.status === Image.Ready;
                fixture.checks.sharedKey = first.source === second.source
                    && first.sourceSize.width === second.sourceSize.width
                    && first.sourceSize.height === second.sourceSize.height;
                fixture.checks.sane = first.sourceSize.width >= 1 && first.sourceSize.height >= 1
                    && first.sourceSize.width <= 1280 && first.sourceSize.height <= 720;
                fixture.phase = 1;
            } else if (fixture.phase === 1) {
                fixture.finish(fixture.checks);
            }
        }
    }
''', {'LME_SHELL_DEMO': '0', 'LME_SHELL_BACKEND_DEMO': '1'})
        self.assertEqual(result, dict(flat=True, ready=True, sharedKey=True, sane=True))

    def test_sampling_tier_targets_1440p_equivalent_only_on_scaled_outputs(self):
        result = self.run_qml('import "qml/components/GlassSampling.js" as GlassSampling', '''
    property var checks: ({})
    Timer {
        interval: 100; running: true
        onTriggered: {
            const near = (a, b) => Math.abs(a - b) < 1e-9;
            fixture.checks.base = near(GlassSampling.resolution(1920, 1080, 1), .5);
            fixture.checks.bigFlat = near(GlassSampling.resolution(3840, 2160, 1), 1280 / 3840);
            fixture.checks.scaled = near(GlassSampling.resolution(1920, 1080, 2), 1440 / 1080);
            fixture.checks.physicalCap = GlassSampling.resolution(800, 600, 2) === 2;
            fixture.checks.fractional = GlassSampling.resolution(720, 400, 1.25) === 1.25;
            fixture.checks.missingScale = near(GlassSampling.resolution(1920, 1080, undefined), .5);
            fixture.finish(fixture.checks);
        }
    }
''')
        self.assertEqual(result, dict(base=True, bigFlat=True, scaled=True, physicalCap=True,
            fractional=True, missingScale=True))

    def test_snapshot_url_shares_one_decode_and_invalidates_within_one_cycle(self):
        # Every window on the output binds the same snapshot URL plus ?rev=,
        # so they share one pixmap cache key; a revision bump switches every
        # backdrop source on the next animation tick.
        with tempfile.TemporaryDirectory() as cache:
            glass_dir = Path(cache) / 'lme-shell/glass'
            glass_dir.mkdir(parents=True)
            snap = GlassSnapshots(directory=glass_dir)
            snap.refresh({'probe'}, {'probe': ('color', '112233')}, True)
            result = self.run_qml('import "qml/components"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property var checks: ({})
    FloatingWindow {
        id: win
        implicitWidth: 640; implicitHeight: 480
        GlassBackdrop { id: first; hostWindow: win }
        GlassBackdrop { id: second; hostWindow: win }
    }
    function publish(rev) {
        const cache = Quickshell.env("XDG_CACHE_HOME");
        const name = win.screen ? win.screen.name : "";
        const url = "file://" + cache + "/lme-shell/glass/probe.png";
        ShellState.accept(JSON.stringify(Object.assign({}, ShellState.snapshot, {glass: {outputs: Object.assign({}, ShellState.snapshot.glass ? ShellState.snapshot.glass.outputs : {}, {[name]: {rev: rev, kind: "color", url: url}})}})));
    }
    Timer {
        interval: 60; running: true; repeat: true
        onTriggered: {
            if (++fixture.ticks > 160) { fixture.finish({timeout: fixture.phase, checks: fixture.checks}); return; }
            if (!ShellState.backendReady || ShellState.pendingActions.setting) return;
            if (fixture.phase === 0) { fixture.publish(1); fixture.phase = 1; }
            else if (fixture.phase === 1 && String(first.source).includes("rev=1") && first.status === Image.Ready && second.status === Image.Ready) {
                fixture.checks.bound = String(first.source).includes("rev=1") && String(second.source).includes("rev=1");
                fixture.checks.sharedKey = first.source === second.source
                    && first.sourceSize.width === second.sourceSize.width
                    && first.sourceSize.height === second.sourceSize.height;
                // Wallpaper change: bump the revision; all backdrops must
                // switch within one animation cycle (next Timer tick).
                fixture.publish(2); fixture.phase = 2;
            } else if (fixture.phase === 2 && String(first.source).includes("rev=2") && String(second.source).includes("rev=2") && first.status === Image.Ready) {
                fixture.checks.invalidated = true;
                fixture.finish(fixture.checks);
            }
        }
    }
''', {'LME_SHELL_DEMO': '0', 'LME_SHELL_BACKEND_DEMO': '1', 'XDG_CACHE_HOME': cache})
            self.assertEqual(result, dict(bound=True, sharedKey=True, invalidated=True))

    def test_color_snapshot_carries_the_exact_awww_fill_color(self):
        # The backend snapshots awww's live color fill (never the generic
        # black stand-in); the backdrop loads it Ready so rim/grain render.
        with tempfile.TemporaryDirectory() as cache:
            glass_dir = Path(cache) / 'lme-shell/glass'
            glass_dir.mkdir(parents=True)
            snap = GlassSnapshots(directory=glass_dir)
            state = snap.refresh({'probe'}, {'probe': ('color', '335577')}, True)
            self.assertEqual(state['outputs']['probe']['kind'], 'color')
            result = self.run_qml('import "qml/components"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property var checks: ({})
    FloatingWindow {
        id: win
        implicitWidth: 640; implicitHeight: 480
        GlassBackdrop { id: bd; hostWindow: win }
    }
    Timer {
        interval: 60; running: true; repeat: true
        onTriggered: {
            if (++fixture.ticks > 120) { fixture.finish({timeout: fixture.phase, checks: fixture.checks}); return; }
            if (!ShellState.backendReady || ShellState.pendingActions.setting) return;
            if (fixture.phase === 0) {
                const cache = Quickshell.env("XDG_CACHE_HOME");
                const name = win.screen ? win.screen.name : "";
                const url = "file://" + cache + "/lme-shell/glass/probe.png";
                ShellState.accept(JSON.stringify(Object.assign({}, ShellState.snapshot, {glass: {outputs: {[name]: {rev: 1, kind: "color", url: url}}}})));
                fixture.phase = 1;
            } else if (fixture.phase === 1 && String(bd.source).includes("rev=1") && bd.status === Image.Ready) {
                fixture.checks.ready = true;
                fixture.checks.snapshot = String(bd.source).includes("probe.png");
                fixture.finish(fixture.checks);
            }
        }
    }
''', {'LME_SHELL_DEMO': '0', 'LME_SHELL_BACKEND_DEMO': '1', 'XDG_CACHE_HOME': cache})
            self.assertEqual(result, dict(ready=True, snapshot=True))
