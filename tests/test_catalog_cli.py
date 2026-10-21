"""Page admission and explicit validation use disposable copies, never user settings."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CatalogCliCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('scripts', 'config', 'bin'): (self.root/name).mkdir()
        for name in ('settings.sh', 'feature_catalog.py'):
            shutil.copy2(ROOT/'scripts'/name, self.root/'scripts'/name)
        (self.root/'config/features.json').write_text('{"version":1,"features":[]}')
        self.qs = self.root/'bin/qs'
        self.qs.write_text('#!/bin/bash\n[[ " $* " == *" ipc "* ]] && exit 1\nprintf "accepted:%s\\n" "$LME_SETTINGS_PAGE"\n')
        self.qs.chmod(0o700)
        self.env = dict(os.environ, LME_QS_BINARY=str(self.qs), LME_SHELL_DEMO='1')

    def launch(self, page):
        return subprocess.run(['bash', str(self.root/'scripts/settings.sh'), '--page', page],
            env=self.env, capture_output=True, text=True, timeout=5)

    def test_legacy_pages_and_empty_unknown_keep_messages_and_codes(self):
        for page in ('appearance', 'clipboard', 'controlLayout', 'about'):
            result = self.launch(page)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'accepted:'+page+'\n', ''))
        result = self.launch('absent')
        self.assertEqual((result.returncode, result.stdout, result.stderr),
            (2, '', 'Error: unknown settings page: absent\n'))

    def test_enabled_inline_page_and_disabled_page_admission(self):
        entry = self.root/'page.qml'; entry.write_text('import QtQuick\nItem {}\n')
        descriptor = {'id': 'sample'}
        (self.root/'config/sample.json').write_text(json.dumps(descriptor))
        record = {'id': 'sample', 'descriptor': 'config/sample.json', 'enabled': True,
            'startup': {'settingsPage': {'key': 'sample', 'title': 'Sample', 'icon': 'settings', 'entry': 'page.qml'}}}
        index = self.root/'config/features.json'
        index.write_text(json.dumps({'version': 1, 'features': [record]}))
        result = self.launch('sample')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'accepted:sample\n', ''))
        record['enabled'] = False
        index.write_text(json.dumps({'version': 1, 'features': [record]}))
        result = self.launch('sample')
        self.assertEqual((result.returncode, result.stdout, result.stderr),
            (2, '', 'Error: unknown settings page: sample\n'))

    def test_explicit_check_still_rejects_missing_descriptor(self):
        (self.root/'config/features.json').write_text(json.dumps({'version': 1, 'features': [
            {'id': 'sample', 'descriptor': 'config/missing.json', 'enabled': True}]}))
        result = subprocess.run(['python3', str(self.root/'scripts/feature_catalog.py'), '--check'],
            capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Feature catalog: Missing or escaping resource:', result.stderr)
