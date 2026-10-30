"""Deployment contracts; all writes use disposable directories, never a session."""
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


class ExistingInstallCase(unittest.TestCase):
    def test_dry_run_leaves_config_untouched(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            config = home/'config/niri/config.kdl'
            config.parent.mkdir(parents=True)
            config.write_text('binds { Mod+T { spawn "kitty"; }; }\n')
            env = dict(os.environ, HOME=raw, XDG_CONFIG_HOME=str(home/'config'),
                       XDG_DATA_HOME=str(home/'data'), XDG_STATE_HOME=str(home/'state'))
            before = config.read_bytes()
            result = subprocess.run([str(ROOT/'scripts/setup.sh')], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse((home/'config/quickshell').exists())


class DeployStateCase(unittest.TestCase):
    def test_rollback_preserves_modes_links_and_refuses_later_edits(self):
        from deploy_state import Transaction
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); original = root/'config'; original.write_text('original\n'); original.chmod(0o640)
            link = root/'link'; link.symlink_to('old')
            journal = Transaction(root/'report')
            journal.write(original, b'new\n')
            journal.link(link, root/'new')
            journal.finish()
            self.assertEqual(original.stat().st_mode & 0o777, 0o640)
            original.write_text('user edit\n')
            with self.assertRaisesRegex(ValueError, 'changed'):
                Transaction.rollback(root/'report')
            self.assertEqual(os.readlink(link), str(root/'new'))
            original.write_text('new\n')
            Transaction.rollback(root/'report')
            self.assertEqual(original.read_text(), 'original\n')
            self.assertEqual(os.readlink(link), 'old')
            self.assertEqual(original.stat().st_mode & 0o777, 0o640)
            self.assertEqual((root/'report/manifest.json').stat().st_mode & 0o777, 0o600)

    def test_noop_and_failed_publication(self):
        from deploy_state import Transaction
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); target = root/'file'; target.write_bytes(b'old')
            tx = Transaction(root/'report')
            self.assertFalse(tx.write(target, b'old'))
            with patch('deploy_state.os.replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError): tx.write(target, b'new')
            self.assertEqual(target.read_bytes(), b'old')
            self.assertEqual(list(root.glob('.lme-*')), [])


class DeployNiriCase(unittest.TestCase):
    def test_includes_conflicts_and_idempotence(self):
        from deploy_niri import plan
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw); root = folder/'config.kdl'; part = folder/'keys.kdl'
            root.write_text('include "keys.kdl"\nspawn-at-startup "waybar"\nspawn-at-startup "nm-applet"\nblur { passes 4; }\n')
            part.write_text('// user keys\nbinds { Mod+T { spawn "kitty"; }; Mod+Space { spawn "fuzzel"; }; }\n')
            changes, notes = plan(root, ROOT, folder/'lme-shell', folder/'bin/lme-shell', (26, 4))
            self.assertIn('/- Mod+Space', changes[part].decode())
            self.assertIn('Mod+T { spawn "kitty";', changes[part].decode())
            self.assertIn('/- spawn-at-startup "waybar"', changes[root].decode())
            self.assertIn('spawn-at-startup "nm-applet"', changes[root].decode())
            managed = folder/'lme-shell-deploy.kdl'
            self.assertNotIn('\nblur {', changes[managed].decode())
            self.assertTrue(notes)
            for path, value in changes.items(): path.write_bytes(value)
            again, _ = plan(root, ROOT, folder/'lme-shell', folder/'bin/lme-shell', (26, 4))
            self.assertEqual(again, {})

    def test_mixed_startup_fails_closed_and_disabled_nodes_survive(self):
        from deploy_niri import plan
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)/'config.kdl'
            root.write_text('spawn-sh-at-startup "waybar & fcitx5 -d"\n')
            with self.assertRaisesRegex(ValueError, 'mixed|ambiguous'):
                plan(root, ROOT, root.parent/'lme', root.parent/'bin/lme-shell', (26, 4))
            root.write_text('/- spawn-at-startup "waybar"\nbinds { /- Mod+A { spawn "old"; }; }\n')
            changes, _ = plan(root, ROOT, root.parent/'lme', root.parent/'bin/lme-shell', (26, 4))
            self.assertNotIn('/- /-', changes[root].decode())

    def test_symlink_config_keeps_relative_include_base(self):
        from deploy_niri import plan
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw); real = folder/'real'; real.mkdir(); logical = folder/'niri'; logical.mkdir()
            target = real/'main.kdl'; target.write_text('include "keys.kdl"\n')
            (logical/'config.kdl').symlink_to(target)
            (logical/'keys.kdl').write_text('binds { Mod+N { spawn "old"; }; }\n')
            changes, _ = plan(logical/'config.kdl', ROOT, folder/'lme', folder/'bin/lme-shell', (26, 4))
            self.assertIn(target, changes)
            self.assertIn(logical/'keys.kdl', changes)
            self.assertTrue((logical/'config.kdl').is_symlink())


class RuntimeCase(unittest.TestCase):
    def test_version_and_actual_capabilities_are_both_required(self):
        from deploy_runtime import probe
        with tempfile.TemporaryDirectory() as raw:
            binary = Path(raw)/'quickshell'
            binary.write_text('#!/bin/sh\nif [ "$1" = --version ]; then echo "quickshell 0.2.1"; else echo LME_RUNTIME_OK; fi\n')
            binary.chmod(0o755)
            with self.assertRaisesRegex(ValueError, '0.3.2'): probe(binary)
            binary.write_text('#!/bin/sh\nif [ "$1" = --version ]; then echo "quickshell 0.3.2"; else echo "bottomRightRadius is missing" >&2; exit 1; fi\n')
            with self.assertRaisesRegex(ValueError, 'capabilit'): probe(binary)

    def test_probe_is_offscreen_and_isolated(self):
        from deploy_runtime import probe
        with tempfile.TemporaryDirectory() as raw:
            binary = Path(raw)/'quickshell'
            binary.write_text('#!/bin/sh\nif [ "$1" = --version ]; then echo "quickshell 0.3.2"; exit; fi\n'
                              'test "$QT_QPA_PLATFORM" = offscreen && test -z "$WAYLAND_DISPLAY" && '
                              'test "$HOME" != "'+str(Path.home())+'" && echo LME_RUNTIME_OK\n')
            binary.chmod(0o755)
            self.assertEqual(probe(binary), (0, 3, 2))

    def test_new_deploy_plan_is_readonly(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            env = dict(os.environ, HOME=raw, XDG_CONFIG_HOME=str(home/'config'),
                       XDG_DATA_HOME=str(home/'data'), XDG_STATE_HOME=str(home/'state'))
            result = subprocess.run([str(ROOT/'scripts/deploy.sh')], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('dry-run', result.stdout.lower())
            self.assertEqual(list(home.iterdir()), [])


if __name__ == '__main__': unittest.main()
