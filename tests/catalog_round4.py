"""Pre-registered round-4 session; invoke inside run-gates' disposable compositor."""
import argparse
import csv
import json
from pathlib import Path
import random
import time

from catalog_end_state import replace_legacy
from catalog_round3 import checkout, machine
from catalog_statistics import compare, describe
from feature_catalog import canonical_index
import migration_startup as startup


def benchmark(output, head):
    output.mkdir(parents=True, exist_ok=False)
    revisions = [('main', '186354a', 'empty'), ('main-aa', '186354a', 'empty'),
        ('final-empty-new', head, 'empty'), ('final-replace-current', '8eabc20', 'replace'),
        ('final-replace-new', head, 'replace')]
    arms = {}; models = {}
    for label, revision, mode in revisions:
        root = output/'checkouts'/label; root.parent.mkdir(exist_ok=True)
        checkout(root, revision)
        if mode == 'replace':
            metadata = replace_legacy(root)
            index = root/'config/features.json'
            index.write_text(canonical_index(json.loads(index.read_text())))
            metadata['json_bytes'] = index.stat().st_size + sum((root/item['descriptor']).stat().st_size
                for item in json.loads(index.read_text())['features'])
            metadata['index_bytes'] = index.stat().st_size
            models[label] = metadata
        arms[label] = root
    assert (arms['final-replace-current']/'config/features.json').read_bytes() == (
        arms['final-replace-new']/'config/features.json').read_bytes()
    plan = [('settings', 60, list(arms)),
        ('preview', 30, ['main', 'final-empty-new', 'final-replace-new'])]
    result = dict(seed=241021, arms=revisions, plan=plan, models=models,
        machine_before=machine(), raw={}, summary={},
        method='Round-3 Launch: warm page cache and per-arm/path XDG cache after one excluded warm-up; '
        'fresh process/config/state/data/runtime. User settings.sh --page appearance or start.sh --preview. '
        'Monotonic launch to first visible mapped nonzero Sway window, 20ms polling. '
        'One seeded random shuffle per round, Settings then Preview, one session. '
        'Both replacement arms use the same canonical index bytes; no production instrumentation.',
        statistics='20000 joint round-block bootstrap resamples of difference of medians; percentile 95% CI. '
        'Exploratory two-sided Mann-Whitney normal approximation with tie/continuity correction, '
        'not adjusted for multiple comparisons. Acceptance is docs/M4A_ROUND4_PREREG.md.')
    rng = random.Random(result['seed'])
    original = startup.REPO, startup.OUTPUT
    with (output/'samples.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['path', 'round', 'order', 'arm', 'commit', 'mode', 'milliseconds', 'start_monotonic_ns'])
        try:
            for kind, rounds, labels in plan:
                values = {label: [] for label in labels}
                for label in labels:
                    stage = output/kind/label; stage.mkdir(parents=True)
                    cache = stage/'cache'; cache.mkdir()
                    startup.REPO, startup.OUTPUT = arms[label], stage
                    with startup.Launch(kind, 'warmup', cache): pass
                for number in range(rounds):
                    order = list(labels); rng.shuffle(order)
                    for position, label in enumerate(order):
                        startup.REPO, startup.OUTPUT = arms[label], output/kind/label
                        started = time.monotonic_ns()
                        with startup.Launch(kind, 'round-'+str(number), startup.OUTPUT/'cache') as launch:
                            values[label].append(launch.elapsed*1000)
                        for bad in ('Failed to load configuration', 'ReferenceError', 'TypeError', 'Binding loop',
                                    'Failed to start IPC server', 'Feature catalog:'):
                            if bad in launch.text: raise AssertionError(launch.text)
                        revision = next(row for row in revisions if row[0] == label)
                        writer.writerow([kind, number, position, *revision, launch.elapsed*1000, started]); stream.flush()
                    if (number+1) % 5 == 0:
                        print(f'{kind}: {number+1}/{rounds} rounds, {len(labels)} arms', flush=True)
                result['raw'][kind] = values
                result['summary'][kind] = {label: dict(describe(data), comparison=compare(values['main'], data))
                    for label, data in values.items()}
                (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
        finally:
            startup.REPO, startup.OUTPUT = original
    result['machine_after'] = machine()
    result['verdict'] = {}
    for kind, data in result['summary'].items():
        empty = data['final-empty-new']['comparison']['ci95_ms']
        replace = data['final-replace-new']['comparison']['ci95_ms']
        result['verdict'][kind] = dict(empty_pass=(empty[0] <= 0 <= empty[1] or empty[1] <= 10),
            replace_pass=replace[1] <= 50)
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--head', required=True)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.output, args.head)['summary'], indent=2))
