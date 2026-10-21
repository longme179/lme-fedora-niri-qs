"""Warm-cache round-robin startup and identical-main A/A; private session only."""
import argparse
import json
from pathlib import Path
import platform
import shutil
import statistics
import tempfile

import migration_startup as startup
from catalog_measurement import synthetic


def percentile(values, fraction):
    ordered = sorted(values)
    point = (len(ordered) - 1) * fraction
    lower = int(point)
    return ordered[lower] + (ordered[min(lower+1, len(ordered)-1)] - ordered[lower]) * (point-lower)


def stats(values):
    return {'median_ms': statistics.median(values)*1000, 'min_ms': min(values)*1000,
            'max_ms': max(values)*1000, 'iqr_ms': (percentile(values, .75)-percentile(values, .25))*1000}


def benchmark(main, empty, output, runs=15, compact=False):
    assert runs >= 15
    output.mkdir(parents=True, exist_ok=False)
    original_repo, original_output = startup.REPO, startup.OUTPUT
    with tempfile.TemporaryDirectory(prefix='catalog-bench-') as directory:
        projected = Path(directory)/'synthetic'
        shutil.copytree(empty, projected, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        metadata = synthetic(projected, compact)
        variants = {'main': main, 'empty': empty, 'synthetic': projected, 'aaA': main, 'aaB': main}
        result = {'runs': runs, 'machine': platform.platform(), 'cpu': next(line.split(':', 1)[1].strip()
            for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),
            'cache_policy': 'One excluded warm-up per variant/path. Reuse XDG_CACHE_HOME per variant/path; '
                'OS page cache warm, never dropped. Fresh process/config/state/data/runtime for every launch.',
            'method': 'M0 monotonic launch-to-first-visible mapped nonzero Sway window; 20ms polling.',
            'synthetic': metadata, 'raw': {}, 'summary': {}}
        try:
            for kind in ('preview', 'settings'):
                values = {key: [] for key in variants}
                for key, repo in variants.items():
                    stage = output/kind/key; stage.mkdir(parents=True)
                    cache = stage/'warm-cache'; cache.mkdir()
                    startup.REPO, startup.OUTPUT = repo, stage
                    with startup.Launch(kind, 'warmup', cache): pass
                keys = list(variants)
                for round_number in range(runs):
                    for key in keys[round_number % len(keys):] + keys[:round_number % len(keys)]:
                        startup.REPO, startup.OUTPUT = variants[key], output/kind/key
                        with startup.Launch(kind, 'round-'+str(round_number), startup.OUTPUT/'warm-cache') as launch:
                            values[key].append(launch.elapsed)
                        for bad in ('Failed to load configuration', 'ReferenceError', 'TypeError'):
                            if bad in launch.text: raise AssertionError(launch.text)
                    if (round_number+1) % 5 == 0: print(f'{kind}: {round_number+1}/{runs} rounds', flush=True)
                result['raw'][kind] = values
                result['summary'][kind] = {key: stats(data) for key, data in values.items()}
                pairs = [b-a for a,b in zip(values['aaA'], values['aaB'])]
                floor = percentile([abs(value) for value in pairs], .95)*1000
                result['summary'][kind]['noise'] = {'signed_median_ms': statistics.median(pairs)*1000,
                    'paired_difference_iqr_ms': stats(pairs)['iqr_ms'], 'absolute_p95_ms': floor,
                    'definition': '95th percentile of absolute within-round identical-main B minus A differences'}
                base = statistics.median(values['main'])
                result['summary'][kind]['deltas'] = {key: {'median_delta_ms': (statistics.median(values[key])-base)*1000,
                    'within_aa_noise': abs(statistics.median(values[key])-base)*1000 <= floor}
                    for key in ('empty', 'synthetic')}
                (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
        finally:
            startup.REPO, startup.OUTPUT = original_repo, original_output
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main', type=Path, required=True)
    parser.add_argument('--empty', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runs', type=int, default=15)
    parser.add_argument('--compact', action='store_true')
    args = parser.parse_args()
    print(json.dumps(benchmark(args.main, args.empty, args.output, args.runs, args.compact)['summary'], indent=2))
