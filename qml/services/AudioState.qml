// Role: AudioState.qml (audio layer, fan-in 2) — native default sink/source state (QML-first plan Q1).
// REL: Quickshell.Services.Pipewire::Pipewire – defaultAudioSink/defaultAudioSource; PwNode.audio.muted/.volume.
// INVARIANT: section shapes mirror scripts/desktop_backend.py::audio() exactly (tests/test_native_state.py).
// Demo fixtures live in NativeState.qml; this singleton is pure native state.
pragma Singleton
import QtQuick
import Quickshell.Services.Pipewire

QtObject {
    id: root

    // Bind the default nodes: PwNode.audio volume/muted are invalid on unbound nodes.
    property PwObjectTracker tracker: PwObjectTracker {
        objects: [Pipewire.defaultAudioSink, Pipewire.defaultAudioSource]
    }

    readonly property var state: section(Pipewire.defaultAudioSink)
    readonly property var microphone: section(Pipewire.defaultAudioSource)

    // Fired on real volume/mute changes (native, event-driven) so the shell OSD no
    // longer waits for the backend poll; ShellState connects to this signal.
    signal osd(int volume, bool muted)
    property var previous: null
    onStateChanged: {
        if (previous && previous.available && state.available
                && (previous.volume !== state.volume || previous.muted !== state.muted))
            osd(state.volume, state.muted);
        previous = state;
    }

    function section(node) {
        if (!node || !node.audio || !node.ready) return {available: false, volume: null, muted: false};
        return {available: true, volume: Math.round(node.audio.volume * 100), muted: node.audio.muted};
    }
}
