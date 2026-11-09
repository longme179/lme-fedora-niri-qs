"""Observe actual AudioMixer only in a copied checkout/private Wayland session.

Contract/helper: test infrastructure for audio_ui_fixture.py. Related (see docs/WORKSPACE_MAP.md/config/architecture.json)) under test inferred from imports.
"""
from pathlib import Path
import json
from clipboard_slice_fixture import World
from audio_device_fixture import documents

OBSERVE = '''
    property var audioObservedResult: ({})
    Connections {
        target: ShellState
        function onLastResultChanged() {
            const result = ShellState.lastResult;
            if (["audioDevicesRefresh", "audioPort", "audioProfile", "audioRoute"].includes(result.action))
                root.audioObservedResult = Object.assign({}, result);
        }
    }
    IpcHandler {
        target: "audioHeadset"
        function state(): string {
            const names = ["Audio devices & mixer", "Output device", "Input device", "Applications"];
            const fields = ["audioRefresh", "audioRoute", "audioProfile", "audioPort"];
            return JSON.stringify({ready: ShellState.backendReady && FeatureCatalog.ready && Theme.ready,
                open: ShellState.controlOpen, heading: !!root.sliceFind(root.sliceSurface,names[0]),
                labels: names.filter(name => !!root.sliceFind(root.sliceSurface,name)),
                fields: fields.filter(name => !!root.sliceFind(root.sliceSurface,name)),
                audio: ShellState.snapshot.audioDevices || {}, pending: ShellState.pendingActions,
                result: root.audioObservedResult.action ? root.audioObservedResult : ShellState.lastResult, progress: root.sliceProgress});
        }
        function open(): void { ShellState.selectControlTab("audio"); ShellState.togglePanel("control"); }
        function send(action: string, request: string): void { ShellState.run(action,JSON.parse(request)); }
        function select(name: string, index: int): bool {
            const field=root.sliceFind(root.sliceSurface,name);
            if(!field || !field.enabled) return false;
            field.currentIndex=index; field.activated(index); return true;
        }
        function choice(name: string): string {
            const field=root.sliceFind(root.sliceSurface,name);
            return JSON.stringify(field?{index:field.currentIndex,text:field.displayText,
                enabled:field.enabled,disabled:field.disabledIndices,popup:field.popup.visible}:null);
        }
        function popup(name: string): bool {
            const field=root.sliceFind(root.sliceSurface,name);
            if(!field || !field.enabled) return false;field.popup.open();return true;
        }
        function cloneAudio(): void {
            ShellState.snapshot=Object.assign({},ShellState.snapshot,{audioDevices:JSON.parse(JSON.stringify(ShellState.snapshot.audioDevices))});
        }
    }
'''


class AudioWorld(World):
    def __init__(self, directory):
        super().__init__(Path(directory))
        path=self.root/'shell.qml'
        path.write_text(path.read_text().replace('    id: root\n','    id: root\n'+OBSERVE,1))

    def fake_audio(self):
        self.audio_file=self.home/'audio.json';self.audio_calls=self.home/'audio-calls.jsonl'
        self.audio_file.write_text(json.dumps(dict(documents=documents(),apply=True)))
        self.audio_file.chmod(0o600)
        self.env.update(AUDIO_FIXTURE=str(self.audio_file),AUDIO_CALLS=str(self.audio_calls))
        path=self.home/'bin/pactl'
        path.write_text('''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
path=Path(os.environ['AUDIO_FIXTURE']);state=json.loads(path.read_text());d=state['documents'];a=sys.argv[1:]
with Path(os.environ['AUDIO_CALLS']).open('a') as log:log.write(json.dumps(a)+'\\n')
if a[0]=='--format=json':print(json.dumps(d['info' if a[1]=='info' else a[2]]))
elif state['apply']:
 command,index,value=a[1:];index=int(index)
 if command=='set-card-profile':next(x for x in d['cards'] if x['index']==index)['active_profile']=value
 elif command in ('set-sink-port','set-source-port'):next(x for x in d['sinks' if command=='set-sink-port' else 'sources'] if x['index']==index)['active_port']=value
 elif command=='move-sink-input':next(x for x in d['sink-inputs'] if x['index']==index)['sink']=int(value)
 path.write_text(json.dumps(state))
''');path.chmod(0o700)
