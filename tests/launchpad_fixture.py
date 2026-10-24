"""Keep controller unit mocks at their literal-command boundary; relay has real tests."""
import subprocess


def direct_spawn(*args, **kwargs):
    return subprocess.Popen(*args, **kwargs)
