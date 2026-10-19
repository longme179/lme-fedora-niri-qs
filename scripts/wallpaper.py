"""Bounded wallpaper playlists and per-output awww images; no rendering daemon."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from contextlib import contextmanager
import fcntl
import math
import os
import random
import re
import time

TRANSITIONS = ('fade','wipe','wave','grow','outer','left','right','top','bottom','simple','none','random')
EXTENSIONS = {'.png','.jpg','.jpeg','.webp','.gif','.bmp'}
DEFAULTS = {'wallpaperPlaylist':[], 'wallpaperPlaylistEnabled':False, 'wallpaperPlaylistPaused':False,
            'wallpaperPlaylistShuffle':False, 'wallpaperPlaylistInterval':300, 'wallpaperPlaylistOutput':'',
            'wallpaperTransition':'fade', 'wallpaperTransitionDuration':3.0, 'wallpaperOutputs':{}}


def output_name(value, shared=False):
    if isinstance(value,str) and ((shared and value=='') or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',value)):
        return value
    raise ValueError('Choose a valid display name')


def image_path(value):
    if not isinstance(value,str) or not value or len(value)>4096 or any(ord(c)<32 for c in value):
        raise ValueError('Choose a wallpaper image path')
    path=Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError('Choose an absolute PNG, JPEG, WebP, GIF, or BMP path')
    try: path=path.resolve()
    except RuntimeError as exc: raise ValueError('Wallpaper path contains a symlink loop') from exc
    text=str(path)
    if path.suffix.lower() not in EXTENSIONS or len(text)>4096 or any(ord(c)<32 or 0xd800<=ord(c)<=0xdfff for c in text):
        raise ValueError('Choose an absolute PNG, JPEG, WebP, GIF, or BMP path')
    return text


def validate(key,value):
    if key in {'wallpaperPlaylistEnabled','wallpaperPlaylistPaused','wallpaperPlaylistShuffle'} and type(value) is bool: return value
    if key=='wallpaperPlaylistInterval' and type(value) is int and 30<=value<=86400: return value
    if key=='wallpaperPlaylistOutput': return output_name(value,shared=True)
    if key=='wallpaperTransition' and isinstance(value,str) and value in TRANSITIONS: return value
    if key=='wallpaperTransitionDuration' and type(value) in (int,float) and math.isfinite(value) and .1<=value<=10: return float(value)
    if key=='wallpaperPlaylist' and isinstance(value,list) and len(value)<=500:
        paths=list(dict.fromkeys(image_path(path) for path in value))
        if sum(len(path.encode('utf-8')) for path in paths)<=128*1024: return paths
    if key=='wallpaperOutputs' and isinstance(value,dict) and len(value)<=32:
        return {output_name(name):image_path(path) for name,path in value.items()}
    raise ValueError('Invalid wallpaper preference: '+key)


def query_outputs(text):
    # Both legacy "OUTPUT: WxH" and current "NAMESPACE: OUTPUT: WxH" are supported.
    return set(re.findall(r'^(?:[^:\n]+:\s*)?([A-Za-z0-9][A-Za-z0-9_.-]*):\s*\d+x\d+\b',text,re.MULTILINE))


class Wallpapers:
    def __init__(self,runner,preferences):
        self.runner=runner
        self.preferences=preferences
        self.applied={}
        self.retry_at=0
        self.deadline=None
        self.remaining=None
        self.signature=None
        self.was_paused=False
        self.connected=None
        self.cursor=None
        self.closed=False

    @contextmanager
    def operation(self):
        self.preferences.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with os.fdopen(os.open(self.preferences.path.parent/'wallpaper.lock',os.O_CREAT|os.O_RDWR,0o600),'w') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as exc: raise ValueError('Another wallpaper change is running; try again shortly') from exc
            self.preferences.reload()
            yield

    def ready(self):
        if self.closed: raise ValueError('Wallpaper operation was cancelled')
        self.runner.executable('awww')
        try: return self.runner.run('awww','query',timeout=1)
        except RuntimeError:
            if self.closed: raise ValueError('Wallpaper operation was cancelled')
            self.runner.spawn([self.runner.executable('awww-daemon')])
        deadline=time.monotonic()+4
        while not self.closed:
            try: return self.runner.run('awww','query',timeout=1)
            except RuntimeError:
                if time.monotonic()>=deadline: break
                time.sleep(.1)
        raise ValueError('awww-daemon did not become ready. Check your Wayland session.')

    def current(self,output):
        p=self.preferences.values
        return p['wallpaperOutputs'].get(output,p['wallpaper']) if output else p['wallpaper']

    def apply(self,raw,output='',save=True,animate=True):
        with self.operation(): return self._apply(raw,output,save,animate)

    def _apply(self,raw,output='',save=True,animate=True):
        output=output_name(output,shared=True)
        path=Path(image_path(raw))
        if not path.is_file(): raise ValueError('Select an existing wallpaper image')
        outputs=query_outputs(self.ready())
        p=self.preferences.values
        targets=[output] if output else sorted(outputs-set(p['wallpaperOutputs']))
        if output and outputs and output not in outputs: targets=[]
        if not output and p['wallpaperOutputs'] and not outputs:
            raise ValueError('awww did not report its displays; existing wallpapers were kept')
        if targets or not output and not p['wallpaperOutputs']:
            transition=p['wallpaperTransition'] if animate and p['animations'] else 'none'
            args=['img',str(path),'--transition-type',transition]
            if targets: args+=['--outputs',','.join(targets)]
            if transition not in ('none','simple') and p['wallpaperTransitionDuration']!=3:
                args+=['--transition-duration',str(p['wallpaperTransitionDuration'])]
            if self.closed: raise ValueError('Wallpaper operation was cancelled')
            self.runner.run('awww',*args,timeout=15)
            self.applied={**self.applied,**{name:str(path) for name in targets}}
        if self.closed: raise ValueError('Wallpaper operation was cancelled')
        if save:
            if output: self.preferences.set('wallpaperOutputs',str(path),token=output)
            else: self.preferences.set('wallpaper',str(path))
        return 'Wallpaper updated' if targets or not output else 'Wallpaper saved for the disconnected display'

    def reset_output(self,output):
        with self.operation():
            output=output_name(output)
            if not self.preferences.values['wallpaper']: raise ValueError('Choose a shared wallpaper first')
            self._apply(self.preferences.values['wallpaper'],output,save=False)
            self.preferences.set('wallpaperOutputs',None,token=output)
        return 'Display uses the shared wallpaper'

    def advance(self,output=None,automatic=False):
        with self.operation():
            p=self.preferences.values
            if automatic and (not p['wallpaperPlaylistEnabled'] or p['wallpaperPlaylistPaused'] or p['wallpaperPlaylistOutput']!=output): return ''
            return self._advance(output)

    def _advance(self,output):
        p=self.preferences.values
        output=output_name(p['wallpaperPlaylistOutput'] if output is None else output,shared=True)
        paths=[path for path in p['wallpaperPlaylist'] if Path(path).is_file()]
        if not paths: raise ValueError('The playlist has no available images')
        current=self.current(output)
        if len(paths)==1 and paths[0]==current: return 'The only playlist image is already active'
        if p['wallpaperPlaylistShuffle']:
            choices=[path for path in paths if path!=current]
            random.shuffle(choices)
        else:
            previous=self.cursor[1] if self.cursor and self.cursor[0]==output and self.cursor[2]==current else current
            index=(paths.index(previous)+1)%len(paths) if previous in paths else 0
            choices=[path for path in paths[index:]+paths[:index] if path!=current]
        error='No wallpaper could be applied'
        for path in choices[:10]:
            self.cursor=(output,path,current)
            try: return self._apply(path,output)
            except (RuntimeError,ValueError,OSError) as exc: error=str(exc)
        raise ValueError(error)

    def due(self,outputs,now=None):
        """Return one job for the existing backend executor; no new polling loop."""
        now=time.monotonic() if now is None else now
        p=self.preferences.values
        outputs=set(outputs)
        if outputs!=self.connected: self.retry_at=0
        if self.connected is None and outputs:
            # start.sh owns the initial shared image, including its --wallpaper override.
            self.applied={**self.applied,**{name:p['wallpaper'] for name in outputs if name not in p['wallpaperOutputs']}}
        if outputs or self.connected is not None: self.connected=outputs
        self.applied={name:path for name,path in self.applied.items() if name in outputs}
        signature=(tuple(p['wallpaperPlaylist']),p['wallpaperPlaylistEnabled'],p['wallpaperPlaylistShuffle'],
                   p['wallpaperPlaylistInterval'],p['wallpaperPlaylistOutput'],p['wallpaper'],tuple(sorted(p['wallpaperOutputs'].items())))
        if signature!=self.signature:
            self.signature=signature; self.cursor=None; self.remaining=None; self.deadline=None
            self.retry_at=0
        paused=p['wallpaperPlaylistPaused']
        if not p['wallpaperPlaylistEnabled'] or not p['wallpaperPlaylist']:
            self.deadline=None; self.remaining=None
        elif paused:
            if self.deadline is not None: self.remaining=max(0,self.deadline-now)
            self.deadline=None
        elif self.deadline is None:
            self.deadline=now+(self.remaining if self.was_paused and self.remaining is not None else p['wallpaperPlaylistInterval'])
            self.remaining=None
        self.was_paused=paused
        if not outputs: return None
        # Restore only changed or newly connected displays, preserving fixed overrides.
        desired={name:self.current(name) for name in outputs}
        restore=[name for name,path in desired.items() if path and Path(path).is_file() and self.applied.get(name)!=path]
        if restore and now>=self.retry_at:
            self.retry_at=now+30
            if self.deadline is not None and self.deadline<=now: self.deadline=now+p['wallpaperPlaylistInterval']
            return lambda: self.restore(restore)
        if self.deadline is not None and now>=self.deadline:
            self.deadline=now+p['wallpaperPlaylistInterval']
            if p['wallpaperPlaylistOutput'] and p['wallpaperPlaylistOutput'] not in outputs: return None
            return lambda output=p['wallpaperPlaylistOutput']: self.advance(output,automatic=True)
        return None

    def restore(self,outputs):
        with self.operation():
            for name in outputs:
                path=self.current(name)
                if path: self._apply(path,name,save=False,animate=False)
        return ''

    def close(self):
        self.closed=True
