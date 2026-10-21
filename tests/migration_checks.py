"""Execute documented migration gates and retain explicit skip evidence."""
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = Path(os.environ['LME_GATE_REPO'])
OUT = Path(os.environ['LME_GATE_OUTPUT'])
GATES = {
    'G0': ([], ['./scripts/check.sh']),
    'G1': (['PERSONALIZATION_UI'], ['migration_startup.SmokeCase', 'test_settings_startup.NativeSettingsStartupCase']),
    'G2': (['PERSONALIZATION_UI'], ['test_settings_startup.NativeSettingsStartupCase', 'test_personalization.NativePersonalizationCase']),
    'G3': (['UPGRADE_UI'], ['test_control_grid.ControlGridUiCase', 'test_upgrade_ui.UpgradeInterfaceCase', 'test_bar_gestures.BarGestureQmlCase', 'test_navigation.TabContractCase', 'test_navigation.NativeTabCase', 'test_feature_catalog', 'test_catalog_failures', 'test_catalog_compact']),
    'G4': (['CLIPBOARD_NATIVE', 'CLIPBOARD_UI', 'ANNOTATION_UI', 'CAPTURE_UI'], ['test_clipboard.NativeClipboardCase', 'test_clipboard.ClipboardInterfaceCase', 'test_image_annotation_ui.AnnotationInterfaceCase', 'test_capture_night']),
    'G5': (['DISPLAY_WATCHDOG', 'UPGRADE_UI'], ['test_upgrades.DetachedDisplayCase', 'test_managed_commands.ManagedCommandsCase', 'test_battery_saver', 'test_battery_saver_backend', 'test_battery_saver_qml']),
    'G6': (['POLLING_UI'], ['test_launchpad.LaunchpadCase', 'test_launchpad.LaunchpadQmlCase', 'test_polling_ui.NativePollingCase']),
}


def selected_env(env):
    prefixes = ('LME_TEST_', 'XDG_', 'QT_', 'QSG_', 'WLR_', 'DBUS_', 'LIBGL_')
    names = ('PATH', 'LD_LIBRARY_PATH', 'QML_IMPORT_PATH', 'WAYLAND_DISPLAY', 'SWAYSOCK', 'NIRI_SOCKET', 'LME_SHELL_DEMO')
    return {key: value for key, value in env.items() if key.startswith(prefixes) or key in names}


def run_gate(name):
    flags, tests = GATES[name]
    env = {key: value for key, value in os.environ.items() if not key.startswith('LME_TEST_') or key in ('LME_TEST_POINTER', 'LME_TEST_DRAG', 'LME_TEST_POINTER_RIGHT')}
    env.update({'LME_TEST_'+key: '1' for key in flags})
    command = tests if name == 'G0' else [sys.executable, '-m', 'unittest', '-v', *tests]
    started = time.monotonic()
    with (OUT/(name+'.log')).open('w') as log:
        try: code = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=1200).returncode
        except subprocess.TimeoutExpired: code = 124
    elapsed = time.monotonic()-started
    text = (OUT/(name+'.log')).read_text(errors='replace')
    counts = re.findall(r'Ran (\d+) tests? in ', text)
    total = int(counts[-1]) if counts else 0
    skipped = [{'name': match[2], 'reason': match[3]} for match in re.finditer(r'^(\w+) \(([^)]+)\) .*?skipped (.+)$', text, re.M)]
    match = re.search(r'^(?:OK|FAILED)(?: \(([^\n]+)\))?$', text, re.M)
    summary = dict(re.findall(r'(\w+)=(\d+)', match[1] or '')) if match else {}
    failed = int(summary.get('failures', 0)) + int(summary.get('errors', 0))
    skip_count = int(summary.get('skipped', 0))
    status = 'failed' if code or not counts else 'completed-with-skips' if skip_count else 'passed'
    result = dict(gate=name, command=command, env=selected_env(env), returncode=code, status=status,
                  tests=total, passed=total-failed-skip_count, failed=failed, skipped=skip_count,
                  skipped_tests=skipped, wall_seconds=round(elapsed, 3), log=name+'.log')
    if len(skipped) != skip_count:
        result['skip_parse_error'] = 'See complete log; parsed skips do not match summary'
        result['status'] = 'failed'
    if name == 'G0':
        imports = [arg for path in env.get('QML_IMPORT_PATH', '').split(':') if path for arg in ('-I', path)]
        lint_started = time.monotonic(); errors = warnings = 0
        files = sorted(ROOT.rglob('*.qml'))
        with (OUT/'qmllint.log').open('w') as log:
            for path in files:
                reply = subprocess.run(['qmllint', *imports, str(path)], env=env, capture_output=True, text=True, timeout=30)
                output = reply.stdout+reply.stderr; log.write(str(path)+'\n'+output)
                errors += sum(line.startswith('Error:') for line in output.splitlines())
                warnings += sum(line.startswith('Warning:') for line in output.splitlines())
        result['qmllint'] = dict(command=['qmllint', *imports, '<each QML file>'], files=len(files), errors=errors, warnings=warnings, wall_seconds=round(time.monotonic()-lint_started, 3))
        if errors: result['status'] = 'failed'
    (OUT/(name+'.json')).write_text(json.dumps(result, indent=2)+'\n')
    print(name+': '+result['status']+'; '+str(result['passed'])+' passed / '+str(failed)+' failed / '+str(skip_count)+' skipped; '+str(result['wall_seconds'])+'s', flush=True)
    return result


def main():
    cpu = next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), 'unknown')
    metadata = dict(head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                    machine=platform.platform(), cpu=cpu, logical_cpus=os.cpu_count(),
                    graphics='headless Sway pixman; Qt RHI/OpenGL forced Mesa software; no hardware GPU claim',
                    env=selected_env(os.environ))
    (OUT/'machine.json').write_text(json.dumps(metadata, indent=2)+'\n')
    results = [run_gate(name) for name in os.environ['LME_GATE_SET'].split(',')]
    count = int(os.environ['LME_GATE_STARTUP_RUNS'])
    if count:
        from migration_startup import measure
        try:
            measurements = measure(count)
            (OUT/'startup.json').write_text(json.dumps(measurements, indent=2)+'\n')
            print('Startup medians: '+str({key: measurements[key]['median_seconds'] for key in ('preview', 'settings')}), flush=True)
        except Exception as exc:
            (OUT/'startup-error.txt').write_text(str(exc)+'\n')
            print('Startup measurement failed: '+str(exc), flush=True)
            return 1
    (OUT/'summary.json').write_text(json.dumps(results, indent=2)+'\n')
    return int(any(item['status'] == 'failed' or item['skipped'] and item['gate'] != 'G0' for item in results))


if __name__ == '__main__':
    raise SystemExit(main())
