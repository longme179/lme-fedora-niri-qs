# scripts/perf — the measurement harness of `perf/responsive-v2`

One goal: measure the four symptoms on the real session, with real input, and prove every
fix with numbers. Nothing here changes what the shell does; the probe only watches.

## The four symptoms

| id | symptom |
|---|---|
| S1 | Control Center: switching tabs sometimes freezes the screen/shell |
| S2 | Settings: rapid page switching stops mid-animation; a page stays dimmed (recede cue never restored) |
| S3 | the whole shell sometimes becomes unresponsive for a moment |
| S4 | the activity island opens but does not close on Escape |

## Files

| file | role |
|---|---|
| `run.py` | one measured session end to end: checks, preflight, quiet gate, swap, scenarios, restore, report |
| `scenarios.py` | S4/S2/S1/S3: real input, probe timeline, one functional assertion per number |
| `sim.py` | a model of the shell for the offline self-test (`run.py --simulate`, faults on purpose) |
| `selftest.py` | 9 cases on the model: every detector must fire on its fault and stay silent on a healthy run |
| `analyze.py` | records -> medians/p95/max, failure rates, exit criteria, before/after tables |
| `standin.py` | swap the deployed shell for an instrumented one and put everything back (dead-man timer) |
| `restore_shell.sh` | the restore, idempotent, armed with retry timers |
| `drill_standin.py` | swap/restore drill against a stand-in shell (sandbox) |
| `idlegate.py` | the quiet gate: 3 s without input from anyone; a foreign input aborts the session |
| `prepare.py` | export a probe tree: `git archive <ref>` + the probe patch, into `~/.cache/lme-perf/rv2/` |
| `probe_patch.py` | the probe patch itself (exact anchors; a drifted anchor stops the run) |
| `probe/Probe.qml` | the probe singleton copied into a scratch tree: marks, frames, state sampler |
| `inject.py` + `uinput_inject.c` | real input through one uinput device pair (keyboard + absolute pointer) |
| `probe.py` | talk to the probe (IPC to observe and open a top-level panel; never to switch tabs) |
| `sampler.py` | external RSS/CPU sampler of the shell and Settings processes |
| `refclient.qml` | reference Wayland client: is the compositor alive when the shell is not |
| `preflight.qml` | parse-check every QML file of a tree before anything is swapped |

## Rules baked into the code

- The IPC never switches a tab or a page; it may open a top-level panel (one S4 route) and
  read state and geometry. Tabs and pages are real clicks on the real items.
- Escape is pressed only while the shell's overlay layer holds the keyboard
  (`lme-overlay`, Exclusive) or the Settings window is focused; each press is asserted.
- Settings is its own process: "open" is niri listing its window (`app_id
  lme-shell-settings`), not a shell flag. `shell close` cannot close it; recovery clicks
  its own close button.
- Every swap arms the dead-man timer BEFORE the deployed shell stops; the restore is
  idempotent and retried by timers until the session is exactly as it was.
- A run refuses to start while the owner's Settings window is up, or the session is
  locked, or an authentication layer holds the keyboard.
- Super+L is never injected. No key is sent to a window of the owner.

## One session

```
run.py --tree ~/.cache/lme-perf/rv2/p-head --label s4-first --budget 900 -- \
       warmup:rounds=1 s4:reps=3 s2:reps=3 s1:reps=2 s3:reps=1
```

`--budget` seconds of scenarios; every scenario stops at its next repetition when less
than 45 s remain. `--max-seconds` (default 600) is the dead-man interval: the longest the
owner waits for their shell if the harness dies. Output lands under
`~/.cache/lme-perf/rv2/runs/<timestamp>-<label>/`: `records.json`, `summary.md`,
`summary.json`, `probe/`, `state/` (swap logs, config snapshot, `verify.json`),
`inject.log` (the replay script: every input with its time), `sampler.jsonl`, `ref.log`,
`kernel.log`, `standin.log`, `preflight.log`.

Exit code 0 = ran and the session is back as it was; 1 = the run failed (still restored);
2 = refused before the swap (nothing to restore); 3 = ran, but the session is NOT as it
was — read `state/verify.json` and `state/restore.log` before doing anything else.

Scenario options: `s4:reps=3,routes=key+click+ipc,delays=5+60+150+400,prior=control,load=8`,
`s2:reps=3,variants=all+aba+toast,burst=6,gap_ms=60,pairs=about-wallpaper`,
`s1:reps=3,variants=ordered+random+fast,clicks=12,seconds=3,seed=1,max_clicks=400`,
`s3:reps=1`, `warmup:rounds=1`.

An S2 burst aims its nav entries once, before the first click, whenever they all lie still
where they were aimed at; the clicks then follow at `gap_ms`. The report's `aimed once` and
`click gap` columns say how many bursts did and how fast the clicks really went. A sidebar
that moved in between makes the harness aim again before every click: slower than asked,
but only what was just aimed at is pressed.

Before every aimed press the sidebar also has to report that it is not moving any more: a
press that lands while its Flickable eases the last wheel notch never reaches the button.
The report's `eaten` column counts such presses. A click on the page that is already shown
navigates nowhere: it is `already there` and reads 0.0.
The press on the wallpaper page's Scan button is aimed the same way: the page scrolls
until the button lies well inside the viewport, and the press goes where the button's rect
came to rest, not where it was when it first came into view while the page was still
easing. The rect is window-relative, so the window's origin is added before the press goes
to the injector: without it every Scan press missed the button by the window offset and no
toast ever came from the button.

## Offline first, live second

```
python3 scripts/perf/selftest.py              # 9 cases on the model, ~3 minutes, no desktop needed
python3 scripts/perf/run.py --simulate --out /tmp/smoke -- s4:reps=1 s2:reps=1
```

The self-test is the contract: every detector must report the fault it was built for
(an Escape swallowed, a page left half faded, a frozen GUI thread, a late close, a missing
keyboard focus, a stall during a burst) and must stay silent on a healthy model. The
timings of the model are made up; they prove the detectors, nothing about the real shell.

## A/B

```
analyze.py compare <run-a> <run-b>            # before/after table per symptom
```

A change is kept only when a measured symptom improves on the real session, N >= 10 per
side, median and p95 and max reported with the functional assertions of each repetition
(`records.json`).
