# Lyrics, search and Bluetooth preference fragments

2026-10-25. Main 8aea87f (device schema PR34 merged), branch
`refactor/content-preference-schema`. Plan precedes tests and implementation.

## Scope

Use the existing preference-only descriptor pattern for three groups:

- lyrics: lyricsEnabled, lyricsOnline, lyricsMode, lyricsFollow, activityLyrics.
- fileSearch: fileSearchEnabled, fileSearchRoots.
- bluetooth: bluetoothPairing, bluetoothAdapter.

Keep the exact existing metadata/defaults, 147-key order, appearance membership
and flat settings file. Online lyrics remains off by default. Search roots keep
the existing home-dependent resolver and roots validator (normalization, bounds,
deduplication and error text). Search roots and adapter selection stay private,
excluded from portable presets. Mode and adapter validation bind existing Python
callbacks, following the Weather/OSD named-validator pattern; no enum schema field.

Each index record has empty startup metadata and no source/UI/provider/bootstrap
entry. Its disabled flag retains schema/data, not withdrawal of legacy UI or
services. No positions are needed because no ordered navigation entry is added.
Core pages, gestures, workers, lookup/privacy/scan/pairing/retry policy, subprocess
ownership, polling/cache/power policy and public facades stay unchanged.

## Plan

1. Commit this note before code. Characterize current defaults/types/errors,
   home contexts, path normalization, adapter constraints, preset privacy,
   persistence and malformed-file reload on unchanged main. Reuse the existing
   full golden schema tests without assertion or frozen-fixture edits. New
   fragment ownership/authority tests are N/A before their fragment exists.
2. Baseline G0 plus relevant settings/schema/personalization/ports, lyrics,
   search and Bluetooth units in disposable XDG/private Sway/D-Bus. Relevant
   native cases run before/after; unavailable cases are reported as skips.
3. One extraction commit per group in the order above: move metadata and remove
   legacy definitions in the same commit. Use existing boolean validation,
   existing lyricsMode/bluetoothAdapter callbacks, and bind search_roots directly.
   Remove migrated boolean names and the redundant fileSearchRoots dispatch;
   retain the two named legacy callbacks until their domain rules move safely.
   Run focused parity/catalog/architecture after each; ratchet any shrinking cap.
4. Once on final runtime/test head: G0-G4/G6 polling, also the affected G0 after
   extraction. One normal ten-launch preview/Settings and T+10s RSS sanity,
   main/head medians only; stop for existing +100ms/+10% thresholds.
5. Final <=30-line migration entry, adapters/retirement, <=6 laptop checks;
   push review branch/draft PR and stop. No raw evidence committed.

No generated Settings UI, extra schema mechanism, provider discovery, async
conversion or M8 moves. Schema coverage becomes 79 descriptor / 68 legacy keys;
action/UI coverage stays. Existing schema facades and bundled-fragment fallback
retain STATE.md conditions. Physical radios/media/compositor behavior and reviewed
whole-shell PSS remain laptop checks. D1 and A6 stay closed/out of scope.
