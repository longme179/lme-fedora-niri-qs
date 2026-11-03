# LME Shell — improvement plan

**Date:** 2026-11-03 · **Baseline:** `578c135` · **Audit:** [AUDIT.md](AUDIT.md) (38 findings) · **Status:** I-01, I-02, I-03, I-04, I-06 and I-08 implemented (§9); the rest are proposals.

## 1. Summary

The shell is functional on the owner's laptop, but its regression gate is red and its settings file is unsafe against partial writes. This plan first makes the gate trustworthy, then makes preferences and the backend crash-proof, then adds diagnostics and reduces idle subprocess churn, and only then adds one small feature (IME indicator). Every item names the audit IDs it closes and a command that proves it.

**Invariants assumed** (from the task and the repo's own docs):

1. Fedora 44, niri 25.11+ (26.04 installed), Quickshell 0.3.2+ (0.3.2 installed); niri IPC and Fedora utilities only, never Hyprland commands or Arch scripts.
2. The backend uses the Python standard library only.
3. The shell runs unprivileged; privileged actions go through Polkit and the existing charge helper.
4. The installer never overwrites `~/.config/niri/config.kdl` and never adds repositories silently.
5. Material 3 Expressive controls on translucent glass, no UI gradients, flat tonal fills, Roboto, dark Dracula Pro-style palette; no continuous GPU blur shader, no discrete-GPU requirement.
6. All UI text, code and docs in English.
7. Existing memory targets (≤400 MB steady, ≤500 MB ordinary use) and the shared-service/worker rules in `AGENTS.md` still apply; no per-widget backend, daemon or timer.

The plan intentionally does **not** change A6 polling/cache policy without the owner's approval; I-13 is flagged as the one item that needs that approval (see *Open questions*).

## 2. Roadmap (ordered by milestone)

**M1 — Make the gate trustworthy** (closes the red `check.sh`)

1. **I-01** Fix the QML fixture platform contract — A-02
2. **I-02** Fix the catalog admission fixture — A-03
3. **I-03** Fix test isolation: `$HOME`, `XDG_DATA_HOME`, `PYTHONPATH` — A-07, A-09, A-10
4. **I-04** Make encoder-dependent tests skip, not error — A-08
5. **I-05** Gate summary output and README alignment — A-01, A-23

**M2 — Preferences and backend safety**

6. **I-06** Preferences durability: corrupt file, unknown keys, oversized numbers — A-04, A-05, A-11, A-28
7. **I-07** Bounded locks and directory fsync — A-14, A-21
8. **I-08** Backend supervisor: catch-all, backoff, recovery banner — A-06, A-25, A-26, A-29

**M3 — Diagnostics, notifications, settings UX**

9. **I-09** Persistent bounded shell/backend log — A-13
10. **I-10** Notification persistence and availability — A-31, A-32
11. **I-11** Settings launcher without killing the window — A-17
12. **I-12** Surface real errors and fix the precedence bug — A-19, A-20, A-34

**M4 — Idle cost on the iGPU**

13. **I-13** Event-driven audio state (`pactl subscribe`) — A-16 *(needs A6 approval)*
14. **I-14** Snapshot revisions and per-batch emit — A-15, A-27

**M5 — Verification and polish**

15. **I-15** Laptop verification matrix as a runnable check — A-18, S-01…S-03
16. **I-16** Theme-load diagnostics — A-24, A-35
17. **I-17** Preview-screenshot timeout and OSD fallback — A-30, A-33
18. **I-18** Docs and installer hygiene — A-22, A-36, A-37
19. **I-19** IME (fcitx5) status indicator — new, borrowed idea

**Backlog (one line):** pin/sign the self-updater (A-38); clipboard/notification retention policy (A-12); FeatureCatalog retry beyond I-10; notification inline reply; lock screen; `shellcheck`+`qmllint` in `run-gates.sh`; HDR/VRR policy beyond Battery saver.

---

## 3. Item cards

### I-01 · Fix the QML fixture platform contract
- **Goal:** native QML fixtures either run on Wayland or skip loudly; no more silent zero-result failures.
- **Why here:** A-02 — 37 of 63 gate failures. `tests/test_local_qml.py:41` forces `QT_QPA_PLATFORM="offscreen"`, while every fixture builds `FloatingWindow`; Quickshell 0.3.2 then loads the config and never emits `LOCAL_QML_RESULT`.
- **Borrowed source:** original.
- **Files:** `tests/test_local_qml.py`, `tests/test_settings_startup.py`.
- **Approach:** (1) choose the platform from the caller: wayland when a compositor is reachable, otherwise offscreen; (2) `skipUnless`/`skipTest` with a printed reason when the fixture needs a surface; (3) keep the existing 15 s timeout and log capture; (4) apply the same rule to `test_settings_startup.py:97` (its `native=True` branch already exists at `:103`).
- **Acceptance:** `env -u WAYLAND_DISPLAY python3 -m unittest discover -s tests -p 'test_local_qml.py' -v` → 0 failures, skips name the reason; inside the niri session the same command runs 7/7 pass; `... -p 'test_settings_startup.py'` → 0 failures.
- **Risk/rollback:** low; test-only. Revert the commit.
- **Effort:** S. **Depends on:** none.

### I-02 · Fix the catalog admission fixture
- **Goal:** the CLI-parity matrix exercises the real entry point again.
- **Why here:** A-03 — 13 failures. The fixture copies only `settings.sh` and `feature_catalog.py` (`tests/catalog_admission_fixture.py:28`), but `scripts/feature_catalog.py:9` imports `catalog_metadata`.
- **Borrowed source:** original.
- **Files:** `tests/catalog_admission_fixture.py`.
- **Approach:** (1) copy the entry point's real module set (an explicit list kept next to the imports, or `scripts/*.py` minus caches); (2) add a fixture self-check that runs `python3 scripts/feature_catalog.py --check` once in `setUp` and fails with the stderr instead of 13 opaque failures; (3) keep the disposable-checkout isolation.
- **Acceptance:** `python3 -m unittest discover -s tests -p 'test_catalog_admission.py' -v` → 13/13 pass.
- **Risk/rollback:** low; test-only.
- **Effort:** S. **Depends on:** none.

### I-03 · Test isolation: `$HOME`, `XDG_DATA_HOME`, `PYTHONPATH`
- **Goal:** tests behave the same on a deployed laptop as in a clean VM.
- **Why here:** A-07 (6 failures: normalization replaces `$HOME` before `$PWD`, so a checkout under `$HOME` never becomes `<ROOT>`), A-09 (2 failures: `settings.sh:47-48` prefers the deployed managed Quickshell, so tests launch the real Settings), A-10 (2 failures: child `python3 -c` has no `PYTHONPATH`).
- **Borrowed source:** original.
- **Files:** `tests/schema_fixture.py`, `tests/test_personalization.py`, `tests/test_features.py`, `tests/test_infrastructure.py`, `tests/test_launchpad_logs.py`, `scripts/check.sh`.
- **Approach:** (1) in `normalize()`, replace `cwd` before `home`; (2) point `XDG_DATA_HOME` at the fixture dir in the two launcher tests; (3) pass `PYTHONPATH=<repo>/scripts` to the two child processes, and export it once in `check.sh` so the whole tree inherits it; (4) do not weaken any assertion.
- **Acceptance:** `... -p 'test_settings_schema.py'`, `... -p 'test_personalization.py'`, `... -p 'test_features.py'`, `... -p 'test_infrastructure.py'`, `... -p 'test_launchpad_logs.py'` → 0 failures; the same commands pass with `HOME=/tmp/fakehome`.
- **Risk/rollback:** low; test-only.
- **Effort:** S. **Depends on:** none.

### I-04 · Make encoder-dependent tests skip, not error
- **Goal:** `ffmpeg-free` is a supported runtime, so its missing encoders must not fail the gate.
- **Why here:** A-08 — 3 errors from `tests/test_recording.py:144` (`libx264`), on `ffmpeg-free-8.1.3-1.fc44`.
- **Borrowed source:** original.
- **Files:** `tests/test_recording.py`.
- **Approach:** probe `ffmpeg -encoders` once per encoder; `skipUnless` with the encoder name in the reason; keep `libvpx-vp9` coverage; add one always-running structural test for the remux argument builder.
- **Acceptance:** `... -p 'test_recording.py' -v` → 0 errors, 3 skips naming the missing encoders; with a full ffmpeg build the same tests run and pass.
- **Risk/rollback:** low; test-only.
- **Effort:** S. **Depends on:** none.

### I-05 · Gate summary output and README alignment
- **Goal:** one command, one honest line: what ran, what failed, what was skipped and why.
- **Why here:** A-01 (the gate is red and `set -e` hides the later stages), A-23 (README says native checks need a private session while `check.sh` runs them unconditionally).
- **Borrowed source:** original.
- **Files:** `scripts/check.sh`, `README.md`.
- **Approach:** (1) run the stages with explicit accounting instead of aborting at the first failure, print `passed/failed/skipped` per stage and a final machine-readable line; (2) keep a non-zero exit when any stage fails; (3) update the README sentence to describe exactly what the gate covers.
- **Acceptance:** on this laptop `./scripts/check.sh` exits 0 and prints the counts; temporarily re-introducing one known failure makes it exit 1 and name the stage.
- **Risk/rollback:** low; revert.
- **Effort:** S. **Depends on:** I-01…I-04.

### I-06 · Preferences durability
- **Goal:** a broken or newer `settings.json` can never be silently replaced or crash the backend.
- **Why here:** A-04 (truncated file → defaults written back; reproduced), A-05 (`math.isfinite(10**400)` → `OverflowError` at startup; reproduced), A-11 (unknown keys erased on rewrite; reproduced), A-28 (`reload()` assigns outside the lock).
- **Borrowed source:** original.
- **Files:** `scripts/desktop_backend.py` (`Preferences.reload/update/_write`, `_validate_legacy_preference`), `scripts/storage.py`, plus a new focused test.
- **Approach:** (1) remember the raw parsed document and merge unknown keys back on write; (2) on any parse failure, set a `load_error`; `update()` then refuses (returns a visible error) or writes a timestamped backup first; (3) bound numeric values (`abs(v) <= 2**53`) before `math.isfinite` and catch `ArithmeticError` in `reload()`/`handle()`; (4) take the same lock in `reload()`'s assignment path; (5) keep the flat-JSON format and file lock.
- **Acceptance:** new tests: corrupt file + `update()` → error, original bytes unchanged; `{"opacity": 10**400}` → `ValueError`, backend starts; `{"futureSetting":42}` survives an `opacity` update; `... -p 'test_backend.py'` → 0 failures.
- **Risk/rollback:** medium (touches the settings writer); rollback by reverting the commit — no format migration is introduced.
- **Effort:** M. **Depends on:** none.

### I-07 · Bounded locks and directory fsync
- **Goal:** no action can hang forever on a stale lock, and a rename survives power loss.
- **Why here:** A-14 (`LOCK_EX` without timeout in `desktop_backend.py:470` and `storage.py:33`), A-21 (no parent-directory fsync after `os.replace`).
- **Borrowed source:** original.
- **Files:** `scripts/desktop_backend.py`, `scripts/storage.py`.
- **Approach:** (1) `LOCK_EX|LOCK_NB` retry loop with a ~2 s deadline, raising `CommandError` with a user-visible message; (2) `os.fsync(os.open(path.parent, os.O_RDONLY))` after `os.replace` in both writers; (3) keep `deploy_state.py:43`'s existing behavior as the reference.
- **Acceptance:** a test holds the lock in a subprocess and asserts `Preferences.update` raises within 3 s; `... -p 'test_backend.py'` and `... -p 'test_storage*'` (if present) pass.
- **Risk/rollback:** low; revert.
- **Effort:** S. **Depends on:** none.

### I-08 · Backend supervisor
- **Goal:** an unexpected exception costs one action, not the session; recovery is visible and bounded.
- **Why here:** A-06 (exception classes outside the five-value tuple escape `handle_line` into a loop that only catches `KeyboardInterrupt`/`BrokenPipeError`; `RecursionError` reproduced), A-25 (`stop()` can mask the real error), A-26 (unbounded `read_json`), A-29 (three restarts then permanent inertness; banner never clears).
- **Borrowed source:** DMS capped-backoff policy — `DankMaterialShell/quickshell/Services/WeatherService.qml` at `f1507fa4fa3f25842dc73a8b25f747f98bcf55fc` (MIT, ©2025 Avenge Media LLC): `Math.min(60000 * Math.pow(2, persistentRetryCount), 300000)`. **Verdict: reimplement** in `ShellState.qml`; no code copied.
- **Files:** `scripts/desktop_backend.py`, `scripts/action_pending.py`, `scripts/command_runner.py`, `qml/services/ShellState.qml`.
- **Approach:** (1) catch `Exception` per input line and per finished job, publish `{ok:false, message}`; (2) keep `RecursionError`/`ArithmeticError` inside that boundary; (3) bound `read_json` by size and cap input nesting; (4) QML: capped exponential backoff (2 s × 2^n, 60 s ceiling), unlimited retries, clear the banner when `backendReady` returns, add an explicit `restartBackend` IPC.
- **Acceptance:** feeding a 100k-deep JSON line keeps the backend alive and returns `ok:false` (new test); `kill -9` of the backend in a disposable session restarts within ~2/4/8 s and never stops retrying and the banner clears (manual).
- **Risk/rollback:** medium; revert. No protocol change beyond a new optional IPC method.
- **Effort:** M. **Depends on:** I-06 (shared error paths).

### I-09 · Persistent bounded log
- **Goal:** a crash can be diagnosed after the fact without a terminal.
- **Why here:** A-13 — no file receives the shell's stderr; `journalctl --user -b` has no shell lines.
- **Borrowed source:** original.
- **Files:** `scripts/start.sh`, `config/niri/lme-shell.kdl`, `scripts/desktop_backend.py`, `qml/settings/AboutPage.qml` (or the existing About host).
- **Approach:** (1) redirect Quickshell and backend stderr into `$XDG_STATE_HOME/lme-shell/log/shell.log` with size-based rotation (e.g. 1 MiB × 3) and 0600; (2) the backend emits structured one-line errors for action failures; (3) Settings → About shows the path and a "Copy diagnostics" button that bundles version, doctor summary and the last N log lines; (4) respect `LME_NO_LOG` for previews/tests.
- **Acceptance:** after a restart, `ls -l ~/.local/state/lme-shell/log/` shows bounded files; a forced backend error appears in the log; the About page shows the path; preview runs leave no log unless asked.
- **Risk/rollback:** low; revert.
- **Effort:** M. **Depends on:** none.

### I-10 · Notification persistence and availability
- **Goal:** notifications are not lost at startup and history is written only when it changed.
- **Why here:** A-31 (`onHistoryChanged` bumps the revision for `active`/`popup` changes and rewrites up to 200 entries + fsync per notification lifecycle), A-32 (`enabled` at `qml/services/Notifications.qml:15` depends on the optional `notifications` settings page, so a catalog failure disables the `NotificationServer` D-Bus name).
- **Borrowed source:** original (the bounded-store idea is already implemented; Noctalia's `kNotificationHistoryMaxEntries` is not needed).
- **Files:** `qml/services/Notifications.qml`, `qml/services/FeatureCatalog.qml`.
- **Approach:** (1) compute a serialized projection of persisted fields and bump `historyRevision` only when it changes; (2) decouple availability from `settingsPageAvailable` — use the feature's enabled flag and `FeatureCatalog.ready`; (3) give the catalog `fail()` a bounded retry path so a transient read error does not latch.
- **Acceptance:** a QML fixture marks a notification read and asserts no save request; with a catalog error the `NotificationServer` still registers; `... -p 'test_notifications*'` passes.
- **Risk/rollback:** medium (notification D-Bus name ownership); revert.
- **Effort:** M. **Depends on:** I-08.

### I-11 · Settings launcher without killing the window
- **Goal:** re-opening Settings never destroys a window the user is editing in.
- **Why here:** A-17 — `settings.sh:67` runs `kill` whenever `ipc call settings openPage` returns non-`true`.
- **Borrowed source:** original.
- **Files:** `scripts/settings.sh`.
- **Approach:** (1) treat "no running instance" (non-zero exit) as "launch"; (2) when an instance exists and the page did not open, wait for `startupPending`, then retry `openPage` once; (3) only kill after an explicit failure reply and after a 2 s grace period; (4) keep `--no-duplicate`.
- **Acceptance:** a fake-`qs` test asserts no `kill` for `false`/pending replies and exactly one `kill` for a real error; manual: open Settings, change a field, press `Mod+Comma` → no window loss.
- **Risk/rollback:** low; revert.
- **Effort:** S. **Depends on:** none.

### I-12 · Surface real errors and fix the precedence bug
- **Goal:** failures are visible; demo behavior matches the guard's intent.
- **Why here:** A-19 (hardcoded action list suppresses `ok:false`), A-20 (malformed snapshot dropped silently), A-34 (`&&`/`||` precedence means `imageAnnotate` closes panels in demo).
- **Borrowed source:** original.
- **Files:** `qml/services/ShellState.qml`.
- **Approach:** (1) always show `ok:false` messages; keep the list only for successful routine actions; (2) log a single line when the snapshot contract is broken and show a status message; (3) parenthesize the close-panels condition.
- **Acceptance:** a fixture returns `ok:false` for `networkRefresh` and the status message is set; a malformed snapshot logs once; demo `imageAnnotate` does not close panels.
- **Risk/rollback:** low; revert.
- **Effort:** S. **Depends on:** none.

### I-13 · Event-driven audio state (`pactl subscribe`)
- **Goal:** volume/route changes stop costing periodic `wpctl` subprocesses.
- **Why here:** A-16 — the ≥1.5 s sample runs `wpctl` twice plus `nmcli`, `brightnessctl`, `busctl`, `niri`, `upower`/sysfs reads, all on the main thread.
- **Borrowed source:** none adopted. Reviewed and rejected: DMS `quickshell/Services/PipewireAudioBackend.qml` (`f1507fa`, MIT) and Caelestia `shell/services/Audio.qml` (`bcbb5d5`, GPL-3.0) — both move audio state into QML, which would create a second owner next to the backend's `wpctl` actions.
- **Files:** `scripts/desktop_backend.py` (event loop + audio sampler), `scripts/audio_inventory.py` if reused.
- **Approach:** (1) run one long-lived `pactl subscribe` child, registered in the existing selector like the niri event stream; (2) on `sink`/`source`/`server` events, invalidate the audio cache and let the next snapshot re-read once; (3) keep the periodic sample as a slow safety net (e.g. 15 s) so a missed event cannot freeze the UI; (4) restart the child with the existing 5 s retry pattern.
- **Acceptance:** `pactl subscribe` is visible as a child of the backend; over 30 s idle with no audio change, no `wpctl` process is spawned (manual `ps` sample); changing volume updates the OSD immediately; a test asserts the sampler is not called by the timer when no event is pending.
- **Risk/rollback:** medium-high — this is the one item that touches A6 polling policy (owner approval needed, see *Open questions*); rollback by reverting.
- **Effort:** M. **Depends on:** owner approval; I-08 for process supervision patterns.

### I-14 · Snapshot revisions and per-batch emit
- **Goal:** the QML no longer serializes whole sections every two seconds, and N queued commands produce one snapshot.
- **Why here:** A-15 (`JSON.stringify` of `niri`/`apps`/`launcherUsage`/`preferences` per snapshot), A-27 (one `emit()` — including two `niri msg` calls — per queued line).
- **Borrowed source:** original.
- **Files:** `scripts/desktop_backend.py` (`emit`, snapshot assembly), `qml/services/ShellState.qml` (`accept`).
- **Approach:** (1) add monotonic `revisions: {apps, niri, preferences, launcherUsage}` to the snapshot, bumped only when the value changes; (2) QML compares integers and reuses the previous object; (3) coalesce all lines read in one `select()` batch into one `emit()`; (4) keep `lastResult` sequencing semantics.
- **Acceptance:** `grep -n "JSON.stringify(next" qml/services/ShellState.qml` returns nothing; a test posts 5 commands in one write and asserts one snapshot with 5 sequenced results; identity of `apps`/`niri` is stable across an unchanged poll.
- **Risk/rollback:** medium (protocol addition, backward compatible); revert.
- **Effort:** M. **Depends on:** I-08.

### I-15 · Laptop verification matrix as a runnable check
- **Goal:** turn the prose "needs target-machine check" rows into a repeatable report.
- **Why here:** A-18 — `docs/VALIDATION.md:1684` still says native blur, 120 Hz pacing, suspend and charging are unverified on this laptop.
- **Borrowed source:** original.
- **Files:** new `scripts/verify_laptop.sh` (read-only), `docs/RELEASE_CHECKLIST.md`.
- **Approach:** (1) collect `niri --version`, `qs --version`, `niri msg --json outputs` (mode/VRR), whether the blur include is present in the niri config, `niri validate`, `wpctl`/`brightnessctl`/UPower readings, `journalctl` error count since boot; (2) print PASS/FAIL/SKIP per row with the evidence line; (3) never change state.
- **Acceptance:** `./scripts/verify_laptop.sh` exits 0 with a complete table on this laptop; removing the blur include is reported as FAIL for that row; the script leaves `git status` clean.
- **Risk/rollback:** low (new read-only script).
- **Effort:** M. **Depends on:** none.

### I-16 · Theme-load diagnostics
- **Goal:** a bad palette/theme file degrades visibly, not with a console line and a thrown `find`.
- **Why here:** A-24 (JSON errors only `console.warn`), A-35 (`data.palettes` unvalidated, then `paletteCatalog.find` at `:48` throws).
- **Borrowed source:** original.
- **Files:** `qml/theme/Theme.qml`, `qml/settings/AppearancePage.qml`.
- **Approach:** (1) `Array.isArray` guards for `palettes`/`schemes`; (2) publish a `themeError` string; (3) show it as a Settings banner with "Reset to Dracula" (writes the palette file through the existing preference path).
- **Acceptance:** a copy of `config/palettes.json` with `{}` in a temp `XDG_CONFIG_HOME` produces a visible message and a working default palette; `... -p 'test_liquid_style.py'` still passes.
- **Risk/rollback:** low; revert.
- **Effort:** S. **Depends on:** none.

### I-17 · Preview-screenshot timeout and OSD fallback
- **Goal:** `LME_SHELL_SCREENSHOT` cannot hang a CI run; volume/brightness feedback never disappears.
- **Why here:** A-30 (the 1.2 s timer repeats forever if the backend never becomes ready or the grab never resolves), A-33 (no OSD when the configured output is absent).
- **Borrowed source:** original.
- **Files:** `shell.qml`, `qml/services/OSDManager.qml`.
- **Approach:** (1) add a 15 s deadline that logs and calls `Qt.quit()`; (2) OSD falls back to focused → first screen when the configured name matches nothing.
- **Acceptance:** `LME_SHELL_SCREENSHOT=/tmp/x.png LME_SHELL_DEMO=0 quickshell -p shell.qml` with no backend exits within 15 s and writes a log line; setting `osdOutput` to a bogus name still shows the OSD on the focused output.
- **Risk/rollback:** low; revert.
- **Effort:** S. **Depends on:** none.

### I-18 · Docs and installer hygiene
- **Goal:** no stale audit in the active docs, no accidental `~` relocation, no mic unmute while locked.
- **Why here:** A-22 (stale `docs/ARCHITECTURE_AUDIT.md` at baseline `1f54934`), A-36 (`XF86AudioMicMute allow-when-locked=true`), A-37 (`install.sh --replace --target ~/.config` would move the tree).
- **Borrowed source:** original.
- **Files:** `docs/ARCHITECTURE_AUDIT.md` → `docs/archive/`, `README.md` doc index, `scripts/install.sh`, `config/niri/media-keys.kdl`.
- **Approach:** (1) move and stamp the old audit; (2) require the target to be absent, empty, or a symlink before `mv`; (3) drop `allow-when-locked` for the microphone bind only; (4) run `niri validate` after the kdl edit (the owner applies it to their config, not the installer).
- **Acceptance:** `install.sh --replace --target <non-empty dir>` exits 1 without moving it; `niri validate` passes with the edited fragment; `docs/ARCHITECTURE_AUDIT.md` no longer resolves.
- **Risk/rollback:** low; revert.
- **Effort:** S. **Depends on:** none.

### I-19 · IME (fcitx5) status indicator
- **Goal:** the current input method is visible and switchable from the bar — relevant because fcitx5 5.1.23 is installed and configured on this laptop.
- **Why here:** not in the README feature list and not implemented; the owner types Vietnamese, and the shell currently offers no IME state.
- **Borrowed source:** `DankMaterialShell/quickshell/Services/Fcitx5Service.qml` at `f1507fa` (MIT, ©2025 Avenge Media LLC) — tray-identity tracking plus `fcitx5-remote -n`. **Verdict: reimplement** in the backend (Python stdlib `subprocess`) plus a small QML bar module; no upstream code copied.
- **Files:** `scripts/desktop_backend.py` (new `fcitxStatus` sample on the existing 5 s cache), `qml/bar/` module + `qml/bar/BarRegistry.qml`, `config/features.json`.
- **Approach:** (1) backend action `fcitxStatus` runs `fcitx5-remote -n` with a 1 s timeout and returns `{available, current}`; (2) poll only when a consumer is visible (existing consumer pattern), or on click; (3) bar module shows an abbreviation, click cycles via `fcitx5-remote -t`; (4) hide when fcitx5 is absent.
- **Acceptance:** the bar shows the current IME; switching with `Ctrl+Space` updates it within 2 s; with fcitx5 stopped the module hides; `./scripts/check.sh` stays green.
- **Risk/rollback:** low-medium (new feature); revert.
- **Effort:** M. **Depends on:** I-05 (green gate), I-08.

---

## 4. Rejected ideas

| Idea | Why rejected |
| --- | --- |
| Copy Noctalia's `x-kde-passwordManagerHint` filter (`noctalia-shell/src/shell/wayland/clipboard_service.cpp:63-75`, MIT, `3c7e634`) into the clipboard worker | `wl-clipboard 2.2.1` already sets `CLIPBOARD_STATE=sensitive` and `scripts/clipboard.py:160` bails out on it; copying C++ into a stdlib Python project would add maintenance for zero behavior change. Keep the current check and cite it in the docs instead. |
| Move audio state into QML via Quickshell `Pipewire` (DMS `PipewireAudioBackend.qml`, Caelestia `services/Audio.qml`) | Creates a second source of truth next to the backend's `wpctl` writes and moves ownership into the UI, contrary to the existing one-owner-per-domain rule; Caelestia's file is also GPL-3.0-only and would add mixing for no gain. |
| Replace sysfs battery/AC reads with UPower (Caelestia `daemons/BatteryMonitor.qml`) | Sysfs reads are already cheap, stdlib and synchronous; UPower adds a D-Bus dependency and a new failure mode for no measurable saving. |
| Port Caelestia/iNiR lock screens | Large feature (PAM, session lock, shader surfaces) competing with the working `swaylock` integration; violates the "no continuous GPU shader" budget and is not a defect. |
| Replace the Python backend with a Go/Rust daemon (DMS model) | Breaks the stdlib-only invariant and the measured memory approach; the JSON-lines backend is adequate for this machine. |
| Adaptive polling only (e.g. 2 s → 10 s when idle) | Reduces but does not remove the subprocess churn and makes OSD latency worse; I-13 removes the work instead. |
| Use SQLite for settings | The flat JSON + file lock is an owner invariant; fix the failure modes (I-06/I-07) instead of replacing the format. |
| Run `qmllint`/`shellcheck` inside `check.sh` | Both are absent on this machine and on a stock Fedora install; `check.sh` would fail closed. Keep them in `run-gates.sh`/developer docs (Backlog). |
| Inline notification replies | Valuable but a feature, not a defect; needs action support in the history contract. Backlog. |

---

## 5. Reference research (Phase 3)

All URLs were verified by a successful `git clone --depth 1` on 2026-11-03; commits are the cloned HEADs, all within the last month.

| Shell | Commit | License (verified from the repo `LICENSE`) | Files inspected | Verdict |
| --- | --- | --- | --- | --- |
| AvengeMedia/DankMaterialShell | `f1507fa4fa3f25842dc73a8b25f747f98bcf55fc` (2026-11-02) | MIT, ©2025 Avenge Media LLC | `quickshell/Services/Fcitx5Service.qml`, `quickshell/Services/PipewireAudioBackend.qml`, `quickshell/Services/WeatherService.qml` (backoff), `quickshell/Services/DMSService.qml` | I-19 reimplement; I-08 policy reimplement; audio ownership rejected |
| noctalia-dev/noctalia-shell | `3c7e6343efac4cb683eb102374cccb210c05dc1c` (2026-11-02) | MIT, ©2026 noctalia-dev | `src/shell/wayland/clipboard_service.cpp`, `src/notification/notification_history_store.h` | rejected (already covered) |
| caelestia-dots/shell | `bcbb5d5139d5159839c7362d8f4954ccc7dbd67d` (2026-11-03) | GPL-3.0 | `shell/services/Audio.qml`, `shell/services/Players.qml`, `shell/modules/lock/` | rejected (ownership/license/scope) |
| snowarch/iNiR | `48cdcecb0f6089cfbb7019054602eab28e154b3b` (2026-10-08) | GPL-3.0 | `services/NiriService.qml` | rejected (LME already consumes the niri event stream) |
| end-4/dots-hyprland | `2f2a376fdb2ad738bf55f693dd0b474b64bb0ab8` (2026-10-11) | GPL-3.0 | Hyprland-specific modules only | rejected (Hyprland IPC, not portable to niri) |

Per-file license note: none of the four inspected files carries an SPDX header, so the repository `LICENSE` is the evidence; the two adopted pieces come from MIT repositories, which is compatible with GPL-3.0-or-later.

## 6. Attribution text to add to THIRD_PARTY.md

For I-08 (restart policy, idea only):

```markdown
`qml/services/ShellState.qml` adopts the capped exponential retry policy (60 s × 2^n,
300 s ceiling) from DankMaterialShell `quickshell/Services/WeatherService.qml`
at `f1507fa4fa3f25842dc73a8b25f747f98bcf55fc` (MIT, Copyright (c) 2025 Avenge Media
LLC). The implementation is original QML for the shell's backend process; the MIT
notice is retained in `third_party/DankMaterialShell-LICENSE`.
```

For I-19 (IME indicator, idea reimplemented):

```markdown
The optional fcitx5 input-method indicator (`scripts/desktop_backend.py`,
`qml/bar/`) follows the tray-identity + `fcitx5-remote -n` approach of
DankMaterialShell `quickshell/Services/Fcitx5Service.qml` at
`f1507fa4fa3f25842dc73a8b25f747f98bcf55fc` (MIT, Copyright (c) 2025 Avenge Media
LLC). LME reads the current method through a stdlib subprocess action, keeps the
existing backend ownership and adds no tray dependency; the MIT notice is retained
in `third_party/DankMaterialShell-LICENSE`.
```

No other item copies or adapts third-party code, so no other attribution is needed.

### Adaptation requirements (if more than the idea is ever copied)

| Requirement | How this plan handles it |
| --- | --- |
| Hyprland → niri IPC | None of the adopted references calls `hyprctl`; DMS `Fcitx5Service.qml` uses the system tray and `fcitx5-remote`, both portable. Any future copy must use `niri msg`/`NIRI_SOCKET` like `scripts/desktop_backend.py:1545-1562`. |
| Arch → Fedora packages | No new package is required: `fcitx5`/`fcitx5-remote` are installed (`rpm -q fcitx5` → `fcitx5-5.1.23-1.fc44`), `pactl` comes from the already-required `pulseaudio-utils`. `dnf repoquery`/`dnf info` could not run in this read-only sandbox (it cannot write its metadata cache), so package presence was verified with `rpm -q` and `command -v` instead. |
| Non-stdlib Python removed | I-19 uses `subprocess` + `json` only; no D-Bus binding, no GObject, matching `scripts/clipboard.py` precedent. |
| Theme tokens | The IME module must use `Theme.barText`/`Theme.barMuted`/`Theme.barFill` and the shared `qml/bar` module contract; no new palette values. |
| `settings.json` + file lock | I-19 adds no preference unless the owner wants a toggle; if added, it goes through `config/features.json` + `Preferences.update()` so the existing lock/merge applies. |
| iGPU cost | I-19 samples only while a consumer is visible (existing consumer pattern) and never per frame; I-08's log/diagnostics run on state changes, not on a timer. |

---

## 7. Verification status

**Confirmed by running (this laptop):** `doctor.sh` green; `backend --once` and `--demo --once` valid; `check.sh` fails 59/4/181; the six fixture causes were each reproduced in isolation; `bash -n` clean; `niri validate` valid; IPC status queries answered; `wl-clipboard 2.2.1` honours `CLIPBOARD_STATE`; the settings-loss, oversized-number, unknown-key and deep-JSON paths were reproduced against temporary files.

**Read only (not executed):** every code finding marked *read* in [AUDIT.md](AUDIT.md), all installer/updater flows (never run), the QML items (no GUI run), and the reference implementations (inspected, not executed).

**Unverified:** idle CPU/RAM (sandbox PID namespace), native blur cost and 120 Hz pacing on the Radeon, sustained niri event delivery, the `settings.sh` timing outside the test harness, the catalog read-timeout path in a normal session, and whether `dnf` can see every package named above (`dnf` cannot write its cache inside this sandbox; fcitx5 was verified as installed with `rpm -q` instead).

**Final audit (Phase 6):** every file:line cited in both documents was re-read; every reference commit and license above was verified from the clone; `git status`/`git diff` in the checkout show only `docs/AUDIT.md` and `docs/PLAN.md` as untracked additions.

## 8. Open questions for the owner

1. **Priority:** is M1 (gate) + M2 (settings/backend safety) the right first branch, or do you want I-13 (idle cost) earlier? I recommend M1 → M2.
2. **A6 approval:** I-13 changes polling policy, which `docs/STATE.md` currently forbids. Do you approve a one-time exception limited to audio (event-driven + 15 s safety net)?
3. **Retention/privacy:** clipboard history is on by default and never expires (bounded at 100 items/64 MB), and notification history keeps message bodies indefinitely. Do you want opt-in defaults, a TTL, or no change?
4. **Update trust:** should the self-updater stay on unpinned `main` (A-38), or move to signed tags/release checksums? This is the only supply-chain decision in the plan.
5. **fcitx5:** keep I-19 as an optional module (off by default) or a default bar item?
6. **Gate scope:** may `check.sh` run QML fixtures inside the real session on this laptop, or should those stay opt-in behind `run-gates.sh`?

## 9. Implementation status (2026-11-03)

The owner selected I-01, I-02, I-03, I-06 and I-08 for implementation, then I-04 to
finish the gate. All six are implemented, verified and pushed on
`fix/audit-gate-settings-backend`.

| Item | State | Evidence |
| --- | --- | --- |
| I-01 | done | `tests/test_local_qml.py` and `tests/test_settings_startup.py` now set `QT_LOGGING_RULES=qml.debug=true`; Quickshell 0.3.2 was filtering `console.log` (debug level), so every fixture result line was invisible. 7/7 and 5/5 (1 opt-in skip) pass. |
| I-02 | done | `tests/catalog_admission_fixture.py` copies `catalog_metadata.py` and self-checks the disposable CLI; 9/9 pass (13 before). |
| I-03 | done | cwd-first normalization in `tests/schema_fixture.py`; `XDG_DATA_HOME` isolation in the two launcher tests; `sys.path` for child interpreters; `scripts/check.sh` exports `PYTHONPATH`. The five affected modules pass. |
| I-06 | done | Unknown-but-not-retired keys survive a rewrite, retired keys (`settings_transfer.RETIRED_PERSISTENCE`) stay dropped, a corrupt file is left untouched and `update()` refuses, and `storage.finite_number` rejects oversized integers; `reload()`/`update()` share a lock. New `tests/test_preferences_durability.py` (5/5). `desktop_backend.py` ratcheted to 1628 lines. |
| I-04 | done | `tests/test_recording.py` probes `ffmpeg -encoders` and skips the container/audio checks with the missing encoder name (`libx264` here); 13 tests, 3 skips, 0 errors on `ffmpeg-free`. |
| I-08 | done | `action_pending.emit` survives a broken snapshot; `handle_line` turns parse failures (`RecursionError` included) and handler exceptions into one `ok:false` result; `storage.read_json` is size-bounded; `command_runner.stop` keeps the original error; QML retries with capped backoff, clears the “backend stopped” banner on reconnect and exposes `shell restartBackend`. New `tests/test_backend_supervisor.py` (6/6). |

Gate after these changes: `./scripts/check.sh` → `Ran 1012 tests`, `OK (skipped=184)`,
exit 0 (it was `59 failures, 4 errors` before the branch). The 184 skips are the
existing opt-in native/device cases plus the three encoder checks I-04 now skips
with a reason. I-05's richer gate summary is still a proposal.
