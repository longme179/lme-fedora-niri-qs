#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a scratch copy of the shell tree with the perf probe applied.

  prepare.py --repo <clone> --ref <commit> --out <dir> [--diagnostics <commit>] [--force]

`git archive` exports <ref> into <dir>: no .git, so nothing there can be committed by
accident. When the tree lacks the heartbeat diagnostics and --diagnostics names the commit
that adds them, the files that commit touched are taken from it (a baseline is main +
diagnostics, so both sides of an A/B carry the same observer). probe_patch.py then applies
and verifies the probe. Running again with the same ref, diagnostics and probe reuses the
tree unless --force is set.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCHER = HERE / "probe_patch.py"
PROBE = HERE / "probe" / "Probe.qml"
DIAGNOSTIC_FILES = ("qml/services/Heartbeat.qml", "qml/components/PageHost.qml")


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        sys.exit(f"PREPARE FAILED (rc={result.returncode}): git {' '.join(args[:4])}\n{result.stderr}")
    return result.stdout


def has_diagnostics(tree: Path) -> bool:
    heartbeat, host = (tree / name for name in DIAGNOSTIC_FILES)
    return heartbeat.is_file() and host.is_file() and "Heartbeat" in (tree / "qml/services/qmldir").read_text()


def add_diagnostics(repo: Path, tmp: Path, commit: str, diagnostics: str) -> str:
    """Copy the diagnostics commit's versions of the files it touched into the scratch tree."""
    target = git(repo, "rev-parse", "--verify", diagnostics + "^{commit}").strip()
    parent = git(repo, "rev-parse", "--verify", target + "^").strip()
    paths = git(repo, "diff", "--name-only", parent, target, "--").split()
    if not paths:
        sys.exit(f"PREPARE FAILED: {diagnostics} changes no file")

    def blob(rev: str, name: str) -> str:
        """Blob id of `name` at `rev`, or "" when the path does not exist there."""
        result = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", rev + ":" + name],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        return result.stdout.strip() if result.returncode == 0 else ""

    # The versions are only valid on the commit's own parent; anything else is a silent clobber.
    for name in paths:
        if blob(parent, name) != blob(commit, name):
            sys.exit(f"PREPARE FAILED: {name} differs between {commit[:12]} and the diagnostics parent")
    git_dir = git(repo, "rev-parse", "--absolute-git-dir").strip()
    # A private index keeps the clone's own index untouched.
    env = dict(os.environ, GIT_INDEX_FILE=str(tmp / ".perf-index"))
    result = subprocess.run(["git", "--git-dir", git_dir, "--work-tree", str(tmp), "checkout", target, "--", *paths],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        sys.exit(f"PREPARE FAILED: cannot take the diagnostics files from {target[:12]}\n{result.stderr}")
    (tmp / ".perf-index").unlink(missing_ok=True)
    return target[:12]


def build(repo: Path, tmp: Path, commit: str, diagnostics: str) -> str:
    """Export `commit` into the empty directory `tmp` and instrument it. Returns the diagnostics note."""
    tmp.mkdir(parents=True)
    archive = subprocess.run(["git", "-C", str(repo), "archive", commit], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if archive.returncode != 0:
        sys.exit(f"PREPARE FAILED: git archive {commit}\n{archive.stderr.decode(errors='replace')}")
    subprocess.run(["tar", "-x", "-C", str(tmp)], input=archive.stdout, check=True)
    note = "already present"
    if not has_diagnostics(tmp):
        if not diagnostics:
            sys.exit("PREPARE FAILED: the tree has no heartbeat diagnostics and --diagnostics was not given")
        note = add_diagnostics(repo, tmp, commit, diagnostics)
        if not has_diagnostics(tmp):
            sys.exit("PREPARE FAILED: the diagnostics commit does not add the heartbeat files")
    for extra in ([], ["--check"]):
        result = subprocess.run([sys.executable, str(PATCHER), "--src", str(tmp), *extra])
        if result.returncode != 0:
            sys.exit("PREPARE FAILED: the probe patch did not apply cleanly (message above)")
    return note


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, type=Path, help="clone to export from (never modified)")
    ap.add_argument("--ref", required=True, help="commit, branch or tag to export")
    ap.add_argument("--out", required=True, type=Path, help="scratch tree to create")
    ap.add_argument("--diagnostics", default="", help="commit adding Heartbeat.qml, applied when the tree lacks it")
    ap.add_argument("--force", action="store_true", help="rebuild even when the tree is current")
    args = ap.parse_args()

    repo, out = args.repo.resolve(), args.out.resolve()
    commit = git(repo, "rev-parse", "--verify", args.ref + "^{commit}").strip()
    probe_sha = hashlib.sha256(PATCHER.read_bytes() + PROBE.read_bytes()).hexdigest()
    want = {"commit": commit, "diagnostics": args.diagnostics, "probe": probe_sha}
    marker = out / ".perf-tree.json"
    if marker.is_file() and json.loads(marker.read_text()) == want and not args.force:
        print(f"reused {out} ({commit[:12]})")
        return 0
    if out.exists():
        shutil.rmtree(out)
    tmp = out.with_name(out.name + f".tmp-{os.getpid()}")
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        note = build(repo, tmp, commit, args.diagnostics)
        tmp.rename(out)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    marker.write_text(json.dumps(want, indent=1) + "\n")
    print(f"prepared {out}\n  commit {commit}\n  diagnostics {note}\n  probe {probe_sha[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
