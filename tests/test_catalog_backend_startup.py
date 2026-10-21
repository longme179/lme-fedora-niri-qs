"""Catalog validation belongs to the owning backend, not an import or Settings CLI."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CatalogBackendStartupCase(unittest.TestCase):
    def test_import_does_not_validate_and_backend_initialization_validates_once(self):
        code = r"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path.cwd()/'scripts'))
import feature_catalog as catalog
calls = []
def load():
    calls.append(True)
    raise catalog.CatalogError('fixture diagnostic')
catalog.catalog = load
import desktop_backend as backend
assert calls == [], calls
backend.initialize_catalog()
backend.initialize_catalog()
assert calls == [True], calls
assert backend.FEATURE_CATALOG_ERROR == 'fixture diagnostic'
assert backend.FEATURE_CATALOG['ids']['bar'] == []
"""
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, XDG_CONFIG_HOME=directory, XDG_STATE_HOME=directory,
                       XDG_DATA_HOME=directory, XDG_CACHE_HOME=directory)
            result = subprocess.run(['python3', '-c', code], cwd=ROOT, env=env,
                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, 'Feature catalog: fixture diagnostic\n')
