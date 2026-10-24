"""Detached log limits and relay lifetime, using finite private jobs only."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from test_backend import Fixture
from launchpad import Launchpad

RELAY = importlib.util.find_spec('detached_log') is not None
LIMIT = 8*1024*1024


class LaunchpadLogCase(Fixture, unittest.TestCase):
    def launch(self, code, key='job', terminal=False, program='kitty'):
        tool = Launchpad()
        entry = dict(name='Private job',kind='command',terminal=terminal,cwd=str(self.root),
                     command=shlex.join([sys.executable,'-c',code]))
        with patch.dict(os.environ,XDG_STATE_HOME=str(self.root/'state')):
            tool.run(key,{key:entry},program)
        child = tool.jobs[key]['process']
        def cleanup():
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGTERM)
                try: child.wait(timeout=2)
                except subprocess.TimeoutExpired: os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=2)
        self.addCleanup(cleanup)
        return tool, child

    def finished(self, tool):
        child = tool.jobs['job']['process']; child.wait(timeout=5)
        return tool.snapshot()['job']

    def test_current_short_log_literal_arguments_and_exit_status(self):
        tool,_ = self.launch('import sys;print("literal $(touch SHOULD_NOT_EXIST)");print("err",file=sys.stderr);sys.exit(7)')
        result = self.finished(tool)
        self.assertEqual(result['exitCode'],7)
        text = Path(result['log']).read_text()
        self.assertIn('literal $(touch SHOULD_NOT_EXIST)',text); self.assertIn('err',text)
        self.assertFalse((self.root/'SHOULD_NOT_EXIST').exists())
        self.assertEqual(Path(result['log']).stat().st_mode & 0o777,0o600)

    def test_active_log_is_bounded_with_marker_and_producer_finishes_successfully(self):
        tool,_ = self.launch('import os;os.write(1,b"prefix"+b"x"*(9*1024*1024));os.write(2,b"stderr")')
        result = self.finished(tool); data = Path(result['log']).read_bytes()
        self.assertEqual(result['exitCode'],0)
        self.assertLessEqual(len(data),LIMIT)
        self.assertTrue(data.startswith(b'prefix')); self.assertIn(b'output truncated',data)

    def test_log_path_symlink_cannot_truncate_another_file(self):
        target=self.put('target','keep')
        folder=self.root/'state/lme-shell/launchpad';folder.mkdir(parents=True)
        (folder/'job.log').symlink_to(target)
        with self.assertRaises(OSError): self.launch('print("should not run")')
        self.assertEqual(target.read_text(),'keep')

    def test_child_sigkill_exit_status_is_preserved(self):
        tool,_ = self.launch('import os,signal;os.kill(os.getpid(),signal.SIGKILL)')
        self.assertEqual(self.finished(tool)['exitCode'],-signal.SIGKILL)

    @unittest.skipUnless(RELAY,'F4 relay not implemented on baseline')
    def test_silent_stubborn_job_is_force_stopped_without_a_polling_service(self):
        marker=self.root/'stubborn'
        tool,child=self.launch(f'import os,signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);open({str(marker)!r},"w").write(str(os.getpid()));time.sleep(30)')
        deadline=time.monotonic()+3
        while not marker.exists() and time.monotonic()<deadline: time.sleep(.01)
        self.assertTrue(marker.exists())
        child.terminate();child.wait(timeout=2)
        self.assertEqual(tool.snapshot()['job']['exitCode'],-signal.SIGKILL)
        stat=Path('/proc')/marker.read_text()/'stat'
        self.assertTrue(not stat.exists() or stat.read_text().rsplit(')',1)[1].split()[0]=='Z')

    @unittest.skipUnless(RELAY,'F4 relay not implemented on baseline')
    def test_detached_job_and_logging_survive_initiator_exit(self):
        marker = self.root/'finished'
        command = shlex.join([sys.executable,'-c',f'import time;from pathlib import Path;time.sleep(.2);Path({str(marker)!r}).touch();print("survived")'])
        entry = dict(name='Detached',kind='command',terminal=False,cwd=str(self.root),command=command)
        code = f'from launchpad import Launchpad;t=Launchpad();t.run("job",{{"job":{entry!r}}},"kitty");print(t.jobs["job"]["process"].pid)'
        env = dict(os.environ,XDG_STATE_HOME=str(self.root/'state'))
        result = subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=3)
        self.assertEqual(result.returncode,0,result.stderr)
        deadline = time.monotonic()+3
        log = self.root/'state/lme-shell/launchpad/job.log'
        while time.monotonic()<deadline and (not marker.exists() or b'survived' not in log.read_bytes()): time.sleep(.01)
        self.assertTrue(marker.exists()); self.assertEqual(log.read_text(),'survived\n')

    @unittest.skipUnless(RELAY,'F4 relay not implemented on baseline')
    def test_inherited_writer_is_drained_before_log_owner_exits(self):
        descendant = "import time;time.sleep(.15);print('last')"
        tool,_ = self.launch('import subprocess,sys;print("first",flush=True);subprocess.Popen([sys.executable,"-c",'+repr(descendant)+'])')
        result = self.finished(tool)
        self.assertEqual(result['exitCode'],0)
        self.assertEqual(Path(result['log']).read_text(),'first\nlast\n')

    @unittest.skipUnless(RELAY,'F4 relay not implemented on baseline')
    def test_explicit_termination_reaps_job_and_keeps_signal_exit(self):
        marker = self.root/'child'
        tool,child = self.launch(f'import os,time;open({str(marker)!r},"w").write(str(os.getpid()));time.sleep(30)')
        deadline = time.monotonic()+3
        while not marker.exists() and time.monotonic()<deadline: time.sleep(.01)
        self.assertTrue(marker.exists()); pid=int(marker.read_text())
        child.terminate();child.wait(timeout=3)
        self.assertEqual(tool.snapshot()['job']['exitCode'],-signal.SIGTERM)
        self.assertFalse((Path('/proc')/str(pid)).exists())

    @unittest.skipUnless(RELAY,'F4 relay not implemented on baseline')
    def test_terminal_wrapper_keeps_literal_argv_cwd_and_exit(self):
        terminal=self.root/'terminal'
        terminal.write_text('#!'+sys.executable+'\nimport os,sys\nfrom pathlib import Path\nPath("terminal-args").write_text(repr(sys.argv[1:]));os.execv(sys.argv[2],sys.argv[2:])\n')
        terminal.chmod(0o700)
        tool,_ = self.launch('import sys;print("terminal");sys.exit(7)',terminal=True,program=str(terminal))
        result=self.finished(tool)
        self.assertEqual(result['exitCode'],7);self.assertTrue(result['terminal'])
        self.assertTrue((self.root/'terminal-args').read_text().startswith("['-e', '/bin/bash'"))
        self.assertIn('terminal',Path(result['log']).read_text())

    @unittest.skipUnless(RELAY,'F4 relay not implemented on baseline')
    def test_failed_exec_handshake_does_not_register_running_job(self):
        broken=self.put('broken','not an executable format');broken.chmod(0o700)
        tool=Launchpad();entry=dict(name='Broken',kind='command',terminal=False,cwd=str(self.root),command=str(broken))
        with patch.dict(os.environ,XDG_STATE_HOME=str(self.root/'state')), self.assertRaises(OSError):
            tool.run('job',{'job':entry},'kitty')
        self.assertFalse(tool.jobs)

    @unittest.skipUnless(RELAY,'F4 relay not implemented on baseline')
    def test_log_sink_failure_drains_and_reports_io_failure_without_killing_producer(self):
        from detached_log import start_detached
        marker=self.root/'finished'
        log=self.put('readonly-log','')
        with log.open('rb') as sink:
            child=start_detached([sys.executable,'-c',f'import os;from pathlib import Path;os.write(1,b"x"*100000);Path({str(marker)!r}).touch()'],
                cwd=self.root,stdin=subprocess.DEVNULL,stdout=sink,stderr=sink,start_new_session=True)
            self.assertEqual(child.wait(timeout=3),74)
        self.assertTrue(marker.exists())

    @unittest.skipUnless(RELAY,'F4 relay not implemented on baseline')
    def test_enospc_writer_is_bounded_and_discards_future_chunks(self):
        import errno
        from detached_log import LimitedLog
        with self.put('sink','').open('wb') as sink:
            writer=LimitedLog(sink.fileno())
            with patch('detached_log.os.write',side_effect=OSError(errno.ENOSPC,'full')) as write:
                writer.write(b'one');writer.write(b'two')
                self.assertEqual(write.call_count,1)
            self.assertTrue(writer.failed)
