#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
target="${XDG_DATA_HOME:-$HOME/.local/share}/applications/lme-shell-settings.desktop"
dry_run=false
replace=false
while (($#)); do
    case "$1" in
        --dry-run) dry_run=true ;;
        --replace) replace=true ;;
        --target)
            if (($# < 2)) || [[ -z "$2" ]]; then printf 'Error: --target requires a path.\n' >&2; exit 2; fi
            target="$2"; shift ;;
        --help|-h) printf 'Usage: scripts/install-settings.sh [--dry-run] [--replace] [--target PATH]\nInstall the settings app launcher. Keep this checkout after installation.\n'; exit 0 ;;
        *) printf 'Error: unknown argument: %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done
export LME_SETTINGS_INSTALL_REPO="$repo_dir"
python3 - "$target" "$dry_run" "$replace" <<'PY'
import os, pathlib, sys, tempfile, time
repo = pathlib.Path(os.environ['LME_SETTINGS_INSTALL_REPO'])
target = pathlib.Path(os.path.abspath(os.path.expanduser(sys.argv[1])))
target = target.parent.resolve() / target.name
dry, replace = sys.argv[2] == 'true', sys.argv[3] == 'true'
if target == pathlib.Path('/') or repo == target or repo in target.parents or target in repo.parents or target.is_dir():
    sys.exit('Error: choose a desktop entry path outside the checkout.')
launcher = str(repo / 'scripts/settings.sh')
# Desktop Entry Exec quoting has its own escaping rules, separate from a shell.
if any(c in launcher for c in '\n\r'):
    sys.exit('Error: the checkout path must not contain newlines.')
quoted = launcher.replace('\\', '\\\\\\\\').replace('"', '\\\\"').replace('`', '\\\\`').replace('$', '\\\\$').replace('%', '%%')
entry = '[Desktop Entry]\nType=Application\nName=LME Shell Settings\nComment=Personalize your Liquid Material desktop\nExec="' + quoted + '"\nIcon=preferences-system\nTerminal=false\nCategories=Settings;DesktopSettings;\nStartupNotify=false\n'
exists = target.exists() or target.is_symlink()
if exists and not target.is_symlink() and target.read_bytes() == entry.encode():
    print('Already installed:', target); sys.exit(0)
if exists and not replace:
    sys.exit('Error: target exists. Use --replace to preserve it in a backup.')
print('Install settings launcher:', target)
if dry:
    sys.exit(0)
target.parent.mkdir(parents=True, exist_ok=True)
backup = None
fd, temporary = tempfile.mkstemp(dir=target.parent, prefix='.lme-settings-')
try:
    with os.fdopen(fd, 'w') as stream:
        stream.write(entry)
    os.chmod(temporary, 0o644)
    if exists:
        backup = target.with_name(target.name + '.backup-' + time.strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid()))
        target.rename(backup)
    os.replace(temporary, target)
except Exception:
    if backup is not None and not target.exists():
        backup.rename(target)
    raise
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
