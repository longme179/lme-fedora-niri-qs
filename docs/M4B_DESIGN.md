# M4b: Clipboard only

Baseline: merged main `c46f934`; accepted M4a review `933750f` has the same tree.
No M5 schema consumer, worker policy, file move or other feature conversion.

- Preserve observed order: bar picker Clipboard is last, after `privacy`;
  Settings follows `notifications`; gesture choice follows `launchpad`.
  Default/saved layout arrays are data: retain the `clipboard` ID after Privacy
  in the right zone, including when disabled. Rendering follows catalog visibility.
- Startup presentation entries gain optional `after: "id"` in their namespace.
  Absent means append. Reject unsafe/self/cyclic anchors; validate existence
  against catalog + actual legacy IDs before projection. Same-anchor siblings
  retain index order. Order all IDs before filtering disabled entries.
  Missing anchors fail with the existing legacy-only diagnostic, never append.
- Duplicate ownership remains an error, including disabled entries. Remove all
  Clipboard UI/dispatch/bootstrap/CLI/worker-ID legacy registrations together
  with the descriptor/index entry, in one conversion commit.
- Extend the existing reader/singleton for data-only panel, bootstrap and gesture
  metadata; use generic host adapters, without callbacks in JSON. Generic host
  files gain no Clipboard registrations. A second entry needs only its own
  implementation/descriptor and one index record, not another host switch.
- `ClipboardFeature.qml` calls unchanged `ClipboardState.start()` once in the
  live main-shell context. Settings/demo/preview cannot bootstrap its worker.
  Keep ClipboardState, panel, page, worker and public compatibility exports.
- Descriptor `preferenceMetadata` documents the three existing keys, defaults
  and the 20–500 limit without entering active schema ownership. Existing
  `preferences` duplicate checks remain strict. M5 alone may migrate consumers.
- Disabled entry: hide bar/panel/page/gesture; no bootstrap/worker. Retain valid
  saved IDs, settings/history bytes and inert metadata. Re-enable on next launch;
  the immutable per-process catalog is not made into a live reload system.
- Preserve public IPC/Super+V, page CLI, gesture routes and capture-owned annotation.
  Generic infrastructure and its tests precede the atomic Clipboard conversion.
- M4a legacy-only expectations must exclude converted ownership after this step;
  proposed existing-test changes are in M4B_TEST_REVIEW.md and need owner approval.
  New characterization pins enabled order/behavior on unmodified main; withdrawal
  contracts additionally pin the disabled case after conversion.
- Startup pre-registration: M4B_STARTUP_PREREG.md. Gates G0–G4, polling-only G6,
  new native tests, and touched QML/callers run privately before/after.
