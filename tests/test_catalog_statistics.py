"""Guard measurement arithmetic; production-independent characterization."""
import unittest
from catalog_statistics import compare, describe, mann_whitney


class CatalogStatisticsCase(unittest.TestCase):
    def test_identical_arms_and_constant_shift_have_known_intervals(self):
        base = list(range(30))
        self.assertEqual(compare(base, base)['ci95_ms'], [0, 0])
        shifted = compare(base, [value+12 for value in base])
        self.assertEqual((shifted['delta_ms'], shifted['ci95_ms']), (12, [12, 12]))
        self.assertEqual(mann_whitney([1]*30, [1]*30), 1)
        self.assertLess(mann_whitney(list(range(30)), list(range(100, 130))), 1e-9)

    def test_reported_difference_is_difference_of_medians(self):
        self.assertEqual(compare([0, 1, 100], [0, 100, 101])['delta_ms'], 99)
        self.assertEqual(describe([0, 1, 2, 3]), dict(median_ms=1.5, min_ms=0, max_ms=3, iqr_ms=1.5))
