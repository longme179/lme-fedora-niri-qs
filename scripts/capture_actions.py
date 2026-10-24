"""Image annotation captures the editor before queueing; capture owns its session."""
from dataclasses import dataclass
from typing import Callable
from backend_actions import ActionSpec, PreparedWork


@dataclass(frozen=True)
class ImageCapabilities:
    preferences: Callable
    annotate: Callable


def provide_image(cap):
    def prepare(request):
        editor=cap.preferences()['captureEditor']
        return PreparedWork(lambda:cap.annotate(editor,request.get('path')))
    return ((ActionSpec('imageAnnotate',{'shell'},lambda request:None,lambda request:None,
        execution='worker',complete=lambda value:None,prepare=prepare),),lambda:{})
