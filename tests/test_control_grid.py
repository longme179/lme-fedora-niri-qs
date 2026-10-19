"""Canvas bounds/transfer and real drag, edit isolation and persistence checks."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from test_backend import Fixture, backend
from desktop_features import DEFAULT_CONTROL_GRID, CONTROL_TILES, LEGACY_CONTROL_MODULES, LEGACY_GRID_IDS, control_grid, control_layout
from settings_transfer import document, validate_document


class ControlGridCase(Fixture, unittest.TestCase):
    def test_canvas_rejects_overlaps_duplicates_and_invalid_coordinates_atomically(self):
        original = copy.deepcopy(DEFAULT_CONTROL_GRID)
        self.preferences.set('controlGrid', original)
        bad = []
        for key, value in [('columns', 6), ('rows', True), ('tiles', []), ('extra', 1)]:
            item = copy.deepcopy(original); item[key] = value; bad.append(item)
        for changes in [{'col': -1}, {'row': 32}, {'col': 3}, {'col': True}, {'id': 'missing'}, {'extra': 0}]:
            item = copy.deepcopy(original); item['tiles'][0].update(changes); bad.append(item)
        item = copy.deepcopy(original); item['tiles'][1].update(col=0, row=0); bad.append(item)
        item = copy.deepcopy(original); item['tiles'][1]['id'] = item['tiles'][0]['id']; bad.append(item)
        for item in bad:
            with self.assertRaises(ValueError): self.preferences.set('controlGrid', item)
            self.assertEqual(self.preferences.values['controlGrid'], original)
        self.assertEqual(backend.Preferences(self.preferences.path).values['controlGrid'], original)

    def test_large_canvas_and_portable_preset_roundtrip_keep_hidden_widgets(self):
        layout = copy.deepcopy(DEFAULT_CONTROL_GRID)
        layout.update(columns=8, rows=8); layout['tiles'][0].update(col=6, row=7)
        next(tile for tile in layout['tiles'] if tile['id'] == 'batterySaver').update(col=4, row=7)
        self.preferences.set('controlGrid', layout)
        cards = copy.deepcopy(self.preferences.values['controlLayout']); cards[0]['enabled'] = False
        self.preferences.set('controlLayout', cards)
        preset = document(self.preferences.values, 'preset')
        values = validate_document(preset, backend.validate_preference, backend.DEFAULT_PREFERENCES)
        self.assertEqual(values['controlGrid'], layout)
        self.assertFalse(values['controlLayout'][0]['enabled'])
        old = backend.Preferences(self.root/'old-settings.json')
        old.path.write_text(json.dumps({'controlLayout': cards}))
        old.reload()
        self.assertEqual(old.values['controlLayout'], cards)
        self.assertEqual(old.values['controlGrid'], DEFAULT_CONTROL_GRID)

    def test_old_layouts_migrate_without_losing_visibility_or_canvas_positions(self):
        old_cards = [{'id': id, 'enabled': id not in ('sliders', 'capture'), 'size': 'half'} for id in sorted(LEGACY_CONTROL_MODULES)]
        new_cards = control_layout(old_cards)
        for id in ('volume', 'micLevel', 'brightness', 'capture', 'captureScreen', 'captureArea', 'captureWindow', 'settings', 'power'):
            self.assertFalse(next(item for item in new_cards if item['id']==id)['enabled'])
        for columns in (4, 8):
            old_tiles = [tile for tile in DEFAULT_CONTROL_GRID['tiles'] if tile['id'] in LEGACY_GRID_IDS]
            old = {'columns': columns, 'rows': 4, 'tiles': old_tiles}
            migrated = control_grid(old)
            for tile in old_tiles: self.assertIn(tile, migrated['tiles'])
            self.assertEqual(migrated['rows'], 9 if columns==4 else 5)
            self.preferences.path.parent.mkdir(parents=True, exist_ok=True)
            self.preferences.path.write_text(json.dumps({'controlLayout': old_cards, 'controlGrid': old}))
            restored = backend.Preferences(self.preferences.path).values
            self.assertEqual(restored['controlLayout'], new_cards)
            self.assertEqual(restored['controlGrid'], migrated)
            for invalid in [dict(old, tiles=old_tiles[:-1]), dict(old, tiles=old_tiles+[old_tiles[0]])]:
                with self.assertRaises(ValueError): control_grid(invalid)

    def test_scattered_legacy_positions_grow_downward_instead_of_repacking(self):
        legacy = [tile for tile in CONTROL_TILES if tile['id'] in LEGACY_GRID_IDS]
        wide = [tile for tile in legacy if tile['cols']==2]
        narrow = [tile for tile in legacy if tile['cols']==1]
        positions = [dict(id=tile['id'], col=3, row=i) for i,tile in enumerate(wide)]
        positions += [dict(id=tile['id'], col=2 if i%2==0 else 5, row=5+i//2) for i,tile in enumerate(narrow)]
        migrated = control_grid({'columns': 8, 'rows': 8, 'tiles': positions})
        self.assertGreater(migrated['rows'], 8)
        self.assertTrue(all(tile in migrated['tiles'] for tile in positions))
        self.assertEqual(control_grid(migrated), migrated)

    def test_battery_saver_is_added_without_moving_or_enabling_existing_controls(self):
        prior = copy.deepcopy(DEFAULT_CONTROL_GRID)
        prior['tiles'] = [tile for tile in prior['tiles'] if tile['id'] != 'batterySaver']
        prior['rows'] = 8
        layout = [dict(item, enabled=False) for item in self.preferences.values['controlLayout'] if item['id'] != 'batterySaver']
        self.preferences.path.parent.mkdir(parents=True, exist_ok=True)
        self.preferences.path.write_text(json.dumps({'controlGrid': prior, 'controlLayout': layout}))
        values = backend.Preferences(self.preferences.path).values
        grid = values['controlGrid']
        self.assertEqual(grid['rows'], 9)
        self.assertTrue(all(tile in grid['tiles'] for tile in prior['tiles']))
        self.assertEqual([item for item in values['controlLayout'] if item['id'] != 'batterySaver'], layout)
        self.assertEqual(next(item for item in values['controlLayout'] if item['id'] == 'batterySaver'),
                         {'id': 'batterySaver', 'enabled': True, 'size': 'half'})
        self.assertEqual(control_grid(grid), grid)


@unittest.skipUnless(os.environ.get('LME_TEST_UPGRADE_UI') == '1', 'private Wayland canvas UI')
class ControlGridUiCase(unittest.TestCase):
    def test_qml_fixed_cells_do_not_reflow_unrelated_controls(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'qml').symlink_to(repo/'qml', target_is_directory=True)
            entry = root/'shell.qml'
            entry.write_text('''import QtQuick
import Quickshell
import "qml/components/ControlGridLogic.js" as Logic
ShellRoot {
    Component.onCompleted: {
        const tiles = ''' + json.dumps(CONTROL_TILES) + ''';
        let checked = 0;
        for (const columns of [4, 8]) for (const rows of [4, 8, 9]) {
            let layout = Logic.pack(tiles, columns);
            if (layout.some(tile => tile.row >= rows)) continue;
            for (let round = 0; round < 3; round++) for (const tile of tiles)
                for (let y = 0; y < rows; y++) for (let x = 0; x + tile.cols <= columns; x++) {
                    const next = Logic.move(layout, tiles, tile.id, x, y, columns, rows);
                    const hits = layout.filter(p => p.id !== tile.id && p.row === y
                        && p.col < x + tile.cols && x < p.col + tiles.find(t => t.id === p.id).cols);
                    const swap = hits.length === 1 && hits[0].col === x && tiles.find(t => t.id === hits[0].id).cols === tile.cols ? hits[0] : null;
                    if (hits.length && !swap) {
                        if (next) throw new Error("Mismatched drop moved other controls");
                        checked++; continue;
                    }
                    if (!next) throw new Error("Empty or matching cell was rejected");
                    for (const old of layout) {
                        if (old.id !== tile.id && (!swap || old.id !== swap.id)) {
                            const current = next.find(t => t.id === old.id);
                            if (current.col !== old.col || current.row !== old.row) throw new Error("Unrelated control moved");
                        }
                    }
                    const occupied = new Set();
                    for (const place of next) {
                        const span = tiles.find(t => t.id === place.id).cols;
                        for (let col = place.col; col < place.col + span; col++) {
                            const key = place.row * columns + col;
                            if (place.row >= rows || col >= columns || occupied.has(key)) throw new Error("Overlapping or outside tile");
                            occupied.add(key);
                        }
                    }
                    if (round % 2) layout = next;
                    checked++;
                }
        }
        console.log("LEGAL_DROPS", checked);
        Qt.callLater(() => Qt.quit());
    }
}
''')
            result = subprocess.run(['quickshell', '-p', str(entry)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            import re
            self.assertGreater(int(re.search(r'LEGAL_DROPS (\d+)', result.stdout + result.stderr)[1]), 5000)

    def test_drag_keyboard_resize_visibility_persistence_and_action_isolation(self):
        pointer, dragger = os.environ.get('LME_TEST_POINTER'), os.environ.get('LME_TEST_DRAG')
        if not pointer or not dragger: raise unittest.SkipTest('private pointer helpers required')
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
            root = Path(directory)
            for name in ('qml', 'scripts', 'config'): (root/name).symlink_to(repo/name, target_is_directory=True)
            fixture = root/'shell.qml'
            fixture.write_text((repo/'upgrades-demo.qml').read_text().replace('//@ pragma Env LME_SHELL_DEMO=1\n', ''))
            # The real settings backend writes private fixture preferences without hardware actions.
            env = dict(os.environ, XDG_CONFIG_HOME=str(root/'user-config'), XDG_STATE_HOME=str(root/'state'),
                       LME_TEST_UPGRADES='1', LME_SHELL_DEMO='0', LME_SHELL_SETTINGS='1')
            keyboard = subprocess.Popen(['wtype', '-s', '60000'], env=env)
            time.sleep(.15)
            def launch(): return subprocess.Popen(['quickshell', '-p', str(fixture)], env=env, stdout=log, stderr=log)
            shell = launch()
            def ipc(method, *args):
                return subprocess.run(['quickshell','-p',str(fixture),'ipc','call','upgradesFixture',method,*args],env=env,capture_output=True,text=True,timeout=4).stdout.strip()
            def state():
                try:return json.loads(ipc('controlGridState'))
                except ValueError:return {}
            def wait(predicate):
                end=time.monotonic()+10
                while time.monotonic()<end:
                    current=state()
                    if predicate(current):return current
                    time.sleep(.1)
                log.seek(0);raise AssertionError(str(current)+'\n'+log.read())
            def point(name):
                result=json.loads(ipc('position',name));self.assertIn('x',result,name);return result
            def click(name):
                p=point(name);time.sleep(.1);subprocess.run([pointer,str(p['x']),str(p['y'])],check=True,timeout=4)
            def cell(s,id):return next(t for t in s['layout'] if t['id']==id)
            def valid(s):
                occupied=set();widths={t['id']:t['cols'] for t in CONTROL_TILES}
                for t in s['layout']:
                    cells={(t['row'],x) for x in range(t['col'],t['col']+widths[t['id']])}
                    self.assertFalse(occupied & cells);occupied |= cells
                    self.assertTrue(all(0<=y<s['rows'] and 0<=x<s['columns'] for y,x in cells))
            try:
                ipc('navigate','control','appearance')
                initial=wait(lambda s:s.get('ready') and len(s.get('slots',[]))==len(CONTROL_TILES))
                valid(initial);self.assertFalse(initial['editing'])
                ipc('rememberCards')
                click('controlEdit');editing=wait(lambda s:s.get('editing'))
                self.assertTrue(all(t['opacity']==1 for t in editing['slots']))
                click('controlTile-dnd');self.assertFalse(state()['dnd'])
                start,finish=point('controlTile-dnd'),point('controlTile-bluetooth')
                subprocess.run([dragger,str(start['x']),str(start['y']),str(finish['x']),str(finish['y'])],check=True,timeout=5)
                moved=wait(lambda s:s.get('ready') and cell(s,'dnd')==dict(id='dnd',col=2,row=0) and s['saved']['tiles']==s['layout'])
                valid(moved);self.assertFalse(moved['dnd'])
                self.assertEqual(ipc('cardsStable'), 'true')
                start=point('controlTile-dnd')
                subprocess.run([dragger,str(start['x']),str(start['y']),str(start['x']+500),str(start['y'])],check=True,timeout=5)
                self.assertEqual(state()['saved'],moved['saved'])
                click('controlTile-dnd')
                self.assertTrue(next(t for t in state()['slots'] if t['id']=='dnd')['focus'])
                subprocess.run(['wtype','-s','200','-k','Right'],env=env,check=True)
                keyed=wait(lambda s:s.get('ready') and cell(s,'dnd')['col']==3);valid(keyed)
                click('controlGridColumns');subprocess.run(['wtype','-s','200','-k','Down','-k','Return'],env=env,check=True)
                large=wait(lambda s:s.get('ready') and s.get('columns')==8);valid(large)
                if large['rows'] != 8:
                    click('controlGridRows');subprocess.run(['wtype','-s','200','-k','Down','-k','Return'],env=env,check=True)
                wait(lambda s:s.get('ready') and s.get('rows')==8)
                click('controlTile-dnd')
                for row in range(4,8):
                    subprocess.run(['wtype','-s','70','-k','Down'],env=env,check=True)
                    bottom=wait(lambda s:s.get('ready') and cell(s,'dnd')['row']==row);valid(bottom)
                self.assertGreater(bottom['scrollY'],0)
                click('Reset grid');reset=wait(lambda s:s.get('ready') and cell(s,'wifi')['col']==0);valid(reset)
                value=reset['saved'];self.assertEqual(value['rows'],8)
                cards=json.loads(ipc('state'))['preferences']['controlLayout']
                # Card order/size and button list order must never move canvas controls.
                reordered=[dict(t,size='half') for t in reversed(cards)]
                ipc('run',json.dumps({'action':'setting','key':'controlLayout','value':reordered}))
                wait(lambda s:s.get('ready'))
                self.assertEqual(state()['layout'],value['tiles'])
                cards=[dict(t,enabled=False) if t['id']=='wifi' else t for t in cards]
                ipc('run',json.dumps({'action':'setting','key':'controlLayout','value':cards}))
                hidden=wait(lambda s:'wifi' not in s.get('visible',[]) and s.get('ready'))
                self.assertEqual(hidden['saved'],value)
                click('controlEdit');wait(lambda s:s.get('editing') is False)
                click('controlTile-dnd');wait(lambda s:s.get('dnd') is True)
                shell.terminate();shell.wait(timeout=6);shell=launch();ipc('navigate','control','appearance')
                restored=wait(lambda s:s.get('ready') and s.get('columns')==8)
                self.assertEqual(restored['saved'],value);self.assertNotIn('wifi',restored['visible'])
                self.assertFalse(restored['editing'])
            finally:
                if shell.poll() is None:shell.terminate();shell.wait(timeout=6)
                keyboard.terminate();keyboard.wait(timeout=3)
            log.seek(0);content=log.read()
            for message in ('ReferenceError','TypeError','binding loop','Unable to assign','Failed to load'):
                self.assertNotIn(message,content)

    def test_slider_mute_profile_actions_and_optional_power_bar_module(self):
        pointer,dragger=os.environ.get('LME_TEST_POINTER'),os.environ.get('LME_TEST_DRAG')
        if not pointer or not dragger:raise unittest.SkipTest('private pointer helpers required')
        repo=Path(__file__).resolve().parents[1];entry=repo/'upgrades-demo.qml'
        with tempfile.TemporaryDirectory() as directory,tempfile.TemporaryFile(mode='w+') as log:
            env=dict(os.environ,LME_TEST_UPGRADES='1',XDG_CONFIG_HOME=directory)
            keyboard=subprocess.Popen(['wtype','-s','60000'],env=env);time.sleep(.15)
            shell=subprocess.Popen(['quickshell','-p',str(entry)],env=env,stdout=log,stderr=log)
            def ipc(method,*args):
                return subprocess.run(['quickshell','-p',str(entry),'ipc','call','upgradesFixture',method,*args],env=env,capture_output=True,text=True,timeout=4).stdout.strip()
            def state():
                try:return json.loads(ipc('state'))
                except ValueError:return {}
            def wait(predicate):
                end=time.monotonic()+10
                while time.monotonic()<end:
                    value=state()
                    if predicate(value):return value
                    time.sleep(.1)
                log.seek(0);raise AssertionError(str(value)+'\n'+log.read())
            def click(name):
                time.sleep(.15)
                p=json.loads(ipc('position',name));self.assertIn('x',p,name);time.sleep(.08)
                subprocess.run([pointer,str(p['x']),str(p['y'])],check=True,timeout=4)
            def run(key,value):ipc('run',json.dumps({'action':'setting','key':key,'value':value}))
            try:
                wait(lambda s:s.get('ready'))
                for channel,device,key,target in [('volume','audio','volume',100),('micLevel','microphone','volume',100),('brightness','brightness','percent',1)]:
                    p=json.loads(ipc('position','controlSlider-'+channel));self.assertIn('x',p)
                    subprocess.run([dragger,str(p['x']),str(p['y']),str(p['x']+(500 if target==100 else -500)),str(p['y'])],check=True,timeout=5)
                    wait(lambda s:s['system'][device][key]==target)
                click('controlMute-volume');wait(lambda s:s['system']['audio']['muted'])
                click('controlMute-micLevel');wait(lambda s:s['system']['microphone']['muted'])
                for profile in ['performance','power-saver','balanced']:
                    click('controlTile-powerProfile');wait(lambda s:s['system']['powerProfile']==profile)
                click('controlEdit')
                previous=copy.deepcopy(state()['system'])
                for name in ['controlTile-powerProfile','controlSlider-volume','controlTile-power','controlTile-settings']:click(name)
                self.assertEqual(state()['system'],previous)
                self.assertFalse(state()['powerOpen']);self.assertFalse(state()['settingsOpen'])
                click('controlEdit')
                click('controlTile-power');wait(lambda s:s['powerOpen'] and s['panelKind']=='power')
                ipc('panel','')
                click('controlTile-settings');wait(lambda s:s['settingsOpen'] and s['panelKind']=='settings')
                ipc('panel','')
                grid=json.loads(ipc('controlGridState'))['saved']
                ipc('navigate','settings','controlLayout')
                click('controlShow-volume');wait(lambda s:not next(item for item in s['preferences']['controlLayout'] if item['id']=='volume')['enabled'])
                ipc('navigate','control','appearance')
                current=json.loads(ipc('controlGridState'));self.assertNotIn('volume',current['visible']);self.assertEqual(current['saved'],grid)
                layout=state()['preferences']['barLayout'];layout['right'].append('power');run('barLayout',layout)
                wait(lambda s:'power' in s['preferences']['barLayout']['right'])
                ipc('navigate','desktop','appearance');time.sleep(.4)
                click('barAction-power');wait(lambda s:s['powerOpen'] and s['panelKind']=='power')
            finally:
                shell.terminate();shell.wait(timeout=6);keyboard.terminate();keyboard.wait(timeout=3)
            log.seek(0);text=log.read()
            for message in ('ReferenceError','TypeError','binding loop','Unable to assign','Failed to load'):
                self.assertNotIn(message,text)
