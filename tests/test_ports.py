"""Selected desktop port regressions using private fixtures."""
import json
import unittest
from test_backend import backend, Fixture, FakeRunner
from privacy import captures

class PrivacyCase(Fixture, unittest.TestCase):
    def node(self, ident, media, **props):
        return {'id':ident,'type':'PipeWire:Interface:Node','info':{'state':'running','props':{'media.class':media,**props}}}
    def test_muted_and_virtual_nodes_do_not_hide_another_capture(self):
        muted=self.node(1,'Stream/Input/Audio');muted['info']['params']={'Props':[{'mute':True}]}
        nodes=[muted,self.node(2,'Stream/Input/Audio',**{'application.name':'Meeting'}),self.node(3,'Stream/Input/Audio',**{'stream.capture.sink':'true'}),self.node(4,'Stream/Input/Audio',**{'node.name':'cava'}),self.node(5,'Video/Source',**{'node.name':'niri-screencast'})]
        self.assertEqual([(c['id'],c['kind']) for c in captures(nodes)],[(2,'microphone'),(5,'screen')])
        nodes[1]['info']['state']='suspended'
        self.assertEqual([c['kind'] for c in captures(nodes)],['screen'])
    def test_invalid_or_unavailable_pipewire_is_not_active(self):
        live=self.make_backend(FakeRunner({('pw-dump',):'invalid'}))
        self.assertFalse(live.privacy()['available'])
        self.assertEqual(live.privacy()['captures'],[])
