"""Freeze live/demo refresh behavior before the light features enter the registry."""
import json
import unittest
from unittest.mock import patch

from test_backend import Fixture, FakeRunner, backend
from niri_keybinds import read_keybinds

DEMO = 'Demo preview: no system command executed'


class LightDispatchCase(Fixture, unittest.TestCase):
    def make(self, demo=False, settings=False, responses=None):
        runner=FakeRunner(responses=responses)
        live=self.make_backend(runner,demo=demo);live.settings_only=settings
        self.addCleanup(live.charge_executor.shutdown);self.addCleanup(live.feature_executor.shutdown)
        return live,runner

    def test_night_refresh_contexts_retry_validation_status_and_exact_sequence(self):
        for demo in (False,True):
            for settings in (False,True):
                with self.subTest(demo=demo,settings=settings):
                    live,runner=self.make(demo,settings)
                    live.night_light.signature=('previous',)
                    path=live.shell_entry
                    state={'available':True,'active':True,'temperature':4200,'error':''}
                    runner.responses[('quickshell','-p',path,'ipc','call','shell','nightLightStatus')]=json.dumps(state)
                    runner.names.add('quickshell')
                    result=live.handle(dict(action='nightLightRefresh',retry=True))
                    self.assertEqual(result,dict(action='nightLightRefresh',ok=True,message=DEMO if demo else 'Night Light refreshed',sequence=1))
                    if demo:
                        self.assertEqual(live.night_state,dict(available=True,enabled=False,active=False,temperature=4500,mode='manual',start='20:00',end='07:00',error=''))
                        self.assertEqual(runner.calls,[])
                    elif settings:
                        self.assertEqual(live.night_state,state)
                        self.assertEqual(runner.calls,[('quickshell','-p',path,'ipc','call','shell','retryNightLight'),
                                                      ('quickshell','-p',path,'ipc','call','shell','nightLightStatus')])
                    else:
                        self.assertIsNone(live.night_light.signature);self.assertEqual(live.night_state,{})
                    result=live.handle(dict(action='nightLightRefresh',retry=1))
                    self.assertEqual(result,dict(action='nightLightRefresh',ok=demo,
                        message=DEMO if demo else 'Night Light retry must be boolean',sequence=2))

    def test_idle_refresh_preserves_shell_settings_fallback_and_demo_profile(self):
        for demo in (False,True):
            for settings in (False,True):
                live,runner=self.make(demo,settings)
                with patch.object(live,'ac_online',return_value=True):
                    result=live.handle(dict(action='idleRefresh'))
                self.assertEqual(result,dict(action='idleRefresh',ok=True,message=DEMO if demo else 'Idle profile refreshed',sequence=1))
                expected=dict(source='battery',available=True,running=False,error='',profile=backend.DEFAULT_IDLE_PROFILES['battery']) if demo else dict(source='ac',available=False,error='')
                self.assertEqual(live.idle_state,expected)
                self.assertEqual(live.feature_jobs,{})
                if settings and not demo:
                    response=dict(source='battery',available=True,running=True,error='')
                    command=('quickshell','-p',live.shell_entry,'ipc','call','shell','idleStatus')
                    runner.names.add('quickshell');runner.responses[command]=json.dumps(response)
                    self.assertTrue(live.handle(dict(action='idleRefresh'))['ok']);self.assertEqual(live.idle_state,response)
                if demo: self.assertEqual(runner.calls,[])

    def test_keybind_refresh_uses_configured_path_live_and_bundled_demo_path(self):
        path=self.put('test.kdl','binds { Mod+T hotkey-overlay-title="A terminal" { spawn "kitty"; } }\n')
        self.preferences.values['niriConfigPath']=str(path)
        for demo in (False,True):
            for settings in (False,True):
                live,runner=self.make(demo,settings)
                self.assertEqual(live.handle(dict(action='keybindRefresh')),dict(action='keybindRefresh',ok=True,
                    message=DEMO if demo else 'Keybindings refreshed',sequence=1))
                expected=read_keybinds(str(backend.Path(backend.__file__).resolve().parents[1]/'config/niri/lme-shell.kdl') if demo else str(path))
                self.assertEqual(live.keybinds,expected);self.assertEqual(runner.calls,[])
                self.assertEqual(live.feature_jobs,{})

    def test_idle_inhibit_contexts_boolean_rejection_and_unregistered_routes(self):
        for demo in (False,True):
            for settings in (False,True):
                live,_=self.make(demo,settings)
                for sequence,value in enumerate((True,False,1),1):
                    error='This action is unavailable in the settings app' if settings else 'Idle inhibit must be boolean'
                    ok=not settings and type(value) is bool
                    message=(DEMO if demo else 'Idle paused' if value else 'Idle resumed') if ok else error
                    self.assertEqual(live.handle(dict(action='idleInhibit',value=value)),dict(action='idleInhibit',ok=ok,message=message,sequence=sequence))
                error='This action is unavailable in the settings app' if settings else 'Unknown action: idleRefreshExtra'
                self.assertEqual(live.handle(dict(action='idleRefreshExtra')),dict(action='idleRefreshExtra',ok=False,message=error,sequence=4))
