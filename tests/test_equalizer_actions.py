"""Contracts for the Serpantinum equalizer state machine (equalizer.sh port)."""
import json  # Contract: test_equalizer_actions.py (headroom 0, trailing note)
import math
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from test_backend import Fixture, FakeRunner

from command_runner import CommandError  # noqa: E402
import equalizer_actions  # noqa: E402

ACTIONS = ('eqStart', 'eqStop', 'eqStatus', 'eqGet', 'eqSetBand', 'eqApply', 'eqRevert',
           'eqPreset', 'eqBalance', 'eqMono', 'eqSwap', 'eqDyneq', 'eqDynamics',
           'eqReset', 'eqTest', 'eqTestStop')
DEMO_MESSAGE = 'Demo preview: no system command executed'
DAEMON_REPORT = 'set 5 0 0 0 0 0 0 0 0 0 -0.5 1 0 balanced 0 1'


class RetryRunner(FakeRunner):
    """FakeRunner with one-shot failures keyed by argv prefix (auto-start retry)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.failures = []

    def run(self, name, *args, **kwargs):
        key = (name, *args)
        for index, (prefix, error) in enumerate(self.failures):
            if key[:len(prefix)] == prefix:
                self.failures.pop(index)
                raise error
        return super().run(name, *args, **kwargs)


class FakeProcess:
    def __init__(self):
        self.pid = 4242
        self.stdin = self.stdout = self.stderr = None
        self.terminated = False

    def poll(self):
        return 0 if self.terminated else None

    def wait(self, timeout=None):
        self.terminated = True
        return 0


class EqualizerActionCase(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'),
            XDG_STATE_HOME=str(self.root/'state'), XDG_RUNTIME_DIR=str(self.root/'runtime'))
        env.start(); self.addCleanup(env.stop)

    def configured(self, demo=False, available=('serpantinum-audio', 'pw-play', 'pw-dump')):
        runner = RetryRunner(available=set(available or ()))
        if 'serpantinum-audio' in runner.names:
            runner.responses[('serpantinum-audio', 'ctl', 'get')] = DAEMON_REPORT
            runner.responses[('pw-dump', '-n', 'Node')] = '{"node.name": "serpantinum_sink"}'
        live = self.make_backend(runner=runner, demo=demo)
        self.addCleanup(live.charge_executor.shutdown)
        self.addCleanup(live.feature_executor.shutdown)
        self.addCleanup(live.weather.close)
        self.addCleanup(live.capture.close)
        return live, runner

    def state_of(self, live):
        reply = live.handle(dict(action='eqGet'))
        self.assertTrue(reply['ok'], reply)
        return json.loads(reply['message']), reply['sequence']

    def test_registration_names_contexts_and_sync_execution(self):
        live, _ = self.configured()
        for name in ACTIONS:
            spec = live.actions.get(name)
            self.assertIsNotNone(spec, name)
            self.assertEqual(spec.contexts, frozenset({'shell', 'settings'}), name)
            self.assertEqual(spec.execution, 'sync', name)

    def test_eqget_seeds_from_the_daemon_report_on_first_use(self):
        live, runner = self.configured()
        state, _ = self.state_of(live)
        self.assertEqual(state['b1'], 5)
        self.assertEqual(state['balance'], -0.5)
        self.assertTrue(state['mono'])
        self.assertEqual(state['dynamics'], 'balanced')
        self.assertTrue(state['dyneq'])
        self.assertEqual(state['preset'], 'Custom')
        self.assertFalse(state['pending'])
        self.assertIn(('serpantinum-audio', 'ctl', 'get'), runner.calls)

    def test_eqget_returns_defaults_without_the_daemon_and_stays_ok(self):
        live, runner = self.configured(available=())
        reply = live.handle(dict(action='eqGet'))
        self.assertTrue(reply['ok'], reply)
        state = json.loads(reply['message'])
        self.assertEqual(state['preset'], 'Flat')
        self.assertEqual(state['b10'], 0)
        self.assertEqual(runner.calls, [])

    def test_eqsetband_stages_without_touching_the_daemon(self):
        live, runner = self.configured()
        self.assertEqual(live.handle(dict(action='eqSetBand', band=3, value=7)),
                         dict(ok=True, action='eqSetBand', message='', sequence=1))
        calls = list(runner.calls)
        state, _ = self.state_of(live)
        self.assertEqual(state['b3'], 7)
        self.assertEqual(state['preset'], 'Custom')
        self.assertTrue(state['pending'])
        self.assertEqual(runner.calls, calls)

    def test_eqapply_pushes_the_documented_ctl_set_argv_and_clears_pending(self):
        live, runner = self.configured()
        live.handle(dict(action='eqSetBand', band=2, value=-3))
        self.assertEqual(live.handle(dict(action='eqApply')),
                         dict(ok=True, action='eqApply', message='', sequence=2))
        self.assertEqual(runner.calls[-1], ('serpantinum-audio', 'ctl', 'set',
                         '5', '-3', '0', '0', '0', '0', '0', '0', '0', '0',
                         '-0.5', '1', '0', 'balanced', '0', '1'))
        state, _ = self.state_of(live)
        self.assertFalse(state['pending'])
        self.assertFalse(live.feature_jobs)

    def test_ctl_failure_auto_starts_the_daemon_and_retries_once(self):
        live, runner = self.configured()
        self.state_of(live)
        sets_before = [call for call in runner.calls if call[1:3] == ('ctl', 'set')]
        runner.failures.append((('serpantinum-audio', 'ctl', 'set'), CommandError('daemon down')))
        reply = live.handle(dict(action='eqDyneq', value=True))
        self.assertTrue(reply['ok'], reply)
        sets_after = [call for call in runner.calls if call[1:3] == ('ctl', 'set')]
        starts = [call for call in runner.calls if call == ('serpantinum-audio', 'start')]
        self.assertEqual(len(sets_after), len(sets_before) + 1)
        self.assertEqual(len(starts), 1)

    def test_eqpreset_pushes_named_gains_and_records_the_preset(self):
        live, runner = self.configured()
        reply = live.handle(dict(action='eqPreset', name='Rock'))
        self.assertTrue(reply['ok'], reply)
        self.assertEqual(runner.calls[-1], ('serpantinum-audio', 'ctl', 'set',
                         '5', '4', '2', '-1', '-2', '-1', '2', '4', '5', '6',
                         '-0.5', '1', '0', 'balanced', '0', '1'))
        state, _ = self.state_of(live)
        self.assertEqual(state['preset'], 'Rock')
        self.assertEqual(state['b1'], 5)
        self.assertFalse(state['pending'])

    def test_eqrevert_restores_committed_bands_and_keeps_live_values(self):
        live, _ = self.configured()
        self.state_of(live)
        live.handle(dict(action='eqSetBand', band=1, value=0))
        live.handle(dict(action='eqBalance', value=0.25))
        state, _ = self.state_of(live)
        self.assertTrue(state['pending'])
        self.assertEqual(state['balance'], 0.25)
        reply = live.handle(dict(action='eqRevert'))
        self.assertTrue(reply['ok'], reply)
        state, _ = self.state_of(live)
        self.assertEqual(state['b1'], 5)
        self.assertEqual(state['balance'], 0.25)
        self.assertFalse(state['pending'])

    def test_live_pushes_update_balance_flags_and_dynamics(self):
        live, runner = self.configured()
        self.state_of(live)
        for action, payload in (('eqBalance', {'value': 0.4}), ('eqSwap', {'value': True}),
                                ('eqDynamics', {'value': 'night'})):
            reply = live.handle(dict(action=action, **payload))
            self.assertTrue(reply['ok'], (action, reply))
        state, _ = self.state_of(live)
        self.assertEqual(state['balance'], 0.4)
        self.assertTrue(state['swap'])
        self.assertEqual(state['dynamics'], 'night')
        reply = live.handle(dict(action='eqReset'))
        self.assertTrue(reply['ok'], reply)
        state, _ = self.state_of(live)
        self.assertEqual(state['balance'], 0)
        self.assertFalse(state['mono'])
        self.assertFalse(state['swap'])
        self.assertEqual(state['dynamics'], 'off')
        self.assertTrue(state['dyneq'], 'reset must not touch dynamic EQ')
        self.assertEqual(len([call for call in runner.calls if call[1:3] == ('ctl', 'set')]), 4)

    def test_eqtest_targets_the_equalizer_sink_and_stop_ends_the_tone(self):
        live, runner = self.configured()
        process = FakeProcess()
        with patch.object(equalizer_actions, 'subprocess') as subprocess_module:
            subprocess_module.Popen.return_value = process
            subprocess_module.DEVNULL = object()
            reply = live.handle(dict(action='eqTest'))
            self.assertTrue(reply['ok'], reply)
            argv = subprocess_module.Popen.call_args[0][0]
            self.assertEqual(argv[0], 'pw-play')
            self.assertIn('--target=serpantinum_sink', argv)
            self.assertTrue(str(argv[-1]).endswith('equalizer-test.wav'))
            reply = live.handle(dict(action='eqTestStop'))
            self.assertTrue(reply['ok'], reply)
            self.assertTrue(process.terminated)
        self.assertIn(('serpantinum-audio', 'start'), runner.calls)
        self.assertTrue(Path(argv[-1]).exists(), 'the test tone wave is generated once')

    def test_eqtest_without_pw_play_reports_it_cleanly(self):
        live, _ = self.configured(available=('serpantinum-audio',))
        reply = live.handle(dict(action='eqTest'))
        self.assertFalse(reply['ok'], reply)
        self.assertIn('pw-play', reply['message'])

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

    def test_pushes_without_the_daemon_fail_without_touching_the_runner(self):
        live, runner = self.configured(available=())
        for action, payload in (('eqStart', {}), ('eqApply', {}), ('eqPreset', {'name': 'Flat'}),
                                ('eqBalance', {'value': 0}), ('eqMono', {'value': True}),
                                ('eqSwap', {'value': True}), ('eqDyneq', {'value': True}),
                                ('eqDynamics', {'value': 'off'}), ('eqRevert', {})):
            reply = live.handle(dict(action=action, **payload))
            self.assertFalse(reply['ok'], action)
            self.assertEqual(reply['message'], 'serpantinum-audio is unavailable', action)
        self.assertEqual(runner.calls, [])
        state_reply = live.handle(dict(action='eqGet'))
        self.assertTrue(state_reply['ok'], 'state actions stay available without the daemon')

    def test_validation_rejects_bad_payloads_without_touching_the_daemon(self):
        live, runner = self.configured()
        self.state_of(live)
        calls = list(runner.calls)
        cases = [
            ('eqSetBand', dict(band=0, value=1), 'Band must be an integer between 1 and 10'),
            ('eqSetBand', dict(band=11, value=1), 'Band must be an integer between 1 and 10'),
            ('eqSetBand', dict(band='mid', value=1), 'Band must be an integer'),
            ('eqSetBand', dict(band=1, value=True), 'numeric gain'),
            ('eqSetBand', dict(band=1, value='5'), 'numeric gain'),
            ('eqSetBand', dict(band=1, value=13), 'out of range'),
            ('eqSetBand', dict(band=1, value=-13), 'out of range'),
            ('eqSetBand', dict(band=1, value=math.nan), 'out of range'),
            ('eqSetBand', dict(band=1, value=10 ** 400), 'out of range'),
            ('eqBalance', dict(value=math.nan), 'Balance must be between -1 and 1'),
            ('eqBalance', dict(value=1.5), 'Balance must be between -1 and 1'),
            ('eqBalance', dict(value=-1.5), 'Balance must be between -1 and 1'),
            ('eqBalance', dict(value=10 ** 400), 'Balance must be between -1 and 1'),
            ('eqBalance', dict(value=True), 'Balance must be numeric'),
            ('eqBalance', dict(value='center'), 'Balance must be numeric'),
            ('eqMono', dict(value='yes'), 'Equalizer switches must be boolean'),
            ('eqDynamics', dict(value='loud'), 'Unknown dynamics mode'),
            ('eqPreset', dict(name='Loudness'), 'Unknown equalizer preset'),
        ]
        for sequence, (action, payload, message) in enumerate(cases, 2):
            with self.subTest(action=action, payload=payload):
                reply = live.handle(dict(action=action, **payload))
                self.assertFalse(reply['ok'])
                self.assertIn(message, reply['message'])
        self.assertEqual(runner.calls, calls)

    def test_settings_context_can_call_every_action(self):
        live, _ = self.configured()
        live.settings_only = True
        with patch.object(equalizer_actions, 'subprocess') as subprocess_module:
            subprocess_module.DEVNULL = object()
            subprocess_module.Popen.return_value = FakeProcess()
            for name in ACTIONS:
                payload = {'band': 1, 'value': 1} if name == 'eqSetBand' else \
                          {'name': 'Flat'} if name == 'eqPreset' else \
                          {'value': 0} if name == 'eqBalance' else \
                          {'value': 'off'} if name == 'eqDynamics' else \
                          {'value': False} if name in ('eqMono', 'eqSwap', 'eqDyneq') else {}
                reply = live.handle(dict(action=name, **payload))
                self.assertTrue(reply['ok'], (name, reply))

    def test_demo_handlers_answer_every_action(self):
        live, _ = self.configured(demo=True)
        for name in ACTIONS:
            reply = live.handle(dict(action=name))
            self.assertEqual(reply, dict(ok=True, action=name, message=DEMO_MESSAGE,
                                         sequence=reply['sequence']))
        state = json.loads(live.actions.get('eqGet').demo({}))
        self.assertEqual(state['preset'], 'Flat')
        self.assertEqual(sorted(state), ['b1', 'b10', 'b2', 'b3', 'b4', 'b5', 'b6',
                                         'b7', 'b8', 'b9', 'balance', 'dynamics', 'dyneq',
                                         'mono', 'pending', 'preset', 'swap'])
        self.assertEqual(live.actions.get('eqStatus').demo({}), 'ok\nDemo Serpantinum status')

    def test_corrupt_state_files_fall_back_to_defaults(self):
        live, _ = self.configured()
        self.state_of(live)
        path = Path(os.environ['XDG_STATE_HOME']) / 'lme-shell/equalizer.json'
        path.write_text('{not json', encoding='utf-8')
        state, _ = self.state_of(live)
        self.assertEqual(state['preset'], 'Flat')

    def test_staged_state_survives_a_backend_restart(self):
        live, runner = self.configured()
        live.handle(dict(action='eqSetBand', band=4, value=6))
        restarted, _ = self.configured()
        state, _ = self.state_of(restarted)
        self.assertEqual(state['b4'], 6)
        self.assertTrue(state['pending'])


if __name__ == '__main__':
    unittest.main()
