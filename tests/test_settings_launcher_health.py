"""A listed Settings instance is left running when openPage cannot confirm it.
Contract: test_settings_launcher_health.py covers settings_launcher_health behavior/contracts; check imports for fixtures/helpers under test.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class SettingsLauncherHealthCase(unittest.TestCase):
    def test_listed_instance_is_not_killed_after_a_non_true_openpage_reply(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "quickshell"
            calls = root / "calls.jsonl"
            fake.write_text('''#!/usr/bin/python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ['QS_CALLS'], 'a') as log: log.write(json.dumps(args)+'\\n')
if 'ipc' in args: print('false')
elif 'list' in args: print('[{"pid": 7}]')
else: print(json.dumps(args))
''')
            fake.chmod(0o755)
            env = {**os.environ, "LME_QS_BINARY": str(fake), "LME_SHELL_DEMO": "1", "QS_CALLS": str(calls)}
            result = subprocess.run(["bash", str(REPO / "scripts/settings.sh"), "--page", "elements"],
                                    env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            recorded = [json.loads(line) for line in calls.read_text().splitlines()]
            self.assertFalse(any("kill" in call for call in recorded), recorded)
            self.assertFalse(any("--no-duplicate" in call for call in recorded), recorded)
            self.assertIn("openPage=false", result.stderr)
            self.assertIn("leaving it open", result.stderr)


if __name__ == "__main__":
    unittest.main()
