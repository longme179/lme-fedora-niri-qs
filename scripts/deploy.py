"""Explicit owner-invoked deployment: verified runtime, journalled niri integration."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys

from deploy_files import desktop, desktop_exec, paths, wrapper
from deploy_niri import plan
from deploy_niri_tree import validate
from deploy_runtime import ensure, run, version
from deploy_state import Transaction, fingerprint
from storage import locked

ROOT = Path(__file__).resolve().parents[1]


def parse():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Apply the plan (default: dry-run)')
    parser.add_argument('--copr', action='store_true', help='Allow the documented third-party Quickshell COPR')
    parser.add_argument('--build-quickshell', action='store_true', help='Allow pinned private source fallback if packages are incompatible')
    parser.add_argument('--charge-helper', action='store_true', help='Install the optional privileged charging helper')
    parser.add_argument('--replace', action='store_true', help='Back up and replace unrelated launcher/install targets')
    parser.add_argument('--skip-packages', action='store_true', help='Use already-provisioned dependencies; still verify runtime/config')
    parser.add_argument('--start', action='store_true', help='Start the installed shell once, in this niri session')
    parser.add_argument('--quickshell', help='Use this executable; never silently replace an explicit choice')
    parser.add_argument('--niri-config', type=Path, help='Root config used by niri --config (default: NIRI_CONFIG or XDG config)')
    parser.add_argument('--jobs', type=int, default=2, choices=range(1, 17), metavar='1..16', help='Source build parallelism (default: 2)')
    parser.add_argument('--rollback', type=Path, metavar='REPORT_DIR', help='Restore a previous journal; refuse later user edits')
    return parser.parse_args()


def session_conflicts(config):
    # Report external ownership; never kill running agents or rewrite desktop autostarts.
    for folder in (config/'autostart', Path('/etc/xdg/autostart')):
        if folder.is_dir():
            for path in sorted(folder.glob('*.desktop')):
                if any(word in path.name.lower() for word in ('polkit', 'policykit', 'mako', 'dunst', 'swaync', 'waybar')):
                    print(f'Review external session agent: {path} (not changed)')
    print('Existing session processes/services are not stopped. Log out/in after resolving duplicate agents.')


def start_shell(command, binary):
    if not os.environ.get('NIRI_SOCKET') or not os.environ.get('WAYLAND_DISPLAY'):
        raise ValueError('--start requires a running niri Wayland session; deployment remains installed')
    # --daemonize waits for configuration load; IPC verifies an actual loaded shell.
    run([command, 'start', '--daemonize'])
    reply = subprocess.run([str(binary), '-c', 'lme-shell', 'ipc', 'call', 'shell', 'nightLightStatus'],
                            capture_output=True, text=True, timeout=10)
    if reply.returncode or not reply.stdout.strip().startswith('{'):
        raise ValueError('Shell did not confirm IPC readiness. Run lme-shell doctor; inspect quickshell logs.')


def deploy(args):
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config'))).expanduser().absolute()
    data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share'))).expanduser().absolute()
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))).expanduser().absolute()
    root = args.niri_config or Path(os.environ.get('NIRI_CONFIG') or config/'niri/config.kdl')
    targets = paths(ROOT, config, data, args.replace)
    shell, command, entry, managed = targets
    niri = shutil.which('niri')
    found = version(niri)[:2] if niri else (26, 4)
    if found < (25, 11): raise ValueError('niri >=25.11 is required; update niri first')
    changes, notes = plan(root, ROOT, config/'lme-shell', command, found)
    print('LME Shell deployment '+('(apply)' if args.install else '(dry-run; no writes)'))
    print(f'Checkout: {ROOT}\nShell link: {shell}\nCommand: {command}\nDesktop entry: {entry}\nVerified runtime link: {managed}')
    for note in notes: print(note)
    for path in changes: print('Write niri config: '+str(path))
    print('Shortcuts: Mod+Space launcher; Mod+A controls; Mod+V clipboard; Mod+N notifications;')
    print('Mod+Comma Settings; Mod+Tab overview; Mod+Shift+Tab board; Mod+Shift+A activity; Mod+Shift+E power.')
    session_conflicts(config)
    if not args.install:
        flags = ['--optional']+(['--copr'] if args.copr else [])
        if not args.skip_packages: run([ROOT/'scripts/install-fedora.sh', *flags])
        print('Apply with --install. Runtime APIs and staged niri config will be validated before publication.')
        return
    if os.geteuid() == 0: raise ValueError('Run deploy as your desktop user, not sudo; privileged steps ask separately')
    if args.start and (not os.environ.get('NIRI_SOCKET') or not os.environ.get('WAYLAND_DISPLAY')):
        raise ValueError('--start requires niri; omit it when deploying from a TTY')
    before = {path: fingerprint(path) for path in (*targets, *changes)}
    report = state/'lme-shell/deployments'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-'+str(os.getpid()))
    tx = Transaction(report)
    print('Report and rollback journal: '+str(report), flush=True)
    rollback = shlex.join([str(ROOT/'scripts/deploy.sh'), '--rollback', str(report)])
    summary = report/'report.txt'
    summary.write_text('\n'.join([f'Checkout: {ROOT}', f'Request: {vars(args)}',
        'Packages, repositories, source builds and the optional charge helper are not uninstalled by rollback.',
        f'Rollback: {rollback}'])+'\n')
    try:
        if not args.skip_packages:
            run([ROOT/'scripts/install-fedora.sh', '--install', '--optional', *(['--copr'] if args.copr else [])])
        binary = ensure(args.quickshell or os.environ.get('LME_QS_BINARY'), managed, data,
                        copr=args.copr, source=args.build_quickshell, jobs=args.jobs)
        niri = shutil.which('niri')
        if not niri: raise ValueError('niri is missing after provisioning')
        found = version(niri)[:2]
        if found < (25, 11): raise ValueError('niri >=25.11 is required')
        # Re-plan if package installation upgraded niri, never publish unvalidated edits.
        changes, notes = plan(root, ROOT, config/'lme-shell', command, found)
        validate(root.expanduser().absolute(), changes, niri)
        if args.charge_helper: run(['sudo', ROOT/'scripts/install-charge-helper.sh', '--install'])
        for path, original in before.items():
            if fingerprint(path) != original: raise ValueError(f'File changed during provisioning; retry: {path}')
        tx.link(shell, ROOT)
        tx.link(managed, binary)
        tx.write(command, wrapper(ROOT, managed), mode=0o755)
        tx.write(entry, desktop(desktop_exec(command)+' settings')+b'X-LME-Deployment=true\n')
        # Root include is published last, after all its dependencies exist.
        actual_root = root.expanduser().resolve()
        for path, content in sorted(changes.items(), key=lambda pair: pair[0] == actual_root): tx.write(path, content)
        result = subprocess.run([niri, 'validate', '--config', str(root)], capture_output=True, text=True, timeout=30)
        if result.returncode: raise ValueError('Published niri validation failed:\n'+result.stdout+result.stderr)
        tx.finish()
    except BaseException as exc:
        with summary.open('a') as stream: stream.write(f'FAILED: {exc}\n')
        Transaction.rollback(report)
        print('User-file changes rolled back; packages/builds/helper are retained.', file=sys.stderr)
        raise
    with summary.open('a') as stream: stream.write('\n'.join([f'Runtime: {binary}', *notes, 'Status: complete'])+'\n')
    print(f'Deployed; {len(tx.entries)} file changes. Read {report}/changes.diff and report.txt.')
    print('Rollback: '+rollback)
    missing = [name for name in ('awww', 'awww-daemon', 'gowall', 'satty') if not shutil.which(name)]
    if missing: print('Optional tools not installed: '+', '.join(missing)+'; see docs/INSTALL.md.')
    print(f'Run {command} doctor inside niri. Log out/in to replace existing bars/agents cleanly.')
    if args.start: start_shell(command, binary)


def main():
    args = parse()
    try:
        if args.rollback:
            if os.geteuid() == 0: raise ValueError('Run rollback as your desktop user, not sudo')
            with locked(args.rollback.absolute().parent.parent/'deploy.lock'): Transaction.rollback(args.rollback)
            print('Rolled back user files; packages/repositories/helper retained.')
        elif args.install:
            if os.geteuid() == 0: raise ValueError('Run deploy as your desktop user, not sudo')
            state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state')))
            with locked(state/'lme-shell/deploy.lock'): deploy(args)
        else: deploy(args)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print('Deployment failed: '+str(exc), file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
