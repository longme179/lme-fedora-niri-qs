"""BlueZ agent protocol checks with no host Bluetooth hardware access."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import test_local_qml as qml_tests
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bluetooth_agent import response_value
from test_backend import backend
from settings_transfer import document, validate_document


class PairingValidationCase(unittest.TestCase):
    def test_pin_and_passkey_validation_preserves_leading_zeroes(self):
        self.assertEqual(response_value('pin', '0012'), ('(s)', ('0012',)))
        self.assertEqual(response_value('passkey', '000123'), ('(u)', (123,)))
        for kind, values in [('pin', ['', None, 'x'*17, '\n123', 'é'*9]), ('passkey', ['', '1000000', '-1', '１２３', True])]:
            for value in values:
                with self.subTest(kind=kind, value=value), self.assertRaises(ValueError): response_value(kind, value)

    def test_pairing_toggle_is_boolean_and_portable(self):
        values = dict(backend.DEFAULT_PREFERENCES, bluetoothPairing=False)
        self.assertFalse(validate_document(document(values, 'preset'), backend.validate_preference, backend.DEFAULT_PREFERENCES)['bluetoothPairing'])
        for value in (None, 'true', 1):
            with self.assertRaises(ValueError): backend.validate_preference('bluetoothPairing', value)


@unittest.skipUnless(os.environ.get('LME_TEST_BLUETOOTH') == '1', 'requires PyGObject and a private D-Bus daemon')
class BluezProtocolCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.repo = Path(__file__).resolve().parents[1]
        self.log = tempfile.TemporaryFile(mode='w+'); self.addCleanup(self.log.close)
        self.bus = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address'], stdout=subprocess.PIPE, stderr=self.log, text=True)
        self.addCleanup(lambda: (self.bus.terminate(), self.bus.wait(timeout=5), self.bus.stdout.close()))
        address = self.bus.stdout.readline().strip()
        self.env = dict(os.environ, DBUS_SYSTEM_BUS_ADDRESS=address, LME_BLUEZ_EVENTS=str(self.root / 'events.jsonl'))
        self.fixture = subprocess.Popen(['/usr/bin/python3', str(self.repo/'tests/bluez_fixture.py')], env=self.env, stdout=subprocess.PIPE, stderr=self.log, text=True)
        self.addCleanup(lambda: (self.fixture.terminate(), self.fixture.wait(timeout=5), self.fixture.stdout.close()))
        self.owner = self.fixture.stdout.readline().strip()
        self.assertTrue(self.owner.startswith(':'))
        command = ['/usr/bin/python3', '-u', str(self.repo/'scripts/bluetooth_agent.py')]
        if self._testMethodName == 'test_scan_and_prompt_timeout':
            command = ['/usr/bin/python3', '-u', '-c', "import sys;sys.path.insert(0,"+repr(str(self.repo/'scripts'))+");from gi.repository import GLib;GLib.timeout_add_seconds=lambda seconds, callback: GLib.timeout_add(300, callback);import bluetooth_agent;raise SystemExit(bluetooth_agent.main())"]
        self.agent = subprocess.Popen(command, env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True)
        self.addCleanup(self.stop_agent)
        self.frames = queue.Queue(); self.latest = {}
        def read():
            for line in self.agent.stdout:
                try: self.frames.put(json.loads(line))
                except ValueError: pass
        self.reader = threading.Thread(target=read, daemon=True); self.reader.start()
        self.wait(lambda state: state.get('ready'))

    def stop_agent(self):
        if self.agent.poll() is None:
            self.agent.terminate()
            try: self.agent.wait(timeout=5)
            except subprocess.TimeoutExpired: self.agent.kill(); self.agent.wait(timeout=3)
        self.agent.stdin.close(); self.reader.join(timeout=2); self.agent.stdout.close()

    def wait(self, predicate, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try: self.latest = self.frames.get(timeout=.1)
            except queue.Empty: continue
            if predicate(self.latest): return self.latest
        self.log.seek(0); self.fail(str(self.latest) + '\n' + self.log.read())

    def send(self, action, **values):
        self.agent.stdin.write(json.dumps(dict(action=action, **values))+'\n'); self.agent.stdin.flush()

    def mode(self, mode):
        subprocess.run(['gdbus', 'call', '--address', self.env['DBUS_SYSTEM_BUS_ADDRESS'], '--dest', 'org.bluez', '--object-path', '/test', '--method', 'org.lme.BlueZTest.SetMode', mode], check=True, capture_output=True, env=self.env, timeout=4)

    def test_scan_pair_pin_passkey_confirm_authorize_and_close(self):
        self.send('scan', enabled=True); state = self.wait(lambda s:s.get('scanning'))
        device = state['devices'][0]['path']
        self.send('scan', enabled=False); self.wait(lambda s:not s.get('scanning') and not s.get('scanPending'))
        for kind, value in [('pin', '0012'), ('passkey', '000123'), ('confirm', ''), ('authorize', ''), ('service', '')]:
            self.mode(kind); self.send('pair', path=device)
            state = self.wait(lambda s:s.get('request', {}).get('kind') == kind)
            request = state['request']
            if kind == 'confirm': self.assertEqual(request['code'], '012345')
            self.send('reply', token='stale', accept=True, value=value)
            state = self.wait(lambda s:'no longer active' in s.get('error', ''))
            self.assertEqual(state['request']['token'], request['token'])
            if kind == 'passkey':
                self.send('reply', token=request['token'], accept=True, value='1000000')
                self.wait(lambda s:'passkey' in s.get('error', '').lower())
            self.send('reply', token=request['token'], accept=True, value=value)
            self.wait(lambda s:not s.get('pairing') and not s.get('request') and s['devices'][0]['paired'])
        self.send('close'); self.agent.wait(timeout=5)
        calls = [json.loads(line) for line in (self.root/'events.jsonl').read_text().splitlines()]
        names = [name for name,args in calls]
        for method in ['RegisterAgent', 'StartDiscovery', 'StopDiscovery', 'Pair', 'Connect', 'UnregisterAgent']: self.assertIn(method, names)
        self.assertNotIn('RequestDefaultAgent', names)
        replies = [args for name,args in calls if name == 'AgentReply']
        self.assertIn(['0012'], replies); self.assertIn([123], replies)

    def test_display_reject_cancel_and_service_reconnect(self):
        device = self.latest['devices'][0]['path']
        for kind in ['display-pin', 'display-passkey', 'confirm']:
            self.mode(kind); self.send('pair', path=device)
            state = self.wait(lambda s:s.get('request', {}).get('kind') == kind)
            if kind == 'display-passkey': self.assertEqual((state['request']['code'], state['request']['entered']), ('012345', 2))
            self.send('reply', token=state['request']['token'], accept=False)
            self.wait(lambda s:not s.get('pairing') and not s.get('request'))
        for method in ['Drop', 'Claim']:
            subprocess.run(['gdbus', 'call', '--address', self.env['DBUS_SYSTEM_BUS_ADDRESS'], '--dest', self.owner, '--object-path', '/test', '--method', 'org.lme.BlueZTest.'+method], check=True, capture_output=True, timeout=4)
            self.wait(lambda s:s.get('ready') == (method == 'Claim'))
        self.mode('wait'); self.send('pair', path=device); self.wait(lambda s:s.get('pairing'))
        self.send('cancel'); self.wait(lambda s:not s.get('pairing'))
        self.send('scan', enabled=True); self.wait(lambda s:s.get('scanning'))
        self.send('close'); self.agent.wait(timeout=5)
        calls = [json.loads(line)[0] for line in (self.root/'events.jsonl').read_text().splitlines()]
        self.assertGreaterEqual(calls.count('RegisterAgent'), 2)
        self.assertIn('CancelPairing', calls); self.assertIn('StopDiscovery', calls)

    def test_scan_and_prompt_timeout(self):
        self.send('scan', enabled=True); self.wait(lambda s:s.get('scanning'))
        self.wait(lambda s:not s.get('scanning'))
        device = self.latest['devices'][0]['path']
        self.send('pair', path=device); self.wait(lambda s:s.get('request', {}).get('kind') == 'confirm')
        state = self.wait(lambda s:not s.get('pairing') and 'timed out' in s.get('error', ''))
        self.assertFalse(state['request'])

    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_pairing_widget_and_device_panel_lifecycle(self):
        self.stop_agent(); self.mode('pin')
        result = self.run_qml('import QtTest\nimport "qml/panels"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property bool rapidLoss: false
    Connections { target: BluetoothState; function onStateChanged() { if (fixture.phase >= 5 && !BluetoothState.state.ready) fixture.rapidLoss = true; } }
    property var observations: ({})
    FloatingWindow {
        implicitWidth: 650; implicitHeight: 900
        DeviceControls { id: panel; anchors.fill: parent }
    }
    TestCase { id: pointer; when: false }
    function find(item, name) {
        if (item.objectName === name) return item;
        for (const child of item.children || []) { const found = find(child, name); if (found) return found; }
        return null;
    }
    Timer {
        interval: 100; repeat: true; running: true
        onTriggered: {
            if (++fixture.ticks > 100) { fixture.finish({timeout: fixture.phase, state: BluetoothState.state, error: BluetoothState.error}); return; }
            if (fixture.phase === 0 && BluetoothState.state.ready && ShellState.backendReady) {
                const button = fixture.find(panel, "bluetoothScan"); pointer.mouseClick(button, 30, 20); fixture.phase++;
            } else if (fixture.phase === 1 && BluetoothState.state.scanning) {
                const path = BluetoothState.state.devices[0].path;
                const button = fixture.find(panel, "bluetoothDevice-" + path); pointer.mouseClick(button, 30, 20); fixture.phase++;
            } else if (fixture.phase === 2 && BluetoothState.request.kind === "pin") {
                fixture.observations.prompt = true;
                const input = fixture.find(panel, "bluetoothPairInput"); input.forceActiveFocus();
                for (const key of [Qt.Key_0, Qt.Key_0, Qt.Key_1, Qt.Key_2]) pointer.keyClick(key);
                fixture.observations.input = input.text;
                const button = fixture.find(panel, "bluetoothPairConfirm"); pointer.mouseClick(button, 30, 20); fixture.phase++;
            } else if (fixture.phase === 3 && !BluetoothState.state.pairing && BluetoothState.state.devices[0]?.connected) {
                fixture.observations.paired = BluetoothState.state.devices[0].paired;
                panel.visible = false; fixture.phase++;
            } else if (fixture.phase === 4 && !BluetoothState.state.ready) {
                fixture.observations.closed = BluetoothState.consumers.length === 0;
                panel.visible = true; fixture.phase++;
            } else if (fixture.phase === 5 && BluetoothState.state.ready) {
                fixture.observations.reopened = BluetoothState.consumers.length === 1;
                panel.visible = false; panel.visible = true; fixture.phase++;
            } else if (fixture.phase === 6 && fixture.rapidLoss && BluetoothState.state.ready) {
                fixture.observations.rapidReopen = !BluetoothState.failed;
                panel.visible = false; fixture.phase++;
            } else if (fixture.phase === 7 && !BluetoothState.state.ready) fixture.finish(fixture.observations);
        }
    }
''', {'LME_SHELL_DEMO': '0', 'LME_SHELL_BACKEND_DEMO': '1', 'DBUS_SYSTEM_BUS_ADDRESS': self.env['DBUS_SYSTEM_BUS_ADDRESS']})
        self.assertEqual(result, dict(prompt=True, input='0012', paired=True, closed=True, reopened=True, rapidReopen=True))

    def test_changing_adapter_cancels_owned_scan_and_pairing(self):
        self.send('scan', enabled=True); state = self.wait(lambda s:s.get('scanning'))
        self.send('pair', path=state['devices'][0]['path']); self.wait(lambda s:s.get('request'))
        self.send('watch', adapter='/org/bluez/hci1')
        state = self.wait(lambda s:s.get('adapter') == '/org/bluez/hci1' and not s.get('pairing') and not s.get('scanning'))
        self.assertEqual(state['devices'][0]['name'], 'Other keyboard')
        self.assertFalse(state['request'])
        self.send('pair', path='/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF')
        self.wait(lambda s:'selected adapter' in s.get('error', ''))
        self.send('scan', enabled=True); self.wait(lambda s:s.get('scanning'))
        self.send('close'); self.agent.wait(timeout=5)
