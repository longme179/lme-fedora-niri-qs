"""Notification settings validation and native content/animation regressions."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from test_backend import backend, Fixture
from settings_transfer import document, validate_document


class NotificationPreferencesCase(Fixture, unittest.TestCase):
    def test_styles_are_bounded_persisted_and_portable(self):
        values = {'notificationWidth': 640, 'notificationPosition': 'bottom-center', 'notificationMargin': 0,
                  'notificationRadius': 0, 'notificationPadding': 28, 'notificationOpacity': .6,
                  'notificationBorderWidth': 4, 'notificationTitleSize': 24, 'notificationBodySize': 22,
                  'notificationIdleAnimation': False, 'notificationIdleSpeed': 6,
                  'themeOverrides': {'notificationTitle': '#ABCDEF', 'notificationBorder': '#80112233'}}
        for key, value in values.items(): self.preferences.set(key, value)
        stored = backend.Preferences(self.preferences.path).values
        transferred = validate_document(document(stored, 'preset'), backend.validate_preference, backend.DEFAULT_PREFERENCES)
        for key in values: self.assertEqual(stored[key], transferred[key])
        for key, value in [('notificationWidth', True), ('notificationWidth', 641), ('notificationPosition', 'center'),
                           ('notificationMargin', -1), ('notificationRadius', 49), ('notificationPadding', 0),
                           ('notificationOpacity', float('nan')), ('notificationOpacity', True), ('notificationOpacity', .59),
                           ('notificationBorderWidth', 5), ('notificationTitleSize', 25), ('notificationBodySize', 10),
                           ('notificationIdleAnimation', 1), ('notificationIdleSpeed', 5)]:
            with self.subTest(key=key), self.assertRaises(ValueError): self.preferences.set(key, value)
        self.assertEqual(stored['themeOverrides']['notificationTitle'], '#abcdef')


@unittest.skipUnless(os.environ.get('LME_TEST_MOTION_UI') == '1', 'opt-in private Wayland notification checks')
class NativeNotificationsCase(unittest.TestCase):
    def test_wrapping_scroll_limits_positions_idle_lifecycle_and_settings(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
            root = Path(directory)
            for name in ('qml', 'scripts', 'config'): (root / name).symlink_to(repo / name, target_is_directory=True)
            entry = root / 'shell.qml'
            entry.write_text('''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/components"
import "qml/panels"
import "qml/services"
import "qml/settings"
import "qml/theme"
ShellRoot {
    id: fixture
    property bool settings: false
    property var data: ({appName: "Test app", summary: "Short title", body: "Short body", actions: []})
    Component.onCompleted: Quickshell.watchFiles = false
    function find(item, name) { if (!item) return null; if (item.objectName === name) return item; for (const child of item.children || []) { const found = find(child, name); if (found) return found; } return null; }
    NotificationToasts { id: toasts }
    StatusWindow { id: status }
    FloatingWindow {
        id: window; title: "Notification appearance test"; width: 920; height: 940; color: Theme.background
        NotificationCard { id: card; x: 20; y: 20; width: 340; height: implicitHeight; maximumHeight: 880; entry: fixture.data; visible: !fixture.settings }
        SettingsView { id: settings; anchors.fill: parent; page: "notifications"; visible: fixture.settings }
    }
    IpcHandler {
        target: "notificationsFixture"
        function state(): string {
            const body = fixture.find(card, "notificationBody"), summary = fixture.find(card, "notificationSummary");
            const emblem = fixture.find(card, "notificationEmblem"), scroll = fixture.find(card, "notificationScroll");
            const flow = fixture.find(card, "notificationActions");
            return JSON.stringify({ready: ShellState.backendReady, prefs: ShellState.preferences,
                height: card.height, overflow: card.overflowing, scrollInteractive: scroll.interactive, bodyHeight: body.height, bodyLines: body.lineCount,
                bodyTruncated: body.truncated, summaryTruncated: summary.truncated, format: body.textFormat,
                scrollEnd: scroll.contentY + scroll.height >= scroll.contentHeight - 1,
                contentHeight: scroll.contentHeight, viewport: scroll.height,
                actions: flow.children.filter(c => c.visible && c.text).map(c => ({x:c.x, y:c.y, width:c.width, right:c.x+c.width, height:c.height})), actionWidth: flow.width,
                rotating: emblem.animating, radius: card.radius, border: card.border.width, titleColor: summary.color.toString(),
                toastHeight: toasts.implicitHeight, toastWidth: toasts.implicitWidth, available: toasts.availableHeight, position: toasts.position,
                anchors: {top:toasts.anchors.top, bottom:toasts.anchors.bottom, left:toasts.anchors.left, right:toasts.anchors.right},
                statusHeight: status.implicitHeight, statusVisible: status.visible,
                previewWidth: fixture.find(settings, "notificationPreview")?.width || 0,
                page: !!fixture.find(settings, "notificationPreview")});
        }
        function message(data: string): void { fixture.data = JSON.parse(data); }
        function setting(key: string, value: string): void { ShellState.run("setting", {key, value:JSON.parse(value)}); }
        function resize(width: int): void { card.width = width; }
        function scrollEnd(): void { const scroll=fixture.find(card,"notificationScroll"); scroll.contentY=Math.max(0,scroll.contentHeight-scroll.height); }
        function popup(count: int): void { Notifications.history=Array.from({length:count},(_,i)=>({id:"card-"+i,appName:"Long message",summary:fixture.data.summary,body:fixture.data.body,actions:fixture.data.actions,active:true,popup:true})); }
        function status(text: string): void { ShellState.statusMessage=text; }
        function settings(): void { fixture.settings=true; }
    }
}''')
            env = dict(os.environ, LME_SHELL_DEMO='1', XDG_CONFIG_HOME=str(root/'home'), XDG_STATE_HOME=str(root/'state'))
            process = subprocess.Popen(['quickshell', '-p', str(entry)], env=env, stdout=log, stderr=log)
            def ipc(method, *args):
                return subprocess.check_output(['quickshell', '-p', str(entry), 'ipc', 'call', 'notificationsFixture', method, *args], env=env, text=True, timeout=5).strip()
            def wait(predicate):
                deadline = time.monotonic() + 8
                state = {}
                while time.monotonic() < deadline:
                    try: state = json.loads(ipc('state'))
                    except (ValueError, subprocess.CalledProcessError): pass
                    if predicate(state): return state
                    time.sleep(.04)
                log.seek(0); self.fail(str(state) + '\n' + log.read())
            def setting(key, value):
                ipc('setting', key, json.dumps(value)); return wait(lambda s: s.get('prefs',{}).get(key)==value)
            try:
                initial = wait(lambda s: s.get('ready') and s.get('rotating'))
                self.assertFalse(initial['scrollInteractive'], 'A fitted history card must leave scrolling to its surrounding list')
                long = {'appName': 'A long app name ' * 10, 'summary': 'Title without clipping ' * 7,
                        'body': 'https://example.org/' + 'long-path-' * 200 + '\nLast line <plain text>',
                        'actions': [{'identifier': str(i), 'text': 'An action with a long label ' * 3} for i in range(4)]}
                ipc('message', json.dumps(long)); measured = wait(lambda s: s.get('height',0)>initial['height']+100)
                self.assertGreater(measured['bodyLines'], 3)
                self.assertFalse(measured['bodyTruncated']); self.assertFalse(measured['summaryTruncated'])
                self.assertLessEqual(measured['height'], 880)
                self.assertTrue(measured['overflow'])
                self.assertTrue(measured['scrollInteractive'])
                self.assertEqual(len(measured['actions']), 4)
                self.assertGreater(len({a['y'] for a in measured['actions']}), 1)
                self.assertTrue(all(a['right'] <= measured['actionWidth']+.1 for a in measured['actions']))
                ipc('scrollEnd'); wait(lambda s:s['scrollEnd'])
                ipc('resize', '600'); wider = wait(lambda s:s['bodyLines']<measured['bodyLines'])
                self.assertLess(wider['contentHeight'], measured['contentHeight'])
                setting('notificationIdleAnimation', False); wait(lambda s:not s['rotating'])
                setting('notificationIdleAnimation', True); setting('animations', False); wait(lambda s:not s['rotating'])
                setting('animations', True); wait(lambda s:s['rotating'])
                setting('notificationRadius', 0); setting('notificationBorderWidth', 4)
                setting('themeOverrides', {'notificationTitle':'#abcdef'})
                wait(lambda s:s['radius']==0 and s['border']==4 and s['titleColor']=='#abcdef')
                ipc('popup', '3'); wait(lambda s:s['toastHeight']>0)
                for position in ('top-left','top-center','top-right','bottom-left','bottom-center','bottom-right'):
                    state=setting('notificationPosition',position)
                    state=wait(lambda s:s['position']==position and s['toastHeight']<=s['available']+1)
                    self.assertEqual(state['anchors']['top'], position.startswith('top'))
                    self.assertEqual(state['anchors']['left'], position.endswith('left'))
                    self.assertEqual(state['anchors']['right'], position.endswith('right'))
                ipc('status', long['body']); state=wait(lambda s:s['statusVisible'] and s['statusHeight']>76)
                self.assertLessEqual(state['statusHeight'], 648)
                ipc('popup','0'); ipc('status',''); ipc('settings')
                wait(lambda s:s['page'] and not s['rotating'] and s['previewWidth']==s['prefs']['notificationWidth'])
                log.seek(0); output=log.read()
                for problem in ('TypeError','ReferenceError','Unable to assign','Binding loop','Failed to load configuration'):
                    self.assertNotIn(problem,output)
            finally:
                process.terminate(); process.wait(timeout=5)
