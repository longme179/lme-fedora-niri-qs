# Shared display layout contract

2026-10-25. Main 53e321a; branch `refactor/shared-display-layout`.
Owner requested the next roadmap boundary, with planning before implementation.

## Scope and contracts

Remove the last Python cross-feature exception: BatterySaver imports layout
helpers from DisplayControl's implementation. Move exactly validate_layout,
current_layout and apply_layout to shared scripts/display_layout.py. The runner
is injected already; the shared module owns no process, state, timer or device.
DisplayControl re-exports all three names; BatterySaver imports the shared names.
Keep normalized_outputs and the preview/watchdog controller in display_control.

Preserve exact validation/error text, bool/finite/bounds rules, field filtering,
input immutability, output ordering, fractional refresh formatting, literal argv,
mode/scale/position order, fail-fast and best-effort exception behavior. Preserve
all journals, locks, watchdog CLI, detached ownership, rollback and mode policy.
No changes to QML, settings/schema, polling, power policy, executors or processes.
Retain old imports until zero consumers and explicit owner-approved retirement.

## Execution order

1. Commit this plan before code. Propose the two necessary legacy-test fixture
   changes separately; obtain approval before editing existing expected data.
2. Add characterization on unchanged production: full validation/error matrix,
   attached-output checks, current-layout filtering/order, exact niri argv,
   partial failure and best-effort handling. Shared import/identity test is N/A
   until extraction. Run G0 and relevant display/saver/infrastructure/backend
   units; run detached fake-niri and private saver UI before and after.
3. Extract the three bodies unchanged in one production commit. Add shared
   ownership and remove only the vanished exception; no new exception/cycle.
4. Run final G0-G4/G6 once on final runtime/test head; one ten-launch preview/
   Settings median and T+10s RSS sanity, main versus head in private sessions.
5. Record one <=30-line migration entry, adapters, <=6 laptop checks; push review
   branch/draft PR and stop. Physical display/power and aggregate laptop PSS
   checks remain pending; VM tests cannot close RELEASE_CHECKLIST.md.

## Required test maintenance (approval pending)

In tests/test_architecture.py, rename the obsolete Python legacy-edge test to
test_battery_saver_uses_shared_layout_contract and change its expected import
from display_control to display_layout (same assertIn). For the stale-exception
fixture, remove GowallSettings from the copied UtilitiesPage instead of removing
the now-shared import from copied BatterySaver. Keep the stale-exception
assertion, all other assertions, timeouts and frozen fixtures unchanged.

Stable 14 coordinator IDs/core pages stay legacy. Catalog provider discovery,
retention/deletion, further schema groups, D1 and A6 are outside this branch.
