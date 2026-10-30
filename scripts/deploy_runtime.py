"""Verify the actual Quickshell APIs; optionally build a pinned, private runtime."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

COMMIT = '4f508be500dea6e5732cc3d50382a0048b17e7b1'  # upstream version: 0.3.2
UPSTREAM = 'https://github.com/quickshell-mirror/quickshell.git'
PROBE = '''import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Io
import Quickshell.Services.SystemTray
import Quickshell.Services.Pipewire
import Quickshell.Services.Polkit
import Quickshell.Services.Mpris
import Quickshell.Services.Notifications
ShellRoot {
    Region { width: 20; height: 20; topLeftRadius: 2; topRightRadius: 2; bottomLeftRadius: 2; bottomRightRadius: 2 }
    FileView { id: receipt; path: Quickshell.env("HOME") + "/probe.ok"; preload: false; blockWrites: true }
    Component.onCompleted: { receipt.setText("LME_RUNTIME_OK"); console.log("LME_RUNTIME_OK") }
    Timer { interval: 50; running: true; onTriggered: Qt.quit() }
}
'''


def run(argv, **kwargs):
    print('+ '+__import__('shlex').join(map(str, argv)), flush=True)
    return subprocess.run(list(map(str, argv)), check=True, **kwargs)


def version(binary):
    reply = subprocess.run([str(binary), '--version'], capture_output=True, text=True, timeout=10)
    match = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', reply.stdout+reply.stderr)
    if reply.returncode or not match: raise ValueError(f'Cannot identify runtime version: {binary}')
    return tuple(int(part or 0) for part in match.groups())


def probe(binary):
    found = version(binary)
    if found < (0, 3, 2): raise ValueError(f'{binary}: Quickshell >=0.3.2 required, found {found}')
    with tempfile.TemporaryDirectory(prefix='lme-runtime-') as raw:
        folder = Path(raw); entry = folder/'shell.qml'; entry.write_text(PROBE)
        env = {k: v for k, v in os.environ.items() if k not in ('WAYLAND_DISPLAY', 'DISPLAY', 'NIRI_SOCKET', 'DBUS_SESSION_BUS_ADDRESS')}
        env.update(HOME=raw, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
        for key in ('XDG_CONFIG_HOME', 'XDG_STATE_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_RUNTIME_DIR'):
            path = folder/key; path.mkdir(mode=0o700); env[key] = str(path)
        reply = subprocess.run([str(binary), '-p', str(entry)], env=env, capture_output=True, text=True, timeout=20)
        output = reply.stdout+reply.stderr
        receipt = folder/'probe.ok'
        confirmed = receipt.is_file() and receipt.read_text() == 'LME_RUNTIME_OK'
        # console.log is debug-level and can be suppressed by distro/user logging rules.
        if reply.returncode or not (confirmed or 'LME_RUNTIME_OK' in output) or 'Failed to load configuration' in output:
            raise ValueError(f'{binary}: required QML capabilities unavailable:\n{output[-4000:]}')
    return found


def candidates(explicit, managed):
    if explicit:
        value = shutil.which(explicit)
        if not value: raise ValueError(f'Runtime not executable: {explicit}')
        return [Path(value).resolve()]
    values = [managed, shutil.which('quickshell'), shutil.which('qs')]
    return list(dict.fromkeys(Path(p).resolve() for p in values if p and Path(p).is_file()))


def build(data, jobs):
    dependencies = ['gcc-c++', 'cmake', 'ninja-build', 'git', 'pkgconf-pkg-config', 'pam-devel',
                    'cmake(Qt6Core)', 'cmake(Qt6Quick)', 'cmake(Qt6QuickPrivate)', 'cmake(Qt6QuickControls2)',
                    'cmake(Qt6WaylandClient)', 'cmake(Qt6WaylandClientPrivate)', 'cmake(Qt6ShaderTools)',
                    'cmake(CLI11)', 'cmake(VulkanHeaders)', 'pkgconfig(wayland-client)', 'pkgconfig(wayland-protocols)',
                    'pkgconfig(libpipewire-0.3)', 'pkgconfig(polkit-agent-1)', 'pkgconfig(polkit-gobject-1)',
                    'pkgconfig(libdrm)', 'pkgconfig(gbm)', 'pkgconfig(egl)', 'pkgconfig(jemalloc)']
    run(['sudo', 'dnf', 'install', *dependencies])
    qt = subprocess.check_output(['pkg-config', '--modversion', 'Qt6Core'], text=True).strip()
    if not re.fullmatch(r'[0-9.]+', qt): raise ValueError('Cannot identify Qt version for private build')
    prefix = data/'lme-shell/runtime'/f'quickshell-{COMMIT[:12]}-qt{qt}'
    binary = prefix/'bin/quickshell'
    if (prefix/'.lme-build.json').is_file() and binary.is_file():
        probe(binary); return binary.resolve()
    if prefix.exists(): raise ValueError(f'Unverified build directory exists; inspect/remove before retrying: {prefix}')
    prefix.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lme-build-', dir=prefix.parent) as raw:
        source = Path(raw)/'source'; output = Path(raw)/'build'
        run(['git', 'init', source])
        run(['git', '-C', source, 'fetch', '--depth=1', UPSTREAM, COMMIT])
        run(['git', '-C', source, 'checkout', '--detach', 'FETCH_HEAD'])
        actual = subprocess.check_output(['git', '-C', source, 'rev-parse', 'HEAD'], text=True).strip()
        if actual != COMMIT: raise ValueError('Pinned Quickshell commit mismatch')
        run(['cmake', '-S', source, '-B', output, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
             f'-DCMAKE_INSTALL_PREFIX={prefix}', '-DCRASH_HANDLER=OFF', '-DHYPRLAND=OFF', '-DI3=OFF', '-DX11=OFF'])
        run(['cmake', '--build', output, '--parallel', str(jobs)])
        run(['cmake', '--install', output])
    probe(binary)
    (prefix/'.lme-build.json').write_text(json.dumps(dict(commit=COMMIT, qt=qt))+'\n')
    return binary.resolve()


def ensure(explicit, managed, data, copr=False, source=False, jobs=2):
    errors = []
    for binary in candidates(explicit, managed):
        try: probe(binary); return binary
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc: errors.append(str(exc))
    if copr and not explicit:
        run(['sudo', 'dnf', 'copr', 'enable', 'errornointernet/quickshell'])
        run(['sudo', 'dnf', 'upgrade', '--refresh', 'quickshell'])
        for binary in candidates(None, managed):
            try: probe(binary); return binary
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc: errors.append(str(exc))
    if source and not explicit: return build(data, jobs)
    raise ValueError('\n'.join(errors)+ '\nNo compatible Quickshell. Retry with --copr --build-quickshell, or --quickshell PATH.')
