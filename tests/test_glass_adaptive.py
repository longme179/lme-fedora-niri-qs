"""Adaptive tint bounded compensation (issue #76): white darkens, dark clears."""
import unittest
from pathlib import Path


def glass_adaptive_tint(tA, l):
    c = max(0.0, min(1.0, l))
    raw = tA * (0.75 + 0.75 * c)
    bounded = max(0.7 * tA, min(raw, min(1.6 * tA, 0.9)))
    return max(0.0, min(1.0, bounded))


class GlassAdaptiveTintCase(unittest.TestCase):
    def glass_contrast_floor(self, alpha, l, tint_lum, yield_mode=False):
        floor = 0.0 if l <= 0.30 or tint_lum >= l else (l - 0.30) / (l - tint_lum)
        return max(alpha, min(floor, 0.30 if yield_mode else 0.75))

    def test_bright_darkens_and_dark_clears(self):
        tA = 0.4
        white = glass_adaptive_tint(tA, 0.95)
        dark = glass_adaptive_tint(tA, 0.05)
        self.assertGreater(white, tA)
        self.assertLess(dark, tA)

    def test_bounds_respected(self):
        for tA in (0.0, 0.1, 0.5, 0.8, 1.0):
            for l in (0.0, 0.5, 1.0):
                out = glass_adaptive_tint(tA, l)
                self.assertGreaterEqual(out, 0.7 * tA)
                self.assertLessEqual(out, min(1.6 * tA, 0.9))
                self.assertGreaterEqual(out, 0.0)
                self.assertLessEqual(out, 1.0)

    def test_qml_mirror_and_shader_wiring(self):
        root = Path(__file__).resolve().parents[1]
        theme = (root / 'qml/theme/Theme.qml').read_text()
        self.assertIn('function glassAdaptiveTint', theme)
        self.assertIn('function glassContrastFloor', theme)
        self.assertIn('yieldMode', theme)
        self.assertIn('adaptiveContrast', theme)
        frag = (root / 'qml/components/shaders/liquid-glass.frag').read_text()
        self.assertIn('adaptiveContrast', frag)
        self.assertIn('tFloor', frag)
        settings = (root / 'qml/settings/LiquidGlassSettings.qml').read_text()
        self.assertIn('adaptiveContrast', settings)

    def test_contrast_floor_white_and_dark(self):
        out = self.glass_contrast_floor(0.1, 0.95, 0.1)
        self.assertGreaterEqual(out, min((0.95 - 0.30) / (0.95 - 0.1), 0.75) - 1e-9)
        self.assertLessEqual(out, 0.75)
        dark = self.glass_contrast_floor(0.2, 0.05, 0.1)
        self.assertEqual(dark, 0.2)

    def test_contrast_floor_yield_cap(self):
        normal = self.glass_contrast_floor(0.1, 0.95, 0.1)
        yielded = self.glass_contrast_floor(0.1, 0.95, 0.1, yield_mode=True)
        self.assertLessEqual(yielded, 0.30)
        self.assertLessEqual(yielded, normal)
        self.assertGreaterEqual(yielded, 0.1)
        self.assertLessEqual(normal, 0.75)


if __name__ == '__main__':
    unittest.main()
