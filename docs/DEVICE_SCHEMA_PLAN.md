# Device preference schema fragments

2026-10-25. Main 8d1764e (PR33 merged), branch
`refactor/device-preference-schema`. Plan precedes characterization and code.

## Useful boundary

Move four remaining scalar definitions to three preference-only descriptors,
using the existing OSD pattern and M5 schema assembler:

- peripherals: peripheralBatteryAlerts (true), peripheralBatteryThreshold (20,
  strict integer 5..50).
- batterySaver: batterySaverBrightness (70, strict integer 1..100).
- mirroring: mirroringEnabled (true).

Each record has empty startup metadata, no sources, UI entry or action provider.
The existing UI/controllers stay legacy. Disabling a schema-only record retains
its definitions/data, as OSD already does; it does not withdraw legacy UI or
disable a hardware feature. No new catalog field or settings-file format.
Index additions introduce no navigation entries or positions; existing order,
search, default layout and gesture projections remain identical.

Defaults and limits become authoritative in their descriptor. Remove their
legacy definitions and redundant coordinator validation in the same commit,
one domain per commit. Reuse Schema's existing boolean/integer validators.
Keep the original 147-key inventory/default order, portable/profile membership,
unknown/type/error policy and Preferences lock/reload/merge/fsync/replace protocol.
No QML, worker/controller, power policy, polling, cache or scheduling change.

## Plan and checks

1. Commit this note before code. Add targeted characterization for defaults,
   strict type/boundary/error behavior, persistence and preset round trips on
   unchanged main; use existing full golden schema tests without assertion edits.
   New descriptor ownership/authority tests are N/A before each fragment exists.
2. Run baseline G0 and relevant settings/schema/personalization/ports plus device
   provider tests in disposable XDG/private Sway/D-Bus. Private saver/peripheral UI
   and mirror checks exercise integration without claiming physical hardware.
3. Three extraction commits in the order above; run schema parity/affected units,
   catalog and architecture checks after each. Ratchet the coordinator size limit
   as branches disappear. No new shared module, exception or dependency.
4. Once on final runtime/test head, G0-G4/G6 polling (also the affected G0 after
   extraction); one normal ten-launch preview/Settings and T+10s RSS sanity.
   Compare main/head medians only; stop for the existing +100ms/+10% flags.
5. Final <=30-line migration entry, adapters, <=6 laptop checks; push review
   branch/draft PR and stop. No raw evidence committed.

DEFAULT_PREFERENCES/validate_preference, portable/profile exports and legacy
schema inventory/default resolvers remain compatibility facades; retire only at
their STATE.md conditions. Schema-only fragment discovery/fallback is unchanged.
Expected coverage: 70 descriptor keys / 77 legacy; action/UI coverage unchanged.
Physical devices/backlight/display restore and reviewed aggregate laptop PSS
remain RELEASE_CHECKLIST.md checks. D1, A6, provider discovery, core-page conversion
and retention/deletion are outside this branch.
