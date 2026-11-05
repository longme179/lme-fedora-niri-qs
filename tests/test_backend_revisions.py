"""Backend section revisions for QML identity reuse."""
import unittest

from test_backend import Fixture, FakeRunner


class BackendRevisionCase(Fixture, unittest.TestCase):
    def test_revisions_bump_only_when_their_section_changes(self):
        runner = FakeRunner(responses={('niri', 'msg', '--json', 'workspaces'): '[]',
                                       ('niri', 'msg', '--json', 'windows'): '[]'}, available={'niri'})
        live = self.make_backend(runner)
        state = live.snapshot()
        self.assertEqual(set(state['revisions']), {'apps', 'niri', 'preferences', 'launcherUsage'})
        self.assertTrue(all(type(value) is int and value >= 0 for value in state['revisions'].values()))

        niri = state['revisions']['niri']; launcher = state['revisions']['launcherUsage']
        again = live.snapshot()
        self.assertEqual(again['revisions']['niri'], niri)
        self.assertEqual(again['revisions']['launcherUsage'], launcher)

        live.niri_cache.invalidate()
        refreshed = live.snapshot()
        self.assertGreater(refreshed['revisions']['niri'], niri)

        preferences = refreshed['revisions']['preferences']
        live.preferences.update({'fontSize': 15})
        updated = live.snapshot()
        self.assertGreater(updated['revisions']['preferences'], preferences)

        apps = updated['revisions']['apps']
        live.last_app_scan = 0
        scanned = live.snapshot()
        self.assertGreater(scanned['revisions']['apps'], apps)

        usage = scanned['revisions']['launcherUsage']
        live.launcher_history.record('app.desktop')
        recorded = live.snapshot()
        self.assertGreater(recorded['revisions']['launcherUsage'], usage)


if __name__ == '__main__':
    unittest.main()
