#!/usr/bin/env python3
"""Bounded lyric lookup: embedded text, local LRC, disk cache, optional LRCLIB."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit, unquote
from urllib.request import Request, urlopen
from storage import write_json

MAX_BYTES = 512 * 1024
MAX_LINES = 4000
STAMP = re.compile(r'\[(\d{1,3}):([0-5]\d)(?:[.:](\d{1,3}))?\]')


def parse(text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Lyrics are too large or invalid')
    offset = re.search(r'\[offset:([+-]?\d+)\]', text, re.I)
    offset = int(offset[1]) / 1000 if offset else 0
    cues = []; expanded_bytes = 0
    for line in text.splitlines()[:MAX_LINES]:
        stamps = list(STAMP.finditer(line)); words = STAMP.sub('', line).strip()
        for stamp in stamps:
            expanded_bytes += len(words.encode('utf-8')) + 64
            if expanded_bytes > MAX_BYTES: raise ValueError('Expanded lyrics are too large')
            seconds = int(stamp[1])*60 + int(stamp[2]) + (int(stamp[3]) / 10**len(stamp[3]) if stamp[3] else 0)
            cues.append({'time': round(max(0, seconds - offset), 3), 'text': words})
            if len(cues) >= MAX_LINES: break
        if len(cues) >= MAX_LINES: break
    cues.sort(key=lambda cue: cue['time'])
    # Group equal timestamps so translations/duets remain visible together.
    grouped = []
    for cue in cues:
        if grouped and grouped[-1]['time'] == cue['time']:
            if cue['text'] and cue['text'] not in grouped[-1]['text'].split('\n'): grouped[-1]['text'] += '\n' + cue['text']
        else: grouped.append(cue)
    plain = '\n'.join(line for line in text.splitlines()[:MAX_LINES] if not re.fullmatch(r'\s*\[[a-zA-Z]+:.*\]\s*', line)).strip()
    return {'synced': bool(grouped), 'lines': grouped, 'plain': '' if grouped else plain}


def track(request):
    if not isinstance(request, dict): raise ValueError('Expected a lyric request')
    result = {}
    for key, limit in [('title', 512), ('artist', 512), ('album', 512), ('url', 4096), ('embedded', MAX_BYTES)]:
        value = request.get(key, '')
        if not isinstance(value, str) or len(value.encode('utf-8')) > limit: raise ValueError('Invalid ' + key)
        result[key] = value.strip()
    duration = request.get('duration', 0)
    if type(duration) not in (int, float) or not math.isfinite(duration) or not 0 <= duration <= 86400: raise ValueError('Invalid duration')
    if type(request.get('online', False)) is not bool: raise ValueError('Online lookup must be boolean')
    result.update(duration=round(duration), online=request.get('online', False))
    return result


def fetch(params):
    request = Request('https://lrclib.net/api/get?' + urlencode(params), headers={
        'User-Agent': 'LME-Shell/2 (https://github.com/longme179/lme-fedora-niri-qs)', 'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=7) as reply:
            body = reply.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES: raise ValueError('Lyrics response is too large')
            data = json.loads(body)
            if not isinstance(data, dict): raise ValueError('Invalid lyrics response')
            return data
    except HTTPError as error:
        if error.code == 404: return {}
        raise


def result(text='', source='', instrumental=False):
    parsed = parse(text)
    return {**parsed, 'status': 'instrumental' if instrumental else 'ready' if parsed['lines'] or parsed['plain'] else 'none', 'source': source}


def lookup(request, cache=None, opener=fetch, now=time.time):
    song = track(request)
    if song['embedded']: return result(song['embedded'], 'Player metadata')
    url = urlsplit(song['url'])
    if url.scheme == 'file' and url.netloc in ('', 'localhost'):
        sidecar = Path(unquote(url.path)).with_suffix('.lrc')
        try:
            if sidecar.is_file():
                with sidecar.open('rb') as file: body = file.read(MAX_BYTES + 1)
                return result(body.decode('utf-8-sig'), 'Local LRC')
        except (OSError, UnicodeError, ValueError): pass
    if not song['title'] or not song['artist']: return {**result(), 'status': 'metadata'}
    directory = Path(cache or Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache'))/'lme-shell/lyrics')
    key = hashlib.sha256(json.dumps([song[k] for k in ('title','artist','album','duration')], ensure_ascii=False).encode()).hexdigest()
    path = directory / (key + '.json')
    try:
        if path.stat().st_size <= MAX_BYTES*2:
            data = json.loads(path.read_text())
            ttl = 6*3600 if data.get('status') == 'none' else 14*86400
            if 0 <= now() - path.stat().st_mtime < ttl and data.get('status') in ('ready','instrumental','none'):
                checked = result(data.get('raw', ''), 'LRCLIB · cached', data.get('status') == 'instrumental')
                return checked
    except (OSError, ValueError, TypeError, AttributeError): pass
    if not song['online']: return {**result(), 'status': 'offline'}
    params = {'track_name': song['title'], 'artist_name': song['artist']}
    if song['album']: params['album_name'] = song['album']
    if song['duration']: params['duration'] = song['duration']
    data = opener(params)
    if not isinstance(data, dict): raise ValueError('Invalid lyrics response')
    raw = data.get('syncedLyrics') or data.get('plainLyrics') or ''
    found = result(raw, 'LRCLIB', data.get('instrumental') is True)
    try:
        write_json(path, {'raw': raw, 'status': found['status']})
        # Cache maintenance is bounded and happens only after a lookup.
        entries = sorted(directory.glob('*.json'), key=lambda item: item.stat().st_mtime, reverse=True)
        for old in entries[128:]: old.unlink(missing_ok=True)
    except OSError: pass
    return found


def main():
    try:
        raw = sys.stdin.buffer.readline(MAX_BYTES + 16384)
        if len(raw) >= MAX_BYTES + 16384: raise ValueError('Lyrics request is too large')
        value = lookup(json.loads(raw))
    except Exception as error:
        value = {**result(), 'status': 'error', 'error': 'Lyrics unavailable. Check your connection or retry.' if isinstance(error, OSError) else str(error)[:300]}
    print(json.dumps(value, ensure_ascii=False), flush=True)


if __name__ == '__main__': main()
