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
from desktop_features import DEFAULT_CONTROL_GRID, CONTROL_TILES
from settings_transfer import document, validate_document


class ControlGridCase(Fixture, unittest.TestCase):
    def test_canvas_rejects_overlaps_duplicates_and_invalid_coordinates_atomically(self):
        original = copy.deepcopy(DEFAULT_CONTROL_GRID)
        self.preferences.set('controlGrid', original)
        bad = []
        for key, value in [('columns', 6), ('rows', True), ('tiles', []), ('extra', 1)]:
            item = copy.deepcopy(original); item[key] = value; bad.append(item)
        for changes in [{'col': -1}, {'row': 4}, {'col': 3}, {'col': True}, {'id': 'missing'}, {'extra': 0}]:
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
        for (const columns of [4, 8]) for (const rows of [4, 8]) {
            let layout = Logic.pack(tiles, columns);
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
            self.assertIn('LEGAL_DROPS 4392', result.stdout + result.stderr)

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
                initial=wait(lambda s:s.get('ready') and len(s.get('slots',[]))==11)
                valid(initial);self.assertFalse(initial['editing'])
                click('controlEdit');editing=wait(lambda s:s.get('editing'))
                self.assertTrue(all(t['opacity']==1 for t in editing['slots']))
                click('controlTile-dnd');self.assertFalse(state()['dnd'])
                start,finish=point('controlTile-dnd'),point('controlTile-bluetooth')
                subprocess.run([dragger,str(start['x']),str(start['y']),str(finish['x']),str(finish['y'])],check=True,timeout=5)
                moved=wait(lambda s:s.get('ready') and cell(s,'dnd')==dict(id='dnd',col=2,row=0) and s['saved']['tiles']==s['layout'])
                valid(moved);self.assertFalse(moved['dnd'])
                start=point('controlTile-dnd')
                subprocess.run([dragger,str(start['x']),str(start['y']),str(start['x']+500),str(start['y'])],check=True,timeout=5)
                self.assertEqual(state()['saved'],moved['saved'])
                click('controlTile-dnd')
                self.assertTrue(next(t for t in state()['slots'] if t['id']=='dnd')['focus'])
                subprocess.run(['wtype','-s','200','-k','Right'],env=env,check=True)
                keyed=wait(lambda s:s.get('ready') and cell(s,'dnd')['col']==3);valid(keyed)
                click('controlGridColumns');subprocess.run(['wtype','-s','200','-k','Down','-k','Return'],env=env,check=True)
                large=wait(lambda s:s.get('ready') and s.get('columns')==8);valid(large)
                click('controlGridRows');subprocess.run(['wtype','-s','200','-k','Down','-k','Return'],env=env,check=True)
                wait(lambda s:s.get('ready') and s.get('rows')==8)
                click('controlTile-dnd')
                for row in range(2,8):
                    subprocess.run(['wtype','-s','70','-k','Down'],env=env,check=True)
                    bottom=wait(lambda s:s.get('ready') and cell(s,'dnd')['row']==row);valid(bottom)
                self.assertGreater(bottom['scrollY'],0)
                click('Reset grid');reset=wait(lambda s:s.get('ready') and cell(s,'wifi')['col']==0);valid(reset)
                value=reset['saved'];self.assertEqual(value['rows'],8)
                cards=json.loads(ipc('state'))['preferences']['controlLayout']
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
