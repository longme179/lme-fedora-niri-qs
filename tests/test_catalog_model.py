"""Synthetic end state keeps the current counts/order and no legacy registrations."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from catalog_end_state import replace_legacy

ROOT = Path(__file__).resolve().parents[1]


class CatalogModelCase(unittest.TestCase):
    def test_replace_removes_legacy_entries_and_preserves_namespace_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('qml', 'scripts', 'config', 'tests/fixtures'):
                shutil.copytree(ROOT/name, root/name)
            replace_legacy(root)
            spec = importlib.util.spec_from_file_location('synthetic_reader', root/'scripts/feature_catalog.py')
            reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
            data = reader.load_catalog(root)
            expected = json.loads((root/'tests/fixtures/catalog-legacy.json').read_text())
            for kind, source, key in [('bar', 'bars', 'id'), ('settingsPage', 'pages', 'key'), ('controlTab', 'tabs', 'id')]:
                self.assertEqual([item[key] for item in data[kind]], [item[key] for item in expected[source]])
            self.assertEqual(len(data['preferences']), 30)
            self.assertIn('legacyModules: []', (root/'qml/bar/BarRegistry.qml').read_text())
            self.assertIn('legacyPages: []', (root/'qml/settings/SettingsRegistry.qml').read_text())
            self.assertEqual(json.loads((root/'config/control-grid.json').read_text())['tabs'], [])
