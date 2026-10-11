"""Night Light scheduling, private screenshot sessions and native editor checks."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import zlib

from test_backend import backend, Fixture, FakeRunner
from test_clipboard import PNG
from desktop_features import appearance_profile, control_layout, MOTION_DEFAULTS
from night_light import NightLight, clock_minutes, desired_state, solar_times
from screen_capture import ScreenCapture, png_size


class CaptureNightCase(Fixture, unittest.TestCase):
    def capture(self):
        controller = ScreenCapture(FakeRunner(available={'niri', 'tesseract'}))
        self.addCleanup(controller.close)
        with patch.dict(os.environ, XDG_RUNTIME_DIR=str(self.root)):
            controller.start('screen')
        Path(controller.state['path']).write_bytes(PNG)
        controller.refresh(); controller.refresh()
        return controller

    def test_clock_boundaries_and_midnight_schedule(self):
        prefs = copy.deepcopy(backend.DEFAULT_PREFERENCES)
        prefs.update(nightLightEnabled=True, nightLightMode='schedule', nightLightStart='20:00', nightLightEnd='07:00')
        for hour, minute, active in [(19, 59, False), (20, 0, True), (0, 0, True), (6, 59, True), (7, 0, False)]:
            self.assertEqual(desired_state(prefs, {}, datetime(2026, 10, 11, hour, minute, tzinfo=timezone.utc))[0], active)
        prefs.update(nightLightStart='08:00', nightLightEnd='10:00')
        self.assertTrue(desired_state(prefs, {}, datetime(2026, 10, 11, 9, tzinfo=timezone.utc))[0])
        prefs['nightLightMode'] = 'manual'
        self.assertTrue(desired_state(prefs, {}, datetime(2026, 10, 11, 12, tzinfo=timezone.utc))[0])
        prefs['nightLightEnabled'] = False
        self.assertFalse(desired_state(prefs, {}, datetime.now().astimezone())[0])
        for invalid in ('24:00', '7:00', '00:60', '', None):
            with self.assertRaises(ValueError): clock_minutes(invalid)

    def test_sunset_coordinates_polar_days_and_location_errors(self):
        sunrise, sunset = solar_times(datetime(2026, 10, 11).date(), 10.82, 106.63)
        self.assertIn(sunrise.hour, (22, 23)); self.assertIn(sunset.hour, (10, 11))
        with self.assertRaises(ValueError): solar_times(datetime(2026, 6, 21).date(), 89, 0)
        with self.assertRaises(ValueError): solar_times(datetime(2026, 6, 21).date(), float('nan'), 0)
        prefs = {**backend.DEFAULT_PREFERENCES, 'nightLightMode': 'sunset', 'nightLightEnabled': True}
        with self.assertRaises(ValueError): desired_state(prefs, {}, datetime.now().astimezone())

    def test_preferences_migrate_profiles_and_old_control_layouts(self):
        old = {k: v for k, v in backend.DRACULA_PROFILE.items() if k not in MOTION_DEFAULTS}
        old['name'] = 'Personal'; normalized = appearance_profile(old, backend.validate_preference)
        self.assertEqual({k: normalized[k] for k in MOTION_DEFAULTS}, MOTION_DEFAULTS)
        old_layout = [m for m in backend.DEFAULT_CONTROL_LAYOUT if m['id'] != 'nightLight']
        self.assertEqual(control_layout(old_layout)[:-1], old_layout)
        self.assertEqual(control_layout(old_layout)[-1]['id'], 'nightLight')
        for key, invalid in [('motionSpeed', 0), ('motionBounce', 1.1), ('motionPreset', 'unknown'), ('nightLightTemperature', 100), ('nightLightEnabled', 1), ('nightLightStart', '25:00')]:
            with self.assertRaises(ValueError): backend.validate_preference(key, invalid)
        self.preferences.update({'motionPreset': 'jelly', 'motionSpeed': .8, 'motionBounce': .6})
        live = self.make_backend(demo=True); live.handle({'action': 'appearanceSave', 'name': 'Jelly'})
        live.handle({'action': 'appearanceApply', 'name': 'Dracula'}); live.handle({'action': 'appearanceApply', 'name': 'Jelly'})
        self.assertEqual(live.preferences.values['motionPreset'], 'jelly')

    def test_missing_gamma_dependency_and_readonly_settings(self):
        controller = NightLight(FakeRunner()); self.addCleanup(controller.close)
        prefs = {**backend.DEFAULT_PREFERENCES, 'nightLightEnabled': True}
        self.assertIn('Install wlsunset', controller.sync(prefs, {})['error'])
        prefs['nightLightEnabled'] = False
        self.assertEqual(controller.sync(prefs, {})['error'], '')
        live = self.make_backend(); live.preferences.set('nightLightEnabled', True)
        live.snapshot(); self.assertIsNone(live.night_light.child)
        call = ('quickshell', '-p', str(Path(__file__).resolve().parents[1]/'shell.qml'), 'ipc', 'call', 'shell', 'nightLightStatus')
        runner = FakeRunner({call: json.dumps({'active': True, 'temperature': 4000})})
        settings = backend.DesktopBackend(runner=runner, preferences=self.preferences, settings_only=True, weather_fetch=False)
        self.addCleanup(settings.weather.close)
        self.assertTrue(settings.handle({'action': 'nightLightRefresh'})['ok'])
        self.assertEqual(settings.night_state['temperature'], 4000)
        runner.responses[call] = backend.CommandError('Shell stopped')
        self.assertTrue(settings.handle({'action': 'nightLightRefresh'})['ok'])
        self.assertFalse(settings.night_state['active'])
        self.assertIn('Start LME Shell', settings.night_state['error'])
        self.assertFalse(settings.handle({'action': 'screenshot'})['ok'])
        self.assertIsNone(settings.night_light.child)

    def test_night_light_owns_only_its_worker_and_reports_gamma_failure(self):
        worker = self.root/'wlsunset'
        worker.write_text('#!/usr/bin/python3\nimport sys,time\nprint("gamma control failed on output",file=sys.stderr,flush=True)\ntime.sleep(30)\n'); worker.chmod(0o755)
        runner = FakeRunner(available={'wlsunset'}); runner.executable = lambda _: str(worker)
        controller = NightLight(runner); self.addCleanup(controller.close)
        prefs = {**backend.DEFAULT_PREFERENCES, 'nightLightEnabled': True}
        controller.sync(prefs, {}); pid = controller.child.pid
        limit = time.monotonic() + 3
        while time.monotonic() < limit:
            state = controller.sync(prefs, {})
            if state['error']: break
            time.sleep(.02)
        self.assertIn('Gamma control failed', state['error']); self.assertFalse(state['active'])
        self.assertEqual(controller.child.pid, pid)
        prefs['nightLightEnabled'] = False
        self.assertFalse(controller.sync(prefs, {})['running'])
        with self.assertRaises(ProcessLookupError): os.kill(pid, 0)

    def test_capture_native_modes_private_path_and_pending_timeout(self):
        controller = self.capture()
        self.assertEqual(controller.state['status'], 'ready'); self.assertEqual((controller.state['width'], controller.state['height']), (1, 1))
        self.assertEqual(Path(controller.state['path']).stat().st_mode & 0o777, 0o600)
        for mode, action in [('area', 'screenshot'), ('window', 'screenshot-window')]:
            controller.close()
            with patch.dict(os.environ, XDG_RUNTIME_DIR=str(self.root)): controller.start(mode)
            self.assertEqual(controller.runner.calls[-1][3], action)
            with self.assertRaises(ValueError): controller.start('screen')
        controller.deadline = 0
        self.assertEqual(controller.refresh()['status'], 'error')
        original_folder = controller.directory.name; controller.close()
        self.assertFalse(Path(original_folder).exists())
        with self.assertRaises(ValueError): controller.start('all')

    def test_png_validation_and_export_never_overwrites(self):
        controller = self.capture(); token = controller.state['token']
        rendered = Path(controller.state['renderPath']); rendered.write_bytes(PNG)
        folder = self.root/'saved'
        with patch('screen_capture.time.strftime', return_value='fixed-'), patch('screen_capture.uuid.uuid4') as identifier:
            identifier.return_value.hex = 'repeatedidentifier'
            controller.export(token, 'save', str(folder))
            with self.assertRaises(FileExistsError): controller.export(token, 'save', str(folder))
        self.assertEqual(next(folder.iterdir()).read_bytes(), PNG)
        self.assertEqual(next(folder.iterdir()).stat().st_mode & 0o777, 0o600)
        controller.export(token, 'save', str(folder)); controller.export(token, 'save', str(folder))
        self.assertEqual(len(list(folder.iterdir())), 3)
        with patch('screen_capture.shutil.copyfileobj', side_effect=OSError('Disk full')):
            with self.assertRaises(OSError): controller.export(token, 'save', str(self.root/'failed-save'))
        self.assertEqual(list((self.root/'failed-save').iterdir()), [])
        with self.assertRaises(ValueError): controller.export('stale', 'save', str(folder))
        with self.assertRaises(ValueError): controller.export(token, 'save', '')
        rendered.write_bytes(b'not png')
        with self.assertRaises(ValueError): png_size(rendered)
        rendered.write_bytes(PNG[:16] + struct.pack('>II', 10000, 10000) + PNG[24:])
        with self.assertRaises(ValueError): png_size(rendered)

    def test_ocr_validates_installed_languages_and_uses_edited_image(self):
        controller = self.capture(); token = controller.state['token']
        Path(controller.state['renderPath']).write_bytes(PNG)
        controller.runner.responses[('tesseract', '--list-langs')] = 'List of available languages (2):\neng\nvie\nosd\n'
        command = ('tesseract', controller.state['renderPath'], 'stdout', '-l', 'eng+vie', '--psm', '3')
        controller.runner.responses[command] = ' Read this text\n'
        self.assertEqual(controller.ocr(token, 'eng+vie'), 'Read this text')
        self.assertEqual(controller.runner.calls[-1], command)
        for invalid in ('missing', 'eng;id', '--help', ''):
            with self.assertRaises(ValueError): controller.ocr(token, invalid)

    def test_closed_capture_cannot_publish_a_late_ocr_result(self):
        live = self.make_backend(); self.addCleanup(live.feature_executor.shutdown)
        live.capture.state = {'status': 'ready', 'token': 'old', 'ocrText': ''}
        with patch.object(live.capture, 'ocr', return_value='Private text'):
            self.assertTrue(live.handle({'action': 'captureOcr', 'token': 'old', 'language': 'eng'})['ok'])
            future = live.feature_jobs['captureOcr']; future.result(timeout=2)
        live.capture.close(); live.capture.state.update(status='ready', token='new', ocrText='')
        live.finish_features()
        self.assertEqual(live.capture.state['ocrText'], '')
        self.assertEqual(live.last_result['message'], '')
        self.assertNotIn('captureOcr', live.feature_jobs)


def png_pixel(path, x, y):
    """Read a pixel of Qt's exported 8-bit RGB(A) PNG, including row filters."""
    data, offset, compressed = path.read_bytes(), 8, bytearray()
    width, height = png_size(path); channels = 4 if data[25] == 6 else 3
    if data[24] != 8 or data[25] not in (2, 6): raise AssertionError('Unexpected Qt PNG format')
    while offset < len(data):
        length = int.from_bytes(data[offset:offset+4], 'big'); kind = data[offset+4:offset+8]
        if kind == b'IDAT': compressed.extend(data[offset+8:offset+8+length])
        offset += length + 12
    raw = zlib.decompress(compressed); stride = width * channels; previous = bytearray(stride)
    for row in range(y+1):
        filter_type = raw[row*(stride+1)]; current = bytearray(raw[row*(stride+1)+1:(row+1)*(stride+1)])
        for index in range(stride):
            a = current[index-channels] if index >= channels else 0; b = previous[index]; c = previous[index-channels] if index >= channels else 0
            prediction = a+b-c; distances = (abs(prediction-a), abs(prediction-b), abs(prediction-c))
            paeth = (a, b, c)[distances.index(min(distances))]
            predictor = (0, a, b, (a+b)//2, paeth)[filter_type]
            current[index] = (current[index]+predictor) & 255
        previous = current
    return tuple(previous[x*channels:x*channels+channels])


@unittest.skipUnless(os.environ.get('LME_TEST_CAPTURE_UI') == '1', 'opt-in private Wayland screenshot editor/OCR check')
class NativeCaptureCase(unittest.TestCase):
    def test_shell_capture_opens_independent_editor_and_can_reopen_after_close(self):
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); config=root/'config'; (config/'lme-shell').mkdir(parents=True)
            (config/'lme-shell/settings.json').write_text(json.dumps({'weatherAutoLocation':False,'clipboardEnabled':False}))
            source=root/'source.png';source.write_bytes(PNG); binaries=root/'bin';binaries.mkdir()
            fake_niri=binaries/'niri'
            fake_niri.write_text('#!/usr/bin/python3\nimport sys,shutil\na=sys.argv[1:]\nif a==["--version"]:print("niri 26.04")\nelif "--path" in a:shutil.copyfile('+repr(str(source))+',a[a.index("--path")+1])\nelif "event-stream" not in a:print("[]")\n');fake_niri.chmod(0o755)
            env={**os.environ,'PATH':str(binaries)+os.pathsep+os.environ['PATH'],'XDG_CONFIG_HOME':str(config),'XDG_DATA_HOME':str(root/'data'),'XDG_STATE_HOME':str(root/'state'),'LME_SHELL_DEMO':'0'}
            for key in ('LME_SHELL_PREVIEW','LME_SHELL_BACKEND_DEMO','LME_SHELL_SETTINGS'):env.pop(key,None)
            entry=repo/'shell.qml'
            with (root/'qml.log').open('w+') as log:
                process=subprocess.Popen(['quickshell','-p',str(entry)],env=env,stdout=log,stderr=subprocess.STDOUT)
                def ipc(method,*args):return subprocess.check_output(['quickshell','-p',str(entry),'ipc','call','shell',method,*args],env=env,text=True,timeout=5).strip()
                def windows():
                    tree=json.loads(subprocess.check_output(['swaymsg','-t','get_tree'],env=env,text=True))
                    def walk(node):
                        return ([node] if node.get('name')=='LME Screenshot' else [])+[child for key in ('nodes','floating_nodes') for item in node.get(key,[]) for child in walk(item)]
                    return walk(tree)
                def wait(predicate,timeout=10):
                    end=time.monotonic()+timeout
                    while time.monotonic()<end:
                        try:
                            result=predicate()
                            if result:return result
                        except (ValueError,subprocess.CalledProcessError):pass
                        time.sleep(.05)
                    log.flush();self.fail('Shell capture timeout: '+(root/'qml.log').read_text()[-1800:])
                try:
                    wait(lambda:json.loads(ipc('idleStatus')).get('source'))
                    for _ in range(2):
                        ipc('capture','screen');window=wait(windows)[0]
                        subprocess.run(['swaymsg',f'[con_id={window["id"]}] kill'],env=env,check=True,stdout=subprocess.DEVNULL)
                        wait(lambda:not windows())
                finally:process.terminate();process.wait(timeout=6)
                output=(root/'qml.log').read_text()
                for error in ('ReferenceError','TypeError','binding loop','Unable to assign','Failed to load configuration'):self.assertNotIn(error,output)

    def test_drawing_undo_redo_flattened_redaction_export_clipboard_and_real_ocr(self):
        repo = Path(__file__).resolve().parents[1]
        pointer = os.environ.get('LME_TEST_POINTER'); drag = os.environ.get('LME_TEST_DRAG')
        self.assertTrue(pointer and drag and shutil.which('quickshell') and shutil.which('tesseract'))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); env = os.environ.copy(); env.update(XDG_CONFIG_HOME=str(root/'config'), LME_TEST_CAPTURE='1', LME_SHELL_DEMO='1')
            capture = ScreenCapture(FakeRunner(available={'niri'})); self.addCleanup(capture.close)
            with patch.dict(os.environ, XDG_RUNTIME_DIR=temporary): capture.start('screen')
            session = {**capture.state, 'width': 960, 'height': 540, 'url': Path(capture.state['path']).as_uri(), 'saveFolder': str(root/'saved'), 'languages': ['eng']}
            env['LME_TEST_CAPTURE_SESSION'] = json.dumps(session)
            entry = repo/'capture-demo.qml'
            with (root/'qml.log').open('w+') as log:
                process = subprocess.Popen(['quickshell', '-p', str(entry)], env=env, stdout=log, stderr=subprocess.STDOUT)
                def ipc(*args): return subprocess.check_output(['quickshell','-p',str(entry),'ipc','call','captureFixture',*map(str,args)], text=True, env=env, timeout=5).strip()
                def wait(predicate, timeout=8):
                    limit = time.monotonic()+timeout
                    while time.monotonic()<limit:
                        try:
                            state = json.loads(ipc('state'))
                            if predicate(state): return state
                        except (subprocess.CalledProcessError, ValueError): pass
                        time.sleep(.05)
                    log.flush(); self.fail('Editor state timeout: '+(root/'qml.log').read_text()[-2000:])
                def click(name):
                    p=json.loads(ipc('position',name)); self.assertTrue(p, name)
                    subprocess.run([pointer,str(p['x']),str(p['y'])],check=True,timeout=5)
                def draw(tool, start, end):
                    click(tool); a=json.loads(ipc('imagePoint',*start)); b=json.loads(ipc('imagePoint',*end))
                    subprocess.run([drag,str(a['x']),str(a['y']),str(b['x']),str(b['y'])],check=True,timeout=5)
                try:
                    wait(lambda s:s['ready']); ipc('resizeEditor',850,700); capture.refresh(); capture.refresh(); self.assertEqual(capture.state['status'],'ready')
                    draw('Redact',(100,180),(260,300)); wait(lambda s:s['strokes']==1)
                    click('Undo'); wait(lambda s:s['strokes']==0 and s['redo']==1)
                    click('Redo'); wait(lambda s:s['strokes']==1 and s['redo']==0)
                    for index,(tool,a,b) in enumerate([('Pen',(520,200),(600,250)),('Highlight',(520,280),(700,330)),('Rectangle',(480,160),(910,440)),('Arrow',(700,350),(820,400))],2):
                        draw(tool,a,b); wait(lambda s:s['strokes']==index)
                    click('Save PNG'); rendered=Path(capture.state['renderPath'])
                    limit=time.monotonic()+3
                    while not rendered.exists() and time.monotonic()<limit:time.sleep(.02)
                    wait(lambda s:not s['busy']); self.assertEqual(png_size(rendered),(960,540))
                    self.assertEqual(png_pixel(rendered,170,240)[:3],(0,0,0)); self.assertEqual(png_pixel(rendered,170,240)[-1],255)
                    self.assertNotEqual(png_pixel(Path(capture.state['path']),170,240)[:3],(0,0,0))
                    capture.runner=backend.CommandRunner(); token=capture.state['token']
                    capture.export(token,'save',str(root/'saved'))
                    self.assertEqual(Path(capture.state['savedPath']).read_bytes(),rendered.read_bytes())
                    capture.export(token,'copy'); self.assertEqual(subprocess.check_output(['wl-paste','--type','image/png'],env=env),rendered.read_bytes())
                    text=capture.ocr(token,'eng'); self.assertIn('LME SCREENSHOT',text)
                    ipc('recognized',text); click('Copy text')
                    self.assertIn('LME SCREENSHOT',subprocess.check_output(['wl-paste','--no-newline'],text=True,env=env))
                    click('screenshotFolder');wait(lambda s:s['folderFocused'])
                    subprocess.run(['wtype','-s','150','-M','ctrl','-k','a','-k','c','-m','ctrl'],env=env,check=True)
                    limit=time.monotonic()+3
                    while subprocess.check_output(['wl-paste','--no-newline'],text=True,env=env)!=session['saveFolder'] and time.monotonic()<limit:time.sleep(.03)
                    self.assertEqual(subprocess.check_output(['wl-paste','--no-newline'],text=True,env=env),session['saveFolder'])
                    ipc('screenshot',str(root/'editor.png'))
                    log.flush(); output=(root/'qml.log').read_text()
                    for error in ('TypeError','ReferenceError','binding loop','Cannot assign','not a function'):self.assertNotIn(error,output)
                finally:
                    process.terminate(); process.wait(timeout=5)
