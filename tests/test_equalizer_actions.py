"""Contracts for the optional Serpantinum equalizer action provider."""
import math
import os
import unittest
from unittest.mock import call, patch

from test_backend import Fixture, FakeRunner

ACTIONS = ('eqStart', 'eqStop', 'eqStatus', 'eqGet', 'eqApply')
FLAT = [0.0] * 10
DEMO_MESSAGE = 'Demo preview: no system command executed'
from command_runner import CommandError  # noqa: E402


class EqualizerActionCase(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'),
            XDG_STATE_HOME=str(self.root/'state'), XDG_RUNTIME_DIR=str(self.root/'runtime'))
        env.start(); self.addCleanup(env.stop)

    def configured(self, demo=False, available=('serpantinum-audio',)):
        runner = FakeRunner(available=set(available or ()))
        live = self.make_backend(runner=runner, demo=demo)
        self.addCleanup(live.charge_executor.shutdown)
        self.addCleanup(live.feature_executor.shutdown)
        self.addCleanup(live.weather.close)
        self.addCleanup(live.capture.close)
        return live, runner

    def apply(self, **overrides):
        payload = dict(gains=FLAT, balance=0.0, mono=False, swap=False,
                       dynamics='off', bypass=False, dyneq=False)
        payload.update(overrides)
        return payload

    def test_registration_names_contexts_and_sync_execution(self):
        live, _ = self.configured()
        for name in ACTIONS:
            spec = live.actions.get(name)
            self.assertIsNotNone(spec, name)
            self.assertEqual(spec.contexts, frozenset({'shell', 'settings'}), name)
            self.assertEqual(spec.execution, 'sync', name)

    def test_live_apply_builds_the_documented_ctl_set_argv(self):
        live, runner = self.configured()
        payload = self.apply(gains=[5, -5, 0.5, 0, 0, 0, 0, 0, 0, 0], balance=-0.25,
                             mono=True, swap=True, dynamics='night', bypass=True, dyneq=True)
        self.assertEqual(live.handle(dict(action='eqApply', **payload)),
                         dict(ok=True, action='eqApply', message='', sequence=1))
        self.assertEqual(runner.calls,
                         [('serpantinum-audio', 'ctl', 'set', '5', '-5', '0.5', '0', '0', '0', '0', '0', '0', '0',
                           '-0.25', '1', '1', 'night', '1', '1')])
        self.assertFalse(live.feature_jobs)

    def test_live_start_status_and_get_use_their_own_subcommands(self):
        live, runner = self.configured()
        runner.responses[('serpantinum-audio', 'ctl', 'ping')] = ' ok '
        runner.responses[('serpantinum-audio', 'ctl', 'status')] = ' running '
        runner.responses[('serpantinum-audio', 'ctl', 'get')] = 'set ' + ' '.join(['0'] * 13) + ' off 0 1'
        self.assertEqual(live.handle(dict(action='eqStart')), dict(ok=True, action='eqStart', message='', sequence=1))
        self.assertEqual(live.handle(dict(action='eqStatus')), dict(ok=True, action='eqStatus', message='ok\nrunning', sequence=2))
        self.assertEqual(live.handle(dict(action='eqGet')),
                         dict(ok=True, action='eqGet', message='set ' + ' '.join(['0'] * 13) + ' off 0 1', sequence=3))
        self.assertEqual(runner.calls, [('serpantinum-audio', 'start'),
                                        ('serpantinum-audio', 'ctl', 'ping'), ('serpantinum-audio', 'ctl', 'status'),
                                        ('serpantinum-audio', 'ctl', 'get')])

    def test_stop_swallows_not_running_but_surfaces_timeouts(self):
        live, runner = self.configured()
        runner.responses[('serpantinum-audio', 'ctl', 'quit')] = 'Equalizer stopped'
        self.assertEqual(live.handle(dict(action='eqStop')), dict(ok=True, action='eqStop', message='Equalizer stopped', sequence=1))
        runner.responses[('serpantinum-audio', 'ctl', 'quit')] = CommandError('serpantinum-audio exited with 1')
        self.assertEqual(live.handle(dict(action='eqStop')), dict(ok=True, action='eqStop', message='Equalizer stopped', sequence=2))
        runner.responses[('serpantinum-audio', 'ctl', 'quit')] = CommandError('serpantinum-audio timed out')
        reply = live.handle(dict(action='eqStop'))
        self.assertFalse(reply['ok'])
        self.assertIn('timed out', reply['message'])
        self.assertFalse(live.feature_jobs)

    def test_missing_binary_short_circuits_every_action(self):
        live, runner = self.configured(available=())
        for name in ACTIONS:
            reply = live.handle(dict(action=name, **self.apply()) if name == 'eqApply' else dict(action=name))
            self.assertFalse(reply['ok'], name)
            self.assertEqual(reply['message'], 'serpantinum-audio is unavailable', name)
        self.assertEqual(runner.calls, [])

    def test_apply_rejects_invalid_payloads_without_touching_the_daemon(self):
        live, runner = self.configured()
        cases = [
            (self.apply(gains=[0] * 9), 'Ten equalizer band gains are required'),
            (self.apply(gains='flat'), 'Ten equalizer band gains are required'),
            (self.apply(gains=[True] + FLAT[1:]), 'Equalizer settings must use numeric gain'),
            (self.apply(gains=['5'] + FLAT[1:]), 'Equalizer settings must use numeric gain'),
            (self.apply(gains=[13] + FLAT[1:]), 'Equalizer gain is out of range'),
            (self.apply(gains=[-13] + FLAT[1:]), 'Equalizer gain is out of range'),
            (self.apply(gains=[math.nan] + FLAT[1:]), 'Equalizer gain is out of range'),
            (self.apply(gains=[10 ** 400] + FLAT[1:]), 'Equalizer gain is out of range'),
            (self.apply(balance=math.nan), 'Balance must be between -1 and 1'),
            (self.apply(balance=1.5), 'Balance must be between -1 and 1'),
            (self.apply(balance=-1.5), 'Balance must be between -1 and 1'),
            (self.apply(balance=10 ** 400), 'Balance must be between -1 and 1'),
            (self.apply(balance=True), 'Balance must be numeric'),
            (self.apply(balance='center'), 'Balance must be numeric'),
            (self.apply(mono='yes'), 'Equalizer switches must be boolean'),
            (self.apply(dynamics='loud'), 'Unknown dynamics mode'),
        ]
        for sequence, (payload, message) in enumerate(cases, 1):
            with self.subTest(message=message):
                self.assertEqual(live.handle(dict(action='eqApply', **payload)),
                                 dict(ok=False, action='eqApply', message=message, sequence=sequence))
        self.assertEqual(runner.calls, [])

    def test_settings_context_can_call_every_action(self):
        live, _ = self.configured()
        live.settings_only = True
        for name in ACTIONS:
            reply = live.handle(dict(action=name, **self.apply()) if name == 'eqApply' else dict(action=name))
            self.assertTrue(reply['ok'], name)

    def test_demo_handlers_answer_every_action_and_get_keeps_the_17_token_contract(self):
        live, _ = self.configured(demo=True)
        for name in ('eqStart', 'eqStop', 'eqApply'):
            sequence = {'eqStart': 1, 'eqStop': 2, 'eqApply': 3}[name]
            reply = live.handle(dict(action=name, **self.apply()) if name == 'eqApply' else dict(action=name))
            self.assertEqual(reply, dict(ok=True, action=name, message=DEMO_MESSAGE, sequence=sequence))
        get = live.actions.get('eqGet').demo({})
        tokens = get.split()
        self.assertEqual(tokens[0], 'set')
        self.assertEqual(len(tokens), 17, 'EqualizerPage/Panel parse exactly 17 tokens')
        status = live.actions.get('eqStatus').demo({})
        self.assertEqual(status, 'ok\nDemo Serpantinum status')


if __name__ == '__main__':
    unittest.main()
