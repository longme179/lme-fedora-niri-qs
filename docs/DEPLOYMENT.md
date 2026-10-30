# One-command deployment

Owner authorization, 2026-10-30: the new deploy command may patch niri config.
Legacy file/package installers keep their conservative behavior. Never modify
the real session while developing; tests use disposable XDG/config directories.
Use Ponytail + Modularity; no new daemon, runtime settings schema or dependencies.

## Plan and contracts

1. Default is a read-only plan. `--install` applies as the desktop user; only DNF
   and the optional existing charge-helper installer use sudo. `--replace` permits
   replacing unrelated install targets with backups. No GPU driver/service policy.
2. Reuse the Fedora package helper. Verify the selected executable (not just RPM
   presence): Quickshell >=0.3.2 and isolated QML imports/per-corner Region APIs.
   If unsuitable, `--copr` allows the documented repository and upgrade; the
   explicitly allowed `--build-quickshell` fallback builds pinned upstream
   4f508be500dea6e5732cc3d50382a0048b17e7b1 into a private Qt-versioned prefix.
   Verify again before publishing any shell/niri files. Never claim package
   installation alone proves compatibility. Missing optional tools are reported.
3. Keep the existing start/Settings/doctor facades. Prefer the verified deployment
   binary when present; an installed `lme-shell` wrapper exposes start/settings/
   doctor/toggle without replacing system Quickshell. Start uses duplicate guard
   only when explicitly requested; preview retains its current behavior.
4. Follow active niri includes using the existing KDL tokenizer/parser, with a
   backward-compatible optional token-offset view. Disable only conflicting LME
   shortcuts, duplicate LME includes/startups and simple known bar/notification/
   Polkit startup commands, preserving their text with `/-`. Reject ambiguous
   mixed shell commands and unwritable included files rather than guess.
5. Append one managed include last. Generate startup, shortcuts, floating-window
   and supported non-xray blur rules. Preserve existing global blur; wire the
   optional Settings-created liquid-blur snippet. Preserve other custom settings.
   Missing user config gets a small usable base, without changing output modes.
6. Stage candidates next to their originals to preserve relative resource paths;
   validate the complete staged include tree with `niri validate --config` before
   atomic writes. A private journal holds backups, checksums and a readable diff.
   Failure restores unchanged tool writes. `--rollback REPORT_DIR` refuses later
   edits; packages/repositories/build dependencies are reported, not uninstalled.
7. Repeat deploy is idempotent. Existing running shell/agents are not killed.
   `--start` is optional, inside niri only, duplicate-safe and health-checked;
   existing conflicting session agents require logout/login. Never force logout.

Tests first: compatibility/source command selection, token parity, include/shortcut/
startup edits and idempotence; real niri validation where available; journal and
rollback/failure/concurrent edits; fake privileged commands and end-to-end isolated
deployment. No old assertion edits. Run affected G0/installation tests and native
compatibility checks, then required final regression once before merge review.
Fedora DNF, source compilation on Fedora and physical device/session checks remain
"needs real-session check" unless actually executed there. Record skips explicitly.
