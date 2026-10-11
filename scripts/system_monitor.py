"""On-demand /proc monitoring. Never opens GPU devices or runs GPU tools."""
from collections import deque
import os
from itertools import islice
from pathlib import Path
import pwd
import time


class SystemMonitor:
    def __init__(self, proc=Path('/proc'), clock=time.monotonic):
        self.proc, self.clock = proc, clock
        self.previous_time = None
        self.cores, self.network, self.processes = {}, {}, {}
        self.users = {}
        self.history = deque(maxlen=60)
        self.state = {}

    def read(self, path):
        try: return path.read_text()
        except (OSError, UnicodeError): return ''

    def sample(self, system):
        now = self.clock()
        elapsed = now - self.previous_time if self.previous_time is not None else 0
        core_rows, cores = [], {}
        for line in self.read(self.proc / 'stat').splitlines():
            fields = line.split()
            if not fields or not fields[0].startswith('cpu') or fields[0] == 'cpu': continue
            try:
                ticks = [int(n) for n in fields[1:9]]
                total, idle = sum(ticks), ticks[3] + ticks[4]
                old = self.cores.get(fields[0])
                percent = None
                if old and total > old[0]: percent = round(max(0, min(100, 100 * (1 - (idle-old[1])/(total-old[0])))), 1)
                cores[fields[0]] = (total, idle)
                core_rows.append({'name': fields[0].upper(), 'percent': percent})
            except (ValueError, IndexError): continue
        interfaces, network = [], {}
        for line in self.read(self.proc / 'net/dev').splitlines():
            name, sep, values = line.partition(':')
            name = name.strip()
            if not sep or name == 'lo': continue
            try:
                fields = values.split(); received, sent = int(fields[0]), int(fields[8])
                old = self.network.get(name)
                download = max(0, received - old[0])/elapsed if old and elapsed > 0 else None
                upload = max(0, sent - old[1])/elapsed if old and elapsed > 0 else None
                network[name] = (received, sent)
                interfaces.append({'name': name, 'download': download, 'upload': upload})
            except (ValueError, IndexError): continue
        processes, identities = [], {}
        try: directories = list(islice((p for p in self.proc.iterdir() if p.name.isdigit()), 4096))
        except OSError: directories = []
        for directory in directories:
            # The comm field can contain spaces and ')'; split after its final ')'.
            line = self.read(directory / 'stat')
            start, end = line.find('('), line.rfind(')')
            if start < 0 or end < start: continue
            try:
                fields = line[end+1:].split()
                ticks, born = int(fields[11])+int(fields[12]), int(fields[19])
                rss = max(0, int(fields[21])) * os.sysconf('SC_PAGE_SIZE')
                ident = (int(directory.name), born)
                old = self.processes.get(ident)
                cpu = max(0, ticks-old)/os.sysconf('SC_CLK_TCK')/elapsed*100 if old is not None and elapsed > 0 else None
                uid = directory.stat().st_uid
                if uid not in self.users:
                    try: self.users[uid] = pwd.getpwuid(uid).pw_name
                    except KeyError: self.users[uid] = str(uid)
                identities[ident] = ticks
                if rss:
                    processes.append({'pid': ident[0], 'name': line[start+1:end], 'user': self.users[uid], 'cpu': round(cpu, 1) if cpu is not None else None, 'memoryBytes': rss})
            except (OSError, ValueError, IndexError): continue
        processes.sort(key=lambda p: (-(p['cpu'] or 0), -p['memoryBytes'], p['pid']))
        self.cores, self.network, self.processes, self.previous_time = cores, network, identities, now
        sample = {'cpu': system.get('cpu'), 'memory': system.get('memoryPercent'),
                  'download': sum(i['download'] or 0 for i in interfaces) if elapsed > 0 else None, 'upload': sum(i['upload'] or 0 for i in interfaces) if elapsed > 0 else None}
        self.history.append(sample)
        self.state = {'cores': core_rows, 'interfaces': interfaces, 'processes': processes,
                      'processCount': len(processes), 'history': list(self.history), 'sampledAt': now,
                      'error': '' if core_rows else 'CPU statistics are unavailable.'}
        return self.state
