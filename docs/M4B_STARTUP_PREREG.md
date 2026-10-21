# M4b startup pre-registration

Committed before startup measurement or production changes. The owner budget is
unchanged: the **95% CI lower bound** of added median cost versus the accepted
M4a head must be **<= 10 ms on both Settings and preview**, otherwise STOP and ask.
No threshold adjustment, selective rerun or M5 work follows a miss.

One warm-cache randomized interleaved session, seed `241021`, **40 timed rounds
per arm per path** (240 samples), one excluded warm-up per arm/path:

- `main`: starting remote main `c46f934`.
- `m4a`: accepted review head `933750f`.
- `m4b`: final production conversion head, exact SHA recorded before running.

Main and M4a have identical trees; retain them as independent A/A arms rather
than silently substituting pre-M4a main. The decisive comparison is M4b minus
M4a. Also report each arm versus main within the same session.

Reuse round-4 Launch: user `settings.sh --page appearance` and
`start.sh --preview`, fresh process/XDG config/state/data/runtime, persistent
per-arm/path cache, warm filesystem cache, private Sway and private D-Bus.
Endpoint: first visible mapped nonzero window, 20 ms polling; this is not full
feature readiness. Record machine/renderer/governor/power exposure and load.
Run no gates, profiling or builds concurrently. No real session/config is used.

Report N, median, IQR, min/max, difference of medians, 95% percentile CI from
20,000 joint round-block bootstrap resamples, and exploratory Mann-Whitney p
using the committed round-4 statistics helper. Keep all raw CSV samples.
Cold launches only; warm IPC/Gear reuse and real GPU appearance need native/manual
checks separately. No synthetic end-state or other feature conversion is included.
