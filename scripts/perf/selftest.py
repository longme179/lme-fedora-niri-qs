#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Prove the detectors on the model: every fault of sim.py has to come out of analyze.py by name.

  selftest.py [--out DIR] [--only NAME,NAME]

The scenarios, run.py and analyze.py are run against sim.py once per case. The model behaves
like a healthy shell except for one fault at a time, and the report must name exactly that
fault: a harness that would miss a swallowed Escape or a ghosted page on the desktop is
worthless, and this is the only place where the answer is known in advance. What this does
not prove is anything about the real shell: the timings are the model's.

Cases (each is one simulated run under <out>/<name>):
  clean     warm-up, S4, S2, S3        no failure, no recovery, every criterion holds
  devices   S1, ordered, no fault      the model's own defect (the devices tab builds for 1.3 s on
                                       the GUI thread) is reported as one frozen rep
  swallow   s4:swallow@2               one island cycle `handled_no_close`
  unhandled s4:unhandled@2             one island cycle `unhandled`
  nofocus   s4:nofocus@9               one island cycle `no_keyboard_focus` (no Escape pressed there)
  late      s4:late@5,ms=400           one island cycle `late`
  frozen    s4:frozen@6,ms=1800        one island cycle `frozen`
  ghost     s2:ghost@2                 one burst whose page host is not opaque, receding, animating
  stall     s1:stall@5,ms=400          two freezes in the Control Center (the devices build and the fault)
"""
import argparse
import json
import shutil
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze  # noqa: E402  (sibling modules of the harness)
import run as runner  # noqa: E402

DEFAULT_OUT = Path.home() / ".cache/lme-perf/rv2/selftest"
MODEL_FEEDBACK_MS = 200.0     # the model's input -> first frame is far below the criterion


def classes_of(summary):
    """{route/delay: classes} of every S4 group, for the failure messages."""
    return {f"{group['route']}/{group['pre_esc_ms']}{' cold' if group['cold'] else ''}": group["classes"] for group in summary["s4"]}


def s4_only(summary, name):
    """All island cycles that ended in `name`: (route, delay, reps)."""
    return [(group["route"], group["pre_esc_ms"], group["reps"]) for group in summary["s4"] if group["classes"].get(name)]


def recoveries(summary):
    return [item for item in summary["problems"] if "recover" in item]


# ---- what each case must produce --------------------------------------------------------------------------

def expect_clean(summary, records):
    bad = []
    m = summary["metrics"]
    if m.get("s4.failures") != 0:
        bad.append(f"s4 failures {m.get('s4.failures')}: {classes_of(summary)}")
    for key, value in m.items():
        if key.startswith("s2.") and key.endswith(".failures") and value:
            bad.append(f"{key} = {value}")
    if m.get("s3.failures") != 0:
        bad.append(f"s3 failures {m.get('s3.failures')}: failed reps {summary['s3']['failed_reps']}")
    if recoveries(summary):
        bad.append(f"recoveries in a healthy model: {recoveries(summary)[:3]}")
    if summary["global"]["stalls"]["count"]:
        bad.append(f"GUI-thread stalls in a healthy model: {summary['global']['stalls']}")
    cycles = sum(group["n"] for group in summary["s4"])
    if cycles != 13 or len(summary["s2"]) != 3 or len(summary["s3"]["panels"]) < 8:
        bad.append(f"expected 13 island cycles (cold + 12), 3 Settings variants and 8 panels; got {cycles}, "
                   f"{len(summary['s2'])}, {len(summary['s3']['panels'])}")
    cold = [group for group in summary["s4"] if group["cold"]]
    if len(cold) != 1 or cold[0]["prior"] != "cold start" or cold[0]["n"] != 1:
        bad.append(f"the cold island cycle must be one group kept apart in the report: "
                   f"{[(group['prior'], group['n']) for group in cold]}")
    for name, value, ok in summary["criteria"]:
        if not ok:
            bad.append(f"criterion not met by the healthy model: {name} = {value}")
    if (m.get("global.input_to_frame_p95_ms") or 1e9) > MODEL_FEEDBACK_MS:
        bad.append(f"input to first frame p95 {m.get('global.input_to_frame_p95_ms')} ms in the model")
    if (m.get("global.input_to_frame_p95_ms") is None):
        bad.append("no input -> first frame value at all")
    if summary["run"]["truncated"]:
        bad.append(f"truncated: {summary['run']['truncated']}")
    if summary["global"]["minutes"] <= 0:
        bad.append(f"the measured window is empty: {summary['global']['minutes']} min")
    for rec in records:
        if rec["scenario"] == "s4" and rec["route"] != "ipc" and not rec.get("open_frame_ms"):
            bad.append(f"island cycle rep {rec['rep']} {rec['route']}/{rec['pre_esc_ms']}: no first frame")
    return bad


def expect_devices(summary, records):
    entry = next((item for item in summary["s1"] if item["variant"] == "ordered"), None)
    if entry is None:
        return ["no `ordered` entry for S1"]
    bad = []
    if entry["freeze_reps"] != 1 or entry["frozen"] != [0]:
        bad.append(f"expected rep 0 frozen by the devices build, got frozen={entry['frozen']}")
    if not 1000 <= entry["stalls"]["max"] <= 2000:
        bad.append(f"expected a stall of about 1300 ms, got {entry['stalls']['max']}")
    if entry["final_ok"] != entry["reps"] or entry["close_failures"]:
        bad.append(f"the ordered pass itself must end right: final_ok={entry['final_ok']} "
                   f"close_failures={entry['close_failures']}")
    if entry["failures"] != 1:
        bad.append(f"failures {entry['failures']} (expected 1)")
    devices = entry["per_tab"].get("devices")
    if not devices or not devices["page_ms"] or devices["page_ms"]["median"] < 1000:
        bad.append(f"the devices tab must be the slow one: {devices}")
    others = {tab: value["page_ms"].get("median") for tab, value in entry["per_tab"].items() if tab != "devices"}
    if any(value is None or value > 200 for value in others.values()):
        bad.append(f"every other tab should be quick: {others}")
    return bad


def expect_island(summary, records, name, where):
    bad = []
    hits = s4_only(summary, name)
    if not hits:
        return [f"no island cycle classified `{name}`: {classes_of(summary)}"]
    if len(hits) != 1 or (hits[0][0], hits[0][1]) != where:
        bad.append(f"`{name}` expected once at {where}, got {hits}")
    if summary["metrics"].get("s4.failures") != 1:
        bad.append(f"s4 failures {summary['metrics'].get('s4.failures')} (expected 1): {classes_of(summary)}")
    others = [item for item in summary["problems"] if "skip" in item]
    if others:
        bad.append(f"a scenario was skipped: {others}")
    return bad


def expect_ghost(summary, records):
    entry = next((item for item in summary["s2"] if item["variant"] == "aba"), None)
    if entry is None:
        return ["no `aba` entry for S2"]
    bad = []
    if entry["violations"] != 1 or entry["ghosted"] != 1:
        bad.append(f"expected one ghosted burst, got violations={entry['violations']} ghosted={entry['ghosted']}")
    for check in ("opaque", "not_receding", "no_animation"):
        if entry["violation_checks"].get(check) != 1:
            bad.append(f"check {check} expected once, got {entry['violation_checks']}")
    if entry["failures"] != 1 or entry["failed_reps"] != [1]:
        bad.append(f"failed reps {entry['failed_reps']} (expected [1])")
    return bad


def expect_stall(summary, records):
    entry = next((item for item in summary["s1"] if item["variant"] == "fast"), None)
    if entry is None:
        return ["no `fast` entry for S1"]
    bad = []
    if entry["stalls"]["over_100"] != 2:
        bad.append(f"expected two freezes (devices build and the fault), got {entry['stalls']['over_100']}")
    if entry["failures"] != 1 or entry["failed_reps"] != [0]:
        bad.append(f"failed reps {entry['failed_reps']} (expected [0])")
    return bad


CASES = [
    ("clean", [], ["warmup:rounds=1", "s4:reps=1", "s2:reps=1", "s3:reps=1"], expect_clean),
    ("devices", [], ["s1:variants=ordered,reps=1"], expect_devices),
    ("swallow", ["s4:swallow@2"], ["s4:reps=1"], lambda s, r: expect_island(s, r, "handled_no_close", ("key", 5))),
    ("unhandled", ["s4:unhandled@2"], ["s4:reps=1"], lambda s, r: expect_island(s, r, "unhandled", ("key", 5))),
    ("nofocus", ["s4:nofocus@9"], ["s4:reps=1"], lambda s, r: expect_island(s, r, "no_keyboard_focus", ("click", 400))),
    ("late", ["s4:late@5,ms=400"], ["s4:reps=1"], lambda s, r: expect_island(s, r, "late", ("key", 400))),
    ("frozen", ["s4:frozen@6,ms=1800"], ["s4:reps=1"], lambda s, r: expect_island(s, r, "frozen", ("click", 5))),
    ("ghost", ["s2:ghost@2"], ["s2:variants=aba,reps=3"], expect_ghost),
    ("stall", ["s1:stall@5,ms=400"], ["s1:variants=fast,reps=1"], expect_stall),
]


def one(name, faults, specs, check, out: Path):
    directory = out / name
    shutil.rmtree(directory, ignore_errors=True)
    args = argparse.Namespace(out=directory, label=f"selftest-{name}", scenarios=specs, faults=faults, budget=900)
    try:
        runner.simulated(args)
        summary = analyze.summarize(directory)
        analyze.compare(summary, summary)             # the A/B table has to accept the block too
        records = json.loads((directory / "records.json").read_text())["records"]
        return check(summary, records)
    except Exception:  # noqa: BLE001  (any exception is a failed case)
        return ["exception:\n" + traceback.format_exc()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"where the simulated runs go (default {DEFAULT_OUT})")
    ap.add_argument("--only", default="", help="comma separated case names")
    args = ap.parse_args()
    wanted = [part for part in args.only.split(",") if part]
    out = args.out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for name, faults, specs, check in CASES:
        if wanted and name not in wanted:
            continue
        print(f"== {name}: {' '.join(specs)}" + (f"  faults {' '.join(faults)}" if faults else ""), flush=True)
        problems = one(name, faults, specs, check, out)
        if problems:
            failed += 1
            print(f"   FAIL {name}")
            for problem in problems:
                print(f"     - {problem}")
        else:
            print(f"   ok {name}")
    print(f"selftest: {failed} failed case(s) under {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
