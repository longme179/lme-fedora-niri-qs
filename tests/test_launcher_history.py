"""Usage is local, bounded and subordinate to launcher name matching."""
import json
from datetime import datetime,timezone
import os
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch
import test_local_qml as qml_tests
from test_backend import Fixture, FakeRunner, backend
from launcher_history import LauncherHistory, MAX_APPS
from settings_transfer import document

NOW=1780000000


class HistoryCase(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'launcher.json';self.history=LauncherHistory(self.path)

    def test_decay_recent_ties_restart_concurrent_writers_and_clear(self):
        self.history.record('old.desktop',now=NOW-7*86400)
        self.history.record('new.desktop',now=NOW)
        other=LauncherHistory(self.path);other.record('new.desktop',now=NOW+1)
        scores=self.history.snapshot(now=NOW+2)
        self.assertEqual(scores['old.desktop']['score'],45)
        self.assertEqual(scores['new.desktop']['score'],180)
        self.assertEqual(scores['new.desktop']['last'],NOW+1)
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)
        self.assertEqual(LauncherHistory(self.path).snapshot(now=NOW+2),scores)
        other.clear();self.assertEqual(self.history.snapshot(now=NOW+2),{})

    def test_old_bad_and_oversized_history_recovers_without_executing_data(self):
        self.history.record('old.desktop',now=NOW-61*86400)
        self.assertEqual(self.history.snapshot(now=NOW),{})
        for payload in ('broken','[]',json.dumps({'schema':True,'apps':{}}),json.dumps({'schema':1,'apps':{'bad':{'last':True,'days':{'2026-01-01':4}}}}),' '*1048577):
            self.path.write_text(payload);self.history.stamp=None
            self.assertEqual(self.history.snapshot(now=NOW),{})
        self.history.record('recovered.desktop',now=NOW)
        self.assertEqual(set(self.history.snapshot(now=NOW)),{'recovered.desktop'})
        # Clocks moving backwards cannot produce negative/infinite weights.
        self.assertGreater(self.history.snapshot(now=NOW-86400)['recovered.desktop']['score'],0)
        day=datetime.fromtimestamp(NOW,timezone.utc).date().isoformat()
        self.path.write_text(json.dumps({'schema':1,'apps':{'overflow':{'last':10**1000,'days':{day:1}}}}))
        self.history.stamp=None;self.assertEqual(self.history.snapshot(now=NOW),{})
        self.path.write_text(json.dumps({'schema':1,'apps':{'bad\ud800':{'last':NOW,'days':{day:1}}}}))
        self.history.record('valid.desktop',now=NOW)
        self.assertEqual(set(self.history.snapshot(now=NOW)),{'valid.desktop'})

    def test_app_cap_and_disabled_reads_do_not_create_state(self):
        with patch.object(self.history,'read',side_effect=AssertionError('Disabled history read')):
            self.assertEqual(self.history.snapshot(enabled=False),{})
        self.assertFalse(self.path.exists())
        # Seed enough valid records to exercise the cap in one atomic update.
        day=datetime.fromtimestamp(NOW,timezone.utc).date().isoformat()
        self.path.write_text(json.dumps({'schema':1,'apps':{str(i):{'last':NOW-i,'days':{day:1}} for i in range(MAX_APPS+10)}}))
        self.history.record('latest.desktop',now=NOW)
        self.assertEqual(len(self.history.snapshot(now=NOW)),MAX_APPS)
        self.assertIn('latest.desktop',self.history.snapshot(now=NOW))


class LaunchIntegrationCase(Fixture,unittest.TestCase):
    def app(self,live):
        live.applications.entries['app.desktop']={'id':'app.desktop','name':'App','terminal':False,'argv':['/usr/bin/app'],'path':'/tmp/app.desktop'}

    def test_record_only_successful_dispatch_and_allow_opt_out_and_clear_in_settings(self):
        live=self.make_backend(FakeRunner());self.app(live)
        self.assertFalse(live.handle(dict(action='launch',id='missing.desktop'))['ok'])
        self.assertFalse(live.launcher_history.path.exists())
        self.assertTrue(live.handle(dict(action='launch',id='app.desktop'))['ok'])
        self.assertEqual(live.launcher_history.snapshot()['app.desktop']['score'],90)
        self.preferences.set('launcherRanking',False)
        before=live.launcher_history.path.read_bytes()
        self.assertTrue(live.handle(dict(action='launch',id='app.desktop'))['ok'])
        self.assertEqual(live.launcher_history.path.read_bytes(),before)
        self.assertEqual(live.feature_snapshot()['launcherUsage'],{})
        self.assertIn('launcherRanking',document(self.preferences.values,'preset')['settings'])
        self.assertNotIn('launcherUsage',document(self.preferences.values,'backup')['settings'])
        live.settings_only=True
        self.assertTrue(live.handle(dict(action='launcherHistoryClear'))['ok'])
        self.assertEqual(live.launcher_history.snapshot(),{})
        for value in ('true',None,1):
            with self.assertRaises(ValueError): self.preferences.set('launcherRanking',value)

    def test_spawn_failure_is_not_counted_and_history_failure_does_not_block_launch(self):
        live=self.make_backend(FakeRunner());self.app(live)
        with patch.object(live.runner,'spawn',side_effect=backend.CommandError('Cannot launch')):
            self.assertFalse(live.handle(dict(action='launch',id='app.desktop'))['ok'])
        self.assertFalse(live.launcher_history.path.exists())
        for error in (PermissionError('Read-only state'),ValueError('Invalid cached encoding')):
            with self.subTest(error=type(error).__name__),patch('launcher_history.write_json',side_effect=error):
                self.assertTrue(live.handle(dict(action='launch',id='app.desktop'))['ok'])
        self.assertIn('could not be saved',live.feature_snapshot()['launcherHistoryError'])
        demo=self.make_backend(demo=True)
        app=demo.demo_snapshot()['apps'][0]['id']
        self.assertTrue(demo.handle(dict(action='launch',id=app))['ok'])
        self.assertFalse(demo.launcher_history.path.exists())


@unittest.skipUnless(shutil.which('quickshell'),'Quickshell is required')
class SearchUsageCase(unittest.TestCase):
    run_qml=qml_tests.LocalQmlCase.run_qml

    def test_empty_query_text_priority_recency_ties_and_stable_snapshot_identity(self):
        result=self.run_qml('import "qml/services/LauncherSearch.js" as Search\nimport "qml/services"','''
    Timer { interval:40;running:true;repeat:true;onTriggered: {
        if(!ShellState.backendReady) return;
        const apps=[{id:"exact",name:"Terminal"},{id:"prefix",name:"Terminal Pro"},{id:"other",name:"Browser"}];
        const usage={prefix:{score:900,last:30},exact:{score:90,last:10},other:{score:90,last:20}};
        const ids=q=>Search.apps(q,apps,usage).map(a=>a.id);
        const text=ids("terminal"),empty=ids(""),plain=Search.apps("",apps).map(a=>a.id);
        const next=Object.assign({},ShellState.snapshot,{launcherUsage:usage});ShellState.accept(JSON.stringify(next));
        const before=ShellState.launcherUsage;ShellState.accept(JSON.stringify(next));
        fixture.finish({text,empty,plain,stable:ShellState.launcherUsage===before,sourceUnchanged:apps[0].id==="exact"});
    }}
''')
        self.assertEqual(result,dict(text=['exact','prefix'],empty=['prefix','other','exact'],plain=['other','exact','prefix'],stable=True,sourceUnchanged=True))


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI')=='1','private launcher usage checks')
class LauncherUsageUiCase(unittest.TestCase):
    run_qml=qml_tests.LocalQmlCase.run_qml

    def test_real_launcher_uses_history_then_name_priority_and_click_dispatch(self):
        result=self.run_qml('import QtTest\nimport "qml/panels"\nimport "qml/services"','''
    property int phase:0
    property int ticks:0
    property string exactId:""
    property string exactName:""
    property string frequentId:""
    property var checks:({})
    FloatingWindow { implicitWidth:800;implicitHeight:850
        Launcher { id:panel;anchors.fill:parent }
        TestCase { id:mouse;when:false }
    }
    Timer { interval:50;repeat:true;running:true;onTriggered: {
        if(++fixture.ticks>200) { fixture.finish({timeout:fixture.phase,checks:fixture.checks});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0 && ShellState.apps.length>1) {
            fixture.exactId=ShellState.apps[0].id;fixture.exactName=ShellState.apps[0].name;
            fixture.frequentId=ShellState.apps[ShellState.apps.length-1].id;
            ShellState.accept(JSON.stringify(Object.assign({},ShellState.snapshot,{launcherUsage:{[fixture.frequentId]:{score:900,last:100}}})));
            fixture.phase++;
        } else if(fixture.phase===1 && panel.results[0].id===fixture.frequentId) {
            fixture.checks.ranked=true;mouse.findChild(panel,"launcherSearch").text=fixture.exactName;fixture.phase++;
        } else if(fixture.phase===2 && panel.results[0].id===fixture.exactId) {
            fixture.checks.exact=true;const button=mouse.findChild(panel,"launcherResult-0");
            mouse.mouseClick(button,button.width/2,button.height/2);fixture.phase++;
        } else if(fixture.phase===3 && ShellState.lastResult.action==="launch" && !ShellState.pendingActions.launch) {
            fixture.checks.launched=ShellState.lastResult.ok;fixture.finish(fixture.checks);
        }
    }}
''',{'QT_QPA_PLATFORM':'wayland'})
        self.assertEqual(result,dict(ranked=True,exact=True,launched=True))
