"""Copied-checkout UI with actual backend/workers and a fake NetworkManager CLI.
Contract: network_ui_fixture.py covers network_ui_fixture behavior/contracts; check imports for fixtures/helpers under test.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import sys

from clipboard_slice_fixture import World, Probe
from network_fixture import data

OBSERVE = '''
    function networkFind(name) {
        let top=root.sliceSurface;while(top && top.parent) top=top.parent;
        return root.sliceFind(top,name);
    }
    property var networkObservedResult: ({})
    Connections {
        target: ShellState
        function onLastResultChanged() {
            const value=ShellState.lastResult;
            if (value && String(value.action).startsWith("network")) root.networkObservedResult=Object.assign({},value);
        }
    }
    IpcHandler {
        target: "networkWorkflow"
        function open(): void { if(!ShellState.panelOpen) ShellState.togglePanel("wifi"); }
        function close(): void { ShellState.closePanels(); }
        function click(name: string): bool {
            const button=root.networkFind(name);
            if(!button || !button.enabled) return false;button.clicked();return true;
        }
        function choose(name: string, index: int): bool {
            const field=root.networkFind(name);
            if(!field || !field.enabled) return false;field.currentIndex=index;field.activated(index);return true;
        }
        function send(action: string, payload: string): void { ShellState.run(action,JSON.parse(payload)); }
        function state(): string {
            const body=root.networkFind("networkConnectionsBody");
            const warning=root.networkFind("networkHotspotWarning");
            const button=root.networkFind("networkDetails");
            return JSON.stringify({ready:ShellState.backendReady && FeatureCatalog.ready && Theme.ready,
                popup:!!body && body.visible, button:!!button && button.visible,
                warning:warning && warning.visible ? warning.text : "",
                model:ShellState.snapshot.networkConnections || {},pending:ShellState.pendingActions,
                result:root.networkObservedResult,panelOpen:ShellState.panelOpen});
        }
    }
'''


class NetworkProbe(Probe):
    def call(self, method, *args, target='networkWorkflow'):
        return super().call(method, *args, target=target)


class NetworkWorld(World):
    def __init__(self, directory):
        super().__init__(directory)
        for name in ('shell.qml', 'qml/settings/SettingsApplication.qml'):
            p=self.root/name;p.write_text(p.read_text().replace('    id: root\n','    id: root\n'+OBSERVE,1))
        self.nm = self.home/'network.json';self.calls = self.home/'network-calls.jsonl'
        self.nm.write_text(json.dumps(dict(model=data(),apply=True,error='',delay=0)))
        self.env.update(NETWORK_FIXTURE=str(self.nm),NETWORK_CALLS=str(self.calls),NETWORK_TEST_ROOT=str(self.root))
        stub='''#!'''+sys.executable+'''
import json,os,sys,time
from pathlib import Path
sys.path[:0]=[str(Path(os.environ['NETWORK_TEST_ROOT'])/'tests'),str(Path(os.environ['NETWORK_TEST_ROOT'])/'scripts')]
from network_fixture import NetworkRunner,connection_text,escape
from command_runner import CommandError
tool=Path(sys.argv[0]).name;a=sys.argv[1:];path=Path(os.environ['NETWORK_FIXTURE']);c=json.loads(path.read_text())
with Path(os.environ['NETWORK_CALLS']).open('a') as log:log.write(json.dumps([tool,*a])+'\\n')
if tool=='nm-connection-editor':sys.exit(0)
if tool=='busctl' and 'GetId' not in a and 'GetNameOwner' not in a:sys.exit(1)
r=NetworkRunner();r.model=c['model'];r.apply=c.get('apply',True)
if c.get('error'):r.fail=CommandError(c['error'])
try:
 if a==['radio','wifi']:result='enabled'
 elif tool=='nmcli' and 'UUID,TYPE,NAME' in a:
  result='\\n'.join(':'.join(map(escape,[p['connection.uuid'],p['connection.type'],p['connection.id']])) for p in r.model['profiles'])
 else:result=r.run(tool,*a)
 if 'up' in a or 'down' in a:
  c['model']=r.model;temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(c));temporary.replace(path)
  if 'up' in a:time.sleep(c.get('delay',0))
 print(result)
except (CommandError,AssertionError) as e:print(str(e),file=sys.stderr);sys.exit(4)
'''
        for name in ('nmcli','busctl','nm-connection-editor'):
            p=self.home/'bin'/name;p.write_text(stub);p.chmod(0o700)

    @contextmanager
    def launch(self, mode='shell', page='appearance'):
        with super().launch(mode,page) as original:
            probe=NetworkProbe(original.entry,original.env,original.process,original.log)
            probe.wait(lambda s:s['ready']);yield probe

    def update(self, **changes):
        value=json.loads(self.nm.read_text());value.update(changes);self.nm.write_text(json.dumps(value))

    def commands(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []
