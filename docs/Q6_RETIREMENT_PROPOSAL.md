# Q6 proposal — storage, settings coordination, backend retirement

**Date:** 2026-11-13 · **Baseline:** `main` at #138 (Q5 closed) · **Status:** review stop — awaiting owner authorization ("duyệt Q6"). Every dimension below is severable: the legs and the D1–D3 decision points can be authorized, trimmed or deferred independently, per the standing phase discipline.

## 1. What Q6 is

The final runtime phase of the QML-first migration: `ShellState` stops spawning `desktop_backend.py`, the JSON-lines protocol, the `Pending.js` host side and the backend restart supervisor retire, and the preferences/storage coordination that justified the backend's last residents moves to a native single-writer. This is the plan's §Q6 scope — a public protocol change, which is why it has always carried its own owner approval.

Target T1 (plan §1): runtime share ≥ 85% QML-side with `desktop_backend.py` retired.

## 2. Why now — what Q5 leaves behind

- Every runtime family Q1–Q5 owns its flows in QML. What still runs Python at runtime: the backend core with its A/B fallbacks, the deprecated snapshot sections, the standalone Settings coordination, the demo/fallback contexts, and the deliberate FS-op helpers (`file_search`, the clipboard one-shots, `json_store`, `charge_control`, `idle_control`).
- The A/B window has produced its evidence: the drift monitoring ran clean through every phase's window (Q4's 12.5 h day: zero Q4-family drift; the only annotated signal ever remaining is Q1's banded strength jitter), each Q5 leg ran its engine cases live on the owner's machine, and the Q5 close-out G0 put the full suite green on the final tree with engine cases live (1296/0-fail, 188 skips).
- The debt the window accrued: **58 `DEPRECATED(Q1..Q5->Q6)` marker sites across 36 files** — Python fallbacks and the QML A/B compare plumbing both (`NativeState.qml` and the state/model files carry markers too).
- Measured baseline on the #138 tree: runtime QML/JS 22,201 · Python 9,463 lines across 76 files (70.1% QML-side).

## 3. The measured retirement inventory

Every runtime Python file dispositioned; buckets sum exactly to the 9,463-line baseline (wc -l, the counter's own units):

| Bucket | Lines | What is in it |
|---|---|---|
| Retires with the sweep | **5,599 (59%)** | `desktop_backend.py` 1,717 + the protocol plumbing (`backend_actions`, `backend_providers`, `action_pending`, `storage`), the settings coordination (`settings_transfer`, `desktop_features`, `desktop_widgets` — after D1), and the Q1–Q5 family fallbacks: `equalizer_actions` 426, `battery_saver` 287, `weather` 209 + `weather_actions` 49, `network_inventory` 197, `wifi_actions` 179, `niri_events` 159, `niri_keybinds` 136, `system_monitor`, `launcher_history`, the night-light/display/audio/ime families |
| D2 — capture/recording + the wallpaper backend paths | 810 | `screen_capture` 200, `screen_recording` 226, `capture_actions`/`recording_actions`, `wallpaper_actions` 94, `gowall_actions`/`palette_actions`/`wallpaper_palette` — the quickshell 0.3.2 FS-op gaps (no mkdir/stat/chmod/exclusive-create/binary-read, no directory listing) |
| D3 — small domains | 900 | `memory_workload` 205, `image_utilities` 181, `launchpad`/`launchpad_actions`, `appearance`/`mirror`/`saver`/`lock_actions`, `liquid_glass`, `privacy`, `content_types`, `local_content_actions` |
| Shared plumbing | 383 | `command_runner` 137, `managed_command` 64, `command_output` 46, `detached_log` 136 — retire only if the one-shot helpers move to standalone argv contracts (a leg-3 detail) |
| Shrinks to one-shot helpers | 393 → ~80 | `lyrics.py` 157 → the `--store` helper; `wallpaper.py` 236 → the shared-rotation flock helper (or a native rewrite) |
| Stays by design | 967 | `file_search`, `clipboard` 249, `clipboard_watch` 60, `json_store`, `charge_control` 151 (pkexec), `idle_control` 182 (the Q4 lock/sleep/PDEATHSIG/probe decision), `shell_update` 214 (becomes a directly-spawned detached Process) |
| Open triage | 375 | `bluetooth_agent` 283 (the pairing agent), `wifi_auth` 79 (secure-wifi feedback), `catalog_metadata` 44 |
| Dev tool misfiled as runtime | 36 | `regen_equalizer_test_tone` (moves to `toolingFiles`) |

**Projection** (QML absorbs the coordination and the re-homed domains, ~+800–1,000 QML lines): conservative (D2/D3 stay as helpers) lands **86.6% QML-side**; lean (D2 one-shots, D3 native re-homes) lands **91.5%**. T1's 85% clears either way — the difference between the two is how much Python remains as helpers. The RSS/launch improvement the plan expects from the backend removal is measured, not assumed, at the leg-4 gates.

## 4. Decision points for the owner

- **D1 — preferences single-writer (the plan's Q-2).** The standalone Settings instance and the shell both write preferences; today's safety is Python lock/merge/fsync. Options: (a) the Settings instance forwards its writes to the live shell over `Quickshell.IpcHandler` — one writer, no new processes *(recommended: both are Quickshell instances, and the plan lists this option first)*; or (b) a minimal prefs helper stays Python. Either way the lock/merge/fsync equivalence tests port to the local set FIRST (leg 1's opening commit), and `weatherSelect` — backend-fed only because it writes preferences — routes natively once D1 lands.
- **D2 — capture/recording and the wallpaper backend paths.** (a) one-shot Python helpers per operation behind the family router (the clipboard/`json_store` precedent: the FS ops stay Python, the QML side owns the flows) *(recommended)*; (b) keep a slim backend binary just for them; (c) park them backend-fed until quickshell gains the FS ops (upstream timing unknown — 0.3.2 lacks them today).
- **D3 — the small domains (900 lines).** Re-home natively per owning family (the interactive ones: privacy, content types, launchpad, appearance/mirror/saver/lock), or retire with the backend where the QML side already covers the surface, or leave as helpers. Each domain can be decided at its leg's review stop.

## 5. Proposed legs (one branch + one review stop each)

- **Leg 1 — preferences coordination (D1).** Port the lock/merge/fsync equivalence tests; land the FileView `atomicWrites` + `watchChanges` JSON adapter and the IpcHandler single-writer; `weatherSelect` routes natively. Exit: the standalone Settings instance and the shell write concurrently for a day without a lost merge.
- **Leg 2 — storage and settings documents.** `storage`/`settings_transfer`/`desktop_features`/`desktop_widgets` re-home; the eq_state and lyrics-cache write paths fold into the single-writer. Exit: G0 + engine cases on both machines; the Settings flows (schema, transfer, feature toggles) parity-checked live.
- **Leg 3 — the retirement sweep.** `ShellState` stops spawning the backend; the JSON-lines protocol, the `Pending.js` host side and the restart supervisor are deleted; the 58 DEPRECATED sites and the §3 retire bucket go; capture/recording per D2; `shell_update` detaches; the shared plumbing per its triage. Exit: `desktop_backend.py` absent from the tree; G0–G3 green on both machines; the fixed-plan probe (the Q3 pattern) exercises every retired family's native path offscreen.
- **Leg 4 — close-out.** `WORKSPACE_MAP.md`'s IPC boundary and every REL tag rewritten in the same commit; G0–G4 + G6 once; 10-launch medians + RSS at 10 s (the standing sanity rule — reported honestly, regression or not); `memory_report.py --label steady` before/after; a live drift day on merged main (the Q4 close-out pattern); the T1 ratio printed by the Q0 counter.

## 6. Verification per leg (the standing discipline)

Test-first: each leg's engine cases land in the local set before its implementation. Sandbox G0 per leg (engine skips documented); the owner's machine runs the full suite with engine cases live per leg; a live day on merged main at leg 4. The A/B window closes WITH the sweep — that is what the window was for. If the live day regresses, the sweep commit is revertible wholesale and the tag at the Q5 close-out pins the pre-Q6 tree.

## 7. What stays Python (unchanged — plan §6)

The deploy chain and its niri KDL validation; `check_architecture.py`, the catalog/schema generators and the gate scripts; `memory_report.py`; the charge-control pkexec helper; and the one-shot helpers of §3 (`file_search`, `clipboard`, `clipboard_watch`, `json_store`, `idle_control`, `shell_update`, plus whatever D2 keeps).

## 8. Risks (plan §7, revisited against the measured tree)

| Risk | Mitigation |
|---|---|
| Preferences single-writer regression (D1) | Equivalence tests ported first; the shell becomes the only writer; a lost-merge check on the owner's machine gates leg 2 |
| Worker-shape change raises peak memory (Q-5) | The backend's PSS disappears with it; G6 + the 10-launch RSS medians at leg 4 measure the landing — reported honestly either way |
| Demo/settings contexts lose the backend (Q-6) | Demo projections exist QML-side; the router carries context checks mirroring `ActionRegistry.check_context`; engine cases cover the demo context |
| The sweep is the migration's largest single change | Severable legs; leg 3 lands only after legs 1–2 verify; the sweep commit reverts wholesale; the pre-Q6 tree is tagged |
| Capture/recording FS ops (D2) | quickshell 0.3.2 lacks them; the one-shot-helper option keeps the flows working without any backend process |
