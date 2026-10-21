# Existing-test adaptations — approved by the owner on 2026-10-21

M4a tests assumed every shipped entry was legacy. M4b intentionally removes
Clipboard from that set; broken/disabled catalogs cannot expose its page or bar.
The owner approved the exact expectation updates below before they were applied. No timeout change,
assertion deletion, replacement of frozen baseline data or default skip is proposed.

1. `test_feature_catalog.CatalogContractCase` metadata parity: continue comparing
   all original metadata/defaults exactly, excluding new routing-only fields from
   the projected entry. New Clipboard characterization separately verifies those
   entry/position fields and all five required order surfaces.

```diff
 state = probe.wait(lambda state: len(state['pages']) == len(expected['pages']))
+for kind in ('bars', 'pages'):
+    state[kind] = [{key: value for key, value in entry.items()
+                    if key not in ('entry', 'after')} for entry in state[kind]]
 self.assertEqual({key: state[key] for key in expected}, expected)
```

2. `test_catalog_failures.NativeCatalogFailureCase`: compare fallback against
   actual legacy ownership, retaining the frozen baseline metadata as input.
   `catalog_fixture.legacy_expected()` filters only IDs owned by the shipped
   index (including disabled records); it returns the original fixture unchanged
   on unmodified M4a main. New withdrawal tests guard Clipboard's absence,
   retained saved IDs/history/schema and successful re-enable explicitly.

```diff
-legacy = json.loads((REPO/'tests/fixtures/catalog-legacy.json').read_text())
+legacy = legacy_expected()
 ... existing exact bars/pages/tabs assertions remain ...
 self.assertEqual(probe.ipc('settings', 'openPage', 'clipboard'), 'true')
-probe.wait(lambda state: state['page'] == 'clipboard')
+target = 'clipboard' if any(p['key'] == 'clipboard' for p in legacy['pages']) else legacy['pages'][0]['key']
+probe.wait(lambda state: state['page'] == target)
```

3. `test_catalog_cli.CatalogCliCase`: its fixture has an empty catalog, so test a
   still-legacy page (`weather`) in the legacy-admission loop. The real Clipboard
   CLI is tested enabled/disabled through the new copied-checkout native case.

```diff
-for page in ('appearance', 'clipboard', 'controlLayout', 'about'):
+for page in ('appearance', 'weather', 'controlLayout', 'about'):
```

Fixture-only companions: remove Clipboard from the admission fixture's LEGACY
list; preserve shipped entries when injecting a test descriptor in a copied
checkout, keeping the test descriptor first for existing compact-fixture setup.
No original fixture JSON is rewritten. All existing tests still execute under
their existing opt-in flags, with no new skips. These changes will be tested on
unmodified production before conversion as well as after it.

Follow-up fixture/caller corrections changed no assertions or timeouts:
`catalog_fixture.session()` waits for the existing catalog barrier before returning;
the delayed Settings fake backend includes the existing `catalogValidation` verdict;
the popup-motion probe samples root completion after bootstrap moved; and the
opt-in native-feature demo uses shared panel admission/visibility. The failed
conversion was reverted before applying the latter fixture/caller corrections.
