"""Characterize existing boundaries, then exercise the guard in copied checkouts."""
import ast
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT/'scripts/check_architecture.py'


class ArchitectureCharacterizationCase(unittest.TestCase):
    def imports(self, path):
        return {n.module for n in ast.walk(ast.parse((ROOT/path).read_text())) if isinstance(n, ast.ImportFrom)}

    def test_clipboard_and_capture_use_shared_content_types(self):
        for path in ('scripts/clipboard.py', 'scripts/screen_capture.py'):
            with self.subTest(path=path):
                self.assertIn('content_types', self.imports(path))
                self.assertNotIn('desktop_backend', self.imports(path))
                self.assertNotIn('clipboard', self.imports(path))

    def test_clipboard_descriptor_owns_its_existing_implementation(self):
        descriptor = json.loads((ROOT/'config/clipboard.json').read_text())
        self.assertEqual(descriptor['id'], 'clipboard')
        self.assertEqual(descriptor['sources'], ['qml/services/ClipboardState.qml', 'scripts/clipboard.py'])
        for kind in ('bar', 'settingsPage', 'panel', 'bootstrap'):
            self.assertTrue((ROOT/descriptor[kind]['entry']).is_file())
        self.assertEqual(descriptor['bar']['after'], 'privacy')
        self.assertEqual(descriptor['settingsPage']['after'], 'notifications')

    def test_current_python_legacy_edges_remain_explicit(self):
        for source, target in [('scripts/battery_saver.py', 'display_control')]:
            with self.subTest(source=source): self.assertIn(target, self.imports(source))


@unittest.skipUnless(CHECKER.is_file(), 'architecture guard not implemented yet (test-first contract)')
class ArchitectureGuardCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='lme-architecture-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)/'checkout'
        self.root.mkdir()
        for name in ('qml', 'scripts', 'config'):
            shutil.copytree(ROOT/name, self.root/name, ignore=shutil.ignore_patterns('__pycache__'))
        for path in ROOT.glob('*.qml'): shutil.copy2(path, self.root/path.name)
        spec = importlib.util.spec_from_file_location('copied_guard', self.root/'scripts/check_architecture.py')
        self.guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.guard)

    def put(self, path, text):
        target = self.root/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def append(self, path, text):
        target = self.root/path
        target.write_text(target.read_text()+text)

    def errors(self):
        return '\n'.join(self.guard.check(self.root))

    def test_current_checkout_and_cli_pass_without_weakening_baseline(self):
        self.assertEqual(self.guard.check(self.root), [])
        result = subprocess.run(['bash', str(self.root/'scripts/check-architecture.sh')],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_deliberate_python_violation_in_copied_checkout_is_rejected(self):
        self.append('scripts/clipboard.py', '\nfrom wallpaper import image_path\n')
        expected = 'Forbidden dependency: scripts/clipboard.py -> scripts/wallpaper.py'
        self.assertIn(expected, self.errors())
        result = subprocess.run(['bash', str(self.root/'scripts/check-architecture.sh')],
                                capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(expected, result.stderr)

    def test_qml_implicit_type_resolves_across_a_mixed_legacy_directory(self):
        self.append('qml/panels/ClipboardPanel.qml', '\n// A deliberate forbidden type\nproperty Component forbidden: LaunchpadEditor {}\n')
        self.assertIn('ClipboardPanel.qml -> qml/panels/LaunchpadEditor.qml', self.errors())

    def test_qml_aliased_directory_import_resolves_type(self):
        self.put('qml/features/b/Entry.qml', 'import QtQuick\nQtObject {}\n')
        self.put('qml/features/a/Main.qml', 'import QtQuick\nimport "../b" as Foreign\nQtObject { property Component page: Foreign.Entry {} }\n')
        self.assertIn('a/Main.qml -> qml/features/b/Entry.qml', self.errors())

    def test_js_literal_import_resolves_cross_feature_edge(self):
        self.put('qml/features/a/logic.js', '.pragma library\n.import "../b/logic.js" as B\n')
        self.put('qml/features/b/logic.js', '.pragma library\n')
        self.assertIn('a/logic.js -> qml/features/b/logic.js', self.errors())

    def test_root_entry_url_resolves_cross_feature_edge(self):
        self.put('qml/features/a/Panel.qml', 'import QtQuick\nLoader { source: "root:/qml/features/b/Panel.qml" }\n')
        self.put('qml/features/b/Panel.qml', 'import QtQuick\nItem {}\n')
        self.assertIn('a/Panel.qml -> qml/features/b/Panel.qml', self.errors())

    def test_python_relative_package_import_resolves_cross_feature_edge(self):
        self.put('scripts/features/a/worker.py', 'from ..b import worker\n')
        self.put('scripts/features/b/worker.py', 'VALUE = 1\n')
        self.assertIn('a/worker.py -> scripts/features/b/worker.py', self.errors())

    def test_own_files_and_shared_service_api_are_allowed(self):
        self.put('qml/features/a/Main.qml', 'import QtQuick\nimport "../../services"\nItem { property var state: ShellState.state; Child {} }\n')
        self.put('qml/features/a/Child.qml', 'import QtQuick\nItem {}\n')
        self.put('scripts/features/a/worker.py', 'from storage import read_json\n')
        self.assertEqual(self.guard.check(self.root), [])

    def test_new_cycle_rejected_even_within_one_feature(self):
        self.put('scripts/features/a/one.py', 'from . import two\n')
        self.put('scripts/features/a/two.py', 'from . import one\n')
        self.assertIn('New cycle edge:', self.errors())

    def test_self_import_cycle_is_rejected(self):
        self.put('scripts/features/a/worker.py', 'from . import worker\n')
        self.assertIn('New cycle edge:', self.errors())

    def test_new_file_limit_counts_nonblank_lines_only(self):
        path = 'scripts/features/a/worker.py'
        self.put(path, '# line\n\n'*250)
        self.assertEqual(self.guard.check(self.root), [])
        self.append(path, '# line\n')
        self.assertIn('Size cap: '+path+': 251 > 250', self.errors())

    def test_existing_large_file_cannot_grow_and_must_ratchet_after_shrink(self):
        path = 'scripts/desktop_backend.py'
        self.append(path, '\n# extra nonblank line\n')
        self.assertIn('Size cap: '+path, self.errors())
        text = (ROOT/path).read_text().splitlines()
        index = next(i for i in range(len(text)-1, -1, -1) if text[i].lstrip().startswith('#'))
        del text[index]
        self.put(path, '\n'.join(text)+'\n')
        self.assertIn('Ratchet size ceiling', self.errors())

    def test_vanished_legacy_exception_must_be_removed(self):
        path = self.root/'scripts/battery_saver.py'
        path.write_text(path.read_text().replace('from display_control import apply_layout, current_layout, validate_layout', ''))
        self.assertIn('Stale legacy exception', self.errors())

    def test_unknown_flat_implementation_requires_ownership(self):
        self.put('scripts/unregistered.py', 'VALUE = 1\n')
        self.assertIn('Unclassified source', self.errors())

    def test_descriptor_adds_ownership_without_a_host_or_policy_edit(self):
        self.put('scripts/new_worker.py', 'from storage import read_json\n')
        self.put('config/new.json', json.dumps({'id': 'new', 'sources': ['scripts/new_worker.py']}))
        path = self.root/'config/features.json'
        index = json.loads(path.read_text())
        index['features'].append({'id': 'new', 'descriptor': 'config/new.json', 'enabled': False})
        path.write_text(json.dumps(index))
        self.assertEqual(self.guard.check(self.root), [])
        self.append('scripts/new_worker.py', 'from clipboard import image_type\n')
        self.assertIn('new_worker.py -> scripts/clipboard.py', self.errors())

    def test_archive_is_not_scanned(self):
        self.put('docs/archive/migration/irrelevant.py', 'this is invalid Python\n'*300)
        self.assertEqual(self.guard.check(self.root), [])

    def test_js_es_module_import_resolves_cross_feature_edge(self):
        self.put('qml/features/a/logic.js', 'import { value } from "../b/logic.js";\n')
        self.put('qml/features/b/logic.js', 'export const value = 1;\n')
        self.assertIn('a/logic.js -> qml/features/b/logic.js', self.errors())
