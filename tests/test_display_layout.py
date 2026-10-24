"""Freeze the shared layout boundary before extracting it from DisplayControl."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

import display_control as display

ROOT = Path(__file__).resolve().parents[1]
ITEM = dict(name='eDP-1', width=1920, height=1080, refresh=60003, scale=1, x=0, y=0)


class DisplayLayoutContractsCase(unittest.TestCase):
    def test_validation_boundaries_and_output_fields_do_not_mutate_input(self):
        for scale in (.5, 1, 1.25, 3):
            for coordinate in (-32768, 0, 32768):
                item = dict(ITEM, name='x'*128, width=1, height=1000000,
                            refresh=1000000, scale=scale, x=coordinate, extra='ignored')
                original = copy.deepcopy(item)
                result = display.validate_layout([item])
                self.assertEqual(result, [{key: item[key] for key in ITEM}])
                self.assertEqual(list(result[0]), list(ITEM))
                self.assertEqual(item, original)
                self.assertIsNot(result[0], item)
        self.assertEqual(len(display.validate_layout([dict(ITEM, name=str(i)) for i in range(16)])), 16)

    def test_exact_validation_errors_and_type_rules(self):
        cases = [(None, 'Choose at least one display'),
                 ((ITEM,), 'Choose at least one display'),
                 ([], 'Choose at least one display'),
                 ([ITEM]*17, 'Choose at least one display'),
                 ([None], 'Invalid display settings'),
                 ([ITEM, ITEM], 'Invalid or duplicate output name')]
        for name in (None, True, '', 'x'*129, 'eDP\n1'):
            cases.append(([dict(ITEM, name=name)], 'Invalid or duplicate output name'))
        for key in ('width', 'height', 'refresh'):
            for value in (None, True, False, '1', 1., 0, -1, 1000001, float('nan'), float('inf')):
                cases.append(([dict(ITEM, **{key: value})], 'Invalid display mode'))
        for scale in (None, True, '1', .4999, 3.0001, float('nan'), float('inf'), -float('inf')):
            cases.append(([dict(ITEM, scale=scale)], 'Scale must be between 0.5 and 3'))
        for key in ('x', 'y'):
            for value in (None, True, 0., '0', -32769, 32769, float('nan'), float('inf')):
                cases.append(([dict(ITEM, **{key: value})],
                              'Display coordinates must be integers between -32768 and 32768'))
        for value, message in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    display.validate_layout(value)
                self.assertEqual(str(caught.exception), message)
        for key in ITEM:
            value = dict(ITEM); del value[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                display.validate_layout([value])

    def test_available_output_and_exact_mode_admission(self):
        outputs = [dict(name=ITEM['name'], enabled=True, modes=[dict(ITEM)])]
        self.assertEqual(display.validate_layout([ITEM], outputs), [ITEM])
        self.assertEqual(display.validate_layout([ITEM], None), [ITEM])
        for unavailable in ([], [dict(outputs[0], enabled=False)],
                            [dict(outputs[0], name='other')],
                            [dict(outputs[0], modes=[dict(ITEM, refresh=60000)])]):
            with self.subTest(outputs=unavailable), self.assertRaises(ValueError) as caught:
                display.validate_layout([ITEM], unavailable)
            self.assertEqual(str(caught.exception), 'Display or mode is no longer available; refresh displays')

    def test_current_layout_order_filtering_and_copy(self):
        outputs = [dict(ITEM, current=dict(ITEM)), dict(ITEM, current=None),
                   dict(ITEM, name='HDMI A 1', current=dict(ITEM, refresh=59940), enabled=False)]
        original = copy.deepcopy(outputs)
        result = display.current_layout(outputs)
        self.assertEqual(result, [ITEM, dict(ITEM, name='HDMI A 1', refresh=59940)])
        self.assertEqual(list(result[0]), list(ITEM))
        result[0]['scale'] = 2
        self.assertEqual(outputs, original)
        self.assertEqual(display.current_layout([]), [])

    def test_literal_argv_order_fractional_refresh_and_success(self):
        calls = []
        layout = [dict(ITEM, name='HDMI A;$(x)', scale=1.25, x=-100, y=3),
                  dict(ITEM, name='eDP-2', refresh=59940, scale=2.)]
        original = copy.deepcopy(layout)
        self.assertEqual(display.apply_layout(layout, lambda *args: calls.append(args)), [])
        self.assertEqual(calls, [
            ('niri', 'msg', 'output', 'HDMI A;$(x)', 'mode', '1920x1080@60.003'),
            ('niri', 'msg', 'output', 'HDMI A;$(x)', 'scale', '1.25'),
            ('niri', 'msg', 'output', 'HDMI A;$(x)', 'position', 'set', '-100', '3'),
            ('niri', 'msg', 'output', 'eDP-2', 'mode', '1920x1080@59.940'),
            ('niri', 'msg', 'output', 'eDP-2', 'scale', '2.0'),
            ('niri', 'msg', 'output', 'eDP-2', 'position', 'set', '0', '0')])
        self.assertEqual(layout, original)

    def test_full_layout_validation_precedes_any_runner_call(self):
        calls = []
        with self.assertRaises(ValueError):
            display.apply_layout([ITEM, dict(ITEM, name='other', scale=True)],
                                 lambda *args: calls.append(args), best_effort=True)
        self.assertEqual(calls, [])

    def test_fail_fast_and_best_effort_keep_exception_identity_and_order(self):
        for error_type in (RuntimeError, OSError, ValueError):
            for best_effort in (False, True):
                calls = []; error = error_type('mode failed')
                def run(*args):
                    calls.append(args)
                    if len(calls) in (1, 4): raise error
                with self.subTest(error=error_type, best_effort=best_effort):
                    if best_effort and error_type in (RuntimeError, OSError):
                        self.assertEqual(display.apply_layout([ITEM, dict(ITEM, name='other')], run, True),
                                         ['mode failed', 'mode failed'])
                        self.assertEqual(len(calls), 6)
                    else:
                        with self.assertRaises(error_type) as caught:
                            display.apply_layout([ITEM], run, best_effort)
                        self.assertIs(caught.exception, error)
                        self.assertEqual(len(calls), 1)

    @unittest.skipUnless(importlib.util.find_spec('display_layout'),
                         'Shared display-layout import contract is N/A before extraction')
    def test_shared_import_isolation_and_compatibility_exports(self):
        import battery_saver
        import display_layout
        for name in ('validate_layout', 'current_layout', 'apply_layout'):
            self.assertIs(getattr(display, name), getattr(display_layout, name))
            self.assertIs(getattr(battery_saver, name), getattr(display_layout, name))
        code = '''
import importlib.abc, json, sys
class BlockDomain(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname in ('display_control', 'desktop_backend'):
            raise ImportError('domain unavailable: '+fullname)
sys.meta_path.insert(0, BlockDomain())
import display_layout, battery_saver
print(json.dumps([name for name in ('display_control', 'desktop_backend') if name in sys.modules]))
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=ROOT/'scripts',
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
