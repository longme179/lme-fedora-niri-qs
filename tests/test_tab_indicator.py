"""Selection fill must share the button's layout, hover and press geometry."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


@unittest.skipUnless(os.environ.get('LME_TEST_MOTION_UI') == '1', 'opt-in private Wayland indicator checks')
class TabIndicatorCase(unittest.TestCase):
    def test_nested_offsets_resize_hover_press_and_selection(self):
        repo = Path(__file__).resolve().parents[1]
        pointer = os.environ.get('LME_TEST_POINTER')
        drag = os.environ.get('LME_TEST_DRAG')
        if not pointer or not drag:
            raise unittest.SkipTest('Set the private Wayland pointer tools')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('qml', 'scripts', 'config'):
                (root / name).symlink_to(repo / name, target_is_directory=True)
            entry = root / 'shell.qml'
            entry.write_text('''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import "qml/components"
import "qml/services"
ShellRoot {
    id: fixture
    property int choice: 0
    Component.onCompleted: Quickshell.watchFiles = false
    FloatingWindow {
        id: window; fullscreen: true
        Item { id: host; x: 400; y: 100; width: 500; height: 500
            StretchIndicator { id: indicator; vertical: true; targetItem: fixture.choice === 0 ? first : second }
            Item { id: container; x: 4; y: 4; width: 230; height: 200
                ColumnLayout { id: column; x: 3; y: 5; width: container.width
                    LiquidButton { id: first; text: "Elements and\\nfonts"; font.weight: Font.Bold
                        Layout.fillWidth: true; Layout.preferredHeight: 58; selected: fixture.choice === 0; selectionFill: false }
                    LiquidButton { id: second; text: "Appearance"; Layout.fillWidth: true; selected: fixture.choice === 1; selectionFill: false }
                }
            }
        }
    }
    IpcHandler {
        target: "indicatorTest"
        function state(): string {
            const button = fixture.choice === 0 ? first : second;
            const fill = indicator.mapToItem(host, 0, 0, indicator.width, indicator.height);
            const plate = button.plate.mapToItem(host, 0, 0, button.plate.width, button.plate.height);
            const point = button.mapToGlobal(button.width / 2, button.height / 2);
            return JSON.stringify({ready: ShellState.backendReady, fill, plate, radius: indicator.radius, plateRadius: button.plate.radius,
                visible: indicator.visible, hovered: button.hovered, down: button.down, scale: button.scale, x: Math.round(point.x), y: Math.round(point.y)});
        }
        function offsets(): void { container.x = 29; container.y = 37; column.x = 13; column.y = 9; }
        function resize(): void { container.width = 280; }
        function select(index: int): void { fixture.choice = index; }
        function motion(enabled: bool): void { ShellState.run("setting", {key: "animations", value: enabled}); }
    }
}''')
            env = dict(os.environ, LME_SHELL_DEMO='1', XDG_CONFIG_HOME=str(root / 'config-home'),
                       XDG_STATE_HOME=str(root / 'state'), XDG_DATA_HOME=str(root / 'data'))
            with (root / 'gui.log').open('w+') as log:
                process = subprocess.Popen(['quickshell', '-p', str(entry)], env=env, stdout=log, stderr=log)
                def ipc(method, *args):
                    reply = subprocess.run(['quickshell', '-p', str(entry), 'ipc', 'call', 'indicatorTest', method, *args],
                                           env=env, capture_output=True, text=True, timeout=5)
                    if method != 'state': self.assertEqual(reply.returncode, 0, reply.stderr + reply.stdout)
                    return reply.stdout.strip()
                def aligned(state):
                    return all(abs(state['fill'][key] - state['plate'][key]) < .05 for key in ('x', 'y', 'width', 'height')) and abs(state['radius'] - state['plateRadius']) < .05
                def wait(predicate):
                    end = time.monotonic() + 5
                    while time.monotonic() < end:
                        try: state = json.loads(ipc('state'))
                        except ValueError: state = {}
                        if predicate(state): return state
                        time.sleep(.025)
                    log.seek(0); self.fail('Indicator mismatch: ' + str(state) + '\n' + log.read())
                try:
                    wait(lambda s: s.get('ready') and aligned(s))
                    ipc('offsets'); wait(lambda s: aligned(s) and s['plate']['x'] == 42)
                    ipc('resize'); wait(lambda s: aligned(s) and abs(s['plate']['width'] - 280) < .05)
                    for choice in (1, 0):
                        ipc('select', str(choice)); state = wait(lambda s: aligned(s))
                        hover = subprocess.Popen([str(Path(pointer).with_name('pointer-move')), str(state['x']), str(state['y']), '6000'], env=env)
                        try:
                            wait(lambda s: s['hovered'] and s['scale'] > 1.009 and aligned(s))
                            press = subprocess.Popen([drag, str(state['x']), str(state['y']), str(state['x']), str(state['y'])], env=env)
                            try: wait(lambda s: s['down'] and s['scale'] < .99 and aligned(s))
                            finally: press.wait(timeout=5)
                        finally: hover.terminate(); hover.wait(timeout=5)
                        wait(lambda s: aligned(s) and not s['down'])
                    ipc('motion', 'false'); wait(lambda s: s['scale'] == 1 and aligned(s))
                    ipc('select', '1'); wait(lambda s: aligned(s))
                    log.seek(0); output = log.read()
                    for problem in ('TypeError', 'ReferenceError', 'Binding loop', 'Unable to assign', 'Failed to load configuration'):
                        self.assertNotIn(problem, output)
                finally:
                    process.terminate(); process.wait(timeout=5)
