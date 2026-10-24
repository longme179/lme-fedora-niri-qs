# Ported-feature follow-up: correctness before further migration

Planning review, 2026-10-23; local source pinned to main **92c74d6**.
No runtime change or further migration is authorized by this document.
Ponytail and Balanced Coupling guide the scope: repair observable failures at
existing owners, reuse services, and avoid a framework or a process per widget.

Execution authorized by the owner after commit 50194c1. First review branch:
`fix/content-result-recovery`, F1/F2 merged in main f28be3d; see MIGRATION_LOG.md.
[F3 pending ownership](F3_PENDING_OWNERSHIP_PLAN.md) is approved and implemented
on fix/action-pending-ownership for review. F4/F5 and recordStop stay later;
[ROADMAP.md](ROADMAP.md) records current coverage and remaining release criteria.

## Scope and current state

- 37/89 coordinator IDs are registered: 28 synchronous, nine workers.
  Reviewed providers: Launchpad, local content, audio/Bluetooth, windows/launcher,
  appearance/transfer, idle, Night Light, keybinds, wallpaper and Wi-Fi.
- Reviewed Clipboard transport, Notifications persistence/bootstrap, Desktop
  output/notes seams and media/lyrics presentation. This is a targeted source
  review with bounded scratch reproductions, not a whole-shell hardware audit.
- PR21 fixes are merged: Bluetooth Connect no longer blocks dispatch; backend
  notification history installs after persistence; export failures permit retry;
  conflicting Wi-Fi mutations share admission. Do not redo those changes.
- Eleven catalog records provide ten Settings pages. Schema ownership remains
  66 descriptor keys / 81 legacy keys. Stable facades and legacy actions stay.
- D1 is closed. A6 polling/cache/power-policy changes, visual redesign, bulk
  conversion and M8 file moves are outside this plan. No startup profiling.

## Findings and confidence

### F1 — Clipboard loses operation results in a request burst — high priority

Evidence: [clipboard.py](../scripts/clipboard.py#L250) reads one chunk, processes
every complete request, then publishes only the final `lastResult` on the next
loop. [ClipboardState](../qml/services/ClipboardState.qml#L62) clears `copyPending`
only on a copy result, and `searching` only on a search result.

A real worker in disposable XDG directories, capture disabled and fake wl-copy,
received `copy(valid_id)\nsearch(example)\n` in one pipe write:

```text
exit=0; published lastResults = [null, {action: search, ok: true, sequence: 2}]
```

Copy succeeded but sequence 1 was never delivered. The inverse order can lose
search completion. UI consequences follow from its reducer; the scratch probe
did not drive the visible UI. Existing worker tests usually await each command.

Plan: publish a result-bearing snapshot after **each** processed command, reusing
the current JSON shape/sequence and state-signature suppression. Do not introduce
a response queue, timer or transport. Quiet unsolicited snapshots stay suppressed.
Keep copy/search error handling, capture ownership and 20–500 history limit.
Cost: burst snapshots increase serialization; history is already bounded. Avoid
retaining a list of snapshots or materializing full image payloads for delivery.

### F2 — Notification save failures have no visible recovery path — medium priority

The backend now correctly retains old memory/disk on failure. However,
[Notifications](../qml/services/Notifications.qml#L32) schedules saves on history
changes/backend readiness and never consumes their outcomes. The status filter in
[ShellState](../qml/services/ShellState.qml#L199) suppresses `notificationSave`
errors as well as success messages. A failure can therefore remain invisible;
without another triggering change/reconnect there is no scheduled retry. Local
notifications often trigger another change when they expire, so do not claim
every failure remains permanently unsaved. This finding is source-verified;
failure/recovery through native UI still needs a regression fixture.

Plan: Notifications owns a dirty revision, the submitted revision and a small
save-error state. Reuse the 500 ms debounce; only one save is in flight. Clear
dirty only for the revision actually saved; changes during a save schedule the
latest state after its result. Failure preserves dirty and offers Retry in the
center, with no recursive error notification, infinite automatic retry or new
periodic timer. Backend reconnect/new history still permits another attempt.
Transient entries, DND/muting, expiry and immutable closed history stay unchanged.
No history/settings format change and no retained second full history copy.

### F3 — Duplicate rejection can clear another job's UI busy flag — medium priority

[start_feature](../scripts/desktop_backend.py#L1123) correctly rejects duplicate
ownership. [ShellState.accept](../qml/services/ShellState.qml#L192) deletes the
action's pending flag for any non-pending result, including that rejection.
An actual backend + ManualExecutor trace, with the QML deletion rule applied:

```text
seq1: bluetoothDevice pending; backend jobs=[bluetoothDevice]; UI pending=true
seq2: duplicate rejected;     backend jobs=[bluetoothDevice]; UI pending=false
seq3: original completes;     backend jobs=[]
```

This is a protocol/reducer mismatch, not failed backend serialization. Ordinary
Bluetooth/Wi-Fi buttons already disable duplicate submits, reducing exposure;
no normal mouse-only reproduction is claimed. Do not classify it as a new Wi-Fi
radio bug or parse the English rejection message to infer ownership.

Plan first: characterize repeated requests, completion/error, reconnect and
fileSearch replacement. Preferred authoritative fix: expose active job ownership
from the **existing** job table and combine it with unsent/unacknowledged UI work;
do not add a second scheduler. An additive snapshot field is a public data-format
change and needs explicit approval before implementation. A per-surface duplicate
guard is cheaper but only mitigation; a broad run() guard would incorrectly drop
slider updates, setting patches and replacing file searches. Do not ship that.

### F4 — Launchpad output is bounded neither by size nor by job duration — medium priority

[Launchpad.run](../scripts/launchpad.py#L43) caps active/tracked jobs at 8/100,
but stdout/stderr write directly to an O_TRUNC file until the command exits.
A finite producer emitted 5,242,880 bytes; its log contained exactly that many
bytes, exit 0. This confirms absent output retention bounds, not an observed
disk exhaustion or a shell RAM leak. Restarting a shell does not own/kill these
detached user commands; preserve that distinction.

Proposed policy: retain a bounded prefix plus a truncation marker; continue
draining/discarding excess output so commands can finish. A possible starting
limit is 8 MiB per entry; settle the policy before coding. Preserve explicit
Bash/argv/terminal selection, log privacy and useful launch/exit failures.
Per-file caps do not bound the whole log directory: deleted entries can leave
old logs. Any later retention cleanup must distinguish still-running detached
writers; deleting or rotating an unknown open file is not a safe quota policy.

Implementation trade-off requiring review:

- A small detached relay per **running background job** can enforce a live cap
  and survive shell exit. It adds processes/RSS; account for all eight jobs,
  readiness/error handshake, inherited descriptors and EOF/exit cleanup. This
  is a conditional proposal, not a free memory optimization or new daemon.
- Completed-log cleanup needs no relay but cannot bound an actively written
  log. It is not a complete remedy for this finding.
- Reject RLIMIT_FSIZE/SIGXFSZ (can fail user commands), renaming an open log
  (the writer retains its inode), and closing a pipe at the cap (SIGPIPE).
- Do not reuse managed_command.py unchanged: its parent-death behavior kills
  backend-owned tools and conflicts with Launchpad's detached ownership.

### F5 — Shared command capture has no retained-output bound — hardening candidate

[CommandRunner.run](../scripts/command_runner.py#L48) uses communicate(); limiting
the error message to 350 characters happens after capture. A finite fake tool
returned 8,388,608 characters successfully. No real installed helper was found
misbehaving, and no RSS/leak claim follows from that probe.

Plan: inventory output contracts first (JSON/text, valid largest response,
stdout/stderr, Wi-Fi observer). Then add bounded draining using the existing
runner lifetime/cancellation path, with domain-appropriate limits. Overflow must
be a clear redacted error, never successful truncated JSON. Preserve timeout,
process-group teardown, memfd secrets, observer semantics and wl-copy pipe rules.
This is subprocess retention hardening, not an A6 cache/polling change. Keep
detached application spawning separate; time-box if runner teardown must change.

## What should remain stable

| Reviewed area | Assessment and next action |
| --- | --- |
| Wi-Fi / Bluetooth | Recent fixes address confirmed dispatch/admission/authentication faults. Keep conservative mutation ownership and bounded authentication checks. Validate slow DHCP, adapter removal and BlueZ in a real session; do not rewrite around another shell's CLI. |
| Appearance / transfer / schema | Export recovery and explicit portable membership are present. Keep Preferences lock/reload/merge/token/fsync/replace, named resolvers and schema ownership. Slow filesystem blocking remains a risk, not a measured defect justifying mechanical async conversion. |
| Launcher / compositor / local content | Literal argv, current-window/file validation and history scoring remain at their owners. No new correctness defect established in these handlers. gio/niri command waits are still synchronous and bounded; lack of a bug report is not a latency guarantee. |
| Idle / Night Light / keybinds | Narrow providers retain existing lifecycle/state readers. Settings IPC can wait for its timeout. No new failure demonstrated; power policy/cadence and hardware behavior stay outside this work. |
| Wallpaper / Weather | Registered scan/status/ensure fit the worker contract; mutation/search and other controllers retain their different contracts. Weather already hides a forecast from an old location/unit. Do not merge executors or alter retries/TTLs as incidental cleanup. |
| Desktop / notes / media / lyrics | Output variants, bounded widgets, dirty/conflict notes and keyed lyrics responses already have useful guards. LME LyricsSession rejects stale song keys, stops unused lookups and schedules cue boundaries. No demonstrated need to rewrite these. Output hotplug, external-note races and renderer behavior still need session checks. |

## Proposed implementation sequence

Each branch needs owner authorization; the names below are proposals.

1. **fix/content-result-recovery**: F1, then F2; one tests/implementation pair
   per feature and final docs. Small/medium, bounded scope, no registry migration.
   New tests: Clipboard burst copy/search in both orders and split/combined reads,
   copy error then search, pending clears after close/reopen; Notification save
   failure, successful Retry, mutation while saving, backend loss and no error
   notification loop. Native copied-checkout fixtures exercise visible recovery.
2. **fix/action-pending-ownership**: F3 only, after approving the ownership
   contract. Medium risk. Pin ack-before-completion, rejection versus original
   job, synchronous actions, fileSearch replace/cancel, error and backend restart.
   Keep old result/sequence readers compatible; no request queue or universal bus.
3. **fix/bounded-command-output**: F5, then F4 only if a detached logging policy
   and its process/memory cost are accepted. Separate logical commits; skip F4
   if it needs a new general job framework. Test finite/noisy tools, both output
   streams, multibyte boundaries, redaction, timeout/cancel, inherited pipes and
   ENOSPC. For Launchpad add shell-exit survival, terminal behavior, launch/exit
   errors and repeated jobs. Never test exhaustion on a real filesystem.
4. Only afterward consider **recordStop** as the next small migration, using
   ASYNC_ACTIONS.md. The other twenty legacy async IDs still need explicit
   preflight/admission/cancellation/lease/controller seams; no bulk port now.

Expected change surfaces (plus focused tests/docs, without file moves):

| Item | Owners to touch |
| --- | --- |
| F1 | scripts/clipboard.py; ClipboardState/ClipboardPanel only if burst UI tests require a latest-search guard. Include Enter during overlapping searches in native coverage. |
| F2 | Notifications.qml and NotificationCenter.qml; reuse existing backend notificationSave/storage unchanged. |
| F3 | ShellState.qml and desktop_backend.py's existing ownership/publication seam; no domain rule copied into ActionRegistry. |
| F4 | launchpad.py, a domain-owned relay if accepted, and LaunchpadEditor only for necessary log feedback; no Utilities-to-Launchpad implementation import. |
| F5 | command_runner.py and callers whose documented output contract needs an explicit bound; preserve public import facades. |

Affected gates follow STATE: Python G0 + focused tests; QML G0 + G1 + native
case. Final runtime review runs G0–G4/G6 once and the single launch/RSS sanity
check. Existing assertion changes require approval; revert a failed change.
No new dependency exceptions, backend/executor per feature or default changes
hidden inside refactors. Withdrawal, preview/demo and Settings remain covered.

Memory acceptance: <=400 MB steady / <=500 MB ordinary active whole-shell use,
including owned workers and open Settings; use aggregate PSS when available.
Recent per-instance pairs (286,818 KiB preview and 238,726 KiB Settings) are **not** a
combined-session total. No memory saving is claimed by this plan. Account for
additional live logging relays explicitly; heavy user jobs/editor peaks are
reported separately, without excluding LME-owned persistent helpers.

## External code and theory: borrow principles, not assumptions

Sources below were read at the pinned commits; none were benchmarked against
LME. Similar UI appearance does not establish better lifecycle or resource use.

| Reference | Useful principle / limitation for LME |
| --- | --- |
| [DMS request dispatch][dms-rpc] and [Clipboard callbacks][dms-clip] | Correlate callbacks to request IDs and fail pending callbacks on disconnect. Relevant to F1/F3. LME can fix F1 with ordered existing results; do not copy a socket backend, per-request timers or RPC framework. DMS timeouts are optional, so request IDs alone are not a universal liveness guarantee. |
| [DMS Bluetooth busy state][dms-bt] | Derive device busy from pairing/connecting/disconnecting state. Good UI feedback principle; it supplements, rather than replaces, backend admission. Keep LME's current BlueZ agent and ownership. |
| [Noctalia process draining][noctalia-output] | Bound retained bytes while continuing to drain; report truncation. Useful for F5 and F4's output principle. This is C++ managed-process capture, not a ready-made detached Launchpad log solution; callbacks and default limits also need scrutiny. |
| [DMS history writes][dms-history] / [Caelestia history writes][cael-history] | Both debounce persistence. LME already does that. The inspected DMS function logs save errors; Caelestia schedules setText. These sections do not establish F2-style retry/dirty acknowledgement, so copying them would not prove recovery. |
| [Noctalia history publication][noctalia-history] | Temporary file + rename is a useful publication pattern, but this function does not explicitly fsync or enforce LME's file/lock policy. Keep LME's stronger existing storage helper; do not replace it from this snippet. |
| [end4-pC Network][end4-network] / [Lyrics][end4-lyrics] | Network exposes process-derived busy/error state; its password-change path passes secrets via environment/Bash, which LME should not adopt over stdin/memfd. Lyrics uses binary search/cue timers, already adopted in LME; keep LME's song-key stale-result guard. No polling/cache changes proposed. |
| [Caelestia launcher actions][cael-actions] | Declarative literal command lists and detached execution reinforce LME's existing argv/ownership split. No bounded log contract is shown here; it does not solve F4. |
| [Serpantinum GlassLens][serp-lens] / [nesting][serp-nest] | Coalesced sync via Qt.callLater is useful, but the lens also owns edge animations/settling and nesting walks up to 48 ancestors. Do not infer cheaper GPU use or copy these into every LME control; retain shared backdrop/current effects pending a separate real-GPU problem. |

Theory: [Python communicate()][python-process] explicitly warns output is buffered
in memory; a timeout is not an output bound. [Qt Quick performance][qt-perf]
recommends asynchronous work and short blocking handlers; LME's coordinator is
separate from QML, but blocking it still delays UI state/acks. [Notification
protocol][notification-spec] distinguishes replacements, transient history and
expiry: preserving those is part of F2, not optional cleanup. [RLIMIT_FSIZE][rlimit]
can signal a writer, hence is unsuitable as transparent log truncation.
[Balanced Coupling][coupling] supports keeping volatile domain rules together
and sharing small contracts; it does not require splitting stable handlers into
new processes or migrating every legacy branch.

This planning branch runs G0 only; native/device/GPU performance and aggregate
live-session memory remain unverified. Implementation begins only after review.

[dms-rpc]: https://github.com/AvengeMedia/DankMaterialShell/blob/b7be4a344a148768f3e931ab70386d13c73185cf/quickshell/Services/DMSService.qml#L375-L446
[dms-clip]: https://github.com/AvengeMedia/DankMaterialShell/blob/b7be4a344a148768f3e931ab70386d13c73185cf/quickshell/Services/ClipboardService.qml#L305-L349
[dms-bt]: https://github.com/AvengeMedia/DankMaterialShell/blob/b7be4a344a148768f3e931ab70386d13c73185cf/quickshell/Services/BluetoothService.qml#L443-L456
[dms-history]: https://github.com/AvengeMedia/DankMaterialShell/blob/b7be4a344a148768f3e931ab70386d13c73185cf/quickshell/Services/NotificationService.qml#L170-L183
[noctalia-output]: https://github.com/noctalia-dev/noctalia-shell/blob/5f90509b7d0a4bc0c2c6d124cc0bf9ec101909c5/src/core/process/process.cpp#L257-L284
[noctalia-history]: https://github.com/noctalia-dev/noctalia-shell/blob/5f90509b7d0a4bc0c2c6d124cc0bf9ec101909c5/src/notification/notification_history_store.cpp#L642-L691
[end4-network]: https://github.com/pctrade/end4-pC/blob/abde3ab4d8e388280b0837879fd25e1f4a794297/services/Network.qml#L76-L145
[end4-lyrics]: https://github.com/pctrade/end4-pC/blob/abde3ab4d8e388280b0837879fd25e1f4a794297/services/LyricsService.qml#L55-L123
[cael-history]: https://github.com/caelestia-dots/shell/blob/0b0beb520a36f6972999c2afc97b311a27ba87f0/services/Notifs.qml#L41-L82
[cael-actions]: https://github.com/caelestia-dots/shell/blob/0b0beb520a36f6972999c2afc97b311a27ba87f0/modules/launcher/services/Actions.qml#L34-L59
[serp-lens]: https://github.com/ilyamiro/serpantinum/blob/e0c1d79375bc7adfd01fecb8a4e319d521df1ea9/src/quickshell/reusables/display/GlassLens.qml#L112-L143
[serp-nest]: https://github.com/ilyamiro/serpantinum/blob/e0c1d79375bc7adfd01fecb8a4e319d521df1ea9/src/quickshell/reusables/display/glassNesting.js#L3-L21
[python-process]: https://docs.python.org/3/library/subprocess.html#subprocess.Popen.communicate
[qt-perf]: https://doc.qt.io/qt-6/qtquick-performance.html#general-performance-tips
[notification-spec]: https://specifications.freedesktop.org/notification-spec/latest-single/
[rlimit]: https://man7.org/linux/man-pages/man2/setrlimit.2.html
[coupling]: https://coupling.dev/
