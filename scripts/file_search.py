"""Bounded name search in explicit local roots; no indexer or hidden traversal.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: launcher; Phase 3 graph).
"""
# SPDX-License-Identifier: AGPL-3.0-or-later
# DEPRECATED(Q5->Q6): the action ownership moved to FileSearchState.qml; this module stays
# the bounded scandir helper (quickshell 0.3.2 cannot list directories) and the A/B source.
import os
import json
import sys
from pathlib import Path
import time


def main():
    """Q5 worker mode: one JSON request line in, one result line out (bounded like lyrics.py)."""
    raw = sys.stdin.buffer.readline(65536)
    if len(raw) >= 65536: raise ValueError('File search request is too large')
    request = json.loads(raw)
    from threading import Event
    print(json.dumps(search(request['query'], request['folders'], Event()), ensure_ascii=False), flush=True)



def roots(value):
    if not isinstance(value,list) or not 1<=len(value)<=8 or not all(isinstance(p,str) and 1<=len(p)<=4096 and not any(ord(c)<32 for c in p) for p in value):
        raise ValueError('Choose one to eight local search folders')
    return list(dict.fromkeys(str(Path(p).expanduser().resolve()) for p in value))


def search(query, folders, cancel, limit=100, max_paths=10000, seconds=1.5):
    if not isinstance(query,str) or not 2<=len(query.strip())<=160: raise ValueError('File search needs 2–160 characters')
    query=query.strip();needle=query.casefold();entries=[];visited=0;truncated=False
    deadline=time.monotonic()+seconds;stack=[Path(p) for p in roots(folders)];seen=set()
    while stack and not cancel.is_set():
        directory=stack.pop()
        if str(directory) in seen: continue
        seen.add(str(directory))
        try:
            with os.scandir(directory) as children:
                for item in children:
                    if cancel.is_set(): return {'query':query,'entries':[],'truncated':False}
                    visited+=1
                    if visited>max_paths or time.monotonic()>=deadline: truncated=True;break
                    if item.name.startswith('.') or item.is_symlink(): continue
                    try:
                        is_dir=item.is_dir(follow_symlinks=False)
                        if not is_dir and not item.is_file(follow_symlinks=False): continue
                        if needle in item.name.casefold(): entries.append({'kind':'file','id':item.path,'path':item.path,'name':item.name,'directory':is_dir})
                        if is_dir: stack.append(Path(item.path))
                    except OSError: continue
                    if len(entries)>=limit: truncated=True;break
        except OSError: continue
        if truncated: break
    entries.sort(key=lambda e:(not e['directory'],e['name'].casefold(),e['path']))
    return {'query':query,'entries':entries,'truncated':truncated}

if __name__ == '__main__':
    if '--worker' in sys.argv: main()
