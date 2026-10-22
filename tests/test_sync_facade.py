"""The retained direct demo facade has no result payload for profile actions."""
import unittest
from test_backend import Fixture


class DemoFacadeCase(Fixture, unittest.TestCase):
    def test_profiles_return_none_and_keep_demo_preferences_in_memory(self):
        live = self.make_backend(demo=True)
        self.addCleanup(live.charge_executor.shutdown)
        self.addCleanup(live.feature_executor.shutdown)
        for action in ('appearanceSave', 'appearanceApply', 'appearanceDelete'):
            with self.subTest(action=action):
                self.assertIsNone(live.perform_demo(action, {'name': 'Facade fixture'}))
        self.assertFalse(self.preferences.path.exists())
