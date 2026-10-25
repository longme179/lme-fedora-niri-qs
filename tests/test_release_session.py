"""Bounded private Smoked/Liquid lifecycle verification; no laptop/GPU certification."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from release_session_fixture import ReleaseWorld, detached_jobs, owned_process, sample


@unittest.skipUnless(os.environ.get('LME_TEST_RELEASE_SESSION') == '1',
                     'private Wayland combined release session')
class NativeReleaseSessionCase(unittest.TestCase):
    def run_profile(self, style, rounds=3):
        with tempfile.TemporaryDirectory(prefix='release-session-') as directory:
            world = ReleaseWorld(Path(directory), style)
            with world.launch() as main:
                state = main.wait(lambda s: s['workerReady'] and s['started'] and s['count'] == 2)
                self.assertEqual(state['release']['style'], style)
                self.assertEqual(state['release']['preset'], 'jelly-v2')
                sample(world, style+'-steady', 1, 1)
                with world.launch('settings', page='appearance') as settings:
                    self.assertFalse(settings.wait(lambda s: s['ready'])['started'])
                    initial, _ = sample(world, style+'-Settings-open', 2, 2)
                    for page in ('behavior', 'clipboard', 'notifications', 'appearance'):
                        self.assertEqual(settings.call('openPage', page, target='settings'), 'true')
                        self.assertEqual(settings.call('startupPending', target='settings'), 'false')
                    for round_index in range(rounds):
                        for panel in ('clipboard', 'control', 'activity', 'notifications', 'launcher', 'power'):
                            main.call('toggle', panel, target='shell')
                            main.wait(lambda s: s['panelOpen'] and (s['release']['activityMounted']
                                and s['release']['activityProgress'] >= .99 if panel == 'activity'
                                else s['release']['mounted'] and s['progress'] >= .99))
                            main.call('close', target='shell')
                            state = main.wait(lambda s: not s['panelOpen'] and not s['release']['mounted']
                                              and not s['release']['activityMounted'] and not s['release']['pending'])
                            self.assertEqual(state['release']['pending'], [])
                        sample(world, style+'-after-panel-round-'+str(round_index+1), 2, 2, ui=state['release'])
                    after, _ = sample(world, style+'-after-'+str(rounds*6)+'-panel-cycles', 2, 2)
                    self.assertEqual({r['pid'] for r in initial}, {r['pid'] for r in after})
                sample(world, style+'-Settings-closed', 1, 1)
                with world.launch('settings', page='behavior') as settings, detached_jobs(world) as jobs:
                    self.assertFalse(settings.wait(lambda s: s['ready'])['started'])
                    active, _ = sample(world, style+'-eight-detached-jobs', 2, 2, relays=8)
                    pids = {r['pid'] for r in active}
                    self.assertTrue({r['pid'] for r in jobs} <= pids)
                    for job in jobs: self.assertTrue(owned_process(job['pid'], job['started'], world.root))
                    old_main = main.process.pid
                    main.process.terminate(); main.process.wait(timeout=8)
                    sample(world, style+'-shell-stopped-jobs-survive', 1, 1, workers=0, relays=8)
                    with world.launch() as restarted:
                        restarted.wait(lambda s: s['workerReady'] and s['started'] and s['count'] == 2)
                        self.assertNotEqual(restarted.process.pid, old_main)
                        rows, _ = sample(world, style+'-shell-restarted', 2, 2, relays=8)
                        self.assertNotIn(old_main, {r['pid'] for r in rows})
                        for job in jobs: self.assertTrue(owned_process(job['pid'], job['started'], world.root))
            print('RELEASE_PROFILE '+json.dumps(dict(style=style, panel_cycles=rounds*6,
                backend='demo', history='real private worker; capture off', motion='jelly-v2',
                outputs=1, desktop_shapes=False, radio_media_jobs='off/synthetic only',
                scope='copied checkout; no compositor blur/GPU/laptop guarantee')), flush=True)

    def test_smoked_panels_shared_settings_workers_and_detached_restart(self):
        self.run_profile('smoked')

    def test_liquid_panels_shared_settings_workers_and_detached_restart(self):
        self.run_profile('liquid')
