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

## Run on the laptop

Close Settings first. Keep your usual theme, monitors/media and graphics environment.
Keep the display awake and avoid clicking/typing in the automatically opened panels.
Opening Notifications marks notifications read. This tool sends timed requests; watch
that the panels actually appear and the animations finish. It cannot observe that
through the existing public IPC. An authentication dialog invalidates this workload.

From the running checkout, without switching branches or installing anything:

```bash
git fetch origin chore/laptop-memory-check
git show FETCH_HEAD:scripts/memory_workload.py | env PYTHONPATH="$PWD/scripts" python3 - --checkout "$PWD" --theme liquid --wait-close
```

Use `--theme smoked` for Smoked; this labels the report, it does not change the theme.
If the script is already in your checkout, use:

```bash
python3 scripts/memory_workload.py --theme liquid --wait-close
```

Expect about 4 minutes plus Settings startup. When prompted, close Settings with
its X; the tool waits up to 120 seconds for Settings/backend exit and then samples
again. It never kills a process. Omit `--wait-close` to leave Settings open instead.
The current implementation starts the existing settings.sh CLI with the caller's
environment; use the same graphics environment as your normal shell. The optional
Gear-route change in LAPTOP_MEMORY_TEST_REVIEW.md awaits test-assertion approval.

The new private file `/tmp/lme-memory-*/report.json` is printed at startup; it is
mode 0600 and never overwrites an existing report. `--output NEW_FILE` selects
another path. Reports include PID/checkout paths, not command arguments, environment
dumps or settings contents. Send the five PSS lines, warm delta and any INCOMPLETE
line; review the complete JSON locally for helper ownership.

Automatic checks compare inclusive PSS at steady/warm-24/warm-48/Settings-closed
with 400 decimal MB and Settings-open with 500 MB. They check persistent main
QS/backend/history PID continuity and the added Settings QS/backend pair. An unreadable
inventory, missing instance, unexpected reply or IPC timeout stops the workload and
saves an incomplete report. Exceeding a budget records OVER and continues sampling.
Exit 0 means all measured inventories fit; exit 1 means incomplete or over budget;
argument errors use exit 2. Neither exit 0 nor a small warm delta is release approval.

The collector excludes the diagnostic itself. Identify independent/shared helpers
such as a detached awww-daemon; include reviewed roots with repeatable `--pid PID`.
Heavy job payloads remain in the inclusive total and have a separate subtotal.
No process/worker is silently excluded to meet the budget. Checkpoints are not peak
RAM, VRAM or FPS measurements; a caller software flag does not identify the main
renderer. GPU identity, animation/blur/sharpness, and any screen blanking need manual
review. This diagnostic never changes renderer, preferences, polling or power policy.

## Verification status

This branch is an unmerged diagnostic prototype, not a runtime RAM optimization.
Thirteen unit contracts pass. Private Wayland trials include success at CLI wiring,
but the final healthy-workload native case fails on an IPC 5-second timeout; the
refusal test passes. A separate unchanged-host probe also times out during its
existing IPC readiness check before invoking this tool (4-second fixture deadline).
Cause is unverified; do not classify this as a confirmed environment or product bug.
The tool records INCOMPLETE instead of silently claiming the run passed.

Initial 100 ms trials were too aggressive to stand in for normal animations. The
final native fixture uses the actual 2-second/5-second defaults, a static Qt software
UI and demo backend in copied XDG/Sway/D-Bus; it does not certify physical GPU effects.
Normal X is represented by the same close-request signal injected in the copy only.
Existing assertions and frozen fixtures are unchanged. Do not merge on these native
results without resolving/accepting the baseline issue; laptop output is still needed.

Final G0 at 3f41415: **695 passed / 3 failed / 157 skipped**; qmllint 148 files,
0 errors, 71 existing warnings. The failures are the existing PendingWireCase
batched-input pipe test (8s timeout), BarGestureQmlCase mouse/wheel test (phase-3
timeout), and BatterySaverVisualCase fast-reversal spectrum test (15s timeout).
No assertion, deadline or production implementation in those areas was changed.
The same three cases on isolated main e91ca29 pass (3/0/0, 7.568s); this does not
turn the failed full gate green or establish the intermittent/suite-order cause.
The corresponding isolated head rerun also passes (3/0/0, 9.127s); no old test was
edited and no full-suite success is inferred from this narrower rerun.
Default skips include the two new native cases; they are not counted as passes.
No G1-G4/G6 or duplicate startup/RSS sanity was run for this standalone prototype;
there is no normal-startup integration or merge request.
