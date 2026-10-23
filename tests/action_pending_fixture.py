"""Private copied checkout observability and one fake Bluetooth tool."""
import json
from pathlib import Path
import sys

from clipboard_slice_fixture import World

BT = '/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF'
OBSERVE = '''
    property bool pendingReenter: false
    Connections {
        target: ShellState
        function onLastResultChanged() {
            if (root.pendingReenter && ShellState.lastResult.action === "calculate") {
                root.pendingReenter = false;
                ShellState.run("calculate", {query:"2+2"});
            }
        }
    }
    IpcHandler {
        target: "actionPending"
        function state(): string {
            const button = root.sliceFind(root.sliceSurface, "bluetoothDevice-/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF");
            return JSON.stringify({ready:ShellState.backendReady, pending:ShellState.pendingActions,
                wire:ShellState.snapshot.actionPending, result:ShellState.lastResult,
                button:button ? button.enabled : null, open:ShellState.panelOpen});
        }
        function run(action: string, payload: string): void { ShellState.run(action, JSON.parse(payload)); }
        function devices(): void { ShellState.selectControlTab("devices"); }
        function restart(): void { ShellState.backend.running = false; }
        function reenter(): string {
            const frame = Object.assign({}, ShellState.snapshot, {lastResult:{action:"calculate",ok:true,message:"2",sequence:-10}});
            root.pendingReenter = true;
            ShellState.accept(JSON.stringify(frame));
            return JSON.stringify({pending:!!ShellState.pendingActions.calculate});
        }
        function delayed(): string {
            const frame = Object.assign({}, ShellState.snapshot, {lastResult:{action:"calculate",ok:true,message:"old",sequence:-11}});
            ShellState.run("calculate",{query:"3+3",clientSerial:9007199254740991});
            ShellState.accept(JSON.stringify(frame));
            return JSON.stringify({pending:!!ShellState.pendingActions.calculate});
        }
    }
'''


def world(directory, legacy=False):
    fixture = World(Path(directory))
    values = json.loads(fixture.settings.read_text()); values.update(bluetoothPairing=False)
    fixture.settings.write_text(json.dumps(values))
    for source in ('shell.qml', 'qml/settings/SettingsApplication.qml'):
        path = fixture.root/source
        path.write_text(path.read_text().replace('    id: root\n', '    id: root\n'+OBSERVE, 1))
    fixture.hold, fixture.started, fixture.fail = (fixture.home/name for name in ('hold', 'started', 'fail'))
    binary = fixture.home/'bin/busctl'
    binary.write_text('#!'+sys.executable+'\nimport sys,time\nfrom pathlib import Path\n'
        f'hold,started,fail=map(Path,{[str(fixture.hold),str(fixture.started),str(fixture.fail)]!r})\n'
        'if sys.argv[-1] in ("Connect","Disconnect"):\n'
        '    started.touch()\n'
        '    while hold.exists(): time.sleep(.01)\n'
        '    if fail.exists(): print("Device unavailable",file=sys.stderr);sys.exit(1)\n')
    binary.chmod(0o700)
    backend = fixture.root/'scripts/desktop_backend.py'
    text = backend.read_text()
    stub = f'\nDesktopBackend.bluetooth = lambda self: dict(available=True,enabled=True,batteries=[],devices=[dict(path={BT!r},name="Fixture headset",connected=False,paired=True)])\n'
    if legacy:
        stub += '''
_pending_original_emit = emit
def emit(backend):
    import io
    from contextlib import redirect_stdout
    output = io.StringIO()
    with redirect_stdout(output): _pending_original_emit(backend)
    frame = json.loads(output.getvalue())
    frame.pop('actionPending', None)
    print(json.dumps(frame), flush=True)
'''
    backend.write_text(text.replace('if __name__ == "__main__":', stub+'\nif __name__ == "__main__":'))
    return fixture
