"""M4b pre-registered three-arm startup session; private compositor only."""
import argparse
import csv
import json
from pathlib import Path
import random
import time

from catalog_round3 import checkout, machine
from catalog_statistics import compare, describe
import migration_startup as startup


def benchmark(output, head):
    output.mkdir(parents=True, exist_ok=False)
    revisions = [('main', 'c46f934'), ('m4a', '933750f'), ('m4b', head)]
    arms = {}
    for label, revision in revisions:
        root = output/'checkouts'/label; root.parent.mkdir(exist_ok=True)
        checkout(root, revision); arms[label] = root
    result = dict(seed=241021, rounds=40, arms=revisions, machine_before=machine(), raw={}, summary={},
        method='docs/M4B_STARTUP_PREREG.md: round-4 Launch, settings then preview, one excluded warm-up per arm/path. '
        'Warm page cache and persistent per-arm/path XDG cache; fresh process/config/state/data/runtime. '
        'User settings.sh --page appearance and start.sh --preview, monotonic to mapped visible nonzero Sway window, 20ms polling.',
        statistics='20000 joint round-block bootstrap resamples of difference of medians, percentile 95% CI. '
        'Exploratory two-sided Mann-Whitney tie/continuity-corrected normal approximation; no threshold tuning.')
    rng = random.Random(result['seed'])
    original = startup.REPO, startup.OUTPUT
    with (output/'samples.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['path', 'round', 'order', 'arm', 'commit', 'milliseconds', 'start_monotonic_ns'])
        try:
            for kind in ('settings', 'preview'):
                values = {label: [] for label in arms}
                for label, root in arms.items():
                    stage = output/kind/label; stage.mkdir(parents=True)
                    cache = stage/'cache'; cache.mkdir()
                    startup.REPO, startup.OUTPUT = root, stage
                    with startup.Launch(kind, 'warmup', cache): pass
                for number in range(40):
                    order = list(arms); rng.shuffle(order)
                    for position, label in enumerate(order):
                        startup.REPO, startup.OUTPUT = arms[label], output/kind/label
                        started = time.monotonic_ns()
                        with startup.Launch(kind, 'round-'+str(number), startup.OUTPUT/'cache') as launch:
                            values[label].append(launch.elapsed*1000)
                        if any(bad in launch.text for bad in ('Failed to load configuration', 'ReferenceError', 'TypeError',
                                                            'Binding loop', 'Failed to start IPC server', 'Feature catalog:')):
                            raise AssertionError(launch.text)
                        revision = next(revision for arm, revision in revisions if arm == label)
                        writer.writerow([kind, number, position, label, revision, launch.elapsed*1000, started]); stream.flush()
                    if (number+1) % 5 == 0: print(f'{kind}: {number+1}/40 rounds, 3 arms', flush=True)
                result['raw'][kind] = values
                result['summary'][kind] = {label: dict(describe(data), versus_main=compare(values['main'], data),
                    versus_m4a=compare(values['m4a'], data)) for label, data in values.items()}
                (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
        finally:
            startup.REPO, startup.OUTPUT = original
    result['machine_after'] = machine()
    result['verdict'] = {kind: dict(lower_bound_ms=data['m4b']['versus_m4a']['ci95_ms'][0],
        met=data['m4b']['versus_m4a']['ci95_ms'][0] <= 10) for kind, data in result['summary'].items()}
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--head', required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.output, args.head)['summary'], indent=2))
