"""Freeze shared value behavior through the existing public imports before extraction."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_backend import backend
import content_types
import image_utilities
import wallpaper
import peripheral_battery as batteries
import bluetooth_agent

ROOT = Path(__file__).resolve().parents[1]
SHARED = importlib.util.find_spec('peripheral_values') is not None
FIRST = 'Choose a wallpaper image path'
ABSOLUTE = 'Choose an absolute PNG, JPEG, WebP, GIF, or BMP path'
DEVICE = '/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF'


class SharedValueCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_image_path_types_raw_bound_controls_relative_extensions_and_absent_output(self):
        for value, message in [(None,FIRST),(True,FIRST),(1,FIRST),(Path('/x.png'),FIRST),('',FIRST),
                ('/'+'x'*4096+'.png',FIRST),('/x\0.png',FIRST),('/x\n.png',FIRST),
                ('relative.png',ABSOLUTE),('/x.svg',ABSOLUTE),('/x.png.exe',ABSOLUTE),
                ('/x.\udcff.png',ABSOLUTE)]:
            with self.subTest(value=repr(value)[:100]):
                for validate in (wallpaper.image_path,image_utilities.image_path):
                    with self.assertRaises(ValueError) as caught: validate(value)
                    self.assertEqual(str(caught.exception),message)
        for suffix in ('.png','.jpg','.jpeg','.webp','.gif','.bmp','.PNG','.JpEg'):
            path = self.root/('missing image;$(literal)'+suffix)
            self.assertEqual(wallpaper.image_path(str(path)),str(path))
            self.assertFalse(path.exists())

    def test_image_path_expansion_symlink_resolution_and_error_boundaries(self):
        target = self.root/'target.PNG'; target.write_bytes(b'unchanged')
        alias = self.root/'alias.png'; alias.symlink_to(target)
        self.assertEqual(wallpaper.image_path(str(alias)),str(target))
        self.assertEqual(wallpaper.image_path('~/shared-values-missing.png'),str(Path.home()/'shared-values-missing.png'))
        with patch.object(Path,'resolve',side_effect=RuntimeError('loop')):
            with self.assertRaises(ValueError) as caught: wallpaper.image_path('/alias.png')
            self.assertEqual(str(caught.exception),'Wallpaper path contains a symlink loop')
        with patch.object(Path,'resolve',side_effect=PermissionError('denied')):
            with self.assertRaisesRegex(PermissionError,'denied'): wallpaper.image_path('/alias.png')
        for resolved in ('/bad\n.png','/bad.\udcff.png','/'+'x'*4096+'.png','/bad.svg'):
            with patch.object(Path,'resolve',return_value=Path(resolved)):
                with self.assertRaises(ValueError) as caught: wallpaper.image_path('/alias.png')
                self.assertEqual(str(caught.exception),ABSOLUTE)
        raw = '/'+'x'*4091+'.png'
        self.assertEqual(len(raw),4096)
        with patch.object(Path,'resolve',return_value=Path('/resolved.png')):
            self.assertEqual(wallpaper.image_path(raw),'/resolved.png')
        self.assertEqual(target.read_bytes(),b'unchanged')

    def test_percentage_identity_and_kind_exact_values_and_fallbacks(self):
        for value in (0,100,22.5): self.assertEqual(batteries.percentage(value),value)
        for value in (None,True,False,'20',-1,101,float('nan'),float('inf'),10**500):
            self.assertIsNone(batteries.percentage(value))
        for value in ('aa:bb:cc:dd:ee:ff','AA_BB_CC_DD_EE_FF','aa-bb-cc-dd-ee-ff'):
            self.assertEqual(batteries.identity(value,'fallback'),'bluetooth:AA:BB:CC:DD:EE:FF')
        for value in (None,1,True,'','AA:BB',' aa:bb:cc:dd:ee:ff '):
            self.assertEqual(batteries.identity(value,'fallback'),'fallback')
        for value, expected in (('HEADPHONES','headphones'),('Earbuds','headphones'),
                ('Bluetooth Mouse','mouse'),('input-keyboard','keyboard'),('Other','device')):
            self.assertEqual(batteries.kind(value),expected)

    def test_bluez_raw_and_typed_property_readers_preserve_shape_and_inputs(self):
        props = {'Alias':'Headset','Name':'Ignored','Address':'aa-bb-cc-dd-ee-ff',
            'Connected':True,'Paired':True,'Icon':'audio-headphones'}
        for typed in (False,True):
            raw = {'org.bluez.Device1':props,'org.bluez.Battery1':{'Percentage':0}}
            if typed: raw = {iface:{key:dict(data=value) for key,value in values.items()} for iface,values in raw.items()}
            before = copy.deepcopy(raw)
            reader = backend.DesktopBackend.bluez_value if typed else lambda p,k,d:p.get(k,d)
            expected = dict(path=DEVICE,id='bluetooth:AA:BB:CC:DD:EE:FF',name='Headset',
                address='aa-bb-cc-dd-ee-ff',kind='headphones',paired=True,connected=True,percentage=0,charging=None)
            self.assertEqual(batteries.bluetooth_device(DEVICE,raw,reader),expected)
            self.assertEqual(bluetooth_agent.bluetooth_device(DEVICE,raw,reader),expected)
            self.assertEqual(raw,before)

    def test_bluez_fallbacks_connected_bool_gate_and_property_read_order(self):
        for props, name, kind in (({},'Bluetooth device','device'),({'Name':'Mouse'},'Mouse','mouse'),
                ({'Alias':'','Name':'Keyboard'},'Keyboard','keyboard'),({'Address':'not-a-mac'},'not-a-mac','device')):
            raw = {'org.bluez.Device1':props}
            self.assertEqual(batteries.bluetooth_device(DEVICE,raw,lambda p,k,d:p.get(k,d)),
                dict(path=DEVICE,id='bluez:'+DEVICE,name=name,address=props.get('Address',''),
                    kind=kind,paired=False,connected=False,percentage=None,charging=None))
        for connected in (True,False,1,'true',None):
            calls = []
            def reader(props,key,default):
                calls.append((key,default)); return props.get(key,default)
            raw = {'org.bluez.Device1':{'Alias':'Named','Connected':connected,'Paired':1},
                'org.bluez.Battery1':{'Percentage':10}}
            value = batteries.bluetooth_device(DEVICE,raw,reader)
            self.assertEqual(value['connected'],connected is True)
            self.assertEqual(value['percentage'],10 if connected is True else None)
            self.assertFalse(value['paired'])
            expected = [('Address',''),('Alias',''),('Connected',False),('Icon',''),('Paired',False)]
            if connected is True: expected.append(('Percentage',None))
            self.assertEqual(calls,expected)
        with self.assertRaises(KeyError): batteries.bluetooth_device(DEVICE,{},reader)

    @unittest.skipUnless(SHARED,'shared peripheral module absent on baseline; export identity N/A')
    def test_old_exports_are_the_shared_objects_and_heavy_modules_are_not_imported(self):
        import peripheral_values
        for name in ('percentage','identity','kind','bluetooth_device'):
            self.assertIs(getattr(batteries,name),getattr(peripheral_values,name))
        self.assertIs(bluetooth_agent.bluetooth_device,peripheral_values.bluetooth_device)
        self.assertIs(wallpaper.image_path,content_types.image_path)
        self.assertIs(image_utilities.image_path,content_types.image_path)
        self.assertIs(wallpaper.EXTENSIONS,content_types.EXTENSIONS)
        env = dict(os.environ,PYTHONPATH=str(ROOT/'scripts'),XDG_CONFIG_HOME=str(self.root/'config'),
            XDG_STATE_HOME=str(self.root/'state'),XDG_RUNTIME_DIR=str(self.root/'runtime'))
        code = '''import content_types, peripheral_values, json, sys
print(json.dumps(sorted(name for name in ('desktop_backend','wallpaper','image_utilities','peripheral_battery','bluetooth_agent','gi') if name in sys.modules)))'''
        result = subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(json.loads(result.stdout),[])
        code = '''import image_utilities, bluetooth_agent, json, sys
print(json.dumps(sorted(name for name in ('wallpaper','peripheral_battery','desktop_backend','gi') if name in sys.modules)))'''
        result = subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(json.loads(result.stdout),[])


if __name__=='__main__': unittest.main()
