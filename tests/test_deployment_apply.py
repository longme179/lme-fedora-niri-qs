"""One-shot apply/failure tests; fake privilege and compositor commands only."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from deploy import deploy
from deploy_niri import plan
from deploy_niri_tree import validate
from deploy_state import Transaction
from niri_keybinds import nodes, tokens


class DeployApplyCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name); self.bin = self.home/'bin'; self.bin.mkdir()
        self.config = self.home/'config'; self.data = self.home/'data'; self.state = self.home/'state'
        self.root = self.config/'niri/config.kdl'; self.root.parent.mkdir(parents=True)
        self.original = 'binds { Mod+T { spawn "kitty"; }; Mod+Space { spawn "fuzzel"; }; }\n'
        self.root.write_text(self.original)
        self.executable('niri', 'if [ "$1" = --version ]; then echo "niri 26.04"; fi\n')
        self.executable('quickshell', 'if [ "$1" = --version ]; then echo "quickshell 0.3.2"; else echo LME_RUNTIME_OK; fi\n')
        self.executable('sudo', 'echo UNEXPECTED-PRIVILEGE >&2; exit 99\n')
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.config),
                        XDG_DATA_HOME=str(self.data), XDG_STATE_HOME=str(self.state),
                        PATH=str(self.bin)+':'+os.environ['PATH'])
        for key in ('LME_QS_BINARY', 'NIRI_CONFIG'): self.env.pop(key, None)
        self.args = argparse.Namespace(install=True, replace=False, copr=False, build_quickshell=False,
                                      charge_helper=False, start=False, skip_packages=True, quickshell=None,
                                      niri_config=None, jobs=2)

    def executable(self, name, body):
        path = self.bin/name; path.write_text('#!/bin/sh\n'+body); path.chmod(0o755); return path

    def apply(self):
        with patch.dict(os.environ, self.env, clear=True), patch('os.geteuid', return_value=1000), contextlib.redirect_stdout(io.StringIO()):
            deploy(self.args)

    def test_apply_repeat_and_rollback(self):
        self.apply()
        self.assertEqual((self.config/'quickshell/lme-shell').resolve(), ROOT)
        self.assertIn('/- Mod+Space', self.root.read_text())
        self.assertTrue((self.home/'.local/bin/lme-shell').stat().st_mode & 0o100)
        first = next((self.state/'lme-shell/deployments').iterdir())
        self.assertIn('original text retained', (first/'report.txt').read_text())
        self.apply()
        reports = sorted((self.state/'lme-shell/deployments').iterdir())
        self.assertEqual(len(reports), 2)
        last = next(p for p in reports if p != first)
        self.assertEqual(json.loads((last/'manifest.json').read_text())['entries'], [])
        Transaction.rollback(first)
        self.assertEqual(self.root.read_text(), self.original)
        self.assertFalse((self.config/'quickshell/lme-shell').exists())

    def test_incompatible_runtime_never_publishes(self):
        self.executable('quickshell', 'echo "quickshell 0.2.1"\n')
        # Do not accidentally choose a developer qs from PATH.
        self.args.quickshell = str(self.bin/'quickshell')
        with self.assertRaisesRegex(ValueError, '0.3.2'): self.apply()
        self.assertEqual(self.root.read_text(), self.original)
        self.assertFalse((self.config/'quickshell').exists())

    def test_invalid_staged_tree_never_publishes(self):
        self.executable('niri', 'if [ "$1" = --version ]; then echo "niri 26.04"; else echo bad-config >&2; exit 1; fi\n')
        with self.assertRaisesRegex(ValueError, 'validation failed'): self.apply()
        self.assertEqual(self.root.read_text(), self.original)
        self.assertEqual(list(self.root.parent.glob('.lme-validate-*')), [])
        self.assertFalse((self.config/'quickshell').exists())

    def test_post_publish_failure_restores_every_user_file(self):
        real = subprocess.run
        def fail_final(argv, **kwargs):
            if str(argv[0]).endswith('/niri') and argv[1:3] == ['validate', '--config'] and str(argv[3]) == str(self.root):
                return subprocess.CompletedProcess(argv, 1, '', 'final failure')
            return real(argv, **kwargs)
        with patch('deploy.subprocess.run', side_effect=fail_final):
            with self.assertRaisesRegex(ValueError, 'Published niri'): self.apply()
        self.assertEqual(self.root.read_text(), self.original)
        self.assertFalse((self.config/'quickshell/lme-shell').is_symlink())
        report = next((self.state/'lme-shell/deployments').iterdir())
        self.assertEqual(json.loads((report/'manifest.json').read_text())['status'], 'rolled-back')

    def test_replace_preserves_existing_directory_and_settings_bytes(self):
        shell = self.config/'quickshell/lme-shell'; shell.mkdir(parents=True); (shell/'old').write_text('old shell')
        preferences = self.config/'lme-shell/settings.json'; preferences.parent.mkdir(); preferences.write_text('{"accent":"#123456"}\n')
        self.args.replace = True
        self.apply()
        report = next((self.state/'lme-shell/deployments').iterdir())
        self.assertEqual(preferences.read_text(), '{"accent":"#123456"}\n')
        Transaction.rollback(report)
        self.assertFalse(shell.is_symlink())
        self.assertEqual((shell/'old').read_text(), 'old shell')

    def test_symlinked_config_is_not_replaced(self):
        actual = self.home/'original.kdl'; actual.write_text(self.original)
        self.root.unlink(); self.root.symlink_to(actual)
        self.apply()
        self.assertTrue(self.root.is_symlink())
        self.assertIn('/- Mod+Space', actual.read_text())
        report = next((self.state/'lme-shell/deployments').iterdir())
        Transaction.rollback(report)
        self.assertTrue(self.root.is_symlink())
        self.assertEqual(actual.read_text(), self.original)


class NiriEditEdgeCase(unittest.TestCase):
    def test_unicode_include_paths_are_literal_kdl_strings(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)/'đường dẫn'; folder.mkdir(); root = folder/'config.kdl'
            changes, _ = plan(root, ROOT, folder/'lme', folder/'lme-shell', (26, 4))
            self.assertIn(str(folder).encode(), changes[root])
            self.assertNotIn(b'\\u0111', changes[root])
            def inspect(argv, **kwargs):
                text = Path(argv[-1]).read_text()
                self.assertIn(str(folder), text)
                self.assertNotIn('\\u0111', text)
                return subprocess.CompletedProcess(argv, 0, '', '')
            with patch('deploy_niri_tree.subprocess.run', side_effect=inspect): validate(root, changes)

    def test_customized_old_fragment_keeps_its_own_settings(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw); root = folder/'config.kdl'; old = folder/'popup-blur.kdl'
            old.write_text((ROOT/'config/niri/popup-blur.kdl').read_text().replace('passes 2', 'passes 4'))
            root.write_bytes(b'include "popup-blur.kdl"\r\n// keep CRLF\r\n')
            changes, _ = plan(root, ROOT, folder/'lme', folder/'bin/lme-shell', (26, 4))
            self.assertIn(b'include "popup-blur.kdl"\r\n// keep CRLF\r\n', changes[root])
            self.assertNotIn(old, changes)
            self.assertNotIn('\nblur {', changes[folder/'lme-shell-deploy.kdl'].decode())

    def test_position_view_does_not_change_old_token_or_node_contract(self):
        text = '/* nested /* comment */ */ binds { "Mod+A" { spawn r#"a}b"#; }; }\n'
        positioned = tokens(text, positions=True)
        self.assertEqual([p[:3] for p in positioned], tokens(text))
        def strip(nodes_):
            for node in nodes_:
                node.pop('offset'); node.pop('argument_spans'); strip(node['children'])
            return nodes_
        self.assertEqual(strip(nodes(text, positions=True)), nodes(text))
        for value, kind, _, begin, end in positioned:
            if kind == 'string': self.assertTrue(text[begin:end].startswith(('"', 'r#')))

    def test_key_alias_and_legacy_includes(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw); root = folder/'config.kdl'; old = folder/'lme-shell.kdl'
            old.write_text((ROOT/'config/niri/lme-shell.kdl').read_text())
            root.write_text('include "lme-shell.kdl"\nbinds { Super+Space { spawn "fuzzel"; }; }\n')
            changes, _ = plan(root, ROOT, folder/'lme', folder/'bin/lme-shell', (26, 4))
            self.assertIn('/- include "lme-shell.kdl"', changes[root].decode())
            self.assertIn('/- Super+Space', changes[root].decode())
            self.assertNotIn(old, changes)

    def test_optional_missing_include_and_unrelated_missing_include(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw); root = folder/'config.kdl'
            root.write_text('include "missing.kdl" optional=true\n')
            self.assertTrue(plan(root, ROOT, folder/'lme', folder/'bin/lme-shell', (26, 4))[0])
            root.write_text('include "missing.kdl"\n')
            with self.assertRaises(FileNotFoundError): plan(root, ROOT, folder/'lme', folder/'bin/lme-shell', (26, 4))

    def test_stage_validation_timeout_cleans_temporary_files(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw); root = folder/'config.kdl'; root.write_text('layout { gaps 10; }\n')
            changes, _ = plan(root, ROOT, folder/'lme', folder/'bin/lme-shell', (26, 4))
            with patch('deploy_niri_tree.subprocess.run', side_effect=subprocess.TimeoutExpired('niri', 30)):
                with self.assertRaises(subprocess.TimeoutExpired): validate(root, changes)
            self.assertEqual(list(folder.glob('.lme-validate-*')), [])
            self.assertEqual(root.read_text(), 'layout { gaps 10; }\n')


if __name__ == '__main__': unittest.main()
