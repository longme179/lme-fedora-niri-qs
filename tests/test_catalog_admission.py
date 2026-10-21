"""Admission parity and a zero-Python hit path, without any real user session."""
import json
from pathlib import Path
import tempfile
import unittest

from catalog_admission_fixture import Checkout, LEGACY


class AdmissionCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='admission-')
        self.addCleanup(self.temp.cleanup)
        self.copy = Checkout(Path(self.temp.name)/'checkout')

    def parity(self, pages):
        for page in pages:
            with self.subTest(page=page):
                expected = self.copy.python('--page', page, *LEGACY)
                actual = self.copy.shell(page)
                self.assertEqual((actual.returncode, actual.stderr), (expected.returncode, expected.stderr))
                self.assertEqual(actual.stdout, 'accepted:'+page+'\n' if expected.returncode == 0 else '')

    def test_enabled_keys_and_prefix_substring_keys_match_python(self):
        self.parity(['sample', 'sampleLong', 'Case_2-X', 'sam', 'ample', 'sampleLon', 'sampleLonger'])

    def test_bar_and_preference_keys_are_not_pages(self):
        self.parity(['barOnly', 'preferenceOnly', 'preferenceFeature'])

    def test_disabled_entry_matches_python(self):
        self.parity(['disabled'])

    def test_missing_malformed_and_empty_index_match_python(self):
        self.copy.index.unlink(); self.parity(['sample', 'absent'])
        for text in ('{invalid', '{"version":2,"features":[]}', '{"version":1,"features":[]}\n'):
            self.copy.index.write_text(text); self.parity(['sample', 'absent'])

    def test_legacy_pages_match_python_even_with_broken_index(self):
        self.copy.index.write_text('{broken')
        self.parity(LEGACY)

    def test_check_accepts_canonical_and_rejects_format_that_can_hide_a_key(self):
        self.assertEqual(self.copy.python('--check').returncode, 0)
        original = self.copy.index.read_text()
        invalid = [json.dumps(json.loads(original)), original.replace('"key":"sample"', '"key":"\\u0073ample"')]
        record = self.copy.records[0]
        page = record['startup']['settingsPage']; page['key'] = page.pop('key')
        self.copy.save(); invalid.append(self.copy.index.read_text())
        for text in invalid:
            with self.subTest(text=text[:80]):
                self.copy.index.write_text(text)
                result = self.copy.python('--check')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('Feature catalog:', result.stderr)

    def test_check_rejects_unsafe_page_keys(self):
        for key in ('bad.key', 'bad/key', 'bad key', 'bad"key', 'badé'):
            with self.subTest(key=key):
                page = self.copy.records[0]['startup']['settingsPage']; page['key'] = key
                descriptor = self.copy.root/self.copy.records[0]['descriptor']
                body = json.loads(descriptor.read_text()); body['settingsPage']['key'] = key
                descriptor.write_text(json.dumps(body)); self.copy.save()
                self.assertEqual(self.copy.python('--check').returncode, 1)

    def test_check_requires_page_keys_in_startup_summary(self):
        self.copy.records[0].pop('startup'); self.copy.save()
        result = self.copy.python('--check')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('Feature catalog:', result.stderr)

    def test_copied_checkout_traces_zero_catalog_python_for_legacy_and_catalog_hits(self):
        fixture = Checkout(Path(self.temp.name)/'full', full=True)
        for page in [*LEGACY, 'sample', 'sampleLong', 'Case_2-X']:
            with self.subTest(page=page):
                self.assertEqual(fixture.shell(page).returncode, 0)
                self.assertEqual(fixture.calls(), [], 'Catalog Python ran on a page hit')
        self.assertEqual(fixture.shell('absent').returncode, 2)
        self.assertEqual(len(fixture.calls()), 1, 'Tracing must observe the Python MISS fallback')
        self.assertIn('feature_catalog.py --page absent', fixture.calls()[0])
