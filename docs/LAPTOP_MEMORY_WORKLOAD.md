# Laptop memory checkpoints

This optional one-shot tool completes the next release-evidence boundary in
[ROADMAP.md](ROADMAP.md). It uses the current shell, collector and public IPC;
it is not a memory optimization or an automatic release approval.

## Run

Close Settings first. Keep your normal theme/GPU/outputs/media unchanged, leave
the screen awake, and avoid keyboard/mouse input during the workload. Run only
one workload at a time. Opening Notifications marks notifications read.

From the checkout that your shell is running:

```bash
python3 scripts/memory_workload.py --theme liquid --wait-close
```

For Smoked, use `--theme smoked`. The option records your observed theme; it
does not select a theme or prove which renderer the main shell uses.
Default time is about four minutes plus Settings startup and your close response.
At the prompt, close Settings normally with its X; wait for Settings-closed.
Without `--wait-close`, Settings stays open after its sample.

If your running shell points to another checkout, use `--checkout /actual/path`.
The tool prefers LME_QS_BINARY, then the deployed private runtime, then PATH.
`--quickshell /actual/binary` pins the client explicitly; it never installs one.
Other Quickshell instances cause refusal rather than an ambiguous attachment.

## Results and ownership

The tool prints the location of a new mode-0600 report before sending UI commands.
Default: `/tmp/lme-memory-…/report.json`; `--output NEW_FILE` selects another path.
Existing files/symlinks are refused. Checkpoints are saved progressively; ordinary
errors/Ctrl-C preserve the partial report. Storage failure or forced termination
can prevent a complete final report. Only shell panels are closed in cleanup;
Settings and user jobs are never killed.

| Checkpoint | Inclusive PSS comparison |
| --- | --- |
| steady | <=400 decimal MB |
| warm-24, warm-48 | <=400 MB, panels closed after settling |
| Settings-open | <=500 MB, main and Settings simultaneously present |
| Settings-closed (`--wait-close`) | <=400 MB; original main identities retained |

The workload opens/closes Clipboard, Controls, Activity, Notifications, Launcher
and Power eight times. Defaults: two seconds open, two closed, five seconds
settling before each sample. Settings opens through the same main-owned route as
Gear, preserving that process's graphics environment/executable selection.
No renderer, theme, preferences, layout, polling or power setting is changed.

Samples reuse [memory_report.py](../scripts/memory_report.py), including all
recognized shell/helpers/job payloads. Independent/shared helpers such as a
surviving awww-daemon need manual ownership review and repeatable `--pid PID`
additions. The collector excludes the diagnostic itself. Reports contain PID/
checkout/counter data, not command arguments, environment dumps or UI contents.

The preflight requires one live main shell, enabled Clipboard/Notifications and
complete counters before closing anything. PID plus start-time continuity guards
main/backend/history; the added Settings/backend pair must exit normally.
Incomplete counters, unexpected instances or IPC errors produce INCOMPLETE and
exit 1. OVER records a budget miss but continues collecting later checkpoints.
Exit 0 means the recorded inventories fit their budgets; exit 2 is an argument
error. No outcome closes the hardware or ownership review automatically.

Send the five PSS lines, the warm-48 minus warm-24 delta and any OVER/INCOMPLETE
line. Review the full JSON locally for scope/helper issues before accepting it.
Positive warm growth alone is not a leak diagnosis. These are checkpoints, not
peak RAM, VRAM or FPS measurements; summed RSS double-counts shared pages.

## Verification and next step

Unit/fake-IPC contracts cover refusal, instance pinning, PID reuse, budgets,
Gear routing, private output and interruption. Copied-checkout private Wayland
cases cover 48 requests and normal Settings close, including owner-environment
inheritance. Their shortened timings/static software UI test CLI wiring, not
normal-animation warming, physical input delivery, GPU blur or laptop budgets.
Keep defaults for the real laptop run; watch that panels actually appear and
finish animating. Stop if authentication interrupts the workload: existing
public IPC cannot certify that every animation rendered or detect that dialog.

After the laptop report, review actual owners and the warm trend. Make a resource
fix only if the evidence identifies an expired resource; otherwise close only
the memory checklist row when its criteria pass. Radio, capture, display and
Battery Saver restore still need the separate [release checklist](RELEASE_CHECKLIST.md).
No further schema/provider/UI conversion is part of this diagnostic branch.
