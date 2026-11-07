"""Glass stays cheap when static; reduced transparency survives persistence."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch
import test_local_qml as qml_tests
from test_backend import Fixture
import desktop_backend as backend


class IdleGateSourceCase(unittest.TestCase):
    def test_glass_material_has_hover_frame_logging(self):
        text = (Path(__file__).resolve().parents[1] / 'qml/components/GlassMaterial.qml').read_text()
        self.assertIn('FrameLogger.sample', text)
        self.assertIn('pointer.hovered || root.hoverAmount', text)


class IdleGatePrefsCase(Fixture, unittest.TestCase):
    def test_reduced_transparency_round_trips(self):
        self.preferences.set('reducedTransparency', True)
        self.assertTrue(backend.Preferences(self.preferences.path).values['reducedTransparency'])


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1', 'private idle QML')
class IdleGateQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_liquid_glass_activates_without_backdrop(self):
        result = self.run_qml('import QtQuick\nimport "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    property int phase: 0
    property int ticks: 0
    property var checks: ({})
    FloatingWindow { implicitWidth: 640; implicitHeight: 480
        GlassMaterial { id: mat; width: 200; height: 120; x: 50; y: 50 }
    }
    Timer { interval: 30; repeat: true; running: true; onTriggered: {
        if (++fixture.ticks > 300) { fixture.finish({timeout: fixture.phase, checks: fixture.checks, active: mat.active}); return; }
        if (!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if (fixture.phase === 0 && !Theme.liquidGlass) { ShellState.run("setting",{key:"surfaceStyle",value:"liquid"}); fixture.phase = 1; }
        else if (fixture.phase === 1 && mat.active) { fixture.checks.active = true; fixture.phase = 2; }
        else if (fixture.phase === 2) { ShellState.run("setting",{key:"surfaceStyle",value:"smoked"}); fixture.phase = 3; }
        else if (fixture.phase === 3 && !Theme.liquidGlass) { fixture.checks.smoked = !mat.active; fixture.finish(fixture.checks); }
    }}
''', {'QT_QPA_PLATFORM': 'wayland', 'QT_QUICK_BACKEND': 'rhi', 'QSG_RHI_BACKEND': 'opengl', 'LIBGL_ALWAYS_SOFTWARE': '1'})
        self.assertEqual(result.get('active'), True)
        self.assertEqual(result.get('smoked'), True)
