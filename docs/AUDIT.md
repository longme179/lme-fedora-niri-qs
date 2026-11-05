# LME Shell — defect audit

**Date:** 2026-11-03 · **Baseline:** `578c135` (merge of PR #46) · **Target:** Fedora 44, niri 26.04, Quickshell 0.3.2, Python 3.14.8, Lenovo IdeaPad Gaming 3 15ARH7 (Radeon iGPU), eDP-1 1920×1080 @ 120.002 Hz.

Method: read `README.md`, `THIRD_PARTY.md`, `docs/STATE.md`, `docs/ROADMAP.md`, `docs/INIR_PORT.md`, `docs/VALIDATION.md`, `docs/TROUBLESHOOTING.md`, `docs/ARCHITECTURE.md` and the code cited below; then ran the read-only commands listed at the end. The live shell was observed only through `quickshell -c lme-shell ipc`; it was never touched, restarted or reconfigured. Nothing was installed and nothing under `~/.config` was written.

Severity: **critical** = unusable or irreversible data loss; **high** = a documented gate or safety net is broken, or user settings can be lost; **medium** = user-visible cost, privacy or diagnosability; **low** = latent or cosmetic.

## Summary

38 findings: 0 critical, 6 high, 15 medium, 17 low. Two independent stories dominate:

1. **The regression gate is red on the owner's machine.** `./scripts/check.sh` runs 1001 tests and ends `FAILED (failures=59, errors=4, skipped=181)`. Six independent fixture defects explain all 63 failures (A-02, A-03, A-07…A-10). None of them is a product regression, but until they are fixed the gate cannot tell a regression from a fixture bug.
2. **`settings.json` is not safe against its own failure modes.** A truncated file silently resets every preference on the next write (A-04); a single oversized number in a hand-edited file crashes the backend at startup (A-05); keys the current build does not know are erased on the next write (A-11); and an exception type outside a five-class tuple kills the backend, which only retries three times (A-06).

## Main table (confirmed = reproduced by a command; read = seen in code)

| ID | Sev | Location | Evidence | Status | One-line fix |
| --- | --- | --- | --- | --- | --- |
| A-01 | high | `scripts/check.sh:8` | `Ran 1001 tests in 141.957s` / `FAILED (failures=59, errors=4, skipped=181)`, exit 1 | confirmed | Make the gate green (or explicitly skip environment cases) before documenting it as the regression gate. |
| A-02 | high | `tests/test_local_qml.py:41` | `env = dict(os.environ, QT_QPA_PLATFORM="offscreen", …)`; log `WARN: WAYLAND_DISPLAY is present but QT_QPA_PLATFORM is "offscreen"` then `AssertionError: 0 != 1`; 37 failures share this cause | confirmed | Run native fixtures on the caller's Wayland platform, or `skipUnless` a compositor is present. |
| A-03 | high | `tests/catalog_admission_fixture.py:28` | `for name in ('settings.sh', 'feature_catalog.py'):` copies two scripts only; `scripts/feature_catalog.py:9` imports `catalog_metadata` → `ModuleNotFoundError: No module named 'catalog_metadata'`; 13 failures | confirmed | Copy the entry point's real module set (or `scripts/`) and fail the fixture loudly if the copy cannot import. |
| A-04 | high | `scripts/desktop_backend.py:449` | `except (OSError, UnicodeError, json.JSONDecodeError): pass` — a truncated `settings.json` leaves defaults in memory; the next `update()` writes them back (`:483`). Reproduced: `accent` reverted to `#9580ff` | confirmed | Record the load failure and refuse to rewrite (or back up first) until a valid parse succeeds. |
| A-05 | high | `scripts/desktop_backend.py:294` | `… and type(value) in (int, float) and math.isfinite(value)` — `math.isfinite(10**400)` raises `OverflowError`; `reload()` catches only `ValueError` (`:437`) and `handle()` does not catch it. Reproduced: `startup raised: OverflowError` | confirmed | Bound integers (`abs(v) <= 2**53`) before `math.isfinite`, and catch `ArithmeticError` in the validator and in `handle()`. |
| A-06 | high | `scripts/desktop_backend.py:1376` | `except (CommandError, ValueError, TypeError, KeyError, OSError)`; `action_pending.py:23` handles only JSON errors; `main` catches only `(KeyboardInterrupt, BrokenPipeError)` (`:1701`); `ShellState.qml:229` retries three times | confirmed (one instance) | Catch `Exception` per input line and per job, return `{ok:false}`, keep the loop alive. |
| A-07 | medium | `tests/schema_fixture.py:47` | `value.replace(str(Path.home()), '<HOME>').replace(str(Path.cwd()), '<ROOT>')`; actual `"<HOME>/lme-fedora-niri-qs/bad"` vs golden `"<ROOT>/bad"`; 6 failures | confirmed | Normalize the longest prefix first (cwd before home), or compare `resolve()`d paths. |
| A-08 | medium | `tests/test_recording.py:144` | `[('mp4','libx264'),('mov','libx264'),('webm','libvpx-vp9')]`; `ffmpeg failed (8): Unknown encoder 'libx264'` with `ffmpeg-free-8.1.3-1.fc44` | confirmed | Probe encoders first and `skipUnless`, instead of erroring. |
| A-09 | medium | `tests/test_personalization.py:60` | test isolates `PATH` only; `scripts/settings.sh:47-48` prefers `$XDG_DATA_HOME/lme-shell/deployment/bin/quickshell`, which exists here → real Settings launched, `TimeoutExpired … after 4 seconds`; `test_features.py:100` fails the same way (255) | confirmed | Isolate `XDG_DATA_HOME` in both tests. |
| A-10 | medium | `tests/test_infrastructure.py:154` | `subprocess.run([sys.executable, '-c', code, …])` with `import display_control` and no `PYTHONPATH`; same in `tests/test_launchpad_logs.py:95` (`from launchpad import …`); 2 failures | confirmed | Pass `PYTHONPATH=<repo>/scripts` to the child, or set it in `check.sh`. |
| A-11 | medium | `scripts/desktop_backend.py:483` | `self._write({**self.values, **values})` where `self.values` was rebuilt from defaults plus keys that validated (`:434-443`); reproduced: `futureSetting` disappeared after one `opacity` update | confirmed | Keep unknown keys from the raw document (or refuse the rewrite) instead of rebuilding from validated values only. |
| A-12 | low | `config/clipboard.json:40`, `scripts/clipboard.py:160` | `"clipboardEnabled"` defaults `true`; capture is bounded (100 items / 64 MB) but never expires; sensitive selections are already skipped (`CLIPBOARD_STATE` check); store = 9 355 264 bytes after ~3 days | confirmed | Keep as is if intended; otherwise make history opt-in and add a TTL. |
| A-13 | medium | `config/niri/lme-shell.kdl:7`, `scripts/start.sh:99` | `spawn-sh-at-startup "exec …/start.sh"` and `exec "$qs_binary" -c "$config_name"` — no redirection; `journalctl --user -b` has no shell/niri lines | confirmed | Redirect stderr to a bounded, rotated file under `$XDG_STATE_HOME` and show its path in Settings → About. |
| A-14 | medium | `scripts/desktop_backend.py:470` | `os.open(self.path.with_suffix(".lock"), …)` then `fcntl.flock(lock, fcntl.LOCK_EX)` — no timeout; same pattern in `scripts/storage.py:33` | read | Bounded `LOCK_EX\|LOCK_NB` retry (≈2 s) with a visible error. |
| A-15 | medium | `qml/services/ShellState.qml:180` | `if (draggingWindow \|\| JSON.stringify(next.niri) === JSON.stringify(niri)) next.niri = niri;` plus re-serialization of `apps`, `launcherUsage`, `preferences` on every snapshot | read | Send per-section revision counters from the backend and compare integers. |
| A-16 | medium | `scripts/desktop_backend.py:1128` | `system.update(tempC=…, battery=…, network=…, audio=…, microphone=…, brightness=…, charging=…, recording=…)` inside the ≥1.5 s sample, on the main thread | read | Move the chain to the worker pool or use Quickshell `Pipewire`/`UPower` services. |
| A-17 | medium | `scripts/settings.sh:67` | `"$qs_binary" -p "$entry" kill` runs whenever the IPC reply is not `true`, without checking whether the window holds unsaved edits | read | Treat "no instance" as "launch"; kill only on a real error and only after `startupPending` is false. |
| A-18 | medium | `docs/VALIDATION.md:1684` | `The cloud compositor is Sway/software rendering, not niri on Radeon. **Native full-screen blur remains unverified on the target Lenovo**` | confirmed (doc) | Track the laptop matrix as a release gate instead of prose. |
| A-19 | low | `qml/services/ShellState.qml:208` | `!["calculate", …, "networkRefresh", …].includes(next.lastResult.action)` — `ok:false` messages for these actions are dropped | read | Show every `ok:false` message; keep the list only for successful routine actions. |
| A-20 | low | `qml/services/ShellState.qml:171` | `if (!next.apps \|\| !next.system \|\| !next.niri) return;` — a malformed snapshot disappears without a log line | read | Log once per contract break and surface a status message. |
| A-21 | low | `scripts/storage.py:18` | `os.replace(temporary, path)` after `fsync` of the file only; `desktop_backend.py:497` does the same; `deploy_state.py:42-44` does fsync the directory | read | `os.fsync(os.open(path.parent, os.O_RDONLY))` after replace in both writers. |
| A-22 | low | `docs/ARCHITECTURE_AUDIT.md:4` | `**Baseline:** `1f54934`` dated 2026-10-20, still in `docs/` and absent from the README doc index | read | Move to `docs/archive/` or stamp it superseded by this file. |
| A-23 | low | `README.md:503` | `Native UI checks require a private Wayland session.` while `scripts/check.sh:8` runs them unconditionally and they fail | read | Align the sentence with the gate (skip markers) or the gate with the sentence. |
| A-24 | low | `qml/theme/Theme.qml:23` | `catch (error) { console.warn("Glass controls could not be loaded:", error); }` — same for palettes (`:57`) and tokens (`:83`); no UI state | read | Route theme-load failure into the existing status/FeatureCatalog diagnostic. |
| A-25 | low | `scripts/command_runner.py:113` | `try: process.wait(timeout=.5)` inside `run()`'s `finally` — a child stuck after `SIGKILL` raises `TimeoutExpired`, masking the original `CommandError` | read | Catch `TimeoutExpired` around that wait and re-raise the original error. |
| A-26 | low | `scripts/storage.py:24` | `json.loads(path.read_text(encoding="utf-8"))` with no size bound, used for `settings.json` (`desktop_backend.py:432`) and notification history (`:649`) | read | `stat()` first and refuse above a small bound. |
| A-27 | low | `scripts/desktop_backend.py:1690` | `error = handle_line(backend.handle, line)` / `emit(backend)` inside the `while b"\n" in input_buffer` loop — one full snapshot (two `niri msg` calls) per queued request | read | Coalesce results per `select()` batch and emit once. |
| A-28 | low | `scripts/desktop_backend.py:443` | `values["recordingEncoder"] = "auto"` / `self.values = values` — `reload()` assigns without the lock that `update()` holds (`:470-472`), while workers call `preferences.set()` | read | Guard reload's assignment with the same lock/mutex as `update()`. |
| A-29 | medium | `qml/services/ShellState.qml:229` | `if (root.restartAttempts < 3) { root.restartAttempts++; root.restartTimer.restart(); }` and nothing clears `statusMessage` when `backendReady` returns to true | read | Retry with capped backoff (or an IPC restart), and clear the banner on reconnect. |
| A-30 | medium | `shell.qml:199-206` | `interval: 1200; repeat: true; running: root.screenshotPath !== ""` with `if (!ShellState.backendReady) return;` before `stop()` and the only `Qt.quit()` inside `grabToImage` | read | Add a hard deadline that logs and quits. |
| A-31 | medium | `qml/services/Notifications.qml:62` | `onHistoryChanged: { if (enabled && historyLoaded && …) { historyRevision++; if (!saving) persistDelay.restart(); } }` — runs for `active`/`popup` changes that are not persisted | read | Persist only when a serialized projection of persisted fields changes. |
| A-32 | medium | `qml/services/Notifications.qml:15`, `qml/services/FeatureCatalog.qml:24` | `readonly property bool enabled: !ShellState.backendReady \|\| ShellState.settingsPageAvailable("notifications")`; `fail()` latches with `if (error) return;` | read | Gate on the feature's own enabled flag rather than an optional settings page, and allow a bounded catalog retry. |
| A-33 | low | `qml/services/OSDManager.qml:12` | `const name=selected === "focused" ? … : selected;` then `for (const screen of Quickshell.screens) if (name === "all" \|\| screen.name===name)` — no match means no OSD at all | read | Fall back to the focused or first screen when the configured output is absent. |
| A-34 | low | `qml/services/ShellState.qml:158` | `if (action === "imageAnnotate" \|\| action === "chargeMode" && !demo \|\| […].includes(action)) closePanels();` — `&&` binds tighter than `\|\|` | read | Parenthesize `(action === "imageAnnotate" \|\| action === "chargeMode") && !demo`. |
| A-35 | low | `qml/theme/Theme.qml:56` | `const data = JSON.parse(text()); root.paletteCatalog = data.palettes; root.paletteSchemes = data.schemes;` — used at `:48` as `paletteCatalog.find(…)` | read | `Array.isArray(data.palettes) ? data.palettes : []`, same for `schemes`. |
| A-36 | low | `config/niri/media-keys.kdl:16` | `XF86AudioMicMute allow-when-locked=true {` / `spawn "wpctl" "set-mute" "@DEFAULT_AUDIO_SOURCE@" "toggle";` | read | Drop `allow-when-locked` for the microphone bind only. |
| A-37 | low | `scripts/install.sh:80` | `mv -- "$target" "$backup"` after the guard at `:53-57` rejects only `/` and repo paths — `--replace --target ~/.config` would relocate it | read | Require the target to be absent, empty, or a symlink. |
| A-38 | low | `scripts/shell_update.py:162` | `self.git('…', 'clone', '--depth', '1', '--branch', 'main', '--', SOURCE_URL, str(temporary), timeout=120)` then `subprocess.run(['bash', str(target/'scripts/install.sh'), …])` | read | Pin/verify a release tag before executing downloaded code (owner decision). |

### Gate root causes (A-01…A-03, A-07…A-10)

All 63 failures are test-side. `scripts/check.sh` itself is correct, but it runs under `set -e`, so the failing `unittest` stage (`:8`) aborts it before the `bash -n` loop (`:9-11`) and the demo-snapshot check (`:12`); those two stages were therefore run separately and pass (`bash -n done`, `Demo backend snapshot: valid`).

Attribution by stage of the 63 failures: 37 Wayland/offscreen (A-02; 31 via `test_local_qml.run_qml`, 6 via `tests/test_settings_startup.py:97`), 13 stale catalog fixture (A-03), 6 checkout-under-`$HOME` normalization (A-07), 3 missing `libx264` (A-08), 2 managed-binary precedence (A-09), 2 missing `PYTHONPATH` (A-10).

Each cause was narrowed to a single mechanism: A-02 by the `LOCAL_QML_RESULT`-missing log with the offscreen warning; A-03 by the `ModuleNotFoundError` traceback; A-07 by the `<HOME>` vs `<ROOT>` diff; A-08 by `Unknown encoder 'libx264'`; A-09 by the `bash -x` trace showing the managed binary and by the same test passing with an isolated `XDG_DATA_HOME`; A-10 by both tests passing when run with `PYTHONPATH=scripts:tests`.

### Settings-safety notes (A-04, A-05, A-11)

These three share one file and one code path, so they should be fixed together: `Preferences.reload()` (`:425-451`), `Preferences.update()` (`:462-484`) and `_write()` (`:486-503`).

- A-04 is a silent **data reset**: the last valid snapshot is not kept once the file becomes unreadable; `reload()` only keeps the previous in-memory values while the process is alive, and a fresh `Preferences` starts from `DEFAULT_PREFERENCES`. The standalone Settings app starts a fresh backend, so opening Settings after a corrupt write also loses the old values.
- A-05 is a **crash**: an integer literal with more than 308 digits appears in any of the float-validated keys (`desktopShapeScale`, `desktopShapeOpacity`, `desktopShapeSpeed`, `notificationOpacity`, `paletteContrast`, `motionSpeed`, `motionBounce`) makes startup raise `OverflowError` before the shell has a backend.
- A-11 is **forward-compatibility loss**: a settings file written by a newer build (or hand-edited) loses every key the running build does not validate.

## Suspected (not reproduced)

- **S-01 — Idle CPU/RAM claim is unverifiable here.** The agent sandbox uses a private PID namespace, so `pgrep`/`/proc` cannot see Quickshell; the only visible cgroup (`app-niri-lme\x2dshell-3212.scope`) spans the whole session (876 pids, 9.35 GB). The `≤400 MB` acceptance in `docs/ROADMAP.md` is taken from the owner's btop observation, not re-measured.
- **S-02 — Native blur and 120 Hz pacing on the Radeon remain unverified by the project's own docs** (`docs/VALIDATION.md:1146`, `:1684`). The live niri config does include `~/.config/lme-shell/liquid-blur.kdl` (`passes 2`, `offset 3.0`), so the path is active; its GPU cost was not measured.
- **S-03 — QML fixture outcome inside a real niri session.** A-02 was reproduced without a private compositor; the helper forces `offscreen` regardless, so the outcome should not change, but this was not run inside the owner's session.
- **S-04 — `settings.sh` 4 s timeout on a normal login.** A-09 attributes it to managed-binary precedence, confirmed by trace; the wall time when no test sandbox is involved is unverified.
- **S-05 — Feature catalog read timeout fallback.** `WARN qml: Feature catalog: Read or validation timed out; using legacy entries` appeared in a restricted-`PATH` trace; whether it can happen in a normal session is unverified.
- **S-06 — Sustained niri event delivery.** `desktop_backend.py:1654` assumes `niri msg --json event-stream` keeps delivering; only that the command exists was checked.

## Checked, no defect found

- `scripts/doctor.sh`: all required checks pass (Quickshell ≥ 0.3.2, niri IPC, D-Bus, Wayland, installed entry point); 1 optional tool missing.
- `niri validate`: `config is valid` for the live `~/.config/niri/config.kdl`, which includes the deploy-managed fragment.
- `python3 scripts/desktop_backend.py --once`: exit 0, 60 324-byte snapshot, empty stderr; the `--demo --once` snapshot also matches `check.sh`'s assertions.
- Privilege boundaries: no `sudo` inside the shell; charging goes through `pkexec --disable-internal-agent /usr/bin/python3 -I /usr/local/libexec/lme-shell-charge` (`desktop_backend.py:1317`); the helper installer refuses symlinked parents, non-root targets and group/other-writable ancestors (`install-charge-helper.sh:15-25`); `deploy.py` refuses to run as root and refuses to sudo-edit a non-writable niri config.
- Installer safety: `scripts/install.sh` refuses targets inside the checkout, backs up on `--replace`, and never edits `~/.config/niri/config.kdl`.
- Permissions: `~/.config/lme-shell` 0700; settings and notification history 0600; clipboard store 0700/0600; writes are temp-file + `os.replace`.
- Clipboard secrets: `wl-clipboard 2.2.1` sets `CLIPBOARD_STATE=sensitive` for password-manager selections (`wl-paste(1)`), and `scripts/clipboard.py:160` bails out unless the state is `data`, so hinted secrets are not stored. Wi-Fi passwords never reach argv or disk (memfd stdin, redacted error text).
- Polkit agent: `qml/auth/AuthenticationAgent.qml` is an 18-line delegate to Quickshell's `PolkitAgent`; no custom password handling.
- Bash: `bash -n` passes for every `.sh`; `set -euo pipefail` present; quoting in `start.sh`, `settings.sh`, `install.sh` and `install-charge-helper.sh` is sound; no `eval`, `sh -c` with interpolation, or unquoted expansion of user data.
- Python: no `shell=True`, `os.system` or `eval` in `scripts/`; every command name passed to `CommandRunner` is listed in its `TOOLS` tuple; `niri_action` bounds its reply.

## Commands run (read-only)

```
./scripts/doctor.sh                         # 0 required missing, 1 optional
python3 scripts/desktop_backend.py --once   # exit 0, 60 KB snapshot
./scripts/check.sh                          # 1001 tests: 59 F, 4 E, 181 S; exit 1
bash -n ./*.sh scripts/*.sh                 # pass (stage skipped by check.sh)
python3 scripts/desktop_backend.py --demo --once   # demo snapshot valid
python3 scripts/feature_catalog.py --check  # exit 0
niri validate                               # config is valid
niri msg --json outputs                     # eDP-1 1920x1080 @120.002 Hz, VRR on
quickshell -c lme-shell ipc call shell {mediaStatus,nightLightStatus,authenticationStatus,idleStatus}
journalctl --user -b                        # no niri/quickshell lines
wl-paste --version                          # wl-clipboard 2.2.1 (CLIPBOARD_STATE)
```

Reproductions for A-04/A-05/A-06/A-11 used temporary directories and a `Preferences` instance pointed at them; the real `settings.json` was never opened for writing.

Not run, by rule: any install/setup/deploy script, `sudo`, `dnf install`, any write to `~/.config`, and any launch/kill of Quickshell or niri.

## Tooling gaps

`shellcheck` and `qmllint` are **not installed**, so shell static analysis and QML linting were not run. `check.sh` does not require them, but `AGENTS.md:65` assumes `qmllint` inside `run-gates.sh`. Recorded as a gap; not installed.
