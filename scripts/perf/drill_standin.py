#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sandbox drill of scripts/perf/standin.py + restore_shell.sh against a fake world.

The scripts that swap the owner's shell for a stand-in must be right before they ever run on
the host. This builds a throw-away HOME with a fake niri, a fake systemctl/systemd-run, a fake
launcher and a fake Quickshell (drill/fakeshell.c, argv kept verbatim) and walks every branch:
idle gate, dry run, normal swap/restore, dead-man timer, foreign input, lock deferral, frozen
(silent) shell with --force, unfinished swap, extend, start failures, pid/age classification,
no deployed shell. Needs gcc and bash; touches nothing outside --work.

Usage: python3 scripts/perf/drill_standin.py [--only NAME ...] [--work DIR]
Exit code 1 when any check fails. Every branch found here was a real bug in the scripts.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
DRILL = Path.home() / ".cache/lme-perf/rv2/drill"
STANDIN = SRC / "scripts/perf/standin.py"
FAKESHELL_C = Path(__file__).resolve().parent / "drill/fakeshell.c"

FAKE_NIRI = r'''#!/usr/bin/env python3
import json, subprocess, sys, time
from pathlib import Path
home = Path.home(); fake = home / ".fake"
def live(name):
    try: pids = [int(p) for p in (fake / name).read_text().split()]
    except OSError: return []
    return [p for p in pids if Path(f"/proc/{p}").exists()]
a = sys.argv[1:]
if a[:3] == ["msg", "--json", "layers"]:
    layers = []
    if live("main.pids"):
        layers.append({"namespace": "lme-bar", "output": "eDP-1", "layer": "Top", "keyboard_interactivity": "None"})
        if (fake / "overlay-exclusive").exists():
            layers.append({"namespace": "lme-overlay", "output": "eDP-1", "layer": "Overlay", "keyboard_interactivity": "Exclusive"})
    print(json.dumps(layers))
elif a[:3] == ["msg", "action", "spawn"]:
    assert a[3] == "--", a
    with open(fake / "spawn.log", "a") as log:
        log.write(f"{time.time():.3f} {' '.join(a[4:])}\n")
        subprocess.Popen(a[4:], start_new_session=True, stdout=log, stderr=log, stdin=subprocess.DEVNULL)
    if (fake / "foreign-on-spawn").exists():  # the owner touches the seat the moment the stand-in starts
        (fake / "foreign-on-spawn").unlink()
        idle = home / ".cache/lme-perf/rv2/idle"; idle.mkdir(parents=True, exist_ok=True)
        with open(idle / "short.log", "a") as handle: handle.write(f"{time.time():.3f} R\n")
    print()
else:
    sys.exit(2)
'''

FAKE_SYSTEMCTL = r'''#!/usr/bin/env python3
import os, signal, sys, time
from pathlib import Path
home = Path.home(); fake = home / ".fake"
a = sys.argv[1:]
def name_of(unit): return unit[:-6] if unit.endswith(".timer") else unit
def alive(unit):
    try: pids = [int(p) for p in (fake / "units" / name_of(unit)).read_text().split()]
    except OSError: return []
    return [p for p in pids if Path(f"/proc/{p}").exists()]
with open(fake / "systemctl.log", "a") as log: log.write(f"{time.time():.3f} {' '.join(a)}\n")
if a[:2] == ["--user", "show-environment"]:
    for line in ("XDG_RUNTIME_DIR=/run/user/1000", "WAYLAND_DISPLAY=wayland-1",
                 "NIRI_SOCKET=/run/user/1000/niri.wayland-1.1.sock",
                 "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus"):
        print(line)
elif a[:2] == ["--user", "is-active"]:
    print("active" if alive(a[2]) else "inactive")
elif a[:2] == ["--user", "stop"]:
    unit = [x for x in a[2:] if not x.startswith("--")][0]
    for pid in alive(unit):
        try: os.kill(pid, signal.SIGTERM)
        except OSError: pass
    (fake / "units" / name_of(unit)).unlink(missing_ok=True)
'''

FAKE_SYSTEMD_RUN = r'''#!/usr/bin/env python3
import shlex, subprocess, sys
from pathlib import Path
home = Path.home(); fake = home / ".fake"; (fake / "units").mkdir(exist_ok=True)
a = sys.argv[1:]
unit = next((x.split("=", 1)[1] for x in a if x.startswith("--unit=")), None)
delay = next((float(x.split("=", 1)[1]) for x in a if x.startswith("--on-active=")), None)
rest = [x for x in a if not x.startswith("--")]
cmd = rest[rest.index("/bin/bash"):]
devnull = subprocess.DEVNULL
if delay is None:
    p = subprocess.Popen(cmd, start_new_session=True, stdin=devnull, stdout=devnull, stderr=devnull)
else:
    shell = "sleep %g; exec %s" % (delay, " ".join(shlex.quote(c) for c in cmd))
    p = subprocess.Popen(["/bin/bash", "-c", shell], start_new_session=True, stdin=devnull, stdout=devnull, stderr=devnull)
(fake / "units" / unit).write_text(f"{p.pid}\n")
print(f"Running timer as unit: {unit}.timer")
'''

LAUNCHER = r'''#!/usr/bin/env bash
set -euo pipefail
export PATH="${HOME}/.local/bin:${PATH}"
case "${1:-start}" in
    start) exec "$HOME/.local/share/lme-shell/deployment/bin/quickshell" -c lme-shell --no-duplicate ;;
    *) echo "fake launcher: only start" >&2; exit 2 ;;
esac
'''

RESULTS = []
MARK = str(DRILL) + "/"  # fake shells are recognised by this path in their command line


def mains():
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if MARK in cmd and "quickshell" in cmd and " -c lme-shell " in cmd and " ipc " not in cmd:
            found.append(int(entry.name))
    return found


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("  PASS " if cond else "  FAIL ") + name + (f"   <- {detail}" if not cond and detail else ""), flush=True)


def build(name):
    root = DRILL / f"world-{name}"
    shutil.rmtree(root, ignore_errors=True)
    home = root / "home"
    for sub in ("bin", ".fake", ".config/quickshell", ".config/lme-shell", ".config/niri", ".local/bin",
                ".local/share/lme-shell/deployment/bin", ".cache/lme-perf/rv2/idle", ".cache/lme-perf/rv2/state"):
        (home / sub).mkdir(parents=True)
    for script_name, body in (("niri", FAKE_NIRI), ("systemctl", FAKE_SYSTEMCTL), ("systemd-run", FAKE_SYSTEMD_RUN)):
        path = home / "bin" / script_name
        path.write_text(body)
        path.chmod(0o755)
    launcher = home / ".local/bin/lme-shell"
    launcher.write_text(LAUNCHER)
    launcher.chmod(0o755)
    qs = home / ".local/share/lme-shell/deployment/bin/quickshell"
    shutil.copy2(DRILL / "fakeshell", qs)
    deployed = home / "lme-fedora-niri-qs"
    (deployed / "scripts").mkdir(parents=True)
    shutil.copy2(SRC / "scripts/start.sh", deployed / "scripts/start.sh")
    tree = home / "probe-tree"
    shutil.copytree(deployed, tree)
    (tree / ".perf-probe.json").write_text("{}\n")
    (tree / "qml/services").mkdir(parents=True)
    (tree / "qml/services/Probe.qml").write_text("pragma Singleton\nimport QtQuick\nItem {}\n")
    for repo in (deployed, tree):
        (repo / "scripts/desktop_backend.py").write_text("import sys\nsys.exit(0)\n")
    (home / ".config/quickshell/lme-shell").symlink_to(deployed)
    (home / ".config/lme-shell/settings.json").write_text('{"wallpaper": "", "theme": "dark"}\n')
    (home / ".config/niri/config.kdl").write_text("input {\n}\n")
    git = ["git", "-C", str(deployed)]
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    subprocess.run(git + ["init", "-q"], env=env, check=True)
    subprocess.run(git + ["-c", "user.name=drill", "-c", "user.email=drill@localhost", "add", "-A"], env=env, check=True)
    subprocess.run(git + ["-c", "user.name=drill", "-c", "user.email=drill@localhost", "commit", "-qm", "drill"], env=env, check=True)
    world = {"root": root, "home": home, "deployed": deployed, "tree": tree, "qs": qs,
             "state": home / ".cache/lme-perf/rv2/state/main", "fake": home / ".fake",
             "idle": home / ".cache/lme-perf/rv2/idle"}
    world["env"] = {"HOME": str(home), "PATH": f"{home}/bin:/usr/bin:/bin", "TERM": "dumb"}
    return world


def sh(world, args, timeout=120, extra_env=None):
    env = dict(world["env"])
    env.update(extra_env or {})
    proc = subprocess.run([str(a) for a in args], env=env, text=True, capture_output=True, timeout=timeout)
    print("  $ " + " ".join(str(a) for a in args[-5:]) + f"  -> rc={proc.returncode}")
    for line in (proc.stdout + proc.stderr).splitlines():
        print("      " + line[:220])
    return proc


def standin(world, *args, timeout=120, extra_env=None):
    return sh(world, ["python3", STANDIN, *args], timeout, extra_env)


def start_deployed(world):
    before = set(pids(world, "main.pids"))
    sh(world, [world["home"] / "bin/niri", "msg", "action", "spawn", "--", world["home"] / ".local/bin/lme-shell", "start"])
    wait(lambda: [p for p in pids(world, "main.pids") if p not in before], 10)
    return [p for p in pids(world, "main.pids") if p not in before]


def wait(predicate, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.2)
    return None


def pids(world, name):
    try:
        return [int(p) for p in (world["fake"] / name).read_text().split()]
    except OSError:
        return []


def alive(pids_list):
    return [p for p in pids_list if Path(f"/proc/{p}").exists()]


def live_main(world):
    return alive(pids(world, "main.pids"))


def link_target(world):
    return Path(os.path.realpath(world["home"] / ".config/quickshell/lme-shell"))


def idle(world, quiet=3.5, timeout=3):
    """The long watcher reports IDLE, so the seat has been quiet for `quiet` seconds (its own
    `timeout` of silence before the IDLE line, recorded in the header like idlegate.py does)."""
    with open(world["idle"] / "long.log", "a") as handle:
        handle.write(f"# timeout={timeout} started=0\n{time.time() - (quiet - timeout):.3f} I\n")


def busy(world):
    """The owner touched the seat half a second ago: a RESUME follows the last IDLE."""
    with open(world["idle"] / "long.log", "a") as handle:
        handle.write(f"# timeout=3 started=0\n{time.time() - 10:.3f} I\n{time.time() - 0.5:.3f} R\n")


def timers(world):
    return sorted(p.name for p in (world["fake"] / "units").glob("*") if p.name.startswith("lme-perf-restore"))


def kill_fakes():
    """Fake shells of earlier cases must never be seen by the next one (they share /proc)."""
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if MARK in cmd and "quickshell" in cmd and (" -c lme-shell " in cmd or "settings.qml" in cmd):
            try:
                os.kill(int(entry.name), 9)
            except OSError:
                pass
    time.sleep(0.3)


# ---- cases ----------------------------------------------------------------------


def case_gate(w):
    check("sandbox clean: no fake shell before the case", not mains(), str(mains()))
    d = start_deployed(w)
    flags = ["swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "120"]
    proc = standin(w, *flags)
    check("no watcher record: swap refused", proc.returncode == 1 and "not been quiet" in proc.stderr, proc.stderr[-200:])
    busy(w)
    proc = standin(w, *flags)
    check("owner active: swap refused", proc.returncode == 1 and "not been quiet" in proc.stderr, proc.stderr[-200:])
    idle(w, quiet=1.2, timeout=1)
    proc = standin(w, *flags)
    check("1.2s quiet, 3s asked: refused (the header timeout is honoured)",
          proc.returncode == 1 and "not been quiet" in proc.stderr, proc.stderr[-200:])
    idle(w, quiet=3.5, timeout=3)
    proc = standin(w, *flags, "--quiet-seconds", "10")
    check("3.5s quiet, 10s asked: refused", proc.returncode == 1 and "not been quiet" in proc.stderr, proc.stderr[-200:])
    check("refused swaps: nothing touched", live_main(w) == d and link_target(w) == w["deployed"] and not timers(w))
    proc = standin(w, *flags)
    check("3.5s quiet, 3s asked: swap goes through", proc.returncode == 0, proc.stderr[-300:])
    check("quiet gate recorded", "quiet gate" in (w["state"] / "events.log").read_text())
    s = live_main(w)
    proc = standin(w, "restore", "--state", w["state"])
    check("after the gate case: restored", proc.returncode == 0 and len(live_main(w)) == 1
          and not alive(s) and not alive(d) and link_target(w) == w["deployed"])


def case_nogate(w):
    start_deployed(w)
    busy(w)
    proc = standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "120", "--no-quiet-gate")
    check("no gate: swap goes through while the owner is active", proc.returncode == 0, proc.stderr[-300:])
    s = live_main(w)
    proc = standin(w, "restore", "--state", w["state"])
    verify = json.loads((w["state"] / "verify.json").read_text())
    check("no gate: restored", proc.returncode == 0 and verify["ok"] and not alive(s))


def case_dry(w):
    d = start_deployed(w)
    idle(w)
    proc = standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "60", "--dry-run")
    check("dry run: rc 0", proc.returncode == 0, proc.stderr[-200:])
    check("dry run: deployed shell untouched", live_main(w) == d)
    check("dry run: symlink untouched", link_target(w) == w["deployed"])
    check("dry run: no timer armed", not timers(w))
    check("dry run: snapshot taken", (w["state"] / "snap/.config/lme-shell/settings.json").is_file())


def case_normal(w):
    d = start_deployed(w)
    idle(w)
    proc = standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "120")
    check("swap: rc 0", proc.returncode == 0, proc.stderr[-300:])
    s = live_main(w)
    check("swap: deployed shell stopped", not alive(d))
    check("swap: stand-in running (one main)", len(s) == 1 and not set(s) & set(d), str(s))
    check("swap: symlink -> tree", link_target(w) == w["tree"])
    check("swap: dead-man timer armed", len(timers(w)) == 1, str(timers(w)))
    check("swap: stand-in log in state dir", (w["state"] / "log/lme-shell.log").is_file())
    status = standin(w, "status", "--state", w["state"])
    report = json.loads(status.stdout)
    check("status: swapped, not restored, timer active", report["swapped"] and not report["restored"] and report["timer_active"] == "active")
    (w["home"] / ".config/lme-shell/settings.json").write_text('{"wallpaper": "", "theme": "light"}\n')
    (w["deployed"] / "leftover.txt").write_text("written into the deployed clone during the run\n")
    proc = standin(w, "restore", "--state", w["state"])
    verify = json.loads((w["state"] / "verify.json").read_text())
    check("restore: rc 1 reports the dirty deployed clone (honest)", proc.returncode == 1 and verify["git_status_same"] is False)
    check("restore: stand-in stopped", not alive(s))
    d2 = live_main(w)
    check("restore: deployed shell running again", len(d2) == 1 and not set(d2) & set(s), str(d2))
    check("restore: symlink -> original", link_target(w) == w["deployed"] and verify["symlink_ok"])
    check("restore: settings.json back to the snapshot", (w["home"] / ".config/lme-shell/settings.json").read_text() == (w["state"] / "snap/.config/lme-shell/settings.json").read_text())
    check("restore: live version kept under after/", (w["state"] / "after/.config/lme-shell/settings.json").read_text() == '{"wallpaper": "", "theme": "light"}\n')
    check("restore: no config file differs", verify["config_files_differing"] == [])
    check("restore: bar layer, head same", verify["bar_layer"] and verify["git_head_same"] and verify["standin_left"] == [])
    check("restore: marker written", (w["state"] / "restored").exists())
    stopped = (w["fake"] / "systemctl.log").read_text()
    check("restore: timer stopped", any("stop" in line and line.rstrip().endswith(".timer") for line in stopped.splitlines()))
    (w["deployed"] / "leftover.txt").unlink()
    again = standin(w, "restore", "--state", w["state"])
    check("restore twice: idempotent, ok once the clone is clean", again.returncode == 0 and "already done" in again.stdout)


def case_deadman(w):
    d = start_deployed(w)
    idle(w)
    proc = standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "30")
    check("dead-man: swap rc 0", proc.returncode == 0, proc.stderr[-300:])
    s = live_main(w)
    check("dead-man: restored marker within 45 s without any caller", wait(lambda: (w["state"] / "restored").exists(), 45))
    check("dead-man: stand-in stopped", not alive(s))
    check("dead-man: deployed shell running again", len(live_main(w)) == 1 and not alive(d))
    check("dead-man: symlink -> original", link_target(w) == w["deployed"])


def case_foreign(w):
    d = start_deployed(w)
    idle(w)
    (w["fake"] / "foreign-on-spawn").touch()
    proc = standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "120")
    check("foreign input: swap fails", proc.returncode != 0 and "the owner is back" in proc.stderr, proc.stderr[-300:])
    check("foreign input: stand-in gone", len(live_main(w)) <= 1)
    check("foreign input: deployed shell running again", len(live_main(w)) == 1 and not alive(d))
    check("foreign input: symlink -> original", link_target(w) == w["deployed"])
    check("foreign input: restored marker", (w["state"] / "restored").exists())


def case_locked(w):
    d = start_deployed(w)
    idle(w)
    standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "120")
    s = live_main(w)
    (w["fake"] / "locked").touch()
    proc = standin(w, "restore", "--state", w["state"])
    check("locked: restore deferred (rc 1, says so)", proc.returncode == 1 and "deferred" in proc.stderr, proc.stderr[-300:])
    check("locked: the locked shell is left running", live_main(w) == s)
    check("locked: symlink already back", link_target(w) == w["deployed"])
    check("locked: no deployed shell started next to it", len(live_main(w)) == 1)
    check("locked: no restored marker", not (w["state"] / "restored").exists())
    retry = [t for t in timers(w) if "retry" in t]
    check("locked: retry timer armed", len(retry) == 1, str(timers(w)))
    (w["fake"] / "locked").unlink()
    (w["fake"] / "units" / retry[0]).unlink(missing_ok=True)
    proc = sh(w, ["/bin/bash", w["state"] / "restore_shell.sh", w["state"]])
    check("locked then unlocked: the retry finishes the job", proc.returncode == 0 and not alive(s) and len(live_main(w)) == 1 and (w["state"] / "restored").exists())


def case_frozen(w):
    d = start_deployed(w)
    idle(w)
    standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "120")
    s = live_main(w)
    (w["fake"] / "locked").touch()
    silent = {"FAKE_IPC_SILENT": "1"}
    proc = standin(w, "restore", "--state", w["state"], extra_env=silent, timeout=150)
    check("frozen: no answer -> deferred, shell not killed", proc.returncode == 1 and "no answer" in proc.stdout and live_main(w) == s, proc.stdout[-300:])
    check("frozen: retry timer armed", any("retry" in t for t in timers(w)), str(timers(w)))
    proc = standin(w, "restore", "--state", w["state"], "--force", extra_env=silent, timeout=150)
    verify = json.loads((w["state"] / "verify.json").read_text())
    check("frozen: --force stops it and restores", proc.returncode == 0 and verify["ok"] and not alive(s), json.dumps(verify))


def case_unfinished(w):
    d = start_deployed(w)
    idle(w)
    other = w["home"] / ".cache/lme-perf/rv2/state/other"
    other.mkdir()
    (other / "swapped").touch()
    proc = standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "120")
    check("unfinished swap elsewhere: refused", proc.returncode == 1 and "unfinished swap" in proc.stderr, proc.stderr[-300:])
    check("unfinished swap elsewhere: nothing touched", live_main(w) == d and link_target(w) == w["deployed"] and not timers(w))


def case_extend(w):
    d = start_deployed(w)
    idle(w)
    standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "30")
    first = timers(w)
    proc = standin(w, "extend", "--state", w["state"], "--max-seconds", "45")
    second = timers(w)
    check("extend: rc 0 and a new timer unit", proc.returncode == 0 and len(second) == 1 and second != first, str((first, second)))
    check("extend: the stand-in survives", len(live_main(w)) == 1 and not alive(d))
    check("extend: old timer stopped", any("stop" in line and first[0] in line for line in (w["fake"] / "systemctl.log").read_text().splitlines()))
    standin(w, "restore", "--state", w["state"])


def case_failstart(w):
    d = start_deployed(w)
    idle(w)
    proc = standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "120", "--env", "FAKE_FAIL_START=1")
    check("start failure: swap fails at once", proc.returncode != 0 and "exited during startup" in proc.stdout, proc.stdout[-300:])
    check("start failure: deployed shell running again", len(live_main(w)) == 1 and not alive(d))
    check("start failure: symlink -> original", link_target(w) == w["deployed"])
    check("start failure: restored marker", (w["state"] / "restored").exists())


def case_dupfail(w):
    """The deployed shell does not come up at the restore: the job must not be marked done."""
    start_deployed(w)
    idle(w)
    standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "120")
    proc = standin(w, "restore", "--state", w["state"], extra_env={"FAKE_FAIL_START": "1"})
    check("deployed start failure: rc 1", proc.returncode == 1 and "not up" in proc.stdout, proc.stdout[-300:])
    check("deployed start failure: not marked restored", not (w["state"] / "restored").exists())
    check("deployed start failure: symlink already back", link_target(w) == w["deployed"])
    check("deployed start failure: retry timer armed", any("retry" in t for t in timers(w)), str(timers(w)))
    check("deployed start failure: attempt counted", (w["state"] / "retries").read_text().strip() == "1")
    proc = sh(w, ["/bin/bash", w["state"] / "restore_shell.sh", w["state"]])
    check("deployed start failure: the retry starts it and finishes", proc.returncode == 0 and len(live_main(w)) == 1 and (w["state"] / "restored").exists())


def case_pidclass(w):
    """A deployed shell started by an earlier run is young too: it must never be mistaken for the stand-in."""
    start_deployed(w)
    idle(w)
    standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "120")
    s = live_main(w)
    check("pid class: stand-in pid recorded", (w["state"] / "standin.pid").read_text().strip() == str(s[0]))
    for pid in s:
        os.kill(pid, 15)
    wait(lambda: not alive(s), 10)
    d = start_deployed(w)  # as an earlier, interrupted run of restore_shell.sh would have
    proc = sh(w, ["/bin/bash", w["state"] / "restore_shell.sh", w["state"]])
    check("pid class: the young deployed shell survives the retry", proc.returncode == 0 and live_main(w) == d and (w["state"] / "restored").exists(), proc.stdout[-400:])
    check("pid class: logged as deployed, not as stand-in", "stand-in=none" in proc.stdout and f"deployed shells={d[0]}" in proc.stdout)


def case_ageclass(w):
    """Without a recorded pid the start time against the swap marker decides (old state dirs)."""
    start_deployed(w)
    idle(w)
    standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "120")
    s = live_main(w)
    (w["state"] / "standin.pid").unlink()
    proc = standin(w, "restore", "--state", w["state"])
    check("age class: stand-in stopped by age", proc.returncode == 0 and not alive(s) and len(live_main(w)) == 1 and link_target(w) == w["deployed"])


def case_nodeployed(w):
    idle(w)
    proc = standin(w, "swap", "--tree", w["tree"], "--state", w["state"], "--max-seconds", "120")
    check("no deployed shell: swap rc 0 (nothing to lock)", proc.returncode == 0, proc.stderr[-300:])
    s = live_main(w)
    proc = standin(w, "restore", "--state", w["state"])
    verify = json.loads((w["state"] / "verify.json").read_text())
    check("no deployed shell: restore starts it", proc.returncode == 0 and verify["ok"] and len(live_main(w)) == 1 and not alive(s), json.dumps(verify))


CASES = {"gate": case_gate, "nogate": case_nogate, "dry": case_dry, "normal": case_normal,
         "deadman": case_deadman, "foreign": case_foreign,
         "locked": case_locked, "frozen": case_frozen, "unfinished": case_unfinished, "extend": case_extend,
         "failstart": case_failstart, "dupfail": case_dupfail, "pidclass": case_pidclass,
         "ageclass": case_ageclass, "nodeployed": case_nodeployed}


def main() -> int:
    global DRILL, MARK
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=[], help="run just these cases")
    ap.add_argument("--work", type=Path, default=DRILL, help="where the fake worlds are built")
    args = ap.parse_args()
    DRILL = args.work.resolve()
    MARK = str(DRILL) + "/"
    DRILL.mkdir(parents=True, exist_ok=True)
    subprocess.run(["gcc", "-O1", "-Wall", "-o", str(DRILL / "fakeshell"), str(FAKESHELL_C)], check=True)
    unknown = [name for name in args.only if name not in CASES]
    if unknown:
        ap.error(f"unknown case(s) {unknown}; known: {sorted(CASES)}")
    for name in args.only or CASES:
        print(f"== {name}")
        kill_fakes()
        try:
            CASES[name](build(name))
        except Exception as error:  # a crashed case is a failed case, the rest still runs
            check(f"{name}: case crashed", False, repr(error))
    kill_fakes()
    print(f"sanity: fake shells left after the drill: {mains()}")
    failed = [name for name, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed" + (f"; FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
