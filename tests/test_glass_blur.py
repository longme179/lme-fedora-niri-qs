"""Compositor blur snippet: always xray false, version/ownership guarded, retired keys dropped."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import liquid_glass
from test_backend import Fixture, FakeRunner, backend


def marker():
    return liquid_glass.MARKER


class GlassBlurCase(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'),
            XDG_STATE_HOME=str(self.root/'state'), XDG_RUNTIME_DIR=str(self.root/'runtime'))
        env.start(); self.addCleanup(env.stop)
        probe = patch('liquid_glass.probe_niri_version', return_value=(26, 4))
        probe.start(); self.addCleanup(probe.stop)

    def test_snippet_has_xray_false_and_passes_offset(self):
        text = liquid_glass.snippet({'passes': 3, 'offset': 2.5})
        self.assertTrue(text.startswith(marker()))
        self.assertEqual(text.count('xray false'), 2)
        self.assertNotIn('xray true', text)
        self.assertIn('passes 3', text)
        self.assertIn('offset 2.5', text)
        self.assertIn('match namespace="^lme-(bar|overlay|authentication|desktop|notifications|osd)$"', text)
        self.assertIn('match app-id="^lme-shell-settings$"', text)

    def test_version_refusal_writes_nothing(self):
        with patch('liquid_glass.probe_niri_version', return_value=(25, 11)):
            with self.assertRaises(ValueError) as exc:
                liquid_glass.apply_blur(self.root/'config/lme-shell', liquid_glass.DEFAULTS)
        self.assertIn('26.04', str(exc.exception))
        self.assertFalse((self.root/'config/lme-shell/liquid-blur.kdl').exists())
        with patch('liquid_glass.probe_niri_version', return_value=None):
            with self.assertRaises(ValueError):
                liquid_glass.apply_blur(self.root/'config/lme-shell', liquid_glass.DEFAULTS)
        self.assertFalse((self.root/'config/lme-shell/liquid-blur.kdl').exists())

    def test_marker_and_ownership_refusal(self):
        folder = self.root/'config/lme-shell'
        folder.mkdir(parents=True)
        path = folder/'liquid-blur.kdl'
        path.write_text('user-owned')
        with self.assertRaises(ValueError) as exc:
            liquid_glass.apply_blur(folder, liquid_glass.DEFAULTS)
        self.assertIn('Refusing to replace', str(exc.exception))
        self.assertEqual(path.read_text(), 'user-owned')
        target = self.root/'target.kdl'; target.write_text('target')
        path.unlink(); path.symlink_to(target)
        with self.assertRaises(ValueError):
            liquid_glass.apply_blur(folder, liquid_glass.DEFAULTS)
        self.assertEqual(target.read_text(), 'target')
        path.unlink(); path.write_text(marker() + 'old\n')
        liquid_glass.apply_blur(folder, liquid_glass.DEFAULTS)
        self.assertIn('xray false', path.read_text())

    def test_validate_drops_retired_keys_and_preserves_survivors(self):
        result = liquid_glass.validate({'tint': '#112233', 'opacity': 0.8, 'blur': 2, 'blurPreset': 'true', 'appliedBlur': 'frosted'})
        self.assertEqual(result['tint'], '#112233')
        self.assertEqual(result['opacity'], 0.8)
        for key in ('blur', 'blurPreset', 'appliedBlur'):
            self.assertNotIn(key, result)
        with self.assertRaises(ValueError):
            liquid_glass.validate({'notARealKey': 1})

    def test_apply_records_nothing_and_backend_action_writes(self):
        preferences = backend.Preferences(self.root/'state/settings.json')
        live = self.make_backend(FakeRunner(available={}), demo=False)
        for owner in (live.charge_executor, live.feature_executor, live.weather, live.capture, live.mirror):
            self.addCleanup(owner.shutdown if hasattr(owner, 'shutdown') else owner.close)
        live.preferences.set('liquidGlass', {'passes': 4, 'offset': 2.0})
        result = live.handle(dict(action='glassBlurApply'))
        self.assertTrue(result.get('ok'), result)
        path = live.preferences.path.parent/'liquid-blur.kdl'
        self.assertTrue(path.is_file())
        self.assertIn('xray false', path.read_text())
        self.assertIn('passes 4', path.read_text())
        self.assertNotIn('appliedBlur', live.preferences.values['liquidGlass'])
        self.assertNotIn('blurPreset', live.preferences.values['liquidGlass'])
