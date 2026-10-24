# Command output and detached job logs

2026-10-24. Implemented on the resource/lifecycle review branch.

## Owned tools: fail explicitly on oversized output

CommandRunner retains a bounded combined stdout/stderr prefix while draining both
pipes. The default is 8 MiB; niri/busctl/pw-dump allow 16 MiB, nmcli 2 MiB.
These are defensive bounds, not claims about measured maximum valid responses.
Domain code can pass a tested positive integer `max_output=BYTES` explicitly.
The byte budget is shared between stdout and stderr; it is not a character count.

On overflow, the runner continues to drain/discard until exit, its existing timeout
or cancellation. Even exit 0 produces `TOOL output exceeds N bytes`; truncated
JSON is never returned as success. Timeout/cancellation/observer errors keep their
existing messages and cleanup. Normal UTF-8 replacement, newline normalization,
secret redaction, error truncation and memfd stdin semantics remain.

This limits retained subprocess output, not every caller's parsed state or total
shell RAM. Concurrent commands have individual budgets. wl-copy still discards
its inherited output pipes; detached application spawning stays separate.

## Launchpad: cap the log, let the command finish

Each current Launchpad log is at most 8 MiB, including a single marker:

```text
[LME: output truncated at 8 MiB; remaining output discarded]
```

The prefix is retained; extra stdout/stderr is drained and discarded so the child
does not receive SIGPIPE at the cap. A small detached stdlib relay owns the pipe
and log lifetime. It uses event-driven waits while idle; a one-shot alarm is used
only to finish explicit termination of a stubborn process group.

- Zero relay processes when there are no running jobs. One relay per running job;
  the existing eight-job limit is per controller, not global across restarts.
- Shell/backend exit does not stop user jobs or their relay. Count surviving
  relays and every LME instance in whole-shell memory measurements.
- Literal argv, explicit Bash/terminal choice, cwd and normal exit/signal status
  remain. The tracked process is now the relay/group leader. It remains running
  until inherited output writers close, even if the initial child exited earlier.
- A launch/exec failure is returned through a bounded readiness handshake instead
  of being reported as a successful launch. Explicit termination targets the
  owned group; ordinary shell exit does not.
- Logs are private (0600); a symlink cannot redirect a write. A sink write failure
  discards further output and lets the command finish. If that command succeeded,
  the relay reports exit 74 (I/O failure); an existing nonzero/signal exit wins.
  A child may itself use exit 74, so inspect storage and the log when diagnosing it.

The relay-only prototype measured about 5 MiB PSS for one and 34 MiB aggregate PSS
for eight (exact final figures and combined scenarios: MIGRATION_LOG.md). User
command memory is additional. These are VM measurements, not a fixed cost promise.

This is a per-file bound, not a directory quota. Logs from removed/old IDs are not
automatically deleted. Do not rotate/delete active writers to fake a quota; a
completed-log retention policy needs a separate decision. Heavy user commands,
editors/recorders and their temporary peaks remain separate from idle shell cost.

## Scoped simultaneous VM check

Default Smoked, one virtual output, software OpenGL, weather auto-refresh and
clipboard capture off; the history worker remains active. PSS includes both
Quickshells/backends while Settings is open, plus persistent workers and relays.

| Scenario | Main 03e7006 PSS KiB | Review branch PSS KiB | Branch decimal MB |
| --- | ---: | ---: | ---: |
| Main shell + backend + history worker (3 processes) | 199,479 | 199,425 | 204.21 |
| Above + Settings and its backend (5 processes) | 365,589 | 365,670 | 374.45 |
| Above + eight jobs, including relays but excluding command payloads | 401,489 | 436,009 | 446.47 |
| Above including all eight test command payloads (branch: 21 processes) | 424,964 | 458,777 | 469.79 |

Payloads are idle Python sleep processes, not editors/upscalers/recorders. Private
Sway/D-Bus and shared OS services are outside the LME inventory. These totals meet
the stated targets only in this scenario. They do not establish Liquid, multiple
outputs, physical GPU/radio behavior or real-laptop peak memory. Eight relays add
about 34 MiB PSS; this is a bounded-log trade-off, not a RAM reduction.
