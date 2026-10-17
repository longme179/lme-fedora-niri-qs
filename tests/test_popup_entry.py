"""Edge entry for actual bar clicks and migration of retired popup settings."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from test_backend import backend, Fixture
from desktop_features import DRACULA_PROFILE
from settings_transfer import validate_document


class PopupPreferenceCase(Fixture, unittest.TestCase):
    def legacy(self):
        profile = dict(copy.deepcopy(DRACULA_PROFILE), name='My motion', connectedPopups=True,
                       accent='#ff80bf', motionPreset='jelly', themeOverrides={'buttonFill':'#123456'},
                       fontOverrides={'body':'Roboto'})
        return dict(accent='#ff80bf', connectedPopups=True, springMotion=True, motionPreset='jelly',
                    appearanceProfiles=[profile])

    def test_saved_preferences_and_profiles_keep_customization_without_the_retired_flag(self):
        self.preferences.path.parent.mkdir(parents=True, exist_ok=True)
        self.preferences.path.write_text(json.dumps(self.legacy()))
        saved = backend.Preferences(self.preferences.path)
        self.assertNotIn('connectedPopups', saved.values)
        self.assertTrue(saved.values['springMotion'])
        self.assertEqual(saved.values['motionPreset'], 'jelly')
        profile = next(p for p in saved.values['appearanceProfiles'] if p['name'] == 'My motion')
        self.assertEqual(profile['name'], 'My motion')
        self.assertNotIn('connectedPopups', profile)
        self.assertEqual(profile['themeOverrides'], {'buttonFill':'#123456'})
        self.assertEqual(profile['fontOverrides'], {'body':'Roboto'})
        self.assertEqual(profile['accent'], '#ff80bf')

    def test_old_backups_and_presets_import_without_reintroducing_connected_popups(self):
        for kind in ('backup', 'preset'):
            values = self.legacy()
            if kind == 'preset': values.pop('appearanceProfiles')
            payload = dict(schema=1, kind=kind, settings=values)
            result = validate_document(payload, backend.validate_preference, backend.DEFAULT_PREFERENCES)
            self.assertNotIn('connectedPopups', result)
            self.assertEqual(result['accent'], '#ff80bf')
            self.assertTrue(result['springMotion'])
            if kind == 'backup':
                self.assertTrue(all('connectedPopups' not in p for p in result['appearanceProfiles']))
                profile = next(p for p in result['appearanceProfiles'] if p['name'] == 'My motion')
                self.assertEqual(profile['themeOverrides'], {'buttonFill':'#123456'})
                self.assertEqual(profile['fontOverrides'], {'body':'Roboto'})
            self.assertTrue(values['connectedPopups'], 'Import must not mutate its input')
            payload['settings']['unknownSetting'] = True
            with self.assertRaises(ValueError):
                validate_document(payload, backend.validate_preference, backend.DEFAULT_PREFERENCES)


@unittest.skipUnless(os.environ.get('LME_TEST_MOTION_UI') == '1' and os.environ.get('LME_TEST_POINTER'),
                     'requires private Wayland and virtual pointer')
class BarPopupEntryCase(unittest.TestCase):
    def test_bar_openings_start_outside_the_output_and_island_still_resizes_with_a_spring(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('qml', 'scripts', 'config', 'assets'):
                (root/name).symlink_to(repo/name, target_is_directory=True)
            source = (repo/'shell.qml').read_text().replace('id: root\n', '''id: root
    property var fixtureBar: null
    property var fixtureEntry: ({})
    function captureEntry(popup) {
        const bounds=popup.mapToItem(overlay.contentItem,0,0,popup.width,popup.height);
        fixtureEntry={outside:bounds.right<0 || bounds.left>overlay.screen.width || bounds.bottom<0 || bounds.top>overlay.screen.height,
            edge:popup.travelEdge, opacity:popup.opacity, contentOpacity:popup.item.opacity};
    }
    Connections { target: panelLoader; function onShownChanged() { if (panelLoader.shown) Qt.callLater(() => root.captureEntry(panelLoader)); } }
    Connections { target: activityIsland; function onShownChanged() { if (activityIsland.shown) Qt.callLater(() => root.captureEntry(activityIsland)); } }
''', 1)
            source = source.replace('id: bar; anchors.fill:', 'id: bar; Component.onCompleted: root.fixtureBar = bar; anchors.fill:', 1)
            source = source.replace('target: "shell"', '''target: "shell"
        function fixtureStatus(): string { return JSON.stringify({ready:ShellState.backendReady && !!root.fixtureBar,
            control:ShellState.controlOpen, activity:ShellState.activityOpen, mounted:panelLoader.mounted || activityIsland.mounted,
            progress:ShellState.activityOpen ? activityIsland.progress : panelLoader.progress,
            height:activityIsland.height, targetHeight:activityIsland.expandedHeight, entry:root.fixtureEntry}); }
        function fixtureGrow(): void { activityIsland.item.implicitHeight += 140; }
        function fixturePoint(module: string): string {
            function find(item) { if (item.moduleId===module && item.item) return item; for (const child of item.children || []) { const hit=find(child); if (hit) return hit; } return null; }
            const item=find(root.fixtureBar);
            const p=item.mapToItem(null,item.width/2,item.height/2);
            return JSON.stringify([p.x+Theme.barSideMargin,p.y+Theme.barTopMargin]);
        }''', 1)
            entry = root/'shell.qml'; entry.write_text(source)
            env = dict(os.environ, LME_SHELL_DEMO='1', XDG_CONFIG_HOME=str(root/'home'),
                       XDG_STATE_HOME=str(root/'state'), XDG_DATA_HOME=str(root/'data'))
            with (root/'gui.log').open('w+') as log:
                process = subprocess.Popen(['quickshell','-p',str(entry)],env=env,stdout=log,stderr=log)
                def ipc(method, *args):
                    reply = subprocess.run(['quickshell','-p',str(entry),'ipc','call','shell',method,*args],
                                           env=env,capture_output=True,text=True,timeout=5)
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
                    for module, panel, edge in [('audio','control',1),('activity','activity',2)]:
                        point=json.loads(ipc('fixturePoint',module))
                        subprocess.run([os.environ['LME_TEST_POINTER'],str(point[0]),str(point[1])],env=env,check=True,timeout=4)
                        state=wait(lambda s:s.get(panel) and s['progress']==1)
                        self.assertEqual(state['entry'],dict(outside=True,edge=edge,opacity=1,contentOpacity=1))
                        if panel == 'activity':
                            before=state['height']; ipc('fixtureGrow')
                            wait(lambda s:before+1<s['height']<s['targetHeight']-1)
                            wait(lambda s:abs(s['height']-s['targetHeight'])<.1)
                        ipc('close'); wait(lambda s:not s.get('mounted',True))
                    log.seek(0); output=log.read()
                    for failure in ('TypeError','ReferenceError','Unable to assign','Binding loop','Failed to load configuration'):
                        self.assertNotIn(failure,output)
                finally:
                    process.terminate(); process.wait(timeout=5)
