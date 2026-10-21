"""Stdlib statistics for the single, randomized warm-cache measurement session."""
import math
import random
import statistics


def percentile(values, fraction):
    ordered = sorted(values)
    point = (len(ordered)-1)*fraction
    lower = int(point)
    return ordered[lower]+(ordered[min(lower+1, len(ordered)-1)]-ordered[lower])*(point-lower)


def describe(values):
    return dict(median_ms=statistics.median(values), min_ms=min(values), max_ms=max(values),
                iqr_ms=percentile(values, .75)-percentile(values, .25))


def mann_whitney(a, b):
    """Two-sided normal approximation, average ties and continuity correction."""
    ranked = sorted((value, group) for group, values in enumerate((a, b)) for value in values)
    rank_sum, correction, index = 0, 0, 0
    while index < len(ranked):
        end = index+1
        while end < len(ranked) and ranked[end][0] == ranked[index][0]: end += 1
        rank_sum += ((index+1+end)/2)*sum(group == 0 for _, group in ranked[index:end])
        ties = end-index; correction += ties**3-ties
        index = end
    n, m = len(a), len(b); total = n+m
    u = rank_sum-n*(n+1)/2
    variance = n*m/12*(total+1-correction/(total*(total-1)))
    if not variance: return 1.0
    z = max(0, abs(u-n*m/2)-.5)/math.sqrt(variance)
    return math.erfc(z/math.sqrt(2))


def compare(base, arm, seed=241021, resamples=20000):
    """Resample round blocks jointly; compare medians, never median of differences."""
    assert len(base) == len(arm) and resamples >= 10000
    rng = random.Random(seed)
    deltas = []
    for _ in range(resamples):
        indices = rng.choices(range(len(base)), k=len(base))
        deltas.append(statistics.median([arm[i] for i in indices])-statistics.median([base[i] for i in indices]))
    return dict(delta_ms=statistics.median(arm)-statistics.median(base),
                ci95_ms=[percentile(deltas, .025), percentile(deltas, .975)],
                mann_whitney_p=mann_whitney(base, arm), resamples=resamples)
