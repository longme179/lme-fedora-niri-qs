"""Keep controller unit mocks at their literal-command boundary; relay has real tests.

Contract/helper: test infrastructure for launchpad_fixture.py. REL: scripts/launchpad.py.
"""
import subprocess


def direct_spawn(*args, **kwargs):
    return subprocess.Popen(*args, **kwargs)
