#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run an instrumented shell in place of the deployed one (a stand-in), then put everything back.

  standin.py swap    --tree DIR --state DIR [--max-seconds S] [--quiet-seconds S] [--env KEY=VALUE ...]
                               [--no-quiet-gate] [--no-notice] [--dry-run]
  standin.py extend  --state DIR --max-seconds S
  standin.py status  --state DIR
  standin.py restore --state DIR

Why a stand-in: a second Quickshell instance cannot share the owner's session (one `lme-shell`
config, layer namespaces, IPC names), so the measured shell has to BE the session's shell.
swap therefore stops the deployed shell, points `~/.config/quickshell/lme-shell` at an
instrumented tree prepared by prepare.py and starts that tree through the deployed launcher
logic, in the real session (same HOME, settings, niri keybinds, GPU). restore_shell.sh undoes
it; swap arms it as a systemd user timer before touching anything, so the owner's shell comes
back even when this process dies.

Guarantees:
  - the deployed clone is never written to; only the symlink and the wrapper in the state dir change
  - the launcher's start.sh is reused verbatim except for two lines (repo_dir, log_dir), so
    the stand-in gets the same pre-steps and environment but logs into the state dir
  - config files are snapshotted before the swap and compared again after the restore
  - only Quickshell main/Settings processes of this config are ever stopped; `quickshell ...
    ipc call` clients and anything else are left alone
  - the seat must have been quiet for --quiet-seconds (idlegate.py watch has to run), the
    owner is told by a desktop notification just before the swap, and input that arrives
    while the stand-in starts restores the deployed shell at once
Nothing here injects input; scenarios do that through inject.py.
"""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import idlegate  # noqa: E402  (sibling module of the harness)

HOME = Path.home()
LINK = HOME / ".config/quickshell/lme-shell"
QS = HOME / ".local/share/lme-shell/deployment/bin/quickshell"
LAUNCHER = HOME / ".local/bin/lme-shell"
STATE_ROOT = HOME / ".cache/lme-perf/rv2/state"
SNAPSHOT_DIRS = [(".config/lme-shell", (".json", ".kdl")), (".config/niri", (".kdl",))]
SNAPSHOT_FILES = [".local/bin/lme-shell"]
SESSION_KEYS = ("XDG_RUNTIME_DIR", "WAYLAND_DISPLAY", "NIRI_SOCKET", "DBUS_SESSION_BUS_ADDRESS")
MAX_SECONDS = 1200
QUIET_SECONDS = 3  # the owner waived the long idle wait: a few quiet seconds are the gate
NOTICE_APP = "LME perf harness"
NOTICE_MS = "12000"
START_REPO_LINE = 'repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"\n'
START_LOG_LINE = 'log_dir="${XDG_STATE_HOME:-$HOME/.local/state}/lme-shell/log"\n'


class Fail(Exception):
    pass


def log(state: Path, message: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {int(time.time() * 1000) % 1000:03d} standin: {message}"
    with open(state / "events.log", "a") as handle:
        handle.write(line + "\n")
    print(line, flush=True)


def sh(args, env=None, timeout=30, check=False):
    """A tool call that never throws: a timeout is rc 124 ("no answer"), a missing tool rc 127."""
    args = [str(a) for a in args]
    try:
        result = subprocess.run(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        result = subprocess.CompletedProcess(args, 124, "", f"no answer within {timeout}s")
    except OSError as error:
        result = subprocess.CompletedProcess(args, 127, "", f"{error}")
    if check and result.returncode != 0:
        raise Fail(f"{' '.join(args[:5])} failed rc={result.returncode}: {result.stderr.strip()[:300]}")
    return result


def session_env() -> dict:
    """The compositor session's environment, from the user manager (never from another process),
    on top of this process's own PATH. Only the session keys are ever handed to a shell: the
    stand-in wrapper exports them explicitly, nothing else leaks from the harness into it."""
    result = sh(["systemctl", "--user", "show-environment"], check=True)
    session = {k: v for k, v in (line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)}
    missing = [key for key in SESSION_KEYS if key not in session]
    if missing:
        raise Fail(f"session environment lacks {missing}; run inside the owner's user session")
    env = dict(os.environ)
    env.update(session)
    return env


def unit_of(pid: int) -> str:
    try:
        cgroup = Path(f"/proc/{pid}/cgroup").read_text()
    except OSError:
        return ""
    return cgroup.strip().rsplit("/", 1)[-1]


def shells(tree: str = "") -> list:
    """Quickshell main and Settings processes of this config. `ipc call` clients are skipped:
    they share the command line prefix and must never be mistaken for a shell."""
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
            started = (entry / "stat").stat().st_mtime
        except OSError:
            continue
        argv = [part.decode(errors="replace") for part in argv if part]
        if not argv or not argv[0].endswith("quickshell") or "ipc" in argv:
            continue
        main = "-c" in argv and argv[argv.index("-c") + 1:argv.index("-c") + 2] == ["lme-shell"]
        settings = any(part.endswith("settings.qml") and ("lme-shell" in part or (tree and part.startswith(tree + "/")))
                       for part in argv)
        if not (main or settings):
            continue
        found.append({"pid": int(entry.name), "kind": "main" if main else "settings", "started": started,
                      "unit": unit_of(int(entry.name)), "cmd": " ".join(argv)})
    return sorted(found, key=lambda item: item["started"])


def layers(env: dict) -> list:
    result = sh(["niri", "msg", "--json", "layers"], env=env, check=True)
    return json.loads(result.stdout)


def lock_status(env: dict, qs: Path) -> str:
    result = sh([qs, "-c", "lme-shell", "ipc", "call", "lock", "status"], env=env, timeout=15)
    return (result.stdout.strip().splitlines() or [""])[-1]


def stop_shells(entries: list, log_fn) -> None:
    """Stop whole units (a shell and the backend/watchers it started), signal the rare shell that
    has no unit of its own, then make sure they are all gone."""
    units = sorted({entry["unit"] for entry in entries if entry["unit"].endswith((".scope", ".service"))})
    direct = [entry["pid"] for entry in entries if not entry["unit"].endswith((".scope", ".service"))]
    for unit in units:
        log_fn(f"systemctl --user stop {unit}")
        sh(["systemctl", "--user", "stop", "--no-block", unit])
    for pid in direct:
        log_fn(f"SIGTERM {pid}")
        try:
            os.kill(pid, 15)
        except OSError:
            pass
    pids = [entry["pid"] for entry in entries]
    deadline = time.time() + 20
    while time.time() < deadline and any(Path(f"/proc/{pid}").exists() for pid in pids):
        time.sleep(0.25)
    for pid in pids:
        if Path(f"/proc/{pid}").exists():
            log_fn(f"SIGKILL {pid}")
            try:
                os.kill(pid, 9)
            except OSError:
                pass
    time.sleep(0.3)
    if any(Path(f"/proc/{pid}").exists() for pid in pids):
        raise Fail(f"processes {pids} survived the stop")


def snapshot(state: Path) -> list:
    files = []
    for folder, suffixes in SNAPSHOT_DIRS:
        base = HOME / folder
        if base.is_dir():
            files += sorted(str(path.relative_to(HOME)) for path in base.iterdir()
                            if path.is_file() and path.suffix in suffixes)
    files += [name for name in SNAPSHOT_FILES if (HOME / name).is_file()]
    for rel in files:
        target = state / "snap" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HOME / rel, target)
    (state / "files").write_text("\n".join(files) + "\n")
    return files


def config_diff(state: Path) -> dict:
    """Files that differ from the snapshot, by kind, so a restore can be reported honestly."""
    report = {}
    for rel in (state / "files").read_text().split():
        live, snap = HOME / rel, state / "snap" / rel
        if not live.exists():
            report[rel] = "missing"
        elif not snap.exists():
            report[rel] = "new"
        elif live.read_bytes() != snap.read_bytes():
            report[rel] = "changed"
    return report


def write_env(state: Path, values: dict) -> None:
    (state / "env").write_text("".join(f"{key}={value}\n" for key, value in values.items() if "\n" not in str(value)))


def read_env(state: Path) -> dict:
    values = {}
    for line in (state / "env").read_text().splitlines():
        key, _, value = line.partition("=")
        values[key] = value
    return values


def arm_timer(state: Path, seconds: int) -> str:
    unit = f"lme-perf-restore-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid() % 1000}"
    result = sh(["systemd-run", "--user", f"--on-active={seconds}", f"--unit={unit}", "--timer-property=AccuracySec=1s",
                 "/bin/bash", str(state / "restore_shell.sh"), str(state)], check=True)
    if f"{unit}.timer" not in result.stdout:
        raise Fail(f"systemd-run did not confirm the dead-man timer: {result.stdout.strip()}")
    return unit


def disarm_timer(unit: str) -> None:
    if unit:
        sh(["systemctl", "--user", "stop", unit + ".timer"])


def quiet_gate(seconds: int, skip: bool) -> dict:
    """The seat has been quiet for `seconds` (long watcher of idlegate.py), or no swap."""
    if skip:
        return {"gate": "skipped"}
    since = idlegate.is_quiet(idlegate.DEFAULT_DIR / "long.log", seconds, time.time())
    if since is None:
        raise Fail(f"the owner has not been quiet for {seconds}s; run `idlegate.py watch` and "
                   f"`idlegate.py wait --seconds {seconds}` first")
    return {"gate": "quiet", "since": round(since, 3)}


def notify(env: dict, text: str) -> None:
    """One desktop notification for the owner (the shell runs the notification daemon; with
    none running nothing is shown and nothing fails)."""
    tool = shutil.which("notify-send")
    if tool:
        sh([tool, "-a", NOTICE_APP, "-t", NOTICE_MS, NOTICE_APP, text], env=env, timeout=10)


def unfinished_swaps(current: Path) -> list:
    """Other state dirs whose swap was never restored: a stand-in of theirs may still be running."""
    if not STATE_ROOT.is_dir():
        return []
    return sorted(str(path.name) for path in STATE_ROOT.iterdir() if path.is_dir() and path != current
                  and (path / "swapped").exists() and not (path / "restored").exists())


def make_launcher(state: Path, original: Path, tree: Path, extra_env: dict) -> Path:
    """start.sh of the deployed clone, pointed at the probe tree (so its scripts and its QML
    match) with the log directory moved into the state dir."""
    source = (original / "scripts/start.sh").read_text()
    for anchor in (START_REPO_LINE, START_LOG_LINE):
        if source.count(anchor) != 1:
            raise Fail("scripts/start.sh changed: the stand-in launcher anchors no longer match")
    source = source.replace(START_REPO_LINE, f'repo_dir="{tree}"\n')
    source = source.replace(START_LOG_LINE, f'log_dir="{state}/log"\n')
    (state / "start.sh").write_text(source)
    (state / "log").mkdir(exist_ok=True)
    lines = ["#!/usr/bin/env bash",
             "# Generated by scripts/perf/standin.py: the deployed launcher path, logs in the state dir.",
             "set -euo pipefail",
             '# The pid survives the exec chain (wrapper -> start.sh -> Quickshell): it is how the',
             '# harness tells the stand-in from the deployed shell after the restore.',
             f'echo $$ > "{state}/standin.pid"',
             'export PATH="${HOME}/.local/bin:${PATH}"',
             f"export LME_QS_BINARY={QS}"]
    lines += [f"export {key}={shlex.quote(str(value))}" for key, value in extra_env.items()]
    lines += [f'exec bash "{state}/start.sh" --no-duplicate']
    wrapper = state / "lme-perf-standin"
    wrapper.write_text("\n".join(lines) + "\n")
    wrapper.chmod(0o755)
    return wrapper


def swap_link(target: Path) -> None:
    tmp = LINK.with_name(f"{LINK.name}.perf.{os.getpid()}")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(target)
    os.replace(tmp, LINK)


def standin_pid(state: Path) -> int:
    try:
        return int((state / "standin.pid").read_text())
    except (OSError, ValueError):
        return 0


def wait_ready(state: Path, env: dict, tree: str) -> dict:
    """Bar layer mapped and the probe answering; gives up after 60 s or when the stand-in dies."""
    started = time.time()
    pid = 0
    while time.time() - started < 60:
        pid = pid or standin_pid(state)
        if pid and not Path(f"/proc/{pid}").exists():
            raise Fail(f"stand-in {pid} exited during startup (see {state}/log)")
        live = [entry for entry in shells(tree) if entry["pid"] == pid and entry["kind"] == "main"]
        if live and any(layer.get("namespace") == "lme-bar" for layer in layers(env)):
            ping = sh([QS, "-c", "lme-shell", "ipc", "call", "probe", "ping"], env=env, timeout=15)
            if ping.returncode == 0 and ping.stdout.strip():
                state.joinpath("standin.json").write_text(json.dumps(live, indent=1))
                return {"seconds": round(time.time() - started, 2), "pids": [entry["pid"] for entry in live],
                        "units": sorted({entry["unit"] for entry in live})}
        time.sleep(0.25)
    raise Fail("stand-in did not become ready within 60 s")


def swap(args) -> int:
    state, tree = args.state.resolve(), args.tree.resolve()
    env = session_env()
    if not QS.is_file():
        raise Fail(f"{QS} (the deployed Quickshell) is missing")
    state.mkdir(parents=True, exist_ok=True)
    if (state / "swapped").exists() and not (state / "restored").exists():
        raise Fail(f"{state} holds an unfinished swap: run restore first")
    if not (tree / ".perf-probe.json").is_file() or not (tree / "qml/services/Probe.qml").is_file():
        raise Fail(f"{tree} is not a probe tree (prepare.py --out ...)")
    if not LINK.is_symlink():
        raise Fail(f"{LINK} is not a symlink; refusing to guess")
    original = Path(os.path.realpath(LINK))
    if original == tree:
        raise Fail("the symlink already points at the probe tree")
    if not (original / "scripts/start.sh").is_file():
        raise Fail(f"{original} has no scripts/start.sh")
    if not 30 <= args.max_seconds <= MAX_SECONDS:
        raise Fail(f"--max-seconds must be within 30..{MAX_SECONDS}")
    extra = dict(item.split("=", 1) for item in args.env)
    for key in extra:
        if key in SESSION_KEYS or key in ("HOME", "PATH", "LME_QS_BINARY", "XDG_STATE_HOME", "XDG_CONFIG_HOME"):
            raise Fail(f"refusing to override {key}")
    before = shells(str(tree))
    info = {"tree": str(tree), "original": str(original), "deployed": before, "extra_env": extra,
            "git_head": sh(["git", "-C", original, "rev-parse", "HEAD"]).stdout.strip(),
            "git_status": sh(["git", "-C", original, "status", "--porcelain"]).stdout}
    log(state, f"swap tree={tree.name} original={original} max={args.max_seconds}s dry={args.dry_run}")
    log(state, "deployed shells: " + ", ".join(f"{e['pid']} {e['kind']} [{e['unit']}]" for e in before))
    if args.dry_run:
        files = snapshot(state)
        log(state, f"dry run: would snapshot {len(files)} files, arm a {args.max_seconds}s dead-man timer, "
                   f"stop {[e['pid'] for e in before]}, point {LINK.name} at the tree and start the stand-in")
        return 0

    others = unfinished_swaps(state)
    if others:
        raise Fail(f"unfinished swap(s) {others}: restore them first, a stand-in of theirs may be running")
    info["quiet"] = quiet_gate(args.quiet_seconds, args.no_quiet_gate)
    log(state, f"quiet gate: {info['quiet']}")
    if any(entry["kind"] == "main" for entry in before) and lock_status(env, QS) != "unlocked":
        raise Fail("the lock screen is active (or its state is unknown); not touching the session")
    if not args.no_notice:
        notify(env, f"Measuring the shell for up to {args.max_seconds}s; it comes back by itself. "
                    "Keyboard or mouse input hands it back at once.")

    for stale in ("restored", "swapped", "standin.pid", "standin.json"):
        (state / stale).unlink(missing_ok=True)
    shutil.copy2(HERE / "restore_shell.sh", state / "restore_shell.sh")
    info["snapshot"] = snapshot(state)
    log(state, f"snapshot of {len(info['snapshot'])} config files")
    niri = shutil.which("niri")
    if not niri:
        raise Fail("niri is not in PATH")
    values = {"LINK": LINK, "ORIGINAL": original, "TREE": tree, "QS": QS, "NIRI": niri,
              "START": f"{LAUNCHER} start", "TIMER": "", **{key: env[key] for key in SESSION_KEYS}}
    write_env(state, values)
    info["timer"] = arm_timer(state, args.max_seconds)
    values["TIMER"] = info["timer"]
    write_env(state, values)
    (state / "swap.json").write_text(json.dumps(info, indent=1))
    log(state, f"dead-man timer {info['timer']} armed for {args.max_seconds}s")
    touched = time.time()
    try:
        if before:
            stop_shells(before, lambda message: log(state, message))
        swap_link(tree)
        (state / "swapped").touch()
        log(state, f"symlink -> {tree}")
        wrapper = make_launcher(state, original, tree, extra)
        sh(["niri", "msg", "action", "spawn", "--", str(wrapper)], env=env, check=True)
        ready = wait_ready(state, env, str(tree))
        foreign = idlegate.foreign_resume(idlegate.DEFAULT_DIR / "short.log", touched, [])
        if foreign:
            raise Fail(f"input arrived at {foreign:.3f} while the stand-in was starting; the owner is back")
    except BaseException as error:
        log(state, f"swap failed: {error!r}; restoring now")
        restore_state(state, env)
        raise
    log(state, f"stand-in ready: {ready}")
    if not args.no_notice:
        notify(env, f"Instrumented shell running (up in {ready['seconds']}s). "
                    f"The normal shell is back in at most {args.max_seconds}s.")
    return 0


def verify(state: Path, env: dict) -> dict:
    info = json.loads((state / "swap.json").read_text()) if (state / "swap.json").exists() else {}
    original = info.get("original", "")
    differing = config_diff(state) if (state / "files").exists() else {}
    live_shells = shells(info.get("tree", ""))
    summary = {
        "symlink": os.path.realpath(LINK) if LINK.is_symlink() else "NOT A SYMLINK",
        "symlink_ok": original == "" or os.path.realpath(LINK) == original,
        "config_files_differing": sorted(differing),
        "shells": [{"pid": entry["pid"], "kind": entry["kind"], "unit": entry["unit"]} for entry in live_shells],
        "shell_running": any(entry["kind"] == "main" for entry in live_shells),
        "bar_layer": any(layer.get("namespace") == "lme-bar" for layer in layers(env)),
        "lock": lock_status(env, QS),
    }
    if original and (Path(original) / ".git").exists():
        summary["git_head_same"] = sh(["git", "-C", original, "rev-parse", "HEAD"]).stdout.strip() == info.get("git_head")
        summary["git_status_same"] = sh(["git", "-C", original, "status", "--porcelain"]).stdout == info.get("git_status")
    # The stand-in is known by its pid (the wrapper recorded it), never by its age: after the
    # restore the freshly started deployed shell is just as young.
    recorded = {standin_pid(state)} | {entry.get("pid") for entry in
                                      (json.loads((state / "standin.json").read_text()) if (state / "standin.json").exists() else [])}
    left = sorted(recorded & {entry["pid"] for entry in live_shells if entry["kind"] == "main"})
    summary["standin_left"] = left
    summary["ok"] = bool(summary["symlink_ok"] and not summary["config_files_differing"] and summary["shell_running"]
                         and summary["bar_layer"] and not left
                         and summary.get("git_head_same", True) and summary.get("git_status_same", True))
    (state / "verify.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


DEFERRED = 3  # restore_shell.sh: the harness shell may be locked, it will run again from a new timer


def restore_state(state: Path, env: dict, force: bool = False) -> dict:
    if not (state / "env").exists():
        (state / "restored").touch()
        return {}
    command = ["/bin/bash", str(state / "restore_shell.sh"), str(state)] + (["--force"] if force else [])
    # Not sh(): a timeout there would kill the script half way through putting the shell back.
    # Here it is left running (the armed timer would run it again, idempotently) and reported.
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, _ = process.communicate(timeout=150)
    except subprocess.TimeoutExpired:
        raise Fail("restore_shell.sh is still running after 150 s; it was left running") from None
    for line in out.splitlines():
        if line.strip():
            print(line, flush=True)
    if process.returncode == DEFERRED:
        raise Fail("restore deferred: the harness shell may be showing the lock screen; a timer retries in 60 s")
    if process.returncode != 0:
        raise Fail(f"restore_shell.sh exited {process.returncode}")
    time.sleep(1.5)
    return verify(state, env)


def restore(args) -> int:
    state = args.state.resolve()
    env = session_env()
    diff = config_diff(state) if (state / "files").exists() else {}
    log(state, f"restore force={args.force}; config files changed during the run: {diff or 'none'}")
    summary = restore_state(state, env, args.force)
    log(state, ("restored OK" if summary.get("ok") else "RESTORE INCOMPLETE") + " " + json.dumps(summary))
    return 0 if summary.get("ok") else 1


def status(args) -> int:
    state = args.state.resolve()
    env = session_env()
    values = read_env(state) if (state / "env").exists() else {}
    report = {
        "symlink": os.path.realpath(LINK) if LINK.is_symlink() else "NOT A SYMLINK",
        "shells": [{k: e[k] for k in ("pid", "kind", "unit")} for e in shells(values.get("TREE", ""))],
        "layers": [[layer.get("namespace"), layer.get("keyboard_interactivity")] for layer in layers(env)],
        "lock": lock_status(env, QS),
        "swapped": (state / "swapped").exists(), "restored": (state / "restored").exists(),
        "timer": values.get("TIMER", ""),
    }
    if report["timer"]:
        report["timer_active"] = sh(["systemctl", "--user", "is-active", report["timer"] + ".timer"]).stdout.strip()
    print(json.dumps(report, indent=1))
    return 0


def extend(args) -> int:
    state = args.state.resolve()
    if not (state / "swapped").exists() or (state / "restored").exists():
        raise Fail("no live swap to extend")
    if not 30 <= args.max_seconds <= MAX_SECONDS:
        raise Fail(f"--max-seconds must be within 30..{MAX_SECONDS}")
    values = read_env(state)
    disarm_timer(values.get("TIMER", ""))
    values["TIMER"] = arm_timer(state, args.max_seconds)
    write_env(state, values)
    log(state, f"dead-man timer re-armed as {values['TIMER']} for {args.max_seconds}s")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("swap", "extend", "status", "restore"):
        command = sub.add_parser(name)
        command.add_argument("--state", required=True, type=Path, help="session state dir (one per swap)")
        if name in ("swap", "extend"):
            command.add_argument("--max-seconds", type=int, default=600, help="dead-man timer, 30..1200 s")
        if name == "swap":
            command.add_argument("--tree", required=True, type=Path, help="probe tree from prepare.py")
            command.add_argument("--env", action="append", default=[], metavar="KEY=VALUE", help="exported into the stand-in")
            command.add_argument("--quiet-seconds", type=int, default=QUIET_SECONDS,
                                 help="quiet time required before the swap (needs idlegate.py watch)")
            command.add_argument("--no-quiet-gate", action="store_true",
                                 help="skip the quiet gate (disposable sessions only; there is then no foreign-input abort either)")
            command.add_argument("--no-notice", action="store_true", help="no desktop notification")
            command.add_argument("--dry-run", action="store_true", help="check and snapshot only")
        if name == "restore":
            command.add_argument("--force", action="store_true",
                                 help="stop the stand-in even if the lock state is unknown (only when no lock "
                                      "was requested during the run)")
    args = ap.parse_args()
    try:
        return {"swap": swap, "extend": extend, "status": status, "restore": restore}[args.command](args)
    except Fail as error:
        print(f"STANDIN FAILED: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
