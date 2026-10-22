"""Observe existing services and private D-Bus in copied feature checkouts."""
from contextlib import contextmanager
import json
import subprocess
from stateful_feature_fixture import StatefulWorld, Probe as StatefulProbe, ROOT, converted
OBSERVE='''
    IpcHandler {
        target: "capabilityFeatures"
        function state(): string {
            return JSON.stringify({ready:ShellState.backendReady && FeatureCatalog.ready && Theme.ready,
                progress:root.sliceProgress,panelOpen:ShellState.panelOpen,notificationsOpen:ShellState.notificationsOpen,
                history:Notifications.history,popups:Notifications.popups,unread:Notifications.unreadCount,
                preferences:ShellState.preferences,pages:SettingsRegistry.pages.map(p=>p.key),bars:BarRegistry.modules.map(p=>p.id),
                tabs:ControlRegistry.tabs.map(t=>({id:t.id,index:t.legacyIndex})),page:root.statefulView(root.sliceSurface)?.page || ShellState.settingsPage,
                about:!!root.sliceFind(root.sliceSurface,"aboutShellName"),windows:(DesktopState.fixtureWindows || []).length,
                ambient:(DesktopState.fixtureAmbient || []).length,lastResult:ShellState.lastResult});
        }
        function mute(app: string, value: bool): void { Notifications.muteApp(app,value); }
        function dnd(value: int): void { Notifications.setDnd(value); }
        function local(): void { Notifications.local("Withdrawn local","Must not persist"); }
    }
'''
class Probe(StatefulProbe):
    def call(self, method, *args, target='capabilityFeatures'):
        return super().call(method,*args,target=target)
    def owns_server(self):
        return subprocess.check_output(['gdbus','call','--session','--dest','org.freedesktop.DBus','--object-path','/org/freedesktop/DBus',
            '--method','org.freedesktop.DBus.NameHasOwner','org.freedesktop.Notifications'],env=self.env,text=True,timeout=4).strip()=='(true,)'
    def notify(self, summary):
        reply=subprocess.check_output(['busctl','--user','call','org.freedesktop.Notifications','/org/freedesktop/Notifications',
            'org.freedesktop.Notifications','Notify','susssasa{sv}i','ContractApp','0','',summary,'Literal <body>','0','0','0'],
            env=self.env,text=True,timeout=4)
        return int(reply.split()[1])
class FeatureWorld(StatefulWorld):
    def __init__(self,directory):
        super().__init__(directory)
        for name in ('shell.qml','qml/settings/SettingsApplication.qml'):
            path=self.root/name;path.write_text(path.read_text().replace('    id: root\n','    id: root\n'+OBSERVE,1))
    @contextmanager
    def launch(self,mode='demo',page='appearance'):
        with super().launch(mode,page) as old:
            probe=Probe(old.entry,old.env,old.process,old.log);probe.wait(lambda s:s['ready']);yield probe
