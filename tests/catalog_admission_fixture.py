"""Cold CLI fixtures and tracing live only inside a disposable checkout."""
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LEGACY = re.search(r'^    (utilities\|appearance\|[^\n]+)\) ;;$',
                   (ROOT/'scripts/settings.sh').read_text(), re.M).group(1).split('|')


def canonical(index):
    records = [json.dumps(record, separators=(',', ':'), ensure_ascii=True) for record in index['features']]
    return '{"version":1,"features":[' + ('\n'+',\n'.join(records)+'\n' if records else '') + ']}\n'


class Checkout:
    def __init__(self, root, full=False):
        self.root = root
        if full:
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        else:
            (root/'scripts').mkdir(parents=True)
            (root/'config').mkdir()
            for name in ('settings.sh', 'feature_catalog.py'):
                shutil.copy2(ROOT/'scripts'/name, root/'scripts'/name)
        (root/'bin').mkdir(exist_ok=True)
        self.trace = root/'catalog-processes.log'
        self.qs = root/'bin/quickshell'
        self.qs.write_text('#!/bin/bash\n[[ " $* " == *" ipc "* ]] && exit 1\nprintf "accepted:%s\\n" "$LME_SETTINGS_PAGE"\n')
        self.qs.chmod(0o700)
        wrapper = root/'bin/python3'
        wrapper.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$CATALOG_TRACE"\nexec "$PYTHON_REAL" "$@"\n')
        wrapper.chmod(0o700)
        self.env = dict(os.environ, PATH=str(root/'bin')+':'+os.environ['PATH'],
            LME_QS_BINARY=str(self.qs), LME_SHELL_DEMO='1', CATALOG_TRACE=str(self.trace), PYTHON_REAL=sys.executable)
        for name in ('CONFIG', 'STATE', 'DATA', 'CACHE', 'RUNTIME'):
            folder = root/('user-'+name.lower()); folder.mkdir(mode=0o700)
            self.env['XDG_'+name+('_DIR' if name == 'RUNTIME' else '_HOME')] = str(folder)
        self.index = root/'config/features.json'
        self.records = []
        (root/'odd}page.qml').write_text('import QtQuick\nItem {}\n')
        for key, enabled in [('sample', True), ('sampleLong', True), ('Case_2-X', True), ('disabled', False)]:
            self.add(key, enabled, settingsPage=dict(key=key, entry='odd}page.qml', title='Page', icon='settings'))
        self.add('barOnly', True, bar=dict(id='barOnly', title='Bar', entry='odd}page.qml', icon='settings'))
        self.add('preferenceFeature', True, preferences={'preferenceOnly': dict(type='boolean', default=True)})
        self.save()

    def add(self, ident, enabled, **parts):
        descriptor = dict(id=ident, **parts)
        path = 'config/'+ident+'.json'
        (self.root/path).write_text(json.dumps(descriptor))
        self.records.append(dict(id=ident, descriptor=path, enabled=enabled,
            startup={kind: value for kind, value in parts.items() if kind != 'preferences'}))

    def save(self):
        self.index.write_text(canonical(dict(version=1, features=self.records)))

    def shell(self, page):
        return subprocess.run(['bash', str(self.root/'scripts/settings.sh'), '--page', page],
            env=self.env, capture_output=True, text=True, timeout=6)

    def python(self, *args):
        return subprocess.run([sys.executable, str(self.root/'scripts/feature_catalog.py'), *args],
            env=self.env, capture_output=True, text=True, timeout=6)

    def calls(self):
        return self.trace.read_text().splitlines() if self.trace.exists() else []
