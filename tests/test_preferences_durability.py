"""Settings survive corruption, unknown keys and oversized numbers.
Contract: test_preferences_durability.py covers preferences_durability behavior/contracts; check imports for fixtures/helpers under test.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import desktop_backend as backend


class PreferencesDurabilityCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'settings.json'

    def test_truncated_file_is_left_untouched_and_update_refuses(self):
        self.path.write_text('{"accent": "#123456", "opacity":')
        preferences = backend.Preferences(self.path)
        before = self.path.read_bytes()
        with self.assertRaises(backend.CommandError):
            preferences.update({'opacity': 0.8})
        self.assertEqual(self.path.read_bytes(), before)

    def test_oversized_integer_is_rejected_instead_of_crashing(self):
        self.path.write_text('{"motionSpeed": ' + '9' * 400 + '}')
        preferences = backend.Preferences(self.path)  # startup must not raise
        self.assertEqual(preferences.values['motionSpeed'], backend.DEFAULT_PREFERENCES['motionSpeed'])
        with self.assertRaises(ValueError):
            backend.validate_preference('motionSpeed', 10 ** 400)

    def test_unknown_keys_survive_an_unrelated_update(self):
        self.path.write_text(json.dumps({'accent': '#123456', 'futureSetting': {'a': 1}}))
        preferences = backend.Preferences(self.path)
        preferences.update({'opacity': 0.8})
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved['accent'], '#123456')
        self.assertEqual(saved['futureSetting'], {'a': 1})
        self.assertEqual(saved['opacity'], 0.8)

    def test_invalid_known_value_keeps_its_default_and_valid_neighbours(self):
        self.path.write_text(json.dumps({'opacity': 'not-a-number', 'shellName': 'Mine'}))
        preferences = backend.Preferences(self.path)
        self.assertEqual(preferences.values['shellName'], 'Mine')
        self.assertEqual(preferences.values['opacity'], backend.DEFAULT_PREFERENCES['opacity'])

    def test_missing_file_still_writes_and_keeps_unknown_keys_next_time(self):
        preferences = backend.Preferences(self.path)
        preferences.update({'shellName': 'Mine'})
        self.assertEqual(json.loads(self.path.read_text())['shellName'], 'Mine')
        saved = json.loads(self.path.read_text())
        saved['futureSetting'] = 7
        self.path.write_text(json.dumps(saved))
        preferences.update({'opacity': 0.7})
        self.assertEqual(json.loads(self.path.read_text())['futureSetting'], 7)
