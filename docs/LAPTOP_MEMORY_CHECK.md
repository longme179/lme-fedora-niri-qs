# Laptop memory workload

Plan: a stdlib, explicitly invoked diagnostic, independent of the normal shell.
Reuse memory_report.collect and existing shell/settings IPC; no production probe,
settings mutation, renderer change, process kill or new background service.

1. Require exactly one main instance for the selected checkout and no open
   Settings. Pin IPC to its instance ID; reject demo, missing/withdrawn catalog
   panels and incomplete memory inventories. Include explicit helper --pid roots.
2. Close panels, settle, measure steady. Cycle Clipboard, Controls, Activity,
   Notifications, launcher and power eight times; measure after 24 and 48 cycles.
3. Launch Settings through settings.sh, wait for its existing visible-window
   confirmation, then measure Settings-open. Leave it open for normal X close.
4. Report inclusive PSS, per-role/PID inventory, persistent-process continuity,
   400 MB closed-panel / 500 MB Settings-open comparisons and warm-48 minus warm-24.
   Incomplete data cannot pass. Positive growth alone is not a leak diagnosis.
5. Save a private new JSON report, including errors/interruption and timings.
   Opening Notifications marks them read. Use timed waits, not a claim of actual
   animation completion; visual quality/FPS, helper ownership and GPU remain manual.

Tests first: unit/fake-IPC cases for admission, pinned commands, budgets, incomplete
data, continuity and Settings readiness; then a copied-checkout private native run.
Run affected G0 and those tests. This optional tool does not enter shell startup;
no D1 benchmark or duplicate launch/RSS sanity of unchanged shell runtime.
