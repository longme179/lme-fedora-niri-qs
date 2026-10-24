# Mirroring fixture review

AGENTS.md says "Never edit an existing assertion without asking". This input
controls an existing expected route; owner approval is requested as for earlier
legacy-routing fixture updates.
One legacy-routing test names mirrorRefresh, which this family converts. Replace
only the input with controlsRefresh, an unchanged legacy route in the two
live/demo modes used by this test:

```diff
--- tests/action_registry_workers.py
+++ tests/action_registry_workers.py
@@
-            for action in ('mirrorRefresh', 'wallpaperUnknown'):
+            for action in ('controlsRefresh', 'wallpaperUnknown'):
```

All assertions, timeouts, other input and frozen fixtures stay unchanged. New
characterization covers mirrorRefresh through the registry after extraction.

Owner approved the proposed legacy-data update on 2026-10-24. Commit 844707c
applies exactly this input replacement, with all assertion ASTs unchanged. The
updated fixture passes all four WorkerRegistryCase tests against unchanged main.
