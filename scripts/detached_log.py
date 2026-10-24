"""Detached user-job relay: bounded disk output, no parent-death cancellation."""
import os
import signal
import sys
import time

MAX_LOG = 8 * 1024 * 1024
MARKER = b'\n[LME: output truncated at 8 MiB; remaining output discarded]\n'


class LimitedLog:
    def __init__(self, descriptor):
        self.descriptor, self.size, self.truncated, self.failed = descriptor, 0, False, False

    def write(self, value):
        if self.failed or self.truncated: return
        try:
            room = MAX_LOG-self.size
            self._write(value[:room])
            self.size += min(len(value), room)
            if len(value) > room:
                os.lseek(self.descriptor, MAX_LOG-len(MARKER), os.SEEK_SET)
                self._write(MARKER)
                self.truncated = True
        except OSError:
            self.failed = True

    def _write(self, value):
        view = memoryview(value)
        while view:
            count = os.write(self.descriptor, view)
            if count <= 0: raise OSError('Log sink did not accept output')
            view = view[count:]


def start_detached(argv, *, cwd, stdin, stdout, stderr, start_new_session):
    import json
    from pathlib import Path
    import selectors
    import subprocess
    read_fd, ready_fd = os.pipe()
    process = None
    try:
        process = subprocess.Popen([sys.executable, '-S', str(Path(__file__).resolve()),
            '--log-fd', str(stdout.fileno()), '--ready-fd', str(ready_fd), '--', *argv],
            cwd=cwd, stdin=stdin, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=start_new_session, pass_fds=(stdout.fileno(), ready_fd))
        os.close(ready_fd); ready_fd = None
        data = bytearray()
        deadline = time.monotonic()+3
        with selectors.DefaultSelector() as selector:
            selector.register(read_fd, selectors.EVENT_READ)
            while b'\n' not in data and len(data) < 8192:
                remaining = deadline-time.monotonic()
                if remaining <= 0: raise OSError('Launchpad log relay did not start')
                if not selector.select(remaining): continue
                chunk = os.read(read_fd, 8192-len(data))
                if not chunk: break
                data.extend(chunk)
        try: reply = json.loads(data)
        except (ValueError, UnicodeError): raise OSError('Launchpad log relay did not start') from None
        if not reply.get('ok'):
            raise OSError(reply['errno'], reply['message'], reply.get('filename'))
        return process
    except BaseException:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=1)
        raise
    finally:
        os.close(read_fd)
        if ready_fd is not None: os.close(ready_fd)


def supervise(command, log_fd, ready_fd):
    import select
    def force_stop(_signum, _frame):
        os.killpg(os.getpid(), signal.SIGKILL)
    signal.signal(signal.SIGALRM, force_stop)
    def stop(signum, _frame):
        signal.signal(signum, signal.SIG_IGN)
        signal.setitimer(signal.ITIMER_REAL, .3)
        os.killpg(os.getpid(), signum)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    os.set_inheritable(log_fd, False)
    os.set_inheritable(ready_fd, False)
    read_fd, write_fd = os.pipe()
    try:
        child = os.posix_spawnp(command[0], command, os.environ, file_actions=[
            (os.POSIX_SPAWN_DUP2, write_fd, 1), (os.POSIX_SPAWN_DUP2, write_fd, 2),
            (os.POSIX_SPAWN_CLOSE, read_fd), (os.POSIX_SPAWN_CLOSE, write_fd)],
            setsigdef=(signal.SIGTERM, signal.SIGINT))
        os.write(ready_fd, b'{"ok":true}\n')
    except OSError as error:
        import json
        os.write(ready_fd, (json.dumps(dict(ok=False, errno=error.errno,
            message=error.strerror, filename=error.filename))+'\n').encode())
        os.close(read_fd)
        return 1
    finally:
        os.close(ready_fd)
        os.close(write_fd)
    sink = LimitedLog(log_fd)
    try:
        while True:
            select.select([read_fd], [], [])
            value = os.read(read_fd, 65536)
            if not value: break
            sink.write(value)
        _, status = os.waitpid(child, 0)
        code = os.waitstatus_to_exitcode(status)
        if code < 0:
            if -code not in (signal.SIGKILL, signal.SIGSTOP): signal.signal(-code, signal.SIG_DFL)
            import resource
            resource.setrlimit(resource.RLIMIT_CORE, (0,0))
            os.kill(os.getpid(), -code)
        return code or (74 if sink.failed else 0)
    finally:
        os.close(read_fd)
        os.close(log_fd)


def main():
    args = sys.argv[1:]
    if len(args) < 6 or args[0] != '--log-fd' or args[2] != '--ready-fd' or args[4] != '--':
        raise SystemExit('Expected log/readiness descriptors and literal command')
    return supervise(args[5:], int(args[1]), int(args[3]))


if __name__ == '__main__': raise SystemExit(main())
