"""A muted debug logger must not turn a compatible runtime into a false rejection."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import deploy_runtime


class ProbeConfirmationCase(unittest.TestCase):
    def invoke(self, receipt=None, code=0, output='INFO: Configuration Loaded\n'):
        def command(argv, **kwargs):
            if argv[-1] == '--version':
                return subprocess.CompletedProcess(argv, 0, 'Quickshell 0.3.2 (Fedora COPR)\n', '')
            self.assertEqual(kwargs['timeout'], 20)
            env = kwargs['env']
            self.assertEqual(env['QT_QPA_PLATFORM'], 'offscreen')
            self.assertNotIn('WAYLAND_DISPLAY', env)
            if receipt is not None: (Path(env['HOME'])/'probe.ok').write_text(receipt)
            return subprocess.CompletedProcess(argv, code, '', output)
        with patch('deploy_runtime.subprocess.run', side_effect=command):
            return deploy_runtime.probe('/fake/quickshell')

    def test_muted_debug_log_accepts_private_completed_receipt(self):
        self.assertEqual(self.invoke('LME_RUNTIME_OK'), (0, 3, 2))

    def test_configuration_loaded_without_confirmation_is_rejected(self):
        with self.assertRaises(ValueError): self.invoke()

    def test_wrong_receipt_is_rejected(self):
        with self.assertRaises(ValueError): self.invoke('not complete')

    def test_failed_exit_is_rejected_even_with_receipt(self):
        with self.assertRaises(ValueError): self.invoke('LME_RUNTIME_OK', code=1)

    def test_qml_load_error_is_rejected_even_with_receipt(self):
        with self.assertRaises(ValueError):
            self.invoke('LME_RUNTIME_OK', output='Failed to load configuration: bottomRightRadius missing')

    def test_existing_console_confirmation_remains_accepted(self):
        self.assertEqual(self.invoke(output='qml: LME_RUNTIME_OK\n'), (0, 3, 2))


@unittest.skipUnless(os.environ.get('LME_TEST_DEPLOY_RUNTIME') == '1',
                     'opt-in real offscreen Quickshell deployment probe')
class NativeProbeCase(unittest.TestCase):
    def setUp(self):
        self.binary = shutil.which('quickshell') or shutil.which('qs')
        self.assertIsNotNone(self.binary)

    def test_debug_disabled_success_is_independent_of_log_output(self):
        with patch.dict(os.environ, QT_LOGGING_RULES='*.debug=false'):
            self.assertGreaterEqual(deploy_runtime.probe(self.binary), (0, 3, 2))

    def test_debug_disabled_missing_property_still_fails(self):
        broken = deploy_runtime.PROBE.replace('bottomRightRadius: 2', 'nonexistentRadius: 2')
        with patch.dict(os.environ, QT_LOGGING_RULES='*.debug=false'), patch('deploy_runtime.PROBE', broken):
            with self.assertRaises(ValueError): deploy_runtime.probe(self.binary)


if __name__ == '__main__': unittest.main()
