# Descriptor/provider ownership pilot

2026-10-31. Owner authorizes the next roadmap boundary after merging the laptop
workload. Laptop GPU/PSS and physical release checks remain open independently.

## Scope and policy

Pilot only Night Light, Idle and Keybinds, which already have catalog pages,
schema fragments and synchronous providers. No new action, schema, UI or worker.
Each descriptor declares `backend: {entry, factory}`. The existing catalog reader
validates a flat Python file beneath scripts/, declared source ownership, a named
top-level factory, unique provider references and checkout containment. No JSON
expression, arbitrary import path, callback or extra discovery mechanism.

The backend composition root resolves these references once after deep catalog
validation. It keeps explicit narrow capability construction and original factory
exports. Providers still return ActionSpec/state projections to ActionRegistry;
registration never invokes actions, projects state or starts workers.

Preserve today's withdrawal policy: disabled entries hide their catalog UI but
do not revoke backend actions or stop domain controllers. Preferences/data stay.
Missing pilot metadata/index entry retains its compatibility factory. Invalid
catalog/provider references publish the existing catalog diagnostic, fall back
to legacy UI and use the same original factories for all three pilot domains.
Resolve all references before publishing a valid catalog. A provider factory or
registered action error never triggers a retry through a fallback dispatcher.

The fallback factory map also declares capability ownership; an unbound backend
record is rejected rather than silently getting the whole DesktopBackend.
Other providers and all 14 legacy action IDs remain untouched. Explicit fallback
and import facades retire only after equivalent withdrawal/fault coverage and
owner-approved removal; this branch does not remove them.

## Sequence and checks

1. Commit this plan; characterize enabled/disabled/broken-catalog dispatch,
   context, demo/live effects, exact results, projections and registration safety
   on unchanged main. New descriptor-resolution cases are N/A before capability.
2. Add the reader/resolver and three declarations in one implementation commit.
   Test duplicate/unbound/missing/escaping/non-factory records and prove a copied
   checkout resolves its own declared factory without host edits or UI pop-in.
3. Run affected G0 plus backend/light/registry units; existing assertions and
   frozen fixtures stay unchanged. Run G0-G4/G6 once on final implementation.
4. One private-session sanity comparison: ten preview/Settings launches per head,
   medians plus QS/backend RSS at ten seconds; stop at STATE's thresholds.
5. Document actual gate/skips, compatibility policy and <=6 laptop checks; open
   a review PR, no merge. No D1 profiling, A6 changes or release approval.
