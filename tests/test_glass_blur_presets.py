"""Issue #75: blur preset snippets, niri version gate and the applied marker."""
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from test_backend import Fixture, backend
import liquid_glass
from liquid_glass import DEFAULTS, MARKER
import test_local_qml as qml_tests


class GlassBlurPresetCase(Fixture, unittest.TestCase):
    """Issue #75: frosted/true snippet generation, version gate, applied marker."""
    def setUp(self):
        super().setUp()
        patcher = patch('liquid_glass.probe_niri_version', return_value=(26, 4))
        patcher.start(); self.addCleanup(patcher.stop)

    def test_snippets_differ_only_in_the_documented_xray_direction(self):
        values = liquid_glass.validate({})
        frosted = liquid_glass.snippet('frosted', values)
        true = liquid_glass.snippet('true', values)
        self.assertEqual(frosted.replace('xray true', 'xray false'), true)
        self.assertEqual(frosted.count('xray true'), 2)
        self.assertEqual(true.count('xray false'), 2)
        self.assertTrue(frosted.startswith(MARKER))
        with self.assertRaises(ValueError):
            liquid_glass.snippet('sideways', values)

    def test_true_snippet_matches_the_bundled_popup_blur_rules(self):
        bundled = (Path(__file__).resolve().parents[1] / 'config/niri/popup-blur.kdl').read_text()
        rules = bundled[bundled.index('layer-rule {'):bundled.index('\nblur {')]
        true = liquid_glass.snippet('true', liquid_glass.validate({}))
        for line in rules.splitlines():
            if line.strip() and not line.lstrip().startswith('//'):
                self.assertIn(line, true)

    def test_apply_writes_preset_records_applied_and_honors_request(self):
        live = self.make_backend()
        path = self.preferences.path.parent / 'liquid-blur.kdl'
        self.assertNotIn('appliedBlur', live.preferences.values['liquidGlass'])
        result = live.handle(dict(action='glassBlurApply', preset='true'))
        self.assertTrue(result['ok'], result)
        self.assertIn('xray false', path.read_text())
        self.assertEqual(live.preferences.values['liquidGlass']['appliedBlur'], 'true')
        saved = backend.Preferences(self.preferences.path).values['liquidGlass']
        self.assertEqual(saved['appliedBlur'], 'true')
        self.assertEqual(saved['passes'], DEFAULTS['passes'])

    def test_version_refusal_writes_nothing_and_records_nothing(self):
        live = self.make_backend()
        path = self.preferences.path.parent / 'liquid-blur.kdl'
        for detected, fragment in (((25, 11), 'niri 25.11'), (None, 'no detectable niri')):
            with patch('liquid_glass.probe_niri_version', return_value=detected):
                result = live.handle(dict(action='glassBlurApply'))
            self.assertFalse(result['ok'], result)
            self.assertIn('niri 26.04+', result['message'])
            self.assertIn(fragment, result['message'])
            self.assertIn('not written', result['message'])
            self.assertFalse(path.exists())
            self.assertNotIn('appliedBlur', live.preferences.values['liquidGlass'])

    def test_preset_and_applied_tokens_validate_like_glass_controls(self):
        self.preferences.set('liquidGlass', 'true', token='blurPreset')
        self.assertEqual(self.preferences.values['liquidGlass']['blurPreset'], 'true')
        for token, value in (('blurPreset', 'xray'), ('blurPreset', None), ('appliedBlur', 'bogus'), ('appliedBlur', 1)):
            with self.subTest(token=token, value=value), self.assertRaises(ValueError):
                self.preferences.set('liquidGlass', value, token=token)


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI') == '1' and shutil.which('quickshell'), 'private glass hairline')
class GlassBlurPresetsQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_hairline_border_follows_the_applied_preset_and_smoked_is_untouched(self):
        result = self.run_qml('import "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    FloatingWindow { implicitWidth:600;implicitHeight:400
        GlassPanel { id:panel;width:300;height:120;anchors.centerIn:parent }
    }
    property int phase:0
    property int ticks:0
    property var checks:({})
    Timer { interval:80;running:true;repeat:true;onTriggered: {
        if(++fixture.ticks>120) { fixture.finish({timeout:fixture.phase,checks:fixture.checks});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});fixture.phase++; }
        else if(fixture.phase===1 && Theme.liquidGlass) {
            fixture.checks.unapplied=panel.border.width===0;fixture.phase++;
        } else if(fixture.phase===2) {
            ShellState.run("setting",{key:"liquidGlass",token:"appliedBlur",value:"frosted"});fixture.phase++;
        } else if(fixture.phase===3 && Theme.glass.appliedBlur==="frosted") {
            fixture.checks.applied=panel.border.width===1 && panel.border.color.toString()===Theme.border.toString();fixture.phase++;
        } else if(fixture.phase===4) {
            ShellState.run("setting",{key:"liquidGlass",value:{}});fixture.phase++;
        } else if(fixture.phase===5 && !Theme.glass.appliedBlur) {
            fixture.checks.cleared=panel.border.width===0;fixture.phase++;
        } else if(fixture.phase===6) {
            ShellState.run("setting",{key:"surfaceStyle",value:"smoked"});fixture.phase++;
        } else if(fixture.phase===7 && !Theme.liquidGlass) {
            fixture.checks.smoked=panel.border.width===1 && panel.border.color.toString()===Theme.outlineVariant.toString();
            fixture.finish(fixture.checks);
        }
    }}
''', {'QT_QPA_PLATFORM':'wayland'})
        self.assertEqual(result, dict(unapplied=True, applied=True, cleared=True, smoked=True))

