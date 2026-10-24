# Mirroring fixture review

AGENTS.md requires approval before changing existing assertions/expected cases.
One legacy-routing test names mirrorRefresh, which this family converts. Replace
only the input with controlsRefresh, an unchanged legacy route in both contexts:

```diff
--- tests/action_registry_workers.py
+++ tests/action_registry_workers.py
@@
-            for action in ('mirrorRefresh', 'wallpaperUnknown'):
+            for action in ('controlsRefresh', 'wallpaperUnknown'):
```

All assertions, timeouts, other input and frozen fixtures stay unchanged. New
characterization covers mirrorRefresh through the registry after extraction.
