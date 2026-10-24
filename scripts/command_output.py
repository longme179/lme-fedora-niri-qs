"""Bounded pipe retention while continuing to drain an owned subprocess."""
import os
import selectors
import subprocess
import time

DEFAULT_LIMIT = 8 * 1024 * 1024
LIMITS = {'niri': 16 * 1024 * 1024, 'busctl': 16 * 1024 * 1024,
          'pw-dump': 16 * 1024 * 1024, 'nmcli': 2 * 1024 * 1024}


def capture(process, check, limit, observe=None):
    buffers = [bytearray(), bytearray()]
    retained, overflow = 0, False
    observation_due = time.monotonic() + .1
    with selectors.DefaultSelector() as selector:
        for index, stream in enumerate((process.stdout, process.stderr)):
            if stream is not None: selector.register(stream, selectors.EVENT_READ, index)
        while selector.get_map():
            for key, _ in selector.select(check()):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                room = max(0, limit-retained)
                buffers[key.data].extend(chunk[:room])
                retained += min(room, len(chunk))
                overflow = overflow or len(chunk) > room
            if observe is not None and time.monotonic() >= observation_due:
                observe(bytes(buffers[0]), bytes(buffers[1]))
                observation_due = time.monotonic() + .1
        # Do not poll/reap the group leader while descendants still hold its pipes.
        while True:
            try:
                process.wait(timeout=check())
                break
            except subprocess.TimeoutExpired:
                if observe is not None: observe(bytes(buffers[0]), bytes(buffers[1]))
    return (*[bytes(value) for value in buffers], overflow)


def text(value):
    return value.decode('utf-8', 'replace').replace('\r\n', '\n').replace('\r', '\n')
