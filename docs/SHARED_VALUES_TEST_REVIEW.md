# Legacy test data update proposal

The extraction removes two legacy edges that test_architecture currently freezes.
Proposed changes in tests/test_architecture.py; assertions/timeouts stay identical.

```diff
@@ test_current_python_legacy_edges_remain_explicit
-        for source, target in [('scripts/battery_saver.py', 'display_control'),
-                               ('scripts/bluetooth_agent.py', 'peripheral_battery'),
-                               ('scripts/image_utilities.py', 'wallpaper')]:
+        for source, target in [('scripts/battery_saver.py', 'display_control')]:
@@ test_vanished_legacy_exception_must_be_removed
-        path = self.root/'scripts/image_utilities.py'
-        path.write_text(path.read_text().replace('from wallpaper import image_path', ''))
+        path = self.root/'scripts/battery_saver.py'
+        path.write_text(path.read_text().replace('from display_control import apply_layout, current_layout, validate_layout', ''))
```

The stale-exception fixture keeps testing the guard through the remaining display
edge. Production BatterySaver is untouched. Frozen fixture files are unchanged.
Approval required before applying; new characterization proceeds on main meanwhile.
