"""Native lifecycle checks, without reducing visual effects or imposing VM budgets."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from render_lifetime_fixture import RenderWorld, close_settings
from release_session_fixture import sample


@unittest.skipUnless(os.environ.get('LME_TEST_RENDER_LIFETIME') == '1',
                     'private Wayland render resource lifetime')
class NativeRenderLifetimeCase(unittest.TestCase):
    def test_normal_settings_close_releases_its_processes_and_can_reopen(self):
        with tempfile.TemporaryDirectory(prefix='render-close-') as directory:
            world = RenderWorld(Path(directory))
            with world.launch() as main:
                main.wait(lambda s: s['workerReady'] and s['count'] == 2)
                initial, _ = sample(world, 'normal-close-main', 1, 1)
                for _ in range(2):
                    with world.launch('settings', page='appearance') as settings:
                        state = settings.wait(lambda s: s['visible'])
                        self.assertTrue(all(state['firstVisible'].values()))
                        self.assertFalse(state['started'])
                        opened, _ = sample(world, 'normal-close-Settings-open', 2, 2)
                        extra = {r['pid'] for r in opened} - {r['pid'] for r in initial}
                        self.assertEqual(len(extra), 2)
                        close_settings(settings)
                        self.assertEqual(settings.process.wait(timeout=8), 0)
                    closed, _ = sample(world, 'normal-close-Settings-closed', 1, 1)
                    self.assertEqual({r['pid'] for r in closed}, {r['pid'] for r in initial})
                    self.assertTrue(extra.isdisjoint({r['pid'] for r in closed}))
                    self.assertTrue(main.wait(lambda s: s['ready'])['ready'])

    def test_48_jelly_glass_panel_cycles_release_objects_and_layers(self):
        with tempfile.TemporaryDirectory(prefix='render-cycles-') as directory:
            world = RenderWorld(Path(directory))
            with world.launch() as main, world.launch('settings', page='appearance') as settings:
                main.wait(lambda s: s['workerReady'] and s['count'] == 2)
                initial, _ = sample(world, 'render-cycles-initial', 2, 2)
                counts = json.loads(main.call('lifetime'))
                self.assertFalse(counts['panelLayer'])
                self.assertFalse(counts['islandLayer'])
                for round_index in range(8):
                    for panel in ('clipboard', 'control', 'activity', 'notifications', 'launcher', 'power'):
                        main.call('toggle', panel, target='shell')
                        state = main.wait(lambda s: s['panelOpen'] and (
                            s['release']['activityMounted'] and s['release']['activityProgress'] >= .99
                            if panel == 'activity' else s['release']['mounted'] and s['progress'] >= .99))
                        self.assertEqual(state['release']['preset'], 'jelly-v2')
                        self.assertEqual(state['release']['style'], 'liquid')
                        self.assertGreater(json.loads(main.call('lifetime'))['material'], counts['material'])
                        main.call('close', target='shell')
                        state = main.wait(lambda s: not s['panelOpen'] and not s['release']['mounted']
                            and not s['release']['activityMounted'] and not s['release']['pending'])
                        self.assertEqual(json.loads(main.call('lifetime')), counts)
                    rows, _ = sample(world, 'render-cycles-round-'+str(round_index+1), 2, 2,
                                     ui=state['release'])
                    self.assertEqual({r['pid'] for r in rows}, {r['pid'] for r in initial})
                self.assertEqual(settings.call('openPage', 'clipboard', target='settings'), 'true')
                self.assertEqual(settings.call('startupPending', target='settings'), 'false')


if __name__ == '__main__': unittest.main()
