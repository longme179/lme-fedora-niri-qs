"""User-authored commands; explicit execution only, with per-entry local job logs."""
# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time


def entries(value):
    if not isinstance(value, dict) or len(value)>100: raise ValueError('Launchpad supports up to 100 commands')
    result={}
    for key,item in value.items():
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,64}',key) or not isinstance(item,dict): raise ValueError('Invalid Launchpad entry')
        name,command,kind,terminal,cwd=(item.get(k) for k in ('name','command','kind','terminal','cwd'))
        if not isinstance(name,str) or not 1<=len(name.strip())<=80 or any(ord(c)<32 for c in name): raise ValueError('Enter a command name (up to 80 characters)')
        if not isinstance(command,str) or not command.strip() or len(command)>16384 or '\0' in command: raise ValueError('Enter a command or Bash script (up to 16 KiB)')
        if kind not in ('command','bash') or type(terminal) is not bool: raise ValueError('Choose a command type and launch mode')
        if not isinstance(cwd,str) or len(cwd)>4096 or any(ord(c)<32 for c in cwd) or cwd and not Path(cwd).expanduser().is_absolute(): raise ValueError('Working directory must be an absolute path, or empty')
        if kind=='command':
            try: argv=shlex.split(command)
            except ValueError as exc: raise ValueError('Command quotes are incomplete') from exc
            if not argv or not argv[0]: raise ValueError('Choose an executable')
        result[key]=dict(name=name.strip(),command=command,kind=kind,terminal=terminal,cwd=cwd)
    return result


class Launchpad:
    def __init__(self):
        self.jobs={}

    def snapshot(self):
        for job in self.jobs.values():
            process=job.get('process')
            if process is not None:
                code=process.poll()
                if code is not None: job.update(process=None,running=False,exitCode=code)
        return {key:{k:v for k,v in job.items() if k!='process'} for key,job in self.jobs.items()}

    def run(self,key,items,terminal,mode=None):
        if key not in items: raise ValueError('This Launchpad command no longer exists')
        self.snapshot()
        if self.jobs.get(key,{}).get('running'): raise ValueError('This command is already running')
        if sum(job['running'] for job in self.jobs.values())>=8: raise ValueError('Up to eight Launchpad commands can run at once')
        entry=entries({key:items[key]})[key]
        if mode not in (None,'background','terminal'): raise ValueError('Choose background or terminal')
        argv=['/bin/bash','-c',entry['command']] if entry['kind']=='bash' else shlex.split(entry['command'])
        argv[0]=os.path.expanduser(argv[0])
        executable=shutil.which(argv[0])
        if not executable: raise ValueError('Executable unavailable: '+argv[0])
        argv[0]=executable
        cwd=Path(entry['cwd']).expanduser() if entry['cwd'] else Path.home()
        if not cwd.is_dir(): raise ValueError('The working directory no longer exists')
        in_terminal=entry['terminal'] if mode is None else mode=='terminal'
        if in_terminal:
            program=shutil.which(terminal)
            if not program: raise ValueError('The configured terminal is unavailable')
            argv=[program,'-e','/bin/bash','-c','"$@"; code=$?; printf "\\nExit status: %s\\n" "$code"; read -r -p "Press Enter to close…"; exit "$code"','launchpad',*argv]
        directory=Path(os.environ.get('XDG_STATE_HOME',Path.home()/'.local/state'))/'lme-shell/launchpad'
        directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        log=directory/(key+'.log')
        flags=os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW
        with os.fdopen(os.open(log,flags,0o600),'w') as output:
            process=subprocess.Popen(argv,cwd=cwd,stdin=subprocess.DEVNULL,stdout=output,stderr=output,start_new_session=True)
        self.jobs[key]=dict(process=process,running=True,exitCode=None,started=time.time(),log=str(log),terminal=in_terminal)
        # Bound history without interrupting user-owned commands.
        for stale in list(self.jobs):
            if len(self.jobs)<=100: break
            if not self.jobs[stale]['running']: del self.jobs[stale]
        return 'Launched '+entry['name']+(' in terminal' if in_terminal else ' · log: '+str(log))
