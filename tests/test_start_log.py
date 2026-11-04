"""Live starts write to a bounded private log; demo startup keeps its terminal output."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class StartLogCase(unittest.TestCase):
    def test_live_start_redirects_and_rotates_two_old_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binaries = root / "bin"; binaries.mkdir()
            for name, body in {
                "quickshell": '#!/bin/sh\nprintf "%s\\n" "$@"\n',
                "python3": '#!/bin/sh\nexit 0\n',
            }.items():
                path = binaries / name
                path.write_text(body)
                path.chmod(0o755)
            state = root / "state"
            log_dir = state / "lme-shell/log"
            log_dir.mkdir(parents=True)
            log = log_dir / "lme-shell.log"
            log.write_text("old current\n")
            (log_dir / "lme-shell.log.1").write_text("old rotated\n")
            log.write_text("x" * (1024 * 1024 + 1))
            env = {**os.environ, "PATH": str(binaries) + ":" + os.environ["PATH"],
                   "XDG_STATE_HOME": str(state), "XDG_CONFIG_HOME": str(root / "config"),
                   "XDG_RUNTIME_DIR": str(root / "runtime"), "LME_QS_BINARY": str(binaries / "quickshell")}
            result = subprocess.run(["bash", str(REPO / "scripts/start.sh"), "--no-wallpaper", "--config", "live"],
                                    env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual((log_dir / "lme-shell.log.2").read_text(), "old rotated\n")
            self.assertEqual((log_dir / "lme-shell.log.1").stat().st_size, 1024 * 1024 + 1)
            self.assertLessEqual(log.stat().st_size, 1024)
            self.assertIn("-c\nlive\n", log.read_text())
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
