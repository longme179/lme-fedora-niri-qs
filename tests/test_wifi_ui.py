"""Private Wayland dialog checks; copied checkout and a fake backend, no radio."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = '''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import "qml/panels"
import "qml/services"
ShellRoot {
    id: root
    function find(item, name) {
        if (!item) return null;
        if (item.objectName === name || item.text === name) return item;
        for (const child of item.children || []) { const found = find(child, name); if (found) return found; }
        if (item.contentItem && item.contentItem !== item) return find(item.contentItem, name);
        return null;
    }
    FloatingWindow {
        id: window; implicitWidth: 650; implicitHeight: 900
        WifiWidget { id: wifi; anchors.fill: parent; anchors.margins: 24 }
    }
    IpcHandler {
        target: "wifiFixture"
        function click(name: string): void { const item = root.find(window.contentItem, name); if(item && item.enabled) item.clicked(); }
        function password(value: string): void { root.find(wifi.connectionPopup.contentItem, "wifiPassword").text = value; }
        function submit(): void { (root.find(wifi.connectionPopup.contentItem, "wifiConnectSubmit") || root.find(wifi.connectionPopup.contentItem, "Connect")).clicked(); }
        function close(): void { wifi.connectionPopup.close(); }
        function hidden(): void { wifi.visible = false; }
        function device(value: string): void {
            ShellState.snapshot = Object.assign({}, ShellState.snapshot, {system: {network: Object.assign({}, wifi.network, {device:value})}});
        }
        function ready(value: bool): void { ShellState.backendReady = value; }
        function state(): string {
            const field = root.find(wifi.connectionPopup.contentItem, "wifiPassword");
            const button = (root.find(wifi.connectionPopup.contentItem, "wifiConnectSubmit") || root.find(wifi.connectionPopup.contentItem, "Connect"));
            const status = root.find(wifi.connectionPopup.contentItem, "wifiConnectionStatus");
            return JSON.stringify({ready:ShellState.backendReady, visible:wifi.connectionPopup.visible,
                pending:!!ShellState.pendingActions.wifiConnect || !!ShellState.pendingActions.wifiSaved,
                text:field.text, inputEnabled:field.enabled, submitEnabled:button.enabled,
                status:status ? status.text : "", selected:!!wifi.selectedNetwork,
                result:ShellState.wifiResult, connected:wifi.connected});
        }
    }
}
'''
BACKEND = '''import json,sys,time
from pathlib import Path
state=json.loads(Path(__file__).with_name('wifi-snapshot.json').read_text())
sequence=0
acknowledged=0
def emit(action,ok=True,message='',pending=False):
    global sequence
    sequence+=1
    state['lastResult']=dict(action=action,ok=ok,message=message,sequence=sequence)
    state['actionPending']=dict(acknowledged=acknowledged,active=[action] if pending else [])
    if pending: state['lastResult']['pending']=True
    print(json.dumps(state),flush=True)
print(json.dumps(state),flush=True)
for line in sys.stdin:
    request=json.loads(line);action=request['action']
    acknowledged=request.get('clientSerial',acknowledged)
    if action not in ('wifiConnect','wifiSaved'): emit(action);continue
    emit(action,message='Working…',pending=True)
    if request.get('password')=='slow password': time.sleep(.8)
    if request.get('password')=='correct password':
        state['system']['network'].update(connected=True,wifiConnected=True,ssid='Home')
        emit(action,message='Wi-Fi connected')
    else: emit(action,False,'Wi-Fi requested the password again. Check it and try again.')
'''


@unittest.skipUnless(os.environ.get('LME_TEST_UPGRADE_UI') == '1', 'private Wayland Wi-Fi dialog opt-in')
class NativeWifiCase(unittest.TestCase):
    def setUp(self):
        if not os.environ.get('WAYLAND_DISPLAY') or not shutil.which('quickshell'):
            self.skipTest('private Wayland and Quickshell required')
        self.temporary = tempfile.TemporaryDirectory(prefix='wifi-ui-'); self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)/'checkout'
        shutil.copytree(REPO,self.root,ignore=shutil.ignore_patterns('.git','__pycache__'))
        self.env=dict(os.environ,LME_SHELL_DEMO='0',LME_SHELL_BACKEND_DEMO='0',LME_SHELL_PREVIEW='0',
            LME_SHELL_SETTINGS='0',QT_QPA_PLATFORM='wayland',DBUS_SYSTEM_BUS_ADDRESS='unix:path='+self.temporary.name+'/no-bus')
        for key,name in [('XDG_CONFIG_HOME','config'),('XDG_STATE_HOME','state'),('XDG_CACHE_HOME','cache'),('XDG_DATA_HOME','data')]:
            self.env[key]=self.temporary.name+'/'+name
        state=json.loads(subprocess.check_output(['python3',str(self.root/'scripts/desktop_backend.py'),'--demo','--once'],env=self.env,text=True,timeout=10))
        state['preferences']['animations']=False
        state['system']['network']=dict(available=True,enabled=True,device='wlan0',connected=False,wifiConnected=False,
            networks=[dict(ssid='Home',bssid='AA:BB',secured=True,security='WPA2',strength=80)],
            saved=[dict(name='Saved Home',uuid='saved-home')])
        (self.root/'scripts/wifi-snapshot.json').write_text(json.dumps(state))
        (self.root/'scripts/desktop_backend.py').write_text(BACKEND)
        self.entry=self.root/'wifi-fixture.qml';self.entry.write_text(QML)
        self.log=tempfile.TemporaryFile(mode='w+'); self.addCleanup(self.log.close)
        self.process=subprocess.Popen(['quickshell','-p',str(self.entry)],env=self.env,stdout=self.log,stderr=self.log)
        self.addCleanup(self.stop)
        self.wait(lambda s:s['ready'])

    def stop(self):
        self.process.terminate();self.process.wait(timeout=6)
        self.log.seek(0); content=self.log.read()
        for error in ('ReferenceError','TypeError','Binding loop','Failed to load configuration'):
            self.assertNotIn(error,content)

    def call(self,method,*args):
        return subprocess.check_output(['quickshell','-p',str(self.entry),'ipc','call','wifiFixture',method,*args],
            env=self.env,text=True,stderr=subprocess.DEVNULL,timeout=4).strip()

    def wait(self,predicate):
        deadline=time.monotonic()+10;state={}
        while time.monotonic()<deadline:
            try:
                state=json.loads(self.call('state'))
                if predicate(state): return state
            except (ValueError,subprocess.CalledProcessError): pass
            time.sleep(.03)
        self.log.seek(0);self.fail(str(state)+'\n'+self.log.read())

    def open(self,name='wifiConnect-Home'):
        self.call('click',name);return self.wait(lambda s:s['visible'])

    def test_fast_error_retains_context_and_retry_success_closes_and_clears_secret(self):
        self.open();self.call('password','wrong password');self.call('submit')
        state=self.wait(lambda s:not s['pending'] and 'password again' in s['status'])
        self.assertTrue(state['visible'] and state['selected'] and state['submitEnabled'])
        self.assertEqual(state['text'],'')
        self.call('password','correct password');self.call('submit')
        state=self.wait(lambda s:s['connected'] and not s['visible'] and not s['pending'])
        self.assertFalse(state['selected']);self.assertEqual(state['text'],'')
        self.open('wifiSaved-saved-home');self.assertEqual(json.loads(self.call('state'))['text'],'')
        self.call('password','correct password');self.call('submit')
        self.wait(lambda s:not s['visible'] and not s['pending'])

    def test_adapter_change_backend_loss_and_closing_pending_are_safe(self):
        self.open();self.call('device','wlan1')
        state=self.wait(lambda s:'adapter changed' in s['status'])
        self.assertFalse(state['submitEnabled'])
        self.call('close');self.wait(lambda s:not s['visible']);self.call('device','wlan0')
        self.open();self.call('password','slow password');self.call('submit')
        state=self.wait(lambda s:s['pending'])
        self.assertFalse(state['inputEnabled'] or state['submitEnabled']);self.assertEqual(state['text'],'')
        self.call('ready','false');self.wait(lambda s:'reconnecting' in s['status'])
        self.call('ready','true');self.wait(lambda s:'backend restarted' in s['status'])
        self.call('close');self.wait(lambda s:not s['pending'] and not s['visible'])
        self.open();self.call('password','slow password');self.call('submit')
        self.wait(lambda s:s['pending']);self.call('hidden')
        state=self.wait(lambda s:not s['pending'] and not s['visible'])
        self.assertFalse(state['selected']);self.assertEqual(state['text'],'')
