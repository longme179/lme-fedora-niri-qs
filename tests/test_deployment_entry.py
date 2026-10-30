"""The root deploy command and its old scripts/ entry share one implementation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RootDeployCase(unittest.TestCase):
    def test_root_help_matches_compatible_entry(self):
        root = subprocess.run([str(ROOT/'deploy.sh'), '--help'], capture_output=True, text=True)
        old = subprocess.run([str(ROOT/'scripts/deploy.sh'), '--help'], capture_output=True, text=True)
        self.assertEqual(root.returncode, 0, root.stderr)
        self.assertEqual((root.stdout, root.stderr), (old.stdout, old.stderr))

    def test_paths_arguments_and_exit_status_from_another_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)/'checkout with spaces'; (folder/'scripts').mkdir(parents=True)
            shutil.copy2(ROOT/'deploy.sh', folder/'deploy.sh')
            shutil.copy2(ROOT/'scripts/deploy.sh', folder/'scripts/deploy.sh')
            (folder/'scripts/deploy.py').write_text('import json,sys; print(json.dumps(sys.argv[1:])); sys.exit(7)\n')
            args = ['--install', '--copr', '--build-quickshell', '--niri-config', 'a path/with spaces.kdl']
            for entry in (folder/'deploy.sh', folder/'scripts/deploy.sh'):
                with self.subTest(entry=entry):
                    result = subprocess.run([str(entry), *args], cwd=raw, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 7, result.stderr)
                    self.assertEqual(json.loads(result.stdout), args)

    def test_root_default_stays_readonly(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            env = dict(os.environ, HOME=raw, XDG_CONFIG_HOME=str(home/'config'),
                       XDG_DATA_HOME=str(home/'data'), XDG_STATE_HOME=str(home/'state'))
            result = subprocess.run([str(ROOT/'deploy.sh')], cwd=raw, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('dry-run', result.stdout)
            self.assertEqual(list(home.iterdir()), [])


if __name__ == '__main__': unittest.main()
