"""Recording preflight captures options before delegating to the existing worker.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: recording; Phase 3 graph).
"""
# REL: qml/panels/RecorderWidget.qml – ActionSpec dispatch via scripts/backend_actions.py::ActionRegistry; scripts/desktop_backend.py host.
from dataclasses import dataclass
from typing import Callable
from backend_actions import ActionSpec, PreparedWork


@dataclass(frozen=True)
class RecordingCapabilities:
    preferences: Callable
    pending: Callable
    saver: Callable
    niri: Callable
    guard: Callable
    start: Callable


def provide(cap):
    def prepare(request):
        if 'batterySaver' in cap.pending() or cap.saver()['busy']:
            raise ValueError('Wait for Battery saver to finish before recording')
        if not cap.preferences()['recordingEnabled']: raise ValueError('Screen recording is disabled')
        niri = cap.niri()
        outputs = {w.get('output') for w in niri['workspaces'] if w.get('output')}
        output = request.get('output')
        if not niri['available'] or not isinstance(output,str) or output not in outputs:
            raise ValueError('Choose a connected niri output')
        prefs = dict(cap.preferences())
        def record():
            with cap.guard(allow_active=True):
                return cap.start(prefs['recordingFolder'],request.get('mode'),output,
                    request.get('audio',prefs['recordingAudio']),prefs['recordingEncoder'],
                    prefs['recordingFormat'],prefs['recordingCodec'],prefs['recordingFps'],prefs['recordingBitrate'])
        return PreparedWork(record)
    return ((ActionSpec('recordStart',{'shell'},lambda request:None,lambda request:None,
        execution='worker',complete=lambda value:None,prepare=prepare),),lambda:{})
