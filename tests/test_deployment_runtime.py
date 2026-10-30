"""Runtime provisioning commands and launcher selection, without installing anything."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from deploy_files import desktop, desktop_exec
from deploy_runtime import COMMIT, build, ensure


class ProvisionCase(unittest.TestCase):
    def test_old_installed_package_is_not_a_successful_probe(self):
        old, new = Path('/old/quickshell'), Path('/new/quickshell')
        with patch('deploy_runtime.candidates', side_effect=[[old], [new]]), \
             patch('deploy_runtime.probe', side_effect=[ValueError('old API'), (0, 3, 2)]), \
             patch('deploy_runtime.run') as run:
            self.assertEqual(ensure(None, Path('/managed'), Path('/data'), copr=True), new)
        self.assertEqual(run.call_args_list[0].args[0], ['sudo', 'dnf', 'copr', 'enable', 'errornointernet/quickshell'])
        self.assertEqual(run.call_args_list[1].args[0], ['sudo', 'dnf', 'upgrade', '--refresh', 'quickshell'])

    def test_explicit_runtime_never_triggers_repository_or_build_fallback(self):
        with patch('deploy_runtime.candidates', return_value=[Path('/chosen')]), \
             patch('deploy_runtime.probe', side_effect=ValueError('wrong API')), \
             patch('deploy_runtime.run') as run, patch('deploy_runtime.build') as builder:
            with self.assertRaisesRegex(ValueError, 'wrong API'):
                ensure('/chosen', Path('/managed'), Path('/data'), copr=True, source=True)
        run.assert_not_called(); builder.assert_not_called()

    def test_source_fallback_only_when_allowed(self):
        with patch('deploy_runtime.candidates', return_value=[]), patch('deploy_runtime.build', return_value=Path('/built')) as builder:
            with self.assertRaises(ValueError): ensure(None, Path('/managed'), Path('/data'))
            builder.assert_not_called()
            self.assertEqual(ensure(None, Path('/managed'), Path('/data'), source=True, jobs=2), Path('/built'))
            builder.assert_called_once_with(Path('/data'), 2)

    def test_source_build_is_pinned_private_and_bounded(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw); commands = []
            def command(argv, **kwargs):
                commands.append(list(map(str, argv)))
                if argv[:2] == ['cmake', '--install']:
                    prefix = folder/'lme-shell/runtime'/f'quickshell-{COMMIT[:12]}-qt6.11.2'
                    (prefix/'bin').mkdir(parents=True)
                    (prefix/'bin/quickshell').write_text('fake executable')
            with patch('deploy_runtime.run', side_effect=command), \
                 patch('deploy_runtime.subprocess.check_output', side_effect=['6.11.2\n', COMMIT+'\n']), \
                 patch('deploy_runtime.probe', return_value=(0, 3, 2)):
                binary = build(folder, 2)
            self.assertTrue(binary.is_relative_to(folder))
            self.assertEqual(commands[2][-1], COMMIT)
            self.assertIn(['cmake', '--build', commands[-2][2], '--parallel', '2'], commands)
            self.assertIn('cmake(Qt6WaylandClientPrivate)', commands[0])
            self.assertEqual(commands[-1][:2], ['cmake', '--install'])
            self.assertNotIn('sudo', commands[-1])


class LauncherCase(unittest.TestCase):
    def test_start_uses_managed_binary_and_duplicate_guard_only_on_request(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw); binary = folder/'data/lme-shell/deployment/bin/quickshell'; binary.parent.mkdir(parents=True)
            binary.write_text('#!/bin/sh\nprintf "selected-managed:%s\\n" "$*"\n'); binary.chmod(0o755)
            env = dict(os.environ, HOME=raw, XDG_DATA_HOME=str(folder/'data'))
            env.pop('LME_QS_BINARY', None)
            first = subprocess.run([str(ROOT/'scripts/start.sh'), '--preview'], env=env, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn('selected-managed:-c lme-shell', first.stdout)
            self.assertNotIn('--no-duplicate', first.stdout)
            second = subprocess.run([str(ROOT/'scripts/start.sh'), '--preview', '--no-duplicate', '--daemonize'], env=env, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn('--no-duplicate --daemonize', second.stdout)
            override = folder/'chosen'; override.write_text('#!/bin/sh\necho explicit-override\n'); override.chmod(0o755)
            env['LME_QS_BINARY'] = str(override)
            third = subprocess.run([str(ROOT/'scripts/start.sh'), '--preview'], env=env, capture_output=True, text=True)
            self.assertEqual(third.stdout.strip(), 'explicit-override')

    def test_desktop_entry_upgrade_matches_existing_generator_exactly(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)/'entry.desktop'
            result = subprocess.run([str(ROOT/'scripts/install-settings.sh'), '--target', str(target)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), desktop(desktop_exec(ROOT/'scripts/settings.sh')))


if __name__ == '__main__': unittest.main()
