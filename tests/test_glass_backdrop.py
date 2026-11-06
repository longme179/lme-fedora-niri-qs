"""Backdrop sampling: flat-tile fallback, shared decode key, HiDPI tier."""
import shutil
import unittest
import test_local_qml as qml_tests


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
