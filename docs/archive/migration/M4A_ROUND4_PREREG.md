# M4a round 4: pre-registration

This document is committed before any round-4 measurement, profiling or gates.
It changes sample size, not the round-3 acceptance rule.

- Empty catalog, on both paths: the 95% bootstrap confidence interval of the
  difference of medians versus main includes zero, **or** its upper bound is
  at most 10 ms.
- Synthetic replacement, on both paths: the upper bound of that interval is
  at most 50 ms.
- Settings: 60 timed rounds per arm: main, main-aa, final-empty-new,
  final-replace-current (`8eabc20`), final-replace-new.
- Preview: 30 timed rounds per arm: main, final-empty-new, final-replace-new.
  This is a regression check; do not interpret an apparent improvement.

Use one randomized interleaved session, warm caches, the same machine and user
entry points as round 3 (`settings.sh` and `start.sh --preview`). Seed policy
remains deterministic (`241021`), shuffling arm order within each round.
Exclude one warm-up per arm/path; use fresh disposable XDG config/state/data/
runtime directories and a private Sway/D-Bus session. Preserve per-arm/path
cache directories. Do not run gates or profiling concurrently with this session.

Report median, IQR, min, max, difference of medians and a percentile 95% CI from
at least 20,000 **joint round-block** bootstrap resamples. Include exploratory
two-sided Mann-Whitney p-values using the round-3 implementation. Commit raw
CSV samples and machine/governor/power-state observations. Compare arms only
within this session; the A/A arm estimates repeatability without becoming a
replacement acceptance threshold. A missed rule requires reporting options
and waiting for the owner; do not tune thresholds or implement aggregate c.
