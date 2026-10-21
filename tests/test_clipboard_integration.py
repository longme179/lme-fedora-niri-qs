"""Clipboard's observable integration is pinned before catalog ownership moves."""
import ast
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import catalog_fixture as fixture
from test_backend import backend
import clipboard
import content_types

ROOT = Path(__file__).resolve().parents[1]
GESTURES = ('default none control audio devices agenda system wifi notifications activity launcher '
    'launchpad clipboard settings power overview workspaceBoard mute dnd volumeUp volumeDown '
    'mediaToggle mediaNext mediaPrevious workspaceNext workspacePrevious').split()
QUERIES = ['', 'clipboard', 'history', 'capture', 'image', 'pin', 'copy']


class ClipboardContractsCase(unittest.TestCase):
    def test_order_default_layout_search_and_gesture_choices(self):
        expected = json.loads((ROOT/'tests/fixtures/catalog-legacy.json').read_text())
        qml = fixture.QML.replace('function entries(): void', '''function contract(): string {
            const searches = {};
            for (const query of ["", "clipboard", "history", "capture", "image", "pin", "copy"])
                searches[query] = SettingsRegistry.search(query).map(page => page.key);
            return JSON.stringify({bars: BarRegistry.modules.map(item => item.id),
                defaults: BarRegistry.defaults, pages: SettingsRegistry.pages.map(item => item.key),
                gestures: BarGestures.actions.map(item => item.id), searches});
        }
        function entries(): void''')
        with patch.object(fixture, 'QML', qml), fixture.session() as probe:
            state = json.loads(probe.call('contract'))
        self.assertEqual(state['bars'], [item['id'] for item in expected['bars']])
        self.assertEqual(state['defaults'], expected['defaults'])
        self.assertEqual(state['pages'], [item['key'] for item in expected['pages']])
        self.assertEqual(state['gestures'], GESTURES)
        for query in QUERIES:
            with self.subTest(query=query):
                keys = [page['key'] for page in expected['pages'] if all(word in
                    (page['title']+' '+page['description']+' '+page['keywords']).lower()
                    for word in query.lower().split())]
                self.assertEqual(state['searches'][query], keys)

    def test_preferences_limits_and_content_compatibility_stay_legacy(self):
        self.assertEqual({key: backend.DEFAULT_PREFERENCES[key] for key in
            ('clipboardEnabled', 'clipboardImages', 'clipboardLimit')},
            dict(clipboardEnabled=True, clipboardImages=True, clipboardLimit=100))
        for value in (20, 100, 500):
            self.assertEqual(backend.validate_preference('clipboardLimit', value), value)
        for value in (19, 501, True, 20.0):
            with self.assertRaises(ValueError): backend.validate_preference('clipboardLimit', value)
        self.assertEqual(clipboard.MAX_TEXT, content_types.MAX_TEXT)
        self.assertIs(clipboard.image_type, content_types.image_type)

    def test_backend_capture_do_not_import_clipboard_and_ui_uses_shared_layers(self):
        for relative in ('scripts/desktop_backend.py', 'scripts/screen_capture.py'):
            tree = ast.parse((ROOT/relative).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom): self.assertNotEqual(node.module, 'clipboard')
                elif isinstance(node, ast.Import): self.assertNotIn('clipboard', [alias.name for alias in node.names])
        for relative in ('qml/panels/ClipboardPanel.qml', 'qml/settings/ClipboardPage.qml'):
            imports = [line.strip() for line in (ROOT/relative).read_text().splitlines() if line.startswith('import ')]
            for line in imports:
                self.assertTrue(line.startswith(('import Qt', 'import Quickshell')) or
                    line in ('import "../components"', 'import "../services"', 'import "../theme"'), line)
