"""Issue #77 idle gates: zero JS when unhovered+static, rebuild no-ops without warps."""
import os
import unittest
from pathlib import Path
import test_local_qml as qml_tests
from test_backend import Fixture
from unittest.mock import patch


class IdleGateSourceCase(unittest.TestCase):
    def test_dirty_gate_in_glass_material(self):
        text = (Path(__file__).resolve().parents[1] / 'qml/components/GlassMaterial.qml').read_text()
        self.assertIn('property bool dirty', text)
        self.assertIn('if (!root.dirty) return', text)
        self.assertIn('FrameLogger.sample', text)
        self.assertIn('pointer.hovered || root.hoverAmount', text)


class IdleGatePrefsCase(Fixture, unittest.TestCase):
    def test_reduced_transparency_round_trips(self):
        patcher = patch('liquid_glass.probe_niri_version', return_value=(26, 4))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.preferences.set('reducedTransparency', True)
        from test_backend import backend
        self.assertTrue(backend.Preferences(self.preferences.path).values['reducedTransparency'])


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'private idle QML')
class IdleGateQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_unhovered_static_zero_sample_calls(self):
        result = self.run_qml('import QtQuick\nimport "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    property int phase: 0
    property int ticks: 0
    property int baseline: -1
    property var checks: ({})
    FloatingWindow { implicitWidth: 640; implicitHeight: 480
        GlassMaterial { id: mat; width: 200; height: 120; x: 50; y: 50 }
        SurfaceBlurRegion { id: region; surface: mat; popup: false }
    }
    Timer { interval: 30; repeat: true; running: true; onTriggered: {
        if (++fixture.ticks > 400) { fixture.finish({timeout: fixture.phase, checks: fixture.checks, sampleCalls: mat.sampleCalls, active: mat.active}); return; }
        if (!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if (fixture.phase === 0 && !Theme.liquidGlass) { ShellState.run("setting",{key:"surfaceStyle",value:"liquid"}); fixture.phase = 1; }
        else if (fixture.phase === 1 && mat.active && mat.backdrop !== null) { fixture.ticks = 0; fixture.phase = 2; }
        else if (fixture.phase === 2 && fixture.ticks > 30) { fixture.baseline = mat.sampleCalls; fixture.ticks = 0; fixture.phase = 3; }
        else if (fixture.phase === 3 && fixture.ticks > 60) {
            fixture.checks.zero = mat.sampleCalls === fixture.baseline;
            region.rebuild();
            fixture.checks.bands = region.bandCapacity === 0;
            mat.width = 210;
            fixture.phase = 4;
        } else if (fixture.phase === 4 && mat.sampleCalls > fixture.baseline) {
            fixture.checks.dirtyWorks = true;
            fixture.finish(fixture.checks);
        }
    }}
''', {'QT_QPA_PLATFORM': 'wayland', 'QT_QUICK_BACKEND': 'rhi', 'QSG_RHI_BACKEND': 'opengl', 'LIBGL_ALWAYS_SOFTWARE': '1'})
        self.assertEqual(result.get('zero'), True)
        self.assertEqual(result.get('bands'), True)
        self.assertEqual(result.get('dirtyWorks'), True)
