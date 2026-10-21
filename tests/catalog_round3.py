"""One randomized, interleaved session for all commits; run in run-gates' private session."""
import argparse
import csv
import json
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import time

import migration_startup as startup
from catalog_end_state import replace_legacy
from catalog_measurement import synthetic
from catalog_statistics import compare, describe


def machine():
    return dict(platform=platform.platform(), cpu=next(line.split(':', 1)[1].strip() for line in
        Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),
        cpu_max=Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
        governors=sorted({path.read_text().strip() for path in Path('/sys/devices/system/cpu').glob('cpu*/cpufreq/scaling_governor')}),
        power={str(path): path.read_text().strip() for path in Path('/sys/class/power_supply').glob('*/online')},
        load_average=os.getloadavg(), graphics='Private Sway pixman, Qt RHI/OpenGL Mesa software; no real GPU claim')


def checkout(destination, revision):
    destination.mkdir()
    archive = subprocess.Popen(['git', 'archive', revision], stdout=subprocess.PIPE)
    try:
        subprocess.run(['tar', '-x', '-C', str(destination)], stdin=archive.stdout, check=True)
    finally:
        archive.stdout.close()
        assert archive.wait() == 0


def benchmark(output, revisions, rounds=30):
    assert rounds >= 30
    output.mkdir(parents=True, exist_ok=False)
    arms = {}; models = {}
    for label, revision, mode in revisions:
        repo = output/'checkouts'/label
        repo.parent.mkdir(exist_ok=True)
        checkout(repo, revision)
        if mode == 'add': models[label] = synthetic(repo, compact=True)
        elif mode == 'replace': models[label] = replace_legacy(repo)
        arms[label] = repo
    original = startup.REPO, startup.OUTPUT
    result = dict(rounds=rounds, seed=241021, arms=revisions, machine_before=machine(), models=models,
        method='Warm page cache and per-arm/path XDG cache after one excluded warm-up; fresh process/config/state/data/runtime. '
        'Same user entry: start.sh --preview or settings.sh --page appearance; monotonic time to first mapped visible nonzero '
        'Sway window, polled every 20ms. Preview mapping can precede catalog completion.',
        statistics='20000 joint round-block bootstrap resamples, percentile 95% CI of difference of medians. '
        'Two-sided Mann-Whitney normal approximation with ties/continuity correction; exploratory p-values, '
        'not corrected for multiple comparisons and not the acceptance rule.', raw={}, summary={})
    rng = random.Random(result['seed'])
    with (output/'samples.csv').open('w') as stream:
        writer = csv.writer(stream); writer.writerow(['path', 'round', 'order', 'arm', 'commit', 'mode', 'milliseconds', 'start_monotonic_ns'])
        try:
            for kind in ('preview', 'settings'):
                values = {key: [] for key in arms}
                for label, repo in arms.items():
                    stage = output/kind/label; stage.mkdir(parents=True)
                    cache = stage/'cache'; cache.mkdir()
                    startup.REPO, startup.OUTPUT = repo, stage
                    with startup.Launch(kind, 'warmup', cache): pass
                for number in range(rounds):
                    order = list(arms); rng.shuffle(order)
                    for position, label in enumerate(order):
                        startup.REPO, startup.OUTPUT = arms[label], output/kind/label
                        started = time.monotonic_ns()
                        with startup.Launch(kind, 'round-'+str(number), startup.OUTPUT/'cache') as launch:
                            values[label].append(launch.elapsed*1000)
                        if any(bad in launch.text for bad in ('Failed to load configuration', 'ReferenceError', 'TypeError')):
                            raise AssertionError(launch.text)
                        revision = next(row for row in revisions if row[0] == label)
                        writer.writerow([kind, number, position, *revision, launch.elapsed*1000, started]); stream.flush()
                    if (number+1) % 5 == 0: print(f'{kind}: {number+1}/{rounds} rounds, {len(arms)} arms', flush=True)
                result['raw'][kind] = values
                result['summary'][kind] = {label: dict(describe(data), comparison=compare(values['main'], data))
                    for label, data in values.items()}
                (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
        finally:
            startup.REPO, startup.OUTPUT = original
    result['machine_after'] = machine()
    result['verdict'] = {}
    for kind, data in result['summary'].items():
        empty = data['final-empty']['comparison']['ci95_ms']
        replace = data['final-replace']['comparison']['ci95_ms']
        result['verdict'][kind] = dict(empty_pass=(empty[0] <= 0 <= empty[1] or empty[1] <= 10), replace_pass=replace[1] <= 50)
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arms', type=Path, required=True, help='JSON list of [label, Git revision, empty|add|replace]')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.output, json.loads(args.arms.read_text()), args.rounds)['summary'], indent=2))
