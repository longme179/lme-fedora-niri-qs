"""Bounded local launch counts; no window tracking or background index."""
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Illia Miroshnichenko
# Launch-score decay adapted from Serpantinum app_rank.py; see THIRD_PARTY.md.
from contextlib import contextmanager
from datetime import date,datetime,timezone
from pathlib import Path
import fcntl
import json
import os
import time
from storage import write_json

HALF_LIFE_DAYS=7
LAUNCH_SECONDS_PER_EVENT=90
RETENTION_DAYS=60
MAX_APPS=256


class LauncherHistory:
    def __init__(self,path=None):
        self.path=path or Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'lme-shell/launcher.json'
        self.error=''
        self.stamp=None
        self.day=None
        self.scores={}

    @contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with os.fdopen(os.open(self.path.with_suffix('.lock'),os.O_CREAT|os.O_RDWR,0o600),'w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            yield

    def read(self,today):
        try:
            if self.path.stat().st_size>1024*1024: return {}
            raw=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,UnicodeError,ValueError,RecursionError): return {}
        if not isinstance(raw,dict) or type(raw.get('schema')) is not int or raw['schema']!=1 or not isinstance(raw.get('apps'),dict): return {}
        result={}
        for app,item in list(raw['apps'].items())[:MAX_APPS*2]:
            if not isinstance(app,str) or not 1<=len(app)<=512 or any(ord(c)<32 or 0xd800<=ord(c)<=0xdfff for c in app) or not isinstance(item,dict): continue
            last=item.get('last');days=item.get('days')
            if type(last) not in (int,float) or not 0<=last<=253402300799 or not isinstance(days,dict): continue
            valid={}
            for key,count in days.items():
                if not isinstance(key,str) or len(key)!=10 or type(count) is not int or not 1<=count<=1000000: continue
                try: age=(today-date.fromisoformat(key)).days
                except ValueError: continue
                if age<RETENTION_DAYS: valid[key]=count
            if valid: result[app]={'last':last,'days':dict(sorted(valid.items(),reverse=True)[:RETENTION_DAYS])}
        return dict(sorted(result.items(),key=lambda entry:entry[1]['last'],reverse=True)[:MAX_APPS])

    def record(self,app,now=None):
        if not isinstance(app,str) or not 1<=len(app)<=512 or any(ord(c)<32 or 0xd800<=ord(c)<=0xdfff for c in app): return
        now=time.time() if now is None else now
        today=datetime.fromtimestamp(now,timezone.utc).date()
        try:
            with self.locked():
                apps=self.read(today)
                item=apps.setdefault(app,{'last':now,'days':{}})
                item['last']=now;key=today.isoformat()
                item['days'][key]=min(1000000,item['days'].get(key,0)+1)
                apps=dict(sorted(apps.items(),key=lambda entry:entry[1]['last'],reverse=True)[:MAX_APPS])
                write_json(self.path,{'schema':1,'apps':apps})
            self.error='';self.stamp=None
        except (OSError,ValueError) as exc:
            # Launch already succeeded; history failure must not turn it into a launch failure.
            self.error='Usage history could not be saved: '+str(exc)[:180]

    def snapshot(self,enabled=True,now=None):
        if not enabled: return {}
        now=time.time() if now is None else now
        today=datetime.fromtimestamp(now,timezone.utc).date()
        try:
            stat=self.path.stat();stamp=(stat.st_mtime_ns,stat.st_size,stat.st_ino)
        except OSError: stamp=()
        if stamp==self.stamp and today==self.day: return self.scores
        scores={}
        for app,item in self.read(today).items():
            total_weight=0.0
            for day,count in item['days'].items():
                age_days=max(0,(today-date.fromisoformat(day)).days)
                weight=0.5**(age_days/HALF_LIFE_DAYS)
                total_weight+=count*weight
            scores[app]={'score':total_weight*LAUNCH_SECONDS_PER_EVENT,'last':min(now,item['last'])}
        self.stamp=stamp;self.day=today;self.scores=scores
        return scores

    def clear(self):
        with self.locked(): write_json(self.path,{'schema':1,'apps':{}})
        self.stamp=None;self.error=''
