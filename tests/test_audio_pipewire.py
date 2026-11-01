"""Direct routing is safe only after proving the Pulse and native core identities."""
import importlib
from pathlib import Path
import unittest

PRESENT=(Path(__file__).resolve().parents[1]/'scripts/audio_pipewire.py').exists()


@unittest.skipUnless(PRESENT,'W1 native routing absent on baseline')
class NativeRouteIdentityCase(unittest.TestCase):
    def fixture(self):
        return {'cookie':'1234:abcd'},[
            dict(id=0,type='PipeWire:Interface:Core',info={'cookie':0x1234abcd}),
            dict(id=5,type='PipeWire:Interface:Node',info={'props':{'object.serial':120,'media.class':'Stream/Output/Audio'}}),
            dict(id=7,type='PipeWire:Interface:Node',info={'props':{'object.serial':111,'media.class':'Audio/Sink'}})]

    def test_node_id_is_resolved_from_serial_and_legacy_target_is_cleared(self):
        module=importlib.import_module('audio_pipewire');info,objects=self.fixture()
        route=module.route_plan(info,objects,'120','111')
        calls=[];module.apply_route(lambda *args:calls.append(args),route)
        self.assertEqual(calls,[('pw-metadata','-n','default','5','target.object','111','Spa:Id'),
                                ('pw-metadata','-n','default','5','target.node')])

    def test_wrong_core_duplicate_serial_or_wrong_node_kind_cannot_write(self):
        module=importlib.import_module('audio_pipewire')
        for change in (lambda x:x[0]['info'].update(cookie=1),
                       lambda x:x.append(x[1]),
                       lambda x:x[2]['info']['props'].update({'media.class':'Audio/Source'})):
            info,objects=self.fixture();change(objects)
            with self.assertRaises(ValueError):module.route_plan(info,objects,'120','111')

    def test_unready_or_malformed_native_objects_are_validation_errors(self):
        module=importlib.import_module('audio_pipewire')
        for position in (0,1,2):
            info,objects=self.fixture();objects[position]['info']=None
            with self.subTest(position=position),self.assertRaises(ValueError):module.route_plan(info,objects,'120','111')
