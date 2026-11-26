#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One measured session: an instrumented shell in place of the deployed one, the scenarios, everything back.

  run.py --tree DIR --label NAME [--out DIR] [--budget 1500] [--max-seconds 600] [--dry-run] -- s4 s2:reps=3 s1 s3
  run.py --simulate --out DIR [--faults s4:swallow@3,s2:ghost@2] -- s4:reps=2 s2:reps=3 s1 s3

Live, in this order:
  1. checks that cost nothing: the tree is a probe tree, the scenarios parse, Quickshell,
     /dev/uinput and the session are there, the injector builds
  2. preflight: every QML file of the tree parses (a throwaway Quickshell, no window)
  3. the idle watchers, then the quiet gate: a few seconds without input from anyone
  4. standin.py swap: dead-man timer, config snapshot, deployed shell stopped, stand-in started
  5. probe sampler, injector, external sampler, reference client; the scenarios in the order given
  6. always (also after a crash, an abort or Ctrl-C): input released, helpers stopped,
     standin.py restore, the session verified, kernel log and records written, analyze.py

`--max-seconds` is the dead-man interval: the longest the owner waits for their shell after
the harness dies (the timer is re-armed while the session lives). `--budget` is the longest
the scenarios run; each one ends at its next repetition when less than 45 s remain.

In <out>: records.json (one record per repetition), meta.json, summary.json, summary.md,
probe/ (probe logs), state/ (stand-in logs, config snapshot, verify.json), inject.log
(the replay script: every input with its time), sampler.jsonl, ref.log, kernel.log,
standin.log, preflight.log. Exit code 0 = ran and the session is back; 1 = the run failed;
2 = refused before the swap (nothing to restore); 3 = ran, but the session is NOT as it was.
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze  # noqa: E402  (sibling modules of the harness)
import idlegate  # noqa: E402
import inject  # noqa: E402
import scenarios  # noqa: E402
import eyes  # noqa: E402  (screenshot eyes, active only with --eyes)
import standin  # noqa: E402
from probe import QS, Probe  # noqa: E402

RUNS = Path.home() / ".cache/lme-perf/rv2/runs"
BIN = Path.home() / ".cache/lme-perf/rv2/bin"
MARGIN_MS = 45000.0        # a scenario stops before the budget is spent by this much
WATCHERS = ("long", "short")


def say(text):
    print(f"{time.strftime('%H:%M:%S')} {text}", flush=True)


class Refused(Exception):
    """Stop before the swap: nothing has to be restored."""


def keep_error(out: Path, text: str):
    """Add to the run's error log; a second failure must not hide the first."""
    with open(out / "error.log", "a") as handle:
        handle.write(time.strftime("%H:%M:%S ") + text.rstrip() + "\n")


def tool(command, env, log_path):
    """A helper of the harness (standin.py): its output streamed here and kept in a log; exit code."""
    with open(log_path, "a") as log:
        process = subprocess.Popen([str(part) for part in command], env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in process.stdout:
            log.write(line)
            say("  " + line.rstrip())
        process.stdout.close()
        return process.wait()


# ---- before the swap ---------------------------------------------------------------------------------

def check_prerequisites(tree: Path, specs: list) -> Path:
    """Everything that must be true before anything is touched. Returns the injector binary."""
    problems = []
    if not (tree / ".perf-probe.json").is_file() or not (tree / "qml/services/Probe.qml").is_file():
        problems.append(f"{tree} is not a probe tree (prepare.py --repo ... --ref ... --out ...)")
    if not standin.QS.is_file():
        problems.append(f"{standin.QS} is missing")
    if not standin.LINK.is_symlink():
        problems.append(f"{standin.LINK} is not a symlink; refusing to guess")
    if not os.access("/dev/uinput", os.W_OK):
        problems.append("/dev/uinput is not writable")
    for name in ("gcc", "swayidle", "niri", "systemd-run", "systemctl", "journalctl"):
        if not shutil.which(name):
            problems.append(f"{name} is not in PATH")
    if problems:
        raise Refused("\n  ".join(problems))
    try:
        binary = inject.build(BIN / "uinput_inject")
    except inject.InjectorError as error:
        raise Refused(str(error)) from None
    try:
        for spec in specs:
            scenarios.parse(spec)        # Refused (Skip) on a typo: now, not ten minutes in
    except scenarios.Skip as error:
        raise Refused(str(error)) from None
    return binary


def preflight(tree: Path, env: dict, log_path: Path) -> list:
    """Every QML file of the tree parses in a throwaway Quickshell. Returns the errors, if any."""
    try:
        with open(log_path, "w") as log:
            done = subprocess.run([str(QS), "-p", str(HERE / "preflight.qml")],
                                  env={**env, "LME_PERF_TREE": str(tree)}, stdin=subprocess.DEVNULL,
                                  stdout=log, stderr=subprocess.STDOUT, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return ["preflight Quickshell did not finish in 240 s"]
    lines = Path(log_path).read_text().splitlines()
    errors = [line.strip() for line in lines if "PREFLIGHT ERROR " in line and not line.rstrip().endswith(" files")]
    if not any("PREFLIGHT OK " in line for line in lines):
        errors.append(f"preflight did not report success (exit {done.returncode}); see {log_path}")
    return errors


def quiet_gate(seconds: int, max_wait: int) -> float:
    """The two idle watchers, then a seat nobody has touched for `seconds`."""
    idlegate.watch(argparse.Namespace(dir=idlegate.DEFAULT_DIR, seconds=seconds))
    long_log = idlegate.DEFAULT_DIR / "long.log"
    started = time.time()
    while True:
        quiet = idlegate.is_quiet(long_log, seconds, time.time())
        if quiet is not None:
            say(f"quiet gate: no input since {time.strftime('%H:%M:%S', time.localtime(quiet))}")
            return quiet
        if not idlegate.running("long"):
            raise Refused("the idle watcher is not running (idlegate.py watch)")
        if time.time() - started >= max_wait:
            raise Refused(f"no {seconds}s of quiet within {max_wait}s: the owner is at the machine")
        time.sleep(0.5)


def no_foreign_settings(env, wait_s=75) -> str:
    """A Settings window that is already up belongs to the owner's shell (the process lingers
    60 s after its last close): wait for it, never touch it. Returns "" or why not."""
    probe = Probe(env, Path(), Path(), Path())
    deadline = time.time() + wait_s
    while time.time() < deadline:
        try:
            if not probe.settings_origin().get("found"):
                return ""
        except ProbeError as error:
            return f"niri does not list the windows: {error}"
        say("waiting: a Settings window of the owner's shell is still up (it closes by itself)")
        time.sleep(3)
    return "a Settings window (app_id lme-shell-settings) is still up after 75 s"


class Deadman:
    """The dead-man timer of the swap, re-armed while the session lives.

    A harness that dies is replaced by the timer within one interval. A harness that lives is
    bounded by --budget, so the timer must not fire under it: every 40% of the interval a new
    timer is armed and only then the old one is stopped (no moment without one)."""

    def __init__(self, state: Path, interval: int):
        self.state, self.interval = state, interval
        self.off = threading.Event()
        self.error = ""
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def re_arm(self):
        values = standin.read_env(self.state)
        previous = values.get("TIMER", "")
        values["TIMER"] = standin.arm_timer(self.state, self.interval)
        standin.disarm_timer(previous)
        standin.write_env(self.state, values)

    def loop(self):
        while not self.off.wait(self.interval * 0.4):
            try:
                self.re_arm()
            except Exception as error:  # noqa: BLE001  (reported; the old timer stays armed)
                self.error = f"{error!r}"[:300]
                return

    def stop(self):
        self.off.set()
        self.thread.join(timeout=30)


# ---- the session -------------------------------------------------------------------------------------

def live(args) -> int:
    out, tree = args.out.resolve(), args.tree.resolve()
    state = out / "state"
    specs = [part for part in (piece.strip() for piece in args.scenarios) if part]
    if (state / "swapped").exists() and not (state / "restored").exists():
        say(f"REFUSED: {state} holds a swap that was never restored: "
            f"`standin.py restore --state {state}` first")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    (out / "probe").mkdir(exist_ok=True)   # the stand-in's Probe sink writes here from its first breath
    say(f"run directory {out}")
    try:
        env = standin.session_env()
        binary = check_prerequisites(tree, specs)
    except (standin.Fail, Refused) as error:
        say(f"REFUSED: {error}")
        return 2
    os.environ.update({key: env[key] for key in standin.SESSION_KEYS})
    provenance = json.loads((tree / ".perf-tree.json").read_text()) if (tree / ".perf-tree.json").is_file() else {}

    errors = preflight(tree, env, out / "preflight.log")
    if errors:
        say("REFUSED: the probe tree does not parse:\n  " + "\n  ".join(errors[:40]))
        return 2
    say(f"preflight: every QML file of {tree.name} parses")
    foreign = no_foreign_settings(env)
    if foreign:
        say(f"REFUSED: {foreign}")
        return 2
    try:
        quiet_gate(args.quiet_seconds, args.max_wait)
    except Refused as error:
        say(f"REFUSED: {error}")
        return 2

    command = [sys.executable, str(HERE / "standin.py"), "swap", "--tree", str(tree), "--state", str(state),
               "--max-seconds", str(args.max_seconds), "--quiet-seconds", str(args.quiet_seconds),
               "--env", f"LME_PERF_PROBE_LOG={out / 'probe'}", "--env", "LME_SHELL_WATCHDOG=1"]
    command += ["--dry-run"] if args.dry_run else []
    command += ["--no-notice"] if args.no_notice else []
    say("standin.py swap" + (" (dry run)" if args.dry_run else ""))
    if tool(command, env, out / "standin.log") != 0:
        say("FAILED: the swap did not happen; the deployed shell was not touched (standin.log)")
        return 2 if args.dry_run else 1
    if args.dry_run:
        idlegate.stop(argparse.Namespace())       # the watchers outlast nothing that did not run
        say("DRY RUN OK: the swap would work; nothing was changed")
        return 0

    started_ms = time.time() * 1000.0
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    ctx = inj = sampler = ref = deadman = probe = None
    code, failure = 0, ""
    workspace_before = workspace_after = {}
    try:
        entries = json.loads((state / "standin.json").read_text())
        pid = next(entry["pid"] for entry in entries if entry["kind"] == "main")
        deadman = Deadman(state, args.max_seconds).start()
        probe = Probe(env, tree, out / "probe", state)
        screen = probe.screen()
        workspace_before = probe.focused_workspace()
        probe.watch(True)
        inj = inject.Injector(out / "inject.log", width=screen["width"], height=screen["height"],
                              binary=binary, settle_ms=args.settle_ms).start()
        with open(out / "sampler.log", "a") as log:
            sampler = subprocess.Popen([sys.executable, str(HERE / "sampler.py"), "--pid", str(pid), "--out", str(out),
                                        "--settings", str(tree / "settings.qml"), "--stall-ms", "150"],
                                       env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        with open(out / "ref.log", "a") as log:
            ref = subprocess.Popen([str(QS), "-p", str(HERE / "refclient.qml")],
                                   env={**env, "LME_PERF_REF_SECONDS": str(args.budget + 120)},
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.DEVNULL)
        ctx = scenarios.Ctx(inj, probe, deadline_ms=time.time() * 1000.0 + args.budget * 1000.0,
                            width=screen["width"], height=screen["height"])
        if args.eyes:
            ctx.eyes = eyes.Eyes(out, screen["width"], screen["height"])
        ctx.meta.update(screen=screen, pid=pid, units=sorted({entry["unit"] for entry in entries}),
                        settings_tree=str(tree), ping_ms=round(probe.ping(), 2))
        say(f"stand-in pid {pid}; output {screen['name']} {screen['width']}x{screen['height']} "
            f"@ {screen['refresh_hz']} Hz; probe ping {ctx.meta['ping_ms']} ms")
        # The first real input only goes out once the seat has been quiet since the stand-in came up.
        scenarios.run(ctx, specs)
    except scenarios.OwnerIsBack as error:
        failure = f"ABORTED, input of the owner: {error}"
    except scenarios.Stuck as error:
        failure = f"STOPPED, {error}"
    except KeyboardInterrupt:
        failure = "ABORTED, interrupted"
    except Exception as error:  # noqa: BLE001  (the session is put back whatever happened)
        failure = f"FAILED, {error!r}"
        keep_error(out, traceback.format_exc())
    finally:
        if failure:
            say(failure)
        if ctx is not None:
            ctx.meta["ended"] = failure or "finished"
            if ctx.eyes is not None:
                ctx.meta["eyes"] = len(ctx.eyes.dump())
            ctx.meta["warmup_end_ms"] = scenarios.warmup_end(ctx) or ctx.now()
            scenarios.dump(ctx, out / "records.json")
        workspace_after = probe.focused_workspace() if probe is not None else {}
        try:
            code = put_back(ctx, inj, sampler, ref, deadman, state, env, out)
        except Exception:  # noqa: BLE001
            code = 3
            say("PUT BACK FAILED: read error.log, then `standin.py restore --state " + str(state) + "`")
            keep_error(out, traceback.format_exc())
        verify_file = state / "verify.json"
        verify = json.loads(verify_file.read_text()) if verify_file.is_file() else None
        seconds = round(time.time() - started_ms / 1000.0, 1)
        meta = {"label": args.label, "tree": str(tree), "ref": provenance.get("commit", "")[:12], "provenance": provenance,
                "started": started, "epoch_ms": started_ms, "seconds": seconds, "simulated": False, "scenarios": specs,
                "warmup_end_ms": (ctx.meta.get("warmup_end_ms") if ctx else None),
                "truncated": ctx.meta.get("truncated") if ctx else None,
                "screen": ctx.meta.get("screen") if ctx else None, "pid": (ctx.meta or {}).get("pid") if ctx else None,
                "workspace_before": workspace_before if ctx else {}, "workspace_after": workspace_after,
                "workspace_back": workspace_before == workspace_after,
                "restore": verify, "ended": failure or "finished", "budget_s": args.budget, "max_seconds": args.max_seconds}
        (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
        collect_kernel_log(out, env, started_ms)
    summary = analyze.summarize(out)
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    (out / "summary.md").write_text(analyze.to_markdown(summary))
    say(f"records: {len(ctx.records) if ctx else 0}; problems and recoveries: {len(ctx.problems) if ctx else 0}")
    say(f"restore: {'OK, the deployed shell is back' if code == 0 else 'NOT VERIFIED, read verify.json'}; summary: {out / 'summary.md'}")
    if failure.startswith(("FAILED", "ABORTED", "STOPPED")) and code == 0:
        code = 1
    return code


def put_back(ctx, inj, sampler, ref, deadman, state, env, out) -> int:
    """End the session: the helpers first, then the deployed shell. 0 when it is verified back."""
    failures = []
    if ctx is not None:
        try:
            ctx.load.stop()
        except Exception as error:  # noqa: BLE001
            failures.append(f"load: {error!r}")
    for name, helper in (("reference client", ref), ("sampler", sampler)):
        if helper is None:
            continue
        try:
            if helper.poll() is None:
                helper.terminate()
                helper.wait(timeout=10)
        except Exception as error:  # noqa: BLE001
            failures.append(f"{name}: {error!r}")
            helper.kill()
    if inj is not None:
        try:
            inj.release()              # every key and button the injector may still hold
        except Exception:  # noqa: BLE001  (the injector releases on its own dead-man as well)
            pass
        inj.close()
    if deadman is not None:
        deadman.stop()
        if deadman.error:
            failures.append(f"dead-man timer: {deadman.error}")
    if ctx is not None:
        try:
            ctx.probe.quit("settings")       # the stand-in's Settings lingers 60 s after its last close
        except Exception:  # noqa: BLE001  (it quits by itself)
            pass
    say("standin.py restore")
    try:
        summary = standin.restore_state(state, env)
    except standin.Fail as error:
        say(f"  RESTORE NOT CONFIRMED: {error}")
        failures.append(str(error))
        summary = standin.verify(state, env) if standin.LINK.is_symlink() else None
    if summary is not None:
        for line in (state / "events.log").read_text().splitlines()[-14:]:
            say("  " + line)
    idlegate.stop(argparse.Namespace())
    for text in failures:
        say(f"  NOT CLEAN: {text}")
    return 0 if summary and summary.get("ok") and not failures else 3


def collect_kernel_log(out: Path, env: dict, since_ms: float):
    """The kernel's own view of the run: GPU resets, OOM kills, hung tasks."""
    try:
        with open(out / "kernel.log", "w") as log:
            subprocess.run(["journalctl", "-k", "--no-pager", "-o", "short-precise", f"--since=@{int(since_ms / 1000.0)}"],
                           env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    except (OSError, subprocess.SubprocessError):
        pass


# ---- without a desktop -------------------------------------------------------------------------------

def simulated(args) -> int:
    import sim
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    specs = [part for part in (piece.strip() for piece in args.scenarios) if part]
    for spec in specs:
        scenarios.parse(spec)
    started = time.time() * 1000.0
    model, inj, probe = sim.build(out, args.faults)
    ctx = scenarios.Ctx(inj, probe, deadline_ms=started + args.budget * 1000.0)
    failure = ""
    try:
        scenarios.run(ctx, specs)
    except scenarios.OwnerIsBack as error:
        failure = f"ABORTED, input of the owner: {error}"
    except scenarios.Stuck as error:
        failure = f"STOPPED, {error}"
    except Exception:  # noqa: BLE001
        failure = "FAILED"
        keep_error(out, traceback.format_exc())
    ctx.meta["warmup_end_ms"] = scenarios.warmup_end(ctx) or ctx.now()
    scenarios.dump(ctx, out / "records.json")
    (out / "meta.json").write_text(json.dumps({
        "label": args.label, "ref": "", "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "epoch_ms": started,
        "seconds": round((ctx.now() - started) / 1000.0, 1), "simulated": True, "scenarios": specs, "faults": args.faults,
        "warmup_end_ms": ctx.meta.get("warmup_end_ms"), "truncated": ctx.meta.get("truncated"), "ended": failure or "finished",
    }, indent=1) + "\n")
    summary = analyze.summarize(out)
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    (out / "summary.md").write_text(analyze.to_markdown(summary))
    print(analyze.to_markdown(summary))
    print(failure or f"simulated {len(ctx.records)} records in {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tree", type=Path, help="probe tree from prepare.py (live)")
    ap.add_argument("--out", type=Path, help=f"run directory (default {RUNS}/<time>-<label>)")
    ap.add_argument("--label", default="run", help="name of the run in the report")
    ap.add_argument("--budget", type=int, default=1500, help="longest the scenarios run, seconds")
    ap.add_argument("--max-seconds", type=int, default=600, help="dead-man interval of the swap, 30..1200 s")
    ap.add_argument("--quiet-seconds", type=int, default=standin.QUIET_SECONDS, help="quiet time the gate needs")
    ap.add_argument("--max-wait", type=int, default=240, help="longest wait for a quiet seat, seconds")
    ap.add_argument("--settle-ms", type=int, default=600, help="wait after the injector created its devices")
    ap.add_argument("--no-notice", action="store_true", help="no desktop notification at the swap")
    ap.add_argument("--eyes", action="store_true", help="screenshot the screen around every click (eyes/ under the run dir)")
    ap.add_argument("--dry-run", action="store_true", help="checks, preflight, standin.py swap --dry-run: no swap")
    ap.add_argument("--simulate", action="store_true", help="run against sim.py instead of the desktop")
    ap.add_argument("--faults", action="append", default=[], metavar="TAG:NAME@N,KEY=V", help="simulated: a fault of sim.py")
    ap.add_argument("scenarios", nargs="*", help="warmup s4 s2 s1 s3, each with options: s4:reps=5,routes=key+ipc")
    args = ap.parse_args()
    if args.simulate:
        if not args.out:
            ap.error("--simulate needs --out")
        return simulated(args)
    if not args.tree:
        ap.error("--tree is needed (probe tree from prepare.py)")
    if not args.out:
        args.out = RUNS / f"{time.strftime('%Y%m%d-%H%M%S')}-{args.label}"
    args.out = args.out.expanduser()
    args.tree = args.tree.expanduser()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))     # through the finally blocks, like Ctrl-C
    return live(args)


if __name__ == "__main__":
    sys.exit(main())
