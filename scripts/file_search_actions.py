"""Replacing search retains its existing cancel Event and single Future owner."""
from dataclasses import dataclass
from typing import Callable
from backend_actions import ActionSpec, PreparedWork


@dataclass(frozen=True)
class SearchCapabilities:
    preferences: Callable
    replace: Callable
    install: Callable
    search: Callable


def provide(cap):
    def prepare(request):
        if not cap.preferences()['fileSearchEnabled']: raise ValueError('File search is disabled')
        query=request.get('query')
        if not isinstance(query,str) or not 2<=len(query.strip())<=160:
            raise ValueError('File search needs 2–160 characters')
        cancel=cap.replace()
        folders=list(cap.preferences()['fileSearchRoots'])
        cap.install({'query':query,'entries':[],'truncated':False})
        return PreparedWork(lambda:cap.search(query,folders,cancel))
    def complete(value):
        if not isinstance(value,Exception): cap.install(value)
    return ((ActionSpec('fileSearch',{'shell'},lambda request:None,lambda request:None,
        execution='worker',complete=complete,presentation='File search completed',prepare=prepare),),lambda:{})
