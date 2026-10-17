"""Connected surface geometry, source capture and popup lifecycle."""
import os
import shutil
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from test_backend import backend, Fixture
import test_local_qml as qml_tests
from settings_transfer import document, validate_document


class ConnectedPreferenceCase(Fixture, unittest.TestCase):
    def test_switch_is_validated_and_portable(self):
        self.assertTrue(backend.DEFAULT_PREFERENCES['connectedPopups'])
        self.preferences.set('connectedPopups', False)
        exported = validate_document(document(self.preferences.values, 'preset'), backend.validate_preference, backend.DEFAULT_PREFERENCES)
        self.assertFalse(exported['connectedPopups'])
        for value in (1, 'true', [], None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                backend.validate_preference('connectedPopups', value)


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is required')
class ConnectedSurfaceCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def exercise_surface(self, environment=None):
        return self.run_qml('import QtTest\nimport "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    FloatingWindow {
        id: window; implicitWidth: 900; implicitHeight: 700
        Item {
            id: stage; anchors.fill: parent
            SlideLoader {
                id: popup; x: 450; y: 220; width: 300; height: 260
                shown: false; exitToEdge: true
                originRect: Qt.rect(100, 20, 40, 30)
                content: GlassPanel { LabelText { text: "Connected popup"; anchors.centerIn: parent } }
            }
        }
    }
    TestCase { id: clock; when: false }
    Timer {
        interval: 200; running: true
        onTriggered: {
            clock.tryVerify(() => ShellState.backendReady, 3000);
            const result = {};
            popup.shown = true;
            const start = popup.mapToItem(stage, 0, 0, popup.width, popup.height);
            result.start = [start.x, start.y, start.width, start.height];
            result.connected = popup.connected;
            clock.wait(80);
            result.transparent = popup.item.connectedSurface && popup.item.color.a === 0;
            const before = popup.progress;
            popup.shown = false;
            result.reverse = popup.progress === before;
            clock.wait(30); popup.shown = true;
            result.reopen = popup.mounted;
            clock.tryVerify(() => popup.progress === 1, 3000);
            result.settled = !popup.item.connectedSurface && popup.item.color.a > 0;
            popup.shown = false;
            popup.originRect = Qt.rect(700, 20, 80, 30);
            result.frozen = popup.openingOrigin.x === 100;
            clock.tryVerify(() => !popup.mounted, 2000);
            result.closed = !popup.item && !popup.active;
            ShellState.snapshot = Object.assign({}, ShellState.snapshot, {preferences: Object.assign({}, ShellState.preferences, {connectedPopups: false})});
            popup.shown = true;
            result.disabled = !popup.connected;
            popup.shown = false;
            clock.tryVerify(() => !popup.mounted, 2000);
            ShellState.snapshot = Object.assign({}, ShellState.snapshot, {preferences: Object.assign({}, ShellState.preferences, {animations: false})});
            popup.shown = true;
            result.reduced = !popup.connected && popup.progress === 1 && !popup.item.connectedSurface;
            popup.shown = false;
            result.reducedClosed = !popup.mounted;
            fixture.finish(result);
        }
    }
''', environment)

    def test_source_geometry_reversal_close_and_software_fallback(self):
        result = self.exercise_surface()
        for actual, expected in zip(result.pop('start'), (100, 20, 40, 30)):
            self.assertAlmostEqual(actual, expected, delta=.01)
        self.assertEqual(result, dict(connected=True, transparent=True, reverse=True, reopen=True,
                                     settled=True, frozen=True, closed=True, disabled=True, reduced=True, reducedClosed=True))

    @unittest.skipUnless(os.environ.get('LME_TEST_MOTION_UI') == '1', 'opt-in Wayland RHI shader check')
    def test_opengl_shader_surface_lifecycle(self):
        result = self.exercise_surface({'QT_QPA_PLATFORM': 'wayland', 'QT_QUICK_BACKEND': 'rhi', 'QSG_RHI_BACKEND': 'opengl'})
        self.assertTrue(result['transparent'] and result['settled'] and result['closed'])

    def test_mouse_origin_is_consumed_and_keyboard_falls_back(self):
        result = self.run_qml('import QtTest\nimport "qml/bar"\nimport "qml/services"', '''
    FloatingWindow {
        implicitWidth: 700; implicitHeight: 200
        BarModule { id: audio; moduleId: "audio"; x: 80; y: 20 }
    }
    TestCase { id: pointer; when: false }
    Timer {
        interval: 200; running: true
        onTriggered: {
            pointer.tryVerify(() => ShellState.backendReady, 3000);
            pointer.mouseClick(audio.item, 10, 15, Qt.LeftButton);
            const origin = [ShellState.popupAnchor.x, ShellState.popupAnchor.y, ShellState.popupAnchor.width, ShellState.popupAnchor.height];
            const clicked = ShellState.controlOpen;
            pointer.wait(30);
            ShellState.closePanels(); ShellState.togglePanel("control");
            const keyboard = ShellState.popupAnchor.width === 0;
            ShellState.snapshot = Object.assign({}, ShellState.snapshot, {preferences: Object.assign({}, ShellState.preferences,
                {barEdge: "bottom", barHeight: 50, barSideMargin: 20, barEdgeMargin: 30})});
            const serial = ShellState.armBarOrigin(audio, {height:1000}, {});
            const bottom = [ShellState.nextBarAnchor.x, ShellState.nextBarAnchor.y];
            ShellState.clearBarOrigin(serial);
            fixture.finish({clicked, origin, keyboard, bottom});
        }
    }
''')
        self.assertTrue(result['clicked'] and result['keyboard'])
        self.assertEqual(result['origin'][:2], [80, 20])
        self.assertGreater(result['origin'][2], 30)
        self.assertEqual(result['origin'][3], 30)
        self.assertEqual(result['bottom'], [100, 940])

    @unittest.skipUnless(os.environ.get('LME_TEST_MOTION_UI') == '1' and os.environ.get('LME_TEST_POINTER'), 'requires private Wayland and virtual pointer')
    def test_real_bar_click_opens_at_its_source_and_settles(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('qml', 'scripts', 'config', 'assets'):
                (root/name).symlink_to(repo/name, target_is_directory=True)
            source = (repo/'shell.qml').read_text().replace('id: root\n', 'id: root\n    property var fixtureBar: null\n', 1)
            source = source.replace('id: bar; anchors.fill:', 'id: bar; Component.onCompleted: root.fixtureBar = bar; anchors.fill:', 1)
            source = source.replace('target: "shell"', '''target: "shell"
        function fixtureStatus(): string { return JSON.stringify({ready: ShellState.backendReady && !!root.fixtureBar,
            control: ShellState.controlOpen, activity: ShellState.activityOpen, mounted: panelLoader.mounted || activityIsland.mounted,
            connected: ShellState.activityOpen ? activityIsland.connected : panelLoader.connected,
            progress: ShellState.activityOpen ? activityIsland.progress : panelLoader.progress,
            morphing: ShellState.activityOpen ? activityIsland.morphing : panelLoader.morphing,
            height: activityIsland.height, targetHeight: activityIsland.expandedHeight,
            anchor: [ShellState.popupAnchor.x, ShellState.popupAnchor.y, ShellState.popupAnchor.width, ShellState.popupAnchor.height]}); }
        function fixtureGrow(): void { activityIsland.item.implicitHeight += 140; }
        function fixturePoint(module: string): string {
            function find(item) { if(item.moduleId===module && item.item) return item; for(const child of item.children || []) { const hit=find(child); if(hit) return hit; } return null; }
            const item=find(root.fixtureBar);
            const p=item.mapToItem(null,item.width/2,item.height/2);
            return JSON.stringify([p.x+Theme.barSideMargin,p.y+Theme.barTopMargin]);
        }''', 1)
            entry = root/'shell.qml'; entry.write_text(source)
            env = dict(os.environ, LME_SHELL_DEMO='1', XDG_CONFIG_HOME=str(root/'home'), XDG_STATE_HOME=str(root/'state'), XDG_DATA_HOME=str(root/'data'))
            with (root/'gui.log').open('w+') as log:
                process = subprocess.Popen(['quickshell','-p',str(entry)],env=env,stdout=log,stderr=log)
                def ipc(method, *args):
                    reply = subprocess.run(['quickshell','-p',str(entry),'ipc','call','shell',method,*args],env=env,capture_output=True,text=True,timeout=5)
                    if method in ('fixtureStatus', 'fixturePoint') and not reply.stdout.strip():
                        log.seek(0); self.fail(method + ': ' + reply.stderr + '\n' + log.read())
                    return reply.stdout.strip()
                def wait(predicate):
                    deadline = time.monotonic()+5
                    while time.monotonic()<deadline:
                        try: state=json.loads(ipc('fixtureStatus'))
                        except ValueError: state={}
                        if predicate(state): return state
                        time.sleep(.025)
                    log.seek(0); self.fail(str(state)+'\n'+log.read())
                try:
                    wait(lambda s:s.get('ready'))
                    for module, panel in [('audio','control'),('activity','activity')]:
                        point=json.loads(ipc('fixturePoint',module))
                        subprocess.run([os.environ['LME_TEST_POINTER'],str(point[0]),str(point[1])],env=env,check=True,timeout=4)
                        state=wait(lambda s:s.get(panel) and s['progress']==1 and not s['morphing'])
                        self.assertTrue(state['connected'])
                        anchor=state['anchor']
                        self.assertAlmostEqual(anchor[0]+anchor[2]/2,point[0],delta=1)
                        self.assertAlmostEqual(anchor[1]+anchor[3]/2,point[1],delta=1)
                        if panel == 'activity':
                            before = state['height']; ipc('fixtureGrow')
                            wait(lambda s: before+1 < s['height'] < s['targetHeight']-1)
                            wait(lambda s: abs(s['height']-s['targetHeight']) < .1)
                        ipc('close'); wait(lambda s:not s.get('mounted',True))
                    log.seek(0); output=log.read()
                    for failure in ('TypeError','ReferenceError','Unable to assign','Binding loop','Failed to load configuration','Failed to create shader'):
                        self.assertNotIn(failure,output)
                finally:
                    process.terminate(); process.wait(timeout=5)
