# Render resource lifetime

Scope: investigate the owner-authorized memory issue on `fix/render-resource-lifetime`.
Keep blur, texture resolution, Jelly motion, public interfaces and worker policy.
Do not reopen D1 or change polling/power policy. Use Ponytail and Modularity.

1. Ownership: distinguish standalone Settings from the main shell; confirm normal
   Settings close terminates its Quickshell and backend. The owner confirmed
   `settings.qml` as the second instance at e91ca29; closed total is 186.12 MB PSS.
2. Baseline: reuse the copied-checkout release fixture in private Sway/D-Bus/XDG.
   Run the same theme/output/renderer workload for 48 panel cycles, sampling
   total PSS and per-owner counts after each six-cycle round and Settings close.
3. Diagnose in scratch copies: inspect Loader destruction, Jelly layer lifetime,
   glass backdrop references and decoded images. Separate retained live objects
   from Qt/driver/allocator high-water memory; do not label either a leak without
   evidence. No diagnostic instrumentation enters the runtime checkout.
4. Add focused characterization before a fix. Change only a demonstrated owner
   of expired resources; keep existing assertions. If no safe application fix is
   supported, report the measured limit rather than add speculative cleanup.
5. Repeat the identical workload. Run affected G0/G1/native checks while working;
   full G0-G4/G6 once on the final runtime/test head. If runtime changes, perform
   the existing ten-launch median and T+10s RSS sanity once before review.
6. Record a concise final summary, adapters and laptop checks. Review branch only.

Acceptance: <=400 MB steady / <=500 MB ordinary active total PSS, all shell-owned
processes included; heavy job payloads labeled separately. VM software rendering
cannot certify the laptop GPU or niri blur. Laptop warm/Settings/theme samples
remain required before release approval; no unverified "100%" claim.
