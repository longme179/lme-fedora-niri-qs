# One-command deployment

Owner authorization, 2026-10-30: the new deploy command may patch niri config.
Legacy file/package installers keep their conservative behavior. Never modify
the real session while developing; tests use disposable XDG/config directories.
Use Ponytail + Modularity; no new daemon, runtime settings schema or dependencies.

## Run it

From a permanent checkout, as your desktop user (do **not** sudo this command):

```bash
./scripts/deploy.sh                         # Read-only plan
./scripts/deploy.sh --install --copr --build-quickshell --charge-helper
```

DNF and sudo retain their interactive confirmations. `--copr` authorizes the
documented third-party repository only if needed; `--build-quickshell` permits
the pinned private fallback only if package/runtime probes fail. The fallback
uses two compiler jobs by default (`--jobs 1` for less temporary build memory).
Building can take several minutes; it is not a new persistent process.

Add `--replace` to back up and replace an unrelated existing shell link, Settings
desktop entry or command. Conflicts are checked before installing packages.
Old `setup.sh` remains available for manual niri integration.

After deployment, log out and select **niri** at your login screen, then log in.
The script does not replace your login manager, stop current agents or force a
logout. If already in niri, `--start` optionally starts the shell immediately
with duplicate protection and an IPC readiness check. Starting retains the
existing saved wallpaper/confirmed-display restoration behavior.

```bash
~/.local/bin/lme-shell doctor
~/.local/bin/lme-shell settings
```

The default config is `$NIRI_CONFIG`, or `$XDG_CONFIG_HOME/niri/config.kdl`.
If you launch niri with another `--config`, pass `--niri-config /absolute/path`.
Existing manually provisioned dependencies: `--skip-packages --quickshell PATH`.
Neither command bypasses the runtime capability probe or niri validation.

## Exactly what changes

| Target | Change |
| --- | --- |
| `~/.config/quickshell/lme-shell` | Link to this checkout; keep the checkout in place |
| `~/.local/bin/lme-shell` | Start/Settings/doctor/toggle wrapper |
| `$XDG_DATA_HOME/applications/lme-shell-settings.desktop` | Settings launcher |
| `$XDG_DATA_HOME/lme-shell/deployment/bin/quickshell` | Link to the verified runtime; system `quickshell` stays installed |
| niri root and active includes | Preserve text; prefix conflicting shortcut/startup nodes with `/-`; append one managed include last |
| `niri/lme-shell-deploy.kdl` | Startup, nine shortcuts, floating Settings rules and supported non-xray blur rules |
| `$XDG_STATE_HOME/lme-shell/deployments/…` | Private backups, manifest, `changes.diff`, `report.txt`, including failed attempts |

Unset XDG paths use the standard `~/.config`, `~/.local/share`, `~/.local/state`
defaults. Existing niri symlinks are retained. Customized old LME fragments are
patched selectively; identical bundled copies are replaced by the managed include.
Existing global blur settings are preserved. On niri >=26.04, the optional
Settings-generated `lme-shell/liquid-blur.kdl` is included automatically.
On older supported niri, blur integration is omitted and reported by the version.

Conflicts covered: Mod+Space, Mod+A, Mod+V, Mod+N, Mod+Comma, Mod+Tab,
Mod+Shift+Tab, Mod+Shift+A, Mod+Shift+E; simple Waybar/Mako/Dunst/SwayNC/known
Polkit-agent startup commands. Other binds, outputs, input settings and startup
commands are retained. Ambiguous shell pipelines/chains stop deployment.
External desktop autostarts are reported for review, not rewritten. Keep only one
notification server and Polkit agent in the eventual session.

Shell settings/history/widget data are untouched. Optional awww/Gowall/Satty
availability is printed; unavailable packages/models/codecs are not claimed to
be installed. No GPU driver, power provider or service policy is replaced.

## Inspect and undo

The command prints its report directory and an exact rollback command. Read
`report.txt` and `changes.diff` there, then, if needed:

```bash
./scripts/deploy.sh --rollback /path/printed/by/deploy
```

Rollback checks **all** targets first and refuses later user edits; review/restore
those manually instead of forcing it. It restores files, directories, modes and
symlinks, and does not remove existing shell preferences. Empty parent directories
may remain. Packages, enabled COPR repositories, build dependencies/private builds
and the optional privileged charge helper are retained; use DNF history and the
charge-helper guide to review those separately. Runtime/system Quickshell is
never globally replaced. Re-running deploy creates a new report, with zero file
changes when the installation is already correct.

## Implementation contracts

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

Tests: compatibility/source command selection, token parity, include/shortcut/
startup edits and idempotence; real niri validation where available; journal and
rollback/failure/concurrent edits; fake privileged commands and end-to-end isolated
deployment. No old assertion edits. Run affected G0/installation tests and native
compatibility checks, then required final regression once before merge review.
Fedora DNF, source compilation on Fedora and physical device/session checks remain
"needs real-session check" unless actually executed there. Record skips explicitly.
