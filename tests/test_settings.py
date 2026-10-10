"""Shared preference and standalone settings contracts."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_backend import backend, FakeRunner


class SettingsCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "config/settings.json"

    def test_bar_layout_rejects_unknown_duplicate_and_malformed_modules(self):
        invalid = [None, {}, {"left": [], "center": []},
                   {"left": ["launcher"], "center": ["launcher"], "right": []},
                   {"left": ["../../scripts/run"], "center": [], "right": []},
                   {"left": "clock", "center": [], "right": []},
                   {"left": [42], "center": [], "right": []}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                backend.validate_preference("barLayout", value)
        layout = {"left": ["clock"], "center": [], "right": ["settings", "media"]}
        self.assertEqual(backend.validate_preference("barLayout", layout), layout)
        self.assertEqual(backend.validate_preference("barLayout", {z: [] for z in layout}), {z: [] for z in layout})
        for value in [True, 11, 17, 13.0, "13"]:
            with self.assertRaises(ValueError): backend.validate_preference("barFontSize", value)

    def test_nested_defaults_and_validated_layouts_are_independent(self):
        a, b = backend.Preferences(self.path), backend.Preferences(self.path)
        a.values["barLayout"]["left"].append("clock")
        self.assertNotIn("clock", b.values["barLayout"]["left"])
        self.assertNotIn("clock", backend.DEFAULT_PREFERENCES["barLayout"]["left"])
        source = copy.deepcopy(backend.DEFAULT_PREFERENCES["barLayout"])
        validated = backend.validate_preference("barLayout", source)
        validated["left"].clear()
        self.assertTrue(source["left"])

    def test_stale_writers_merge_other_clients_changes(self):
        shell, app = backend.Preferences(self.path), backend.Preferences(self.path)
        shell.set("tasks", [{"id": "test-task", "text": "Keep me", "done": False}])
        app.set("accent", "#ff80bf")
        shell.set("barStyle", "islands")
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["tasks"][0]["text"], "Keep me")
        self.assertEqual(saved["accent"], "#ff80bf")
        self.assertEqual(saved["barStyle"], "islands")
        app.reload()
        self.assertEqual(app.values, saved)

    def test_external_reload_preserves_valid_state_during_bad_edit(self):
        a, b = backend.Preferences(self.path), backend.Preferences(self.path)
        a.set("accent", "#ff80bf")
        b.reload()
        self.assertEqual(b.values["accent"], "#ff80bf")
        self.path.write_text("{invalid")
        b.reload()
        self.assertEqual(b.values["accent"], "#ff80bf")
        self.path.unlink()
        b.reload()
        self.assertEqual(b.values, backend.DEFAULT_PREFERENCES)

    def test_settings_mode_only_reads_preferences_and_restricts_actions(self):
        runner = FakeRunner(available=("niri", "busctl", "nmcli", "wpctl"))
        preferences = backend.Preferences(self.path)
        with patch.object(backend.Applications, "scan", side_effect=AssertionError("Desktop scan")):
            app = backend.DesktopBackend(runner=runner, preferences=preferences, settings_only=True)
            state = app.snapshot()
            self.assertEqual(state["apps"], [])
            self.assertEqual(state["system"], {})
            self.assertFalse(state["niri"]["available"])
            self.assertFalse(app.handle({"action": "power", "value": "shutdown"})["ok"])
            self.assertTrue(app.handle({"action": "setting", "key": "barFontSize", "value": 15})["ok"])
            self.assertTrue(app.handle({"action": "refresh"})["ok"])
        self.assertEqual(runner.calls, [])
        other = backend.Preferences(self.path)
        other.set("barFontSize", 16)
        self.assertEqual(app.snapshot()["preferences"]["barFontSize"], 16)

    def test_settings_demo_does_not_save_or_run_commands(self):
        runner = FakeRunner()
        preferences = backend.Preferences(self.path)
        app = backend.DesktopBackend(runner=runner, preferences=preferences, demo=True, settings_only=True)
        self.assertTrue(app.handle({"action": "setting", "key": "barStyle", "value": "islands"})["ok"])
        self.assertEqual(app.snapshot()["preferences"]["barStyle"], "islands")
        self.assertFalse(self.path.exists())
        self.assertEqual(runner.calls, [])

    def test_desktop_entry_install_is_idempotent_and_preserves_existing_entry(self):
        script = Path(__file__).resolve().parents[1] / "scripts/install-settings.sh"
        target = Path(self.temp.name) / "applications/settings.desktop"
        def install(*args):
            return subprocess.run([str(script), "--target", str(target), *args], capture_output=True, text=True)
        self.assertEqual(install("--dry-run").returncode, 0)
        self.assertFalse(target.exists())
        self.assertEqual(install().returncode, 0)
        self.assertIn('Name=LME Shell Settings', target.read_text())
        self.assertEqual(install().returncode, 0)
        target.write_text("Existing desktop entry")
        self.assertNotEqual(install().returncode, 0)
        self.assertEqual(install("--replace").returncode, 0)
        backups = list(target.parent.glob("settings.desktop.backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "Existing desktop entry")

    def test_desktop_installer_rejects_targets_reached_through_checkout_symlink(self):
        repo = Path(__file__).resolve().parents[1]
        alias = Path(self.temp.name) / "checkout-alias"
        alias.symlink_to(repo, target_is_directory=True)
        result = subprocess.run([str(repo / "scripts/install-settings.sh"), "--target",
                                 str(alias / "unexpected.desktop")], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((repo / "unexpected.desktop").exists())
