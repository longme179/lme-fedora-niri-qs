#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Turn a run directory into numbers that each carry their assertion, and into the exit-criteria block.

  analyze.py DIR                     DIR/summary.json and DIR/summary.md
  analyze.py --a DIR_A --b DIR_B     the metrics of two runs side by side (an A/B)

Reads what run.py left behind: records.json (one record per repetition, written by
scenarios.py), the two probe logs (marks, frames, state samples), the shell's own log
(heartbeat stalls), ref.log (the reference client), sampler.jsonl (threads, pings, niri, GPU).

Per symptom: failures by class, and latency distributions (median, p95, max) next to the
assertion that says what "working" means. Global: the exit criteria of the mission, each
with its measured value. Nothing is rounded before it is computed; every table says its N.

What counts as a failure:
  S4  the island is not gone within 100 ms of the Escape key-down, or it never opened
  S2  after the last click of a burst the page host is not settled within 6 s, or Escape
      did not close Settings at the end of the scenario
  S1  a rep in which the GUI thread was gone for 100 ms or more, the last tab clicked is
      not the one shown and settled, or Escape did not close the Control Center
  S3  a step whose panel did not open or close, or a rep with a stall of 100 ms or more
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from probe import Tail  # noqa: E402

STALL_WARN_MS = 33.0      # exit criterion: no event-loop stall beyond this after warm-up
STALL_FREEZE_MS = 100.0   # a stall this long is a freeze the user can see
STALL_SEVERE_MS = 300.0
FRAME_BUDGET_MS = 8.3     # 120 Hz; the report also names the 16.6 ms budget (60 Hz)
FRAME_TOLERANCE_MS = 0.5  # 1000/120 is 8.33: a shell without a single dropped frame sits at 8.33
FRAME_HITCH_MS = 50.0     # a gap this long inside an animation is not a frame any more
ESC_BUDGET_MS = 100.0
FEEDBACK_BUDGET_MS = 50.0
RSS_BUDGET_MB = 150.0


# ---- statistics ------------------------------------------------------------------------------------

def pct(values, percent):
    """Percentile of a sorted list, linear between the neighbours."""
    if not values:
        return None
    rank = (len(values) - 1) * percent / 100.0
    low, high = math.floor(rank), math.ceil(rank)
    if low == high:
        return values[int(rank)]
    return values[low] + (values[high] - values[low]) * (rank - low)


def stats(values, digits=2):
    values = sorted(float(value) for value in values if value is not None)
    if not values:
        return {"n": 0}
    return {"n": len(values), "median": round(pct(values, 50), digits), "p95": round(pct(values, 95), digits),
            "p99": round(pct(values, 99), digits), "max": round(values[-1], digits), "min": round(values[0], digits)}


def p95(values, digits=2):
    """p95 of a raw list, without the rest of the block (the flat metrics)."""
    values = sorted(float(value) for value in values if value is not None)
    return round(pct(values, 95), digits) if values else None


def fmt(stat):
    if not stat or not stat.get("n"):
        return "–"
    return f"{stat['median']} / {stat['p95']} / {stat['max']} (n={stat['n']})"


def by_threshold(stalls):
    """[[ms, marks], ...] -> counts at the three thresholds and the worst one."""
    values = [float(late) for late, _ in stalls]
    return {"count": len(values), "over_33": sum(v > STALL_WARN_MS for v in values),
            "over_100": sum(v > STALL_FREEZE_MS for v in values), "over_300": sum(v > STALL_SEVERE_MS for v in values),
            "max": round(max(values), 1) if values else 0.0, "total_ms": round(sum(values), 1)}


def froze(stalls):
    """True when one of these stalls is a freeze (100 ms or more)."""
    return any(float(late) > STALL_FREEZE_MS for late, _ in stalls)


def all_stalls(records):
    return [item for rec in records for item in rec.get("stalls", [])]


# ---- S4: the island and Escape -------------------------------------------------------------------------

def summarize_s4(records):
    groups = {}
    for rec in records:
        groups.setdefault(f"{rec['route']}|{rec['pre_esc_ms']}|{rec['prior'] or '-'}|{rec['load']}|"
                          + ("cold" if rec.get("cold") else ""), []).append(rec)
    out = []
    for key, recs in groups.items():
        route, delay, prior, load, cold = key.split("|")
        classes = {}
        for rec in recs:
            classes[rec["class"]] = classes.get(rec["class"], 0) + 1
        failures = sum(count for name, count in classes.items() if name != "ok")
        closed = [rec for rec in recs if rec.get("close_ms") is not None]
        out.append({
            "route": route, "pre_esc_ms": int(delay), "prior": "cold start" if cold else (prior if prior != "-" else ""),
            "load": int(load), "cold": bool(cold), "n": len(recs),
            "failures": failures, "failure_rate": round(failures / len(recs), 4), "classes": classes,
            "reps": [rec["rep"] for rec in recs],
            "open_ms": stats(rec.get("open_ms") for rec in recs),
            "open_frame_ms": stats(rec.get("open_frame_ms") for rec in recs if rec["route"] != "ipc"),
            "toggle_ms": stats(rec.get("t_toggle_ms") for rec in recs),
            "close_ms": stats(rec.get("close_ms") for rec in closed),
            "close_frame_ms": stats(rec.get("close_frame_ms") for rec in recs),
            "gone_after_ms": stats(rec.get("gone_after_ms") for rec in recs),
            "stalls": by_threshold([item for rec in recs for item in rec.get("stalls", [])]),
            "recovered": sum(1 for rec in recs if rec.get("recovery")),
            "no_keyboard_focus": sum(1 for rec in recs if rec.get("exclusive") is False),
        })
    out.sort(key=lambda group: (group["prior"], group["load"], group["route"], group["pre_esc_ms"]))
    return out


# ---- S2: Settings pages ----------------------------------------------------------------------------

def summarize_s2(records):
    variants = {}
    for rec in records:
        variants.setdefault(rec["variant"], []).append(rec)
    out = []
    for variant, recs in variants.items():
        entry = {"variant": variant, "reps": len(recs), "stalls": by_threshold(all_stalls(recs)),
                 "freeze_reps": sum(1 for rec in recs if froze(rec.get("stalls", []))),
                 "close_failures": sum(1 for rec in recs if rec.get("close_recovery"))}
        if variant == "all":
            pages = [page for rec in recs for page in rec.get("pages", []) if not page.get("unreachable")]
            bad = [page for page in pages if not page.get("ok")]
            entry.update({
                "pages": len(pages), "violations": len(bad),
                "violations_detail": [[page["page"], "all", (page.get("host") or {}).get("opacity"), page.get("failed_checks")] for page in bad],
                "unreachable": sorted({page["page"] for rec in recs for page in rec.get("pages", []) if page.get("unreachable")}),
                "react_ms": stats(page.get("react_ms") for page in pages), "frame_ms": stats(page.get("frame_ms") for page in pages),
                "page_ms": stats(page.get("page_ms") for page in pages), "settle_ms": stats(page.get("settle_ms") for page in pages),
                "per_page": {key: {"page_ms": stats(page.get("page_ms") for page in pages if page["page"] == key),
                                   "settle_ms": stats(page.get("settle_ms") for page in pages if page["page"] == key),
                                   "frame_ms": stats(page.get("frame_ms") for page in pages if page["page"] == key)}
                             for key in sorted({page["page"] for page in pages})},
            })
            entry["failed_reps"] = sorted({rec["rep"] for rec in recs if not rec.get("ok") or froze(rec.get("stalls", []))
                                           or rec.get("close_recovery")})
        else:
            bad = [rec for rec in recs if not rec.get("ok")]
            checks = {}
            for rec in bad:
                for name in rec.get("failed_checks", []):
                    checks[name] = checks.get(name, 0) + 1
            react = [value for rec in recs for value in rec.get("react_ms", [])]
            entry.update({
                "bursts": len(recs), "violations": len(bad), "failure_rate": round(len(bad) / len(recs), 4) if recs else 0,
                "violation_checks": checks,
                "violations_detail": [[rec["rep"], [click[0] for click in rec.get("clicks", [])], (rec.get("host") or {}).get("opacity"),
                                       rec.get("failed_checks")] for rec in bad],
                "ghosted": sum(1 for rec in recs if (rec.get("host") or {}).get("opacity", 1) < 0.999),
                "settle_ms": stats(rec.get("settle_ms") for rec in recs), "react_ms": stats(react),
                "react_missed": sum(1 for value in react if value is None),
                "first_frame_ms": stats(rec.get("first_frame_ms") for rec in recs),
                "toast_seen": sum(1 for rec in recs if rec.get("toast_seen")),
            })
            entry["failed_reps"] = sorted({rec["rep"] for rec in bad} | {rec["rep"] for rec in recs if froze(rec.get("stalls", []))}
                                          | {rec["rep"] for rec in recs if rec.get("close_recovery")})
        entry["failures"] = len(entry["failed_reps"])
        out.append(entry)
    return out


# ---- S1: Control Center tabs ---------------------------------------------------------------------------

def summarize_s1(records):
    variants = {}
    for rec in records:
        variants.setdefault(rec["variant"], []).append(rec)
    out = []
    for variant, recs in variants.items():
        per_rep = [by_threshold(rec.get("stalls", [])) for rec in recs]
        duration = sum(rec.get("duration_ms", 0) for rec in recs)
        entry = {
            "variant": variant, "reps": len(recs), "clicks": sum(len(rec.get("clicks", [])) for rec in recs),
            "final_ok": sum(1 for rec in recs if rec.get("ok")), "final_bad": [rec["rep"] for rec in recs if not rec.get("ok")],
            "final_settle_ms": stats(rec.get("final_settle_ms") for rec in recs),
            "close_ms": stats(rec.get("close_ms") for rec in recs), "close_frame_ms": stats(rec.get("close_frame_ms") for rec in recs),
            "close_failures": sum(1 for rec in recs if rec.get("close_recovery")),
            "close_failed_reps": [rec["rep"] for rec in recs if rec.get("close_recovery")],
            "freeze_reps": sum(1 for rec in recs if froze(rec.get("stalls", []))),
            "frozen": [rec["rep"] for rec in recs if froze(rec.get("stalls", []))],
            "severe_reps": sum(1 for item in per_rep if item["over_300"]),
            "stalls": by_threshold(all_stalls(recs)),
            "stalls_per_min": round(sum(item["count"] for item in per_rep) / (duration / 60000.0), 2) if duration else None,
            "ping_ms": stats(rec.get("ping_ms") for rec in recs),
            "react_ms": stats(value for rec in recs for value in rec.get("react_ms", []) if value is not None),
            "react_missed": sum(1 for rec in recs for value in rec.get("react_ms", []) if value is None),
            "duration_ms": round(duration, 1),
        }
        entry["failed_reps"] = sorted(set(entry["final_bad"]) | set(entry["close_failed_reps"]) | set(entry["frozen"]))
        entry["failures"] = len(entry["failed_reps"])
        if variant == "ordered":
            clicks = [click for rec in recs for click in rec.get("clicks", [])]
            entry["per_tab"] = {tab: {"page_ms": stats(click.get("page_ms") for click in clicks if click["tab"] == tab),
                                      "settle_ms": stats(click.get("settle_ms") for click in clicks if click["tab"] == tab),
                                      "frame_ms": stats(click.get("frame_ms") for click in clicks if click["tab"] == tab)}
                                for tab in sorted({click["tab"] for click in clicks})}
        out.append(entry)
    return out


# ---- S3: a working session --------------------------------------------------------------------------------

def step_failed(step):
    return (step.get("closed") is False or (step.get("close_ms") or 0) > ESC_BUDGET_MS
            or step.get("open_ms") is None or bool(step.get("recovery")))


def summarize_s3(records):
    steps = [step for rec in records for step in rec.get("steps", [])]
    panels = {}
    for step in steps:
        panels.setdefault(step["panel"], []).append(step)
    out = []
    for panel, items in panels.items():
        out.append({
            "panel": panel, "n": len(items), "open_ms": stats(step.get("open_ms") for step in items),
            "open_frame_ms": stats(step.get("open_frame_ms") for step in items), "close_ms": stats(step.get("close_ms") for step in items),
            "close_frame_ms": stats(step.get("close_frame_ms") for step in items),
            "close_failures": sum(1 for step in items if step.get("closed") is False or (step.get("close_ms") or 0) > ESC_BUDGET_MS),
            "open_failures": sum(1 for step in items if step.get("open_ms") is None),
            "recovered": sum(1 for step in items if step.get("recovery")),
            "failed_steps": sum(1 for step in items if step_failed(step)),
            "stalls": by_threshold([item for step in items for item in step.get("stalls_open", []) + step.get("stalls_close", [])]),
        })
    reps = []
    for rec in records:
        stalls = by_threshold(rec.get("stalls", []))
        workspace = rec.get("workspace") or {}
        reps.append({"rep": rec["rep"], "load": rec.get("load"), "steps": len(rec.get("steps", [])), "stalls": stalls,
                     "final_open": rec.get("final_open"), "workspace_restored": workspace.get("restored", workspace.get("skipped")),
                     "failed_steps": sum(1 for step in rec.get("steps", []) if step_failed(step))})
    failed = [rep["rep"] for rep in reps if rep["failed_steps"] or rep["stalls"]["over_100"] or rep["final_open"]
              or rep["workspace_restored"] is not True]
    return {"panels": out, "reps": reps, "n": len(records), "failures": len(failed), "failed_reps": failed,
            "failed_steps": sum(1 for step in steps if step_failed(step)), "steps": len(steps),
            "stalls": by_threshold(all_stalls(records))}


# ---- global: logs -------------------------------------------------------------------------------------------

def read_log(path, probe_clock=True):
    path = Path(path)
    return Tail(path, probe_clock).read() if path.is_file() else []


def culprit(marks):
    """The last mark before the thread came back, as a name to group by."""
    parts = [part for part in (marks or "").split(";") if part]
    if not parts:
        return "(no mark)"
    words = parts[-1].split("+")[0].split()
    return " ".join(words[:3] if "." in words[0] else words[:2])


def frame_gaps(events, since_ms):
    """Per window: the gaps between two frame swaps, as long as they are frames of an animation.

    A gap is a frame of an animation only up to two refreshes (16.7 ms at 120 Hz): one
    refresh is a frame, two is one dropped frame, and anything longer between two frame
    marks is more likely the pause between two animations (the window closed and opened
    again) than one very late frame — the log cannot tell the two apart, so the criterion
    counts only what is certainly a frame. Longer gaps are listed as hitches and pauses."""
    per_window = {}
    for event in events:
        if event.kind == "F" and event.epoch >= since_ms:
            per_window.setdefault(event.text.rsplit(" ", 1)[-1], []).append(event.epoch)
    out = {}
    for window, times in per_window.items():
        times.sort()
        gaps = [b - a for a, b in zip(times, times[1:])]
        frames = [gap for gap in gaps if gap <= 2 * FRAME_BUDGET_MS + FRAME_TOLERANCE_MS]
        out[window] = {"frames": len(frames), "frame_ms": stats(frames), "max_ms": round(max(frames), 2) if frames else None,
                       "over_16.6": sum(1 for gap in frames if gap > 2 * FRAME_BUDGET_MS),
                       "hitches_50_250": sum(1 for gap in gaps if 2 * FRAME_BUDGET_MS < gap <= 250),
                       "pauses_over_250": sum(1 for gap in gaps if gap > 250)}
    return out


def ref_gaps(path, stalls):
    """Gaps of the reference client; each long one is matched with a shell stall of the same time."""
    times = []
    path = Path(path)
    if path.is_file():
        pattern = re.compile(r"\bF (\d+) (\d+)")
        for line in path.read_text().splitlines():
            found = pattern.search(line)
            if found:
                times.append(int(found.group(1)))
    times.sort()
    gaps = [(a, b - a) for a, b in zip(times, times[1:])]
    long_gaps = []
    for start, gap in gaps:
        if gap <= FRAME_HITCH_MS:
            continue
        with_shell = any(start - 30 <= stall.epoch <= start + gap + 30 and stall.data["late"] > FRAME_HITCH_MS - 35
                         for stall in stalls)
        long_gaps.append({"start_ms": start, "gap_ms": round(gap, 1), "shell_stalled_too": with_shell})
    frames = [gap for _, gap in gaps if gap <= FRAME_HITCH_MS]
    return {"frames": len(frames), "frame_ms": stats(frames), "long_gaps": len(long_gaps),
            "with_shell_stall": sum(1 for gap in long_gaps if gap["shell_stalled_too"]),
            "screen_only": sum(1 for gap in long_gaps if not gap["shell_stalled_too"]),
            "longest": sorted(long_gaps, key=lambda gap: -gap["gap_ms"])[:10]}


def sampler_summary(path, since_ms):
    summary = {"ping_ms": stats([]), "niri_ms": stats([]), "stacks": 0, "rss": {}, "gpu": {}}
    path = Path(path)
    if not path.is_file():
        return summary
    pings, niri, rss, gpu, amd_busy = [], [], {}, [], []
    for line in path.read_text().splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get("t", 0) < since_ms:
            continue
        kind = record.get("kind")
        if kind == "ping" and record.get("rtt_ms") is not None:
            pings.append(record["rtt_ms"])
            summary["stacks"] += bool(record.get("stack"))
        elif kind == "niri" and record.get("rtt_ms") is not None:
            niri.append(record["rtt_ms"])
        elif kind == "threads":
            for name, proc in (record.get("procs") or {}).items():
                rss.setdefault(name, []).append((record["t"], proc.get("rss_kb", 0)))
        elif kind == "gpu":
            # The six nvidia-smi fields in query order, or nothing when the call failed;
            # the amdgpu counters are read independently and keep counting either way.
            nvidia = [value for value in (record.get("nvidia") or []) if value is not None]
            if len(nvidia) == 6:
                gpu.append(nvidia)
            amd_busy += [card[1] for card in (record.get("amdgpu") or []) if card[1] is not None]
    summary["ping_ms"], summary["niri_ms"] = stats(pings), stats(niri)
    for name, series in rss.items():
        first = next((kb for t, kb in series if t >= since_ms), None)
        top = max((kb for _, kb in series), default=0)
        summary["rss"][name] = {"first_mb": round(first / 1024, 1) if first else None, "max_mb": round(top / 1024, 1),
                                "delta_mb": round((top - first) / 1024, 1) if first else None, "samples": len(series)}
    if gpu:
        # Columns of the six nvidia-smi fields in query order.
        columns = [[row[i] for row in gpu] for i in range(6)]
        summary["gpu"] = {"nvidia_util_max": max(columns[0]), "nvidia_mem_used_max_mb": max(columns[2]),
                          "nvidia_power_max_w": max(columns[3]),
                          "amdgpu_busy_max": max(amd_busy, default=0)}
    return summary


def feedback_times(records):
    """Every measured input -> first frame of the shell, in ms."""
    out = []
    for rec in records:
        for name in ("open_frame_ms", "close_frame_ms", "first_frame_ms"):
            if rec.get(name) is not None:
                out.append(rec[name])
        for click in rec.get("clicks", []):
            if isinstance(click, dict) and click.get("frame_ms") is not None:
                out.append(click["frame_ms"])
        for page in rec.get("pages", []):
            if page.get("frame_ms") is not None:
                out.append(page["frame_ms"])
        for step in rec.get("steps", []):
            for name in ("open_frame_ms", "close_frame_ms"):
                if step.get(name) is not None:
                    out.append(step[name])
    return out


def first_time(rec):
    """When the first input of a record happened (epoch ms)."""
    for click in rec.get("clicks") or []:
        if isinstance(click, dict) and click.get("t"):
            return click["t"]
        if isinstance(click, list) and len(click) > 1:
            return click[1]
    for page in rec.get("pages") or []:
        if page.get("t"):
            return page["t"]
    for step in rec.get("steps") or []:
        if step.get("t_open"):
            return step["t_open"]
    return rec.get("t_open")


def warm_boundary(meta, records):
    """Everything from here on is a warm shell (the warm-up, or else the first scenario); never
    before the run itself started."""
    boundary = float(meta.get("warmup_end_ms") or 0.0) or \
        min((value for value in (first_time(rec) for rec in records) if value), default=0.0)
    return max(boundary, float(meta.get("epoch_ms") or 0.0))


def global_block(run_dir, records, warm_ms):
    run_dir = Path(run_dir)
    shell = read_log(run_dir / "probe/probe.shell.log")
    settings = read_log(run_dir / "probe/probe.settings.log")
    stalls = [event for event in read_log(run_dir / "state/log/lme-shell.log", False) + shell
              if event.kind == "stall" and event.epoch >= warm_ms]
    seen, unique = set(), []
    for stall in stalls:
        if (stall.epoch, stall.data["late"]) not in seen:
            seen.add((stall.epoch, stall.data["late"]))
            unique.append(stall)
    culprits = {}
    for stall in unique:
        name = culprit(stall.data.get("marks"))
        culprits[name] = culprits.get(name, [0, 0.0])
        culprits[name][0] += 1
        culprits[name][1] += stall.data["late"]
    worst = sorted(unique, key=lambda stall: -stall.data["late"])[:15]
    frames = frame_gaps(shell + settings, warm_ms)
    last = max((event.epoch for event in shell + settings), default=warm_ms)
    minutes = max((last - warm_ms) / 60000.0, 0.0)
    reference = ref_gaps(run_dir / "ref.log", unique)
    sampler = sampler_summary(run_dir / "sampler.jsonl", warm_ms)
    counted = by_threshold([[stall.data["late"], stall.data.get("marks", "")] for stall in unique])
    return {
        "warmup_end_ms": warm_ms, "minutes": round(minutes, 2), "stalls": counted,
        "stalls_over_33_per_min": round(counted["over_33"] / minutes, 2) if minutes else None,
        "stalls_over_100_per_min": round(counted["over_100"] / minutes, 2) if minutes else None,
        "stall_culprits": sorted(([name, count, round(total, 1)] for name, (count, total) in culprits.items()),
                                 key=lambda item: -item[2])[:25],
        "worst_stalls": [{"at_ms": round(stall.epoch, 1), "late_ms": round(stall.data["late"], 1),
                          "marks": stall.data.get("marks", "")[:300]} for stall in worst],
        "frames": frames, "input_to_frame_ms": stats(feedback_times(records)), "reference_client": reference,
        "pings": sampler["ping_ms"], "niri": sampler["niri_ms"], "stacks": sampler["stacks"],
        "rss": sampler["rss"], "gpu": sampler["gpu"],
    }


# ---- assemble ------------------------------------------------------------------------------------------------

def metrics(summary, records):
    """The flat list an A/B compares."""
    out = {}
    s4 = summary["s4"]
    if s4:
        out["s4.cycles"], out["s4.failures"] = sum(g["n"] for g in s4), sum(g["failures"] for g in s4)
        out["s4.failure_rate"] = round(out["s4.failures"] / out["s4.cycles"], 4)
        out["s4.close_ms.p95"] = p95(rec.get("close_ms") for rec in records if rec["scenario"] == "s4")
        out["s4.close_ms.max"] = max((g["close_ms"].get("max", 0) or 0) for g in s4) if s4 else None
        out["s4.open_frame_ms.p95"] = p95(rec.get("open_frame_ms") for rec in records
                                          if rec["scenario"] == "s4" and rec.get("route") != "ipc")
    for entry in summary["s2"]:
        prefix = f"s2.{entry['variant']}"
        out[prefix + ".failures"] = entry["failures"]
        out[prefix + ".violations"] = entry.get("violations")
        out[prefix + ".reps"] = entry["reps"]
        out[prefix + ".freeze_reps"] = entry["freeze_reps"]
        out[prefix + ".settle_ms.p95"] = entry["settle_ms"].get("p95")
        out[prefix + ".settle_ms.max"] = entry["settle_ms"].get("max")
        out[prefix + ".react_ms.p95"] = entry["react_ms"].get("p95")
    for entry in summary["s1"]:
        prefix = f"s1.{entry['variant']}"
        out[prefix + ".reps"] = entry["reps"]
        out[prefix + ".failures"] = entry["failures"]
        out[prefix + ".freeze_reps"] = entry["freeze_reps"]
        out[prefix + ".stalls_over_100"] = entry["stalls"]["over_100"]
        out[prefix + ".stalls_over_33_per_min"] = entry["stalls_per_min"]
        out[prefix + ".stall_max_ms"] = entry["stalls"]["max"]
        out[prefix + ".final_settle_ms.p95"] = entry["final_settle_ms"].get("p95")
        out[prefix + ".final_settle_ms.max"] = entry["final_settle_ms"].get("max")
        out[prefix + ".close_failures"] = entry["close_failures"]
        out[prefix + ".react_ms.p95"] = entry["react_ms"].get("p95")
    s3 = summary["s3"]
    if s3:
        out["s3.steps"] = s3["steps"]
        out["s3.failures"] = s3["failures"]
        out["s3.reps"] = s3["n"]
        out["s3.failed_steps"] = s3["failed_steps"]
        out["s3.open_frame_ms.p95"] = max((p["open_frame_ms"].get("p95") or 0) for p in s3["panels"]) if s3["panels"] else None
        out["s3.open_frame_ms.max"] = max((p["open_frame_ms"].get("max") or 0) for p in s3["panels"]) if s3["panels"] else None
        out["s3.stall_max_ms"] = s3["stalls"]["max"]
    g = summary["global"]
    out["global.minutes"] = g["minutes"]
    out["global.stall_max_ms"] = g["stalls"]["max"]
    out["global.stalls_over_33_per_min"] = g["stalls_over_33_per_min"]
    out["global.stalls_over_100_per_min"] = g["stalls_over_100_per_min"]
    for window, values in g["frames"].items():
        out[f"global.frame_p99_ms.{window}"] = values["frame_ms"].get("p99")
        out[f"global.frame_max_ms.{window}"] = values["frame_ms"].get("max")
    out["global.input_to_frame_p95_ms"] = g["input_to_frame_ms"].get("p95")
    out["global.input_to_frame_max_ms"] = g["input_to_frame_ms"].get("max")
    out["global.ping_p99_ms"] = g["pings"].get("p99")
    out["global.niri_p95_ms"] = g["niri"].get("p95")
    out["global.rss_delta_mb.shell"] = g["rss"].get("shell", {}).get("delta_mb")
    out["global.rss_delta_mb.settings"] = g["rss"].get("settings", {}).get("delta_mb")
    out["global.ref_screen_only_gaps"] = g["reference_client"]["screen_only"]
    return out


def criteria(summary, budget_ms=FRAME_BUDGET_MS):
    """The exit criteria, each with its measured value and whether it holds in this run."""
    g = summary["global"]
    checks = []
    if summary["s4"]:
        failures, cycles = sum(group["failures"] for group in summary["s4"]), sum(group["n"] for group in summary["s4"])
        checks.append(["S4 island: Escape closes it within 100 ms", f"{failures} failures / {cycles} cycles", failures == 0])
    if summary["s2"]:
        failures, reps = sum(entry["failures"] for entry in summary["s2"]), sum(entry["reps"] for entry in summary["s2"])
        checks.append(["S2 Settings: page settled after every switch, Escape closes it",
                       f"{failures} failed reps / {reps}", failures == 0])
    if summary["s1"]:
        failures, reps = sum(entry["failures"] for entry in summary["s1"]), sum(entry["reps"] for entry in summary["s1"])
        checks.append(["S1 Control Center: no freeze, last tab shown, Escape closes it",
                       f"{failures} failed reps / {reps}", failures == 0])
    if summary["s3"]["n"]:
        checks.append(["S3 session: every panel opens and closes, no stall over 100 ms",
                       f"{summary['s3']['failures']} failed reps / {summary['s3']['n']}", summary["s3"]["failures"] == 0])
    stalls = g["stalls"]
    checks.append(["No event-loop stall over 33 ms after warm-up",
                   f"{stalls['over_33']} of {stalls['count']} stalls, worst {stalls['max']} ms", stalls["over_33"] == 0])
    over = sum(values["over_16.6"] for values in g["frames"].values())
    checks.append(["No frame over 2x budget (16.6 ms)", f"{over} frames", over == 0])
    for window, values in g["frames"].items():
        checks.append([f"p99 frame time <= {budget_ms:g} ms ({window}; +{FRAME_TOLERANCE_MS:g} ms for the 120 Hz refresh)",
                       f"{values['frame_ms'].get('p99')} ms (n={values['frames']})",
                       (values["frame_ms"].get("p99") or 0) <= budget_ms + FRAME_TOLERANCE_MS])
    feedback = g["input_to_frame_ms"]
    checks.append([f"Input to first visual feedback <= {FEEDBACK_BUDGET_MS:g} ms",
                   f"p95 {feedback.get('p95')} ms, max {feedback.get('max')} ms (n={feedback['n']})",
                   (feedback.get("p95") or 1e9) <= FEEDBACK_BUDGET_MS])
    for name, values in g["rss"].items():
        checks.append([f"RSS <= first sample + {RSS_BUDGET_MB:g} MB ({name})",
                       f"+{values['delta_mb']} MB (max {values['max_mb']} MB)", (values["delta_mb"] or 0) <= RSS_BUDGET_MB])
    return checks


def summarize(run_dir):
    run_dir = Path(run_dir)
    data = json.loads((run_dir / "records.json").read_text()) if (run_dir / "records.json").is_file() \
        else {"records": [], "problems": [], "meta": {}}
    meta = json.loads((run_dir / "meta.json").read_text()) if (run_dir / "meta.json").is_file() else {}
    records = data.get("records", [])
    summary = {
        "run": {"dir": str(run_dir), "label": meta.get("label", run_dir.name), "tree": meta.get("tree"),
                "ref": meta.get("ref"), "started": meta.get("started"), "simulated": meta.get("simulated", False),
                "seconds": meta.get("seconds"), "truncated": (data.get("meta") or {}).get("truncated"),
                "ended": meta.get("ended"), "restored": ((meta.get("restore") or {}).get("ok") if meta.get("restore") is not None
                                                         else None)},
        "s4": summarize_s4([rec for rec in records if rec["scenario"] == "s4"]),
        "s2": summarize_s2([rec for rec in records if rec["scenario"] == "s2"]),
        "s1": summarize_s1([rec for rec in records if rec["scenario"] == "s1"]),
        "s3": summarize_s3([rec for rec in records if rec["scenario"] == "s3"]),
        "problems": data.get("problems", []),
        "global": global_block(run_dir, records, warm_boundary(meta, records)),
    }
    summary["metrics"] = metrics(summary, records)
    summary["criteria"] = criteria(summary)
    return summary


# ---- markdown ------------------------------------------------------------------------------------------------

def table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join("–" if cell is None else str(cell) for cell in row) + " |" for row in rows]
    return lines


def to_markdown(summary):
    run = summary["run"]
    lines = [f"# Perf run `{run['label']}`" + (" (simulated)" if run["simulated"] else ""), ""]
    lines += [f"Tree `{run['tree']}` at `{run['ref']}`; started {run['started']}; {run['seconds']} s; "
              + ("truncated: " + run["truncated"] + "; " if run["truncated"] else "")
              + (f"ended: {run['ended']}; " if run["ended"] else "")
              + ("session restored" if run["restored"] else "SESSION RESTORE NOT VERIFIED" if run["simulated"] is False
                 else "no session") + ".", "",
              "Latency cells are median / p95 / max in ms, with N in brackets.", ""]
    if summary["s4"]:
        lines += ["## S4 - island opens, Escape closes it", "",
                  "Failure = the island is not gone within 100 ms of the Escape key-down, or it did not open. Classes: "
                  "`late` (gone, after 100 ms), `handled_no_close` (the handler ran, the island stayed), `unhandled` (the "
                  "key reached the overlay, nothing handled it), `not_delivered` (no key reached the shell), `frozen`, "
                  "`did_not_open`, `no_keyboard_focus` (the layer does not hold the keyboard, so Escape was not pressed). "
                  "Open and close latencies count from the real input; cycles opened through the IPC have no input.", ""]
        rows = []
        for group in summary["s4"]:
            rows.append([group["route"], group["pre_esc_ms"], group["prior"] or "–", group["load"] or "–",
                         f"{group['failures']}/{group['n']}", ", ".join(f"{name} {count}" for name, count in sorted(group["classes"].items())),
                         fmt(group["open_ms"]), fmt(group["open_frame_ms"]), fmt(group["close_ms"]), fmt(group["close_frame_ms"]),
                         group["stalls"]["over_100"]])
        lines += table(["route", "ESC after ms", "after panel", "load", "fail", "classes", "input->shown",
                        "input->first frame", "ESC->gone", "ESC->first frame", "stalls>100"], rows) + [""]
        rows = [[group["route"], group["pre_esc_ms"], group["prior"], group["load"], group["reps"]]
                for group in summary["s4"] if group["failures"]]
        if rows:
            lines += ["Groups with failures and their repetitions (the record of each is in records.json):", ""] + table(
                ["route", "ESC after ms", "after panel", "load", "reps"], rows) + [""]
    if summary["s2"]:
        lines += ["## S2 - Settings page switching", "",
                  "Violation = after the burst the page host is not in the settled state (wanted page shown, built, opacity "
                  "1, no transition running, nothing pending) within 6 s. A rep fails on a violation, on a GUI-thread "
                  "stall of 100 ms or more, or when Escape did not close Settings.", ""]
        rows = []
        for entry in summary["s2"]:
            if entry["variant"] == "all":
                rows.append(["all", entry["reps"], f"{entry['violations']}/{entry['pages']} pages", "–", fmt(entry["react_ms"]),
                             fmt(entry["frame_ms"]), fmt(entry["settle_ms"]), f"{entry['failures']}", entry["stalls"]["over_100"]])
            else:
                rows.append([entry["variant"], entry["reps"], f"{entry['violations']}/{entry['bursts']}", entry["ghosted"],
                             fmt(entry["react_ms"]), fmt(entry["first_frame_ms"]), fmt(entry["settle_ms"]), entry["failures"],
                             entry["stalls"]["over_100"]])
        lines += table(["variant", "reps", "violations", "ghosted", "click->navigate mark", "input->first frame",
                        "last click->settled", "failed reps", "stalls>100"], rows) + [""]
        for entry in summary["s2"]:
            for item in entry.get("violations_detail", []):
                rep, sequence, opacity, failed = (list(item) + ["", "", "", ""])[:4]
                where = f"rep {rep}, clicks {'+'.join(sequence)}" if entry["variant"] != "all" else f"page {rep}"
                lines.append(f"- {entry['variant']}: {where}; opacity {opacity}; failed {failed}")
        per_page = next((entry["per_page"] for entry in summary["s2"] if entry["variant"] == "all"), {})
        if per_page:
            lines += ["", "Per page (variant `all`):", ""] + table(
                ["page", "click->built/present", "click->settled", "click->first frame"],
                [[key, fmt(value["page_ms"]), fmt(value["settle_ms"]), fmt(value["frame_ms"])] for key, value in per_page.items()]) + [""]
    if summary["s1"]:
        lines += ["## S1 - Control Center tabs", "",
                  "A rep fails when the GUI thread was unavailable for 100 ms or more inside it (heartbeat), when the last "
                  "tab clicked did not end shown, built and opaque, or when Escape did not close the panel.", ""]
        rows = []
        for entry in summary["s1"]:
            rows.append([entry["variant"], entry["reps"], entry["clicks"], f"{entry['final_ok']}/{entry['reps']}",
                         f"{entry['failures']}", entry["failed_reps"] or "–", fmt(entry["final_settle_ms"]),
                         f"{entry['freeze_reps']}/{entry['reps']}", f"{entry['stalls']['over_100']} / {entry['stalls']['over_300']}",
                         entry["stalls"]["max"], fmt(entry["close_ms"]), entry["close_failures"]])
        lines += table(["variant", "reps", "clicks", "final tab ok", "failed reps", "which", "last click->settled",
                        "freeze reps", "stalls >100 / >300", "worst stall", "ESC->gone", "ESC failures"], rows) + [""]
        for entry in summary["s1"]:
            if entry["variant"] == "ordered" and entry.get("per_tab"):
                lines += ["Per tab (variant `ordered`):", ""] + table(
                    ["tab", "click->built/present", "click->settled", "click->first frame"],
                    [[tab, fmt(value["page_ms"]), fmt(value["settle_ms"]), fmt(value["frame_ms"])]
                     for tab, value in entry["per_tab"].items()]) + [""]
    if summary["s3"]["panels"]:
        lines += ["## S3 - a working session", "",
                  "A step fails when its panel did not open, was not gone within 100 ms of the Escape key-down (state "
                  "samples, 40 ms resolution), or needed a recovery. A rep fails on a failed step, a stall of 100 ms or "
                  "more, a panel left open, or a workspace that was not restored.", ""]
        rows = [[panel["panel"], panel["n"], fmt(panel["open_frame_ms"]), fmt(panel["open_ms"]), fmt(panel["close_ms"]),
                 panel["close_frame_ms"], panel["failed_steps"], panel["recovered"],
                 f"{panel['stalls']['over_100']} / {panel['stalls']['over_300']}", panel["stalls"]["max"]]
                for panel in summary["s3"]["panels"]]
        lines += table(["panel", "n", "input->first frame", "input->open (sampled)", "ESC->gone", "gone->first frame",
                        "failed steps", "recovered", "stalls >100 / >300", "worst stall"], rows) + [""]
        rows = [[rep["rep"], rep["load"], rep["steps"], rep["failed_steps"], f"{rep['stalls']['over_100']} / {rep['stalls']['over_300']}",
                 rep["stalls"]["max"], rep["workspace_restored"], rep["final_open"]] for rep in summary["s3"]["reps"]]
        lines += ["Per rep:", ""] + table(["rep", "load", "steps", "failed steps", "stalls >100 / >300", "worst stall",
                                           "workspace back", "panel left open"], rows) + [""]
    g = summary["global"]
    lines += [f"## Global (after warm-up, {g['minutes']} min)", "", "Exit criteria:", ""]
    lines += table(["criterion", "measured", "holds"], [[name, value, "yes" if ok else "NO"] for name, value, ok in summary["criteria"]]) + [""]
    rows = [[window, values["frames"], fmt(values["frame_ms"]), values["over_16.6"], values["hitches_50_250"], values["pauses_over_250"]]
            for window, values in g["frames"].items()]
    lines += ["Frame gaps per window (gaps up to 50 ms count as frames of an animation; longer ones are listed apart):", ""] + table(
        ["window", "frames", "frame gap", "> 16.6 ms", "hitches 50-250 ms", "pauses > 250 ms"], rows) + [""]
    lines += ["Stalls of the GUI thread (heartbeat inside the shell): ", ""] + table(
        ["count", "> 33 ms", "> 100 ms", "> 300 ms", "worst", "total ms", ">33 per min", ">100 per min"],
        [[g["stalls"]["count"], g["stalls"]["over_33"], g["stalls"]["over_100"], g["stalls"]["over_300"], g["stalls"]["max"],
          g["stalls"]["total_ms"], g["stalls_over_33_per_min"], g["stalls_over_100_per_min"]]]) + [""]
    if g["stall_culprits"]:
        lines += ["What ran in the stalls (the last mark before the thread came back):", ""] + table(
            ["last mark", "stalls", "total ms"], g["stall_culprits"]) + [""]
        if g["worst_stalls"]:
            lines += ["The worst:", ""] + table(["at ms", "ms", "marks"], [[s["at_ms"], s["late_ms"], s["marks"][:160]] for s in g["worst_stalls"][:8]]) + [""]
    lines += ["Outside the shell:", ""] + table(
        ["probe ping (GUI thread availability)", "niri round trip", "reference client frame gap", "screen-only gaps > 50 ms",
         "stacks taken"],
        [[fmt(g["pings"]), fmt(g["niri"]), fmt(g["reference_client"]["frame_ms"]),
          f"{g['reference_client']['screen_only']} of {g['reference_client']['long_gaps']}", g["stacks"]]]) + [""]
    if g["rss"]:
        lines += ["Memory (first sample after warm-up to the maximum):", ""] + table(
            ["process", "first MB", "max MB", "growth MB", "samples"],
            [[name, values["first_mb"], values["max_mb"], values["delta_mb"], values["samples"]] for name, values in g["rss"].items()]) + [""]
    if summary["problems"]:
        lines += [f"Problems, skips and recoveries of the run: {len(summary['problems'])} (see summary.json).", ""]
        for item in summary["problems"][:12]:
            lines.append(f"- {json.dumps(item)[:240]}")
        lines.append("")
    return "\n".join(lines) + "\n"


# ---- compare -------------------------------------------------------------------------------------------------

def compare(a, b, out=None):
    rows = []
    for key in sorted(set(a["metrics"]) | set(b["metrics"])):
        left, right = a["metrics"].get(key), b["metrics"].get(key)
        if left is None and right is None:
            continue
        delta = None
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            delta = round(right - left, 4)
        rows.append([key, "–" if left is None else left, "–" if right is None else right, "–" if delta is None else delta])
    lines = [f"# A/B: `{a['run']['label']}` (A) against `{b['run']['label']}` (B)", "",
             "Delta = B minus A. Lower is better everywhere except the counts of cycles, reps, steps and minutes.", ""]
    lines += table(["metric", "A", "B", "delta"], rows)
    text = "\n".join(lines) + "\n"
    if out:
        Path(out).write_text(text)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", nargs="?", type=Path)
    ap.add_argument("--a", type=Path, help="run directory of side A")
    ap.add_argument("--b", type=Path, help="run directory of side B")
    ap.add_argument("--out", type=Path, help="where the comparison goes (default: stdout)")
    args = ap.parse_args()
    if args.a and args.b:
        text = compare(summarize(args.a), summarize(args.b), args.out)
        if not args.out:
            print(text)
        return 0
    if not args.run_dir:
        ap.error("a run directory, or --a and --b")
    summary = summarize(args.run_dir)
    (args.run_dir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    (args.run_dir / "summary.md").write_text(to_markdown(summary))
    print(to_markdown(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
