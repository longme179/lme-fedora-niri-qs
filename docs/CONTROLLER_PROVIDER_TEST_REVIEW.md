# Controller provider schema-contract review

The old device-schema milestone froze descriptors to id/preferences only. The
authorized provider batch adds sources/backend for Battery Saver and Mirroring.
Focused controller tests passed, but the existing schema assertion rejected those
two fields. Commit e393dbd was reverted by f2c467d; the unchanged test passes again.

Owner approved the following minimal update on 2026-10-31; applied in 1dcf2bb:

```diff
-    def test_unique_ownership_empty_startup_and_no_new_ui_or_provider_entries(self):
+    def test_unique_ownership_empty_startup_and_no_new_ui_entries(self):
@@
-            self.assertEqual(set(descriptor), {'id', 'preferences'})
+            metadata = {'sources', 'backend'} if group in ('batterySaver', 'mirroring') else set()
+            self.assertEqual(set(descriptor) - metadata, {'id', 'preferences'})
```

Only these two groups may add provider/source metadata; UI registrations are
still forbidden here. Peripheral descriptors remain exactly id/preferences.
The new ControllerDescriptorCase separately requires both metadata fields and
the exact factory reference/source ownership, and tests the whole binding set.
Existing startup, preference-key, unique ownership, portable/privacy, file/backup
permissions, fallback, timeout and frozen-fixture assertions stay unchanged.
The updated test passes before conversion; full catalog checks enforce references
when present. No product behavior or user settings.json format changes.
