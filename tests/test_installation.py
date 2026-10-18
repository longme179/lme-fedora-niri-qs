"""Installation orchestration and DNF selection without changing the host system."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class SetupCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'source checkout'
        scripts = self.repo / 'scripts'
        scripts.mkdir(parents=True)
        (self.repo / 'shell.qml').write_text('// entry point\n')
        for name in ('setup.sh', 'install.sh', 'install-settings.sh'):
            shutil.copy2(REPO / 'scripts' / name, scripts / name)
        # Only privileged steps are stubbed; exercise both real file installers.
        for name in ('install-fedora.sh', 'install-charge-helper.sh'):
            self.executable(scripts / name, r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['LME_TEST_INSTALL_LOG'], 'a') as out:
    out.write(json.dumps([os.path.basename(sys.argv[0]), *sys.argv[1:]])+'\n')
sys.exit(int(os.environ.get('LME_TEST_PACKAGE_EXIT', '0')) if 'fedora' in sys.argv[0] else 0)
''')
        self.executable(self.root / 'bin/sudo', '#!/bin/sh\nexec "$@"\n')
        self.env = dict(os.environ, XDG_CONFIG_HOME=str(self.root / 'config'),
                        XDG_DATA_HOME=str(self.root / 'data'),
                        LME_TEST_INSTALL_LOG=str(self.root / 'calls.jsonl'),
                        PATH=str(self.root / 'bin') + os.pathsep + os.environ['PATH'])
        self.target = self.root / 'config/quickshell/lme-shell'
        self.desktop = self.root / 'data/applications/lme-shell-settings.desktop'

    @staticmethod
    def executable(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o755)

    def setup(self, *args):
        return subprocess.run([str(self.repo / 'scripts/setup.sh'), *args],
                              env=self.env, capture_output=True, text=True, timeout=10)

    def calls(self):
        path = self.root / 'calls.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_preview_help_and_bad_options_do_not_install_files(self):
        # Real package preview must never invoke DNF or sudo, even with all flags.
        shutil.copy2(REPO / 'scripts/install-fedora.sh', self.repo / 'scripts/install-fedora.sh')
        self.executable(self.root / 'bin/sudo', '#!/bin/sh\nexit 99\n')
        self.executable(self.root / 'bin/dnf', '#!/bin/sh\nexit 99\n')
        for args in ((), ('--dry-run', '--copr', '--replace', '--charge-helper'), ('--help',)):
            result = self.setup(*args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(self.target.exists())
            self.assertFalse(self.desktop.exists())
        self.assertEqual(self.setup('--unknown').returncode, 2)
        self.assertFalse((self.root / 'config').exists())
        self.assertFalse((self.root / 'data').exists())

    @unittest.skipIf(os.geteuid() == 0, 'user installation deliberately refuses root')
    def test_install_repeat_and_replace_preserve_preferences_and_backups(self):
        preferences = self.root / 'config/lme-shell/settings.json'
        preferences.parent.mkdir(parents=True)
        preferences.write_text('{"surfaceStyle":"liquid"}')
        for _ in range(2):
            result = self.setup('--install', '--copr', '--charge-helper')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.target.resolve(), self.repo)
        self.assertIn('LME Shell Settings', self.desktop.read_text())
        self.assertEqual(self.calls(), [
            ['install-fedora.sh', '--optional', '--install', '--copr'],
            ['install-charge-helper.sh', '--install']] * 2)
        self.target.unlink()
        self.target.mkdir()
        (self.target / 'previous.qml').write_text('previous shell')
        self.desktop.write_text('previous launcher')
        before = self.calls()
        self.assertNotEqual(self.setup('--install').returncode, 0)
        self.assertEqual(self.calls(), before, 'Check target conflicts before installing packages')
        result = self.setup('--install', '--replace')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(next(self.target.parent.glob('lme-shell.backup-*')).joinpath('previous.qml').read_text(), 'previous shell')
        self.assertEqual(next(self.desktop.parent.glob('*.backup-*')).read_text(), 'previous launcher')
        self.assertEqual(preferences.read_text(), '{"surfaceStyle":"liquid"}')

    @unittest.skipIf(os.geteuid() == 0, 'user installation deliberately refuses root')
    def test_package_failure_leaves_user_files_and_niri_config_untouched(self):
        config = self.root / 'config/niri/config.kdl'
        config.parent.mkdir(parents=True)
        config.write_text('input { }\n')
        self.env['LME_TEST_PACKAGE_EXIT'] = '7'
        result = self.setup('--install', '--charge-helper')
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertFalse(self.target.exists())
        self.assertFalse(self.desktop.exists())
        self.assertEqual(config.read_text(), 'input { }\n')
        self.assertEqual(len(self.calls()), 1)


class FedoraPackagesCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        release = self.root / 'os-release'
        release.write_text('ID=fedora\nVERSION_ID=44\n')
        # Execute the real script against an isolated Fedora identity and fake RPM/DNF.
        self.script = self.root / 'install-fedora.sh'
        self.script.write_text((REPO / 'scripts/install-fedora.sh').read_text().replace('/etc/os-release', str(release)))
        self.script.chmod(0o755)
        SetupCase.executable(self.root / 'bin/sudo', '#!/bin/sh\nexec "$@"\n')
        SetupCase.executable(self.root / 'bin/rpm', '''#!/usr/bin/env python3
import os, sys
sys.exit(0 if sys.argv[-1]=='quickshell' and os.environ.get('LME_TEST_QS_INSTALLED','1')=='1' else 1)
''')
        SetupCase.executable(self.root / 'bin/dnf', r'''#!/usr/bin/env python3
import json, os, sys
args=sys.argv[1:]
with open(os.environ['LME_TEST_INSTALL_LOG'],'a') as out: out.write(json.dumps(args)+'\n')
if 'repoquery' in args:
    package=args[-1]
    if os.environ.get('LME_TEST_QUERY_FAIL')==package: sys.exit(9)
    if package=='awww' and os.environ.get('LME_TEST_AWWW')=='1': print('awww')
    elif package=='quickshell' and os.environ.get('LME_TEST_QS_AVAILABLE')=='1': print('quickshell')
''')
        self.env = dict(os.environ, PATH=str(self.root / 'bin')+os.pathsep+os.environ['PATH'],
                        LME_TEST_INSTALL_LOG=str(self.root / 'calls.jsonl'))

    def install(self, *args):
        return subprocess.run([str(self.script), '--install', *args], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def calls(self):
        path = self.root / 'calls.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_full_package_selection_and_conditional_wallpaper(self):
        for available in ('0', '1'):
            with self.subTest(awww=available):
                self.env['LME_TEST_AWWW'] = available
                result = self.install('--optional')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                transaction = self.calls()[-1]
                self.assertEqual(transaction[0], 'install')
                for package in ('niri', 'quickshell', 'google-roboto-fonts', 'swappy', 'wf-recorder', 'cava', 'matugen'):
                    self.assertIn(package, transaction)
                self.assertEqual('awww' in transaction, available == '1')
                self.assertNotIn('tuned-ppd', transaction)
                self.assertNotIn('power-profiles-daemon', transaction)
                self.assertFalse(any('copr' in call for call in self.calls()))
                if available == '0': self.assertIn('not in enabled repositories', result.stderr)

    def test_quickshell_copr_requires_explicit_flag(self):
        self.env['LME_TEST_QS_INSTALLED'] = '0'
        self.assertNotEqual(self.install().returncode, 0)
        self.assertFalse(any(call[0] in ('install', 'copr') for call in self.calls()))
        result = self.install('--copr')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(['copr', 'enable', 'errornointernet/quickshell'], self.calls())

    def test_repository_lookup_failure_aborts_before_install(self):
        for package in ('quickshell', 'awww'):
            with self.subTest(package=package):
                self.env['LME_TEST_QS_INSTALLED'] = '0'
                self.env['LME_TEST_QS_AVAILABLE'] = '1'
                self.env['LME_TEST_QUERY_FAIL'] = package
                result = self.install('--optional', '--copr')
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(call[0] in ('install', 'copr') for call in self.calls()))
