"""Bounded command pipes; finite fake producers, never real tools or disk exhaustion."""
import inspect
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

from command_runner import CommandRunner, CommandError

BOUNDED = 'max_output' in inspect.signature(CommandRunner.run).parameters


class OutputBoundsCase(unittest.TestCase):
    def runner(self):
        runner = CommandRunner(); runner.commands['wpctl'] = sys.executable
        self.addCleanup(runner.close)
        return runner

    def test_current_unicode_newlines_and_exact_error_redaction(self):
        runner = self.runner()
        self.assertEqual(runner.run('wpctl', '-c', 'import os; os.write(1,b" a\\r\\nb\\rc "+"🌙".encode())'), 'a\nb\nc 🌙')
        script = 'import sys; print("\\x1b[31msecret bad\\x1b[0m",file=sys.stderr);sys.exit(7)'
        with self.assertRaisesRegex(CommandError, r'^wpctl failed \(7\): \[redacted\] bad$'):
            runner.run('wpctl', '-c', script, input='secret\n')

    def test_default_overflow_never_returns_successful_truncated_output(self):
        with self.assertRaisesRegex(CommandError, 'output exceeds'):
            self.runner().run('wpctl', '-c', 'import os; os.write(1,b"x"*(8*1024*1024+1))', timeout=5)

    @unittest.skipUnless(BOUNDED, 'F5 output bound unavailable on baseline')
    def test_combined_limit_boundary_multibyte_and_error_does_not_leak_secret(self):
        runner = self.runner()
        self.assertEqual(runner.run('wpctl', '-c', 'import os; os.write(1,"é".encode()*8)', max_output=16), 'é'*8)
        for code in ('import os;os.write(1,b"x"*17)', 'import os;os.write(2,b"x"*17)',
                     'import os;os.write(1,b"x"*8);os.write(2,b"x"*9)'):
            with self.subTest(code=code), self.assertRaisesRegex(CommandError, '^wpctl output exceeds 16 bytes$'):
                runner.run('wpctl', '-c', code, max_output=16, input='private secret')
        self.assertFalse(runner.pending)
        self.assertEqual(runner.run('wpctl', '-c', 'print("retry")', max_output=16), 'retry')

    @unittest.skipUnless(BOUNDED, 'F5 output bound unavailable on baseline')
    def test_invalid_limits_reject_before_spawn(self):
        runner = self.runner()
        for value in (True, False, 0, -1, 1.2, float('inf'), '100'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'positive integer'):
                runner.run('wpctl', '-c', 'raise AssertionError("spawned")', max_output=value)

    @unittest.skipUnless(BOUNDED, 'F5 output bound unavailable on baseline')
    def test_observer_is_cumulative_bytes_bounded_and_exception_reaps(self):
        runner = self.runner(); seen = []
        code = 'import os,time;os.write(1,b"one");time.sleep(.16);os.write(1,b"two");time.sleep(.16)'
        self.assertEqual(runner.run('wpctl', '-c', code, max_output=16,
            observe=lambda out,err:seen.append((out,err))), 'onetwo')
        self.assertTrue(seen)
        self.assertTrue(all(isinstance(out,bytes) and isinstance(err,bytes) and len(out)+len(err)<=16 for out,err in seen))
        self.assertTrue(all(b'onetwo'.startswith(out) for out,_ in seen))
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory)/'pid'
            code = f'import os,time;open({str(marker)!r},"w").write(str(os.getpid()));print("ready",flush=True);time.sleep(20)'
            def stop(out,err):
                if b'ready' in out: raise CommandError('observer stopped')
            with self.assertRaisesRegex(CommandError, '^observer stopped$'):
                runner.run('wpctl', '-c', code, max_output=64, observe=stop)
            self.assertFalse((Path('/proc')/marker.read_text()).exists())
        self.assertFalse(runner.pending)

    @unittest.skipUnless(BOUNDED, 'F5 output bound unavailable on baseline')
    def test_noisy_streams_drain_until_completion_and_keep_observer_bounded(self):
        runner = self.runner(); seen = []
        code = 'import os,time\nfor i in range(256):\n os.write(1,b"a"*4096);os.write(2,b"b"*4096)\ntime.sleep(.15)'
        with self.assertRaisesRegex(CommandError, 'output exceeds 1024 bytes'):
            runner.run('wpctl', '-c', code, max_output=1024, timeout=3,
                observe=lambda out,err:seen.append(len(out)+len(err)))
        self.assertTrue(seen); self.assertLessEqual(max(seen),1024)

    @unittest.skipUnless(BOUNDED, 'F5 output bound unavailable on baseline')
    def test_noisy_timeout_close_and_inherited_pipe_do_not_hang_or_retain_output(self):
        runner = self.runner()
        noisy = 'import os,time\nwhile True: os.write(1,b"a"*4096);os.write(2,b"b"*4096)'
        with self.assertRaisesRegex(CommandError, 'timed out'):
            runner.run('wpctl', '-c', noisy, max_output=64, timeout=.15)
        errors = []
        def work():
            try: runner.run('wpctl', '-c', noisy, max_output=64, timeout=10)
            except CommandError as error: errors.append(str(error))
        thread = threading.Thread(target=work); thread.start()
        deadline = time.monotonic()+2
        while not runner.pending and time.monotonic()<deadline: time.sleep(.01)
        runner.close(); thread.join(timeout=2)
        self.assertFalse(thread.is_alive()); self.assertTrue(errors); self.assertIn('canceled',errors[0])
        self.assertFalse(runner.pending)
        other = self.runner()
        inherited = 'import subprocess,sys;subprocess.Popen([sys.executable,"-c","import time;time.sleep(5)"])'
        start = time.monotonic()
        with self.assertRaisesRegex(CommandError, 'timed out'):
            other.run('wpctl','-c',inherited,max_output=64,timeout=.15)
        self.assertLess(time.monotonic()-start,2)
