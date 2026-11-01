"""Observe actual AudioMixer only in a copied checkout/private Wayland session."""
from pathlib import Path
from clipboard_slice_fixture import World

OBSERVE = '''
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
                result: ShellState.lastResult, progress: root.sliceProgress});
        }
        function open(): void { ShellState.selectControlTab("audio"); ShellState.togglePanel("control"); }
        function send(action: string, request: string): void { ShellState.run(action,JSON.parse(request)); }
        function select(name: string, index: int): bool {
            const field=root.sliceFind(root.sliceSurface,name);
            if(!field || !field.enabled) return false;
            field.currentIndex=index; field.activated(index); return true;
        }
    }
'''


class AudioWorld(World):
    def __init__(self, directory):
        super().__init__(Path(directory))
        path=self.root/'shell.qml'
        path.write_text(path.read_text().replace('    id: root\n','    id: root\n'+OBSERVE,1))
