#!/usr/bin/env python3
"""Owned Cava bridge, emitting bounded real spectrum frames as JSON lines."""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

CONFIG='''[general]
bars=16
framerate=25
sleep_timer=3
[output]
method=raw
raw_target=/dev/stdout
data_format=ascii
ascii_max_range=100
bar_delimiter=59
frame_delimiter=10
channels=mono
'''


def frame(line):
    parts=line.strip().strip(';').split(';')
    if len(parts)!=16: return None
    try:
        values=[float(p) for p in parts]
        if not all(math.isfinite(v) for v in values): return None
        return [max(0,min(100,v))/100 for v in values]
    except ValueError: return None


def main():
    child=None
    def stop(*_): raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        binary=shutil.which('cava')
        if not binary: raise RuntimeError('Install cava to enable the audio visualizer')
        with tempfile.TemporaryDirectory(prefix='lme-cava-') as folder:
            config=Path(folder)/'config';config.write_text(CONFIG);config.chmod(0o600)
            with tempfile.TemporaryFile(mode='w+') as errors:
                child=subprocess.Popen([binary,'-p',str(config)],stdout=subprocess.PIPE,stderr=errors,text=True)
                for line in iter(lambda:child.stdout.readline(2048),''):
                    values=frame(line)
                    if values is not None: print(json.dumps({'bars':values}),flush=True)
                code=child.wait()
                if code: raise RuntimeError('Cava could not start; check its audio backend support')
    except (OSError,RuntimeError) as error: print(json.dumps({'error':str(error)[:300]}),flush=True)
    finally:
        if child and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=2)
            except subprocess.TimeoutExpired: child.kill();child.wait()

if __name__=='__main__': main()
