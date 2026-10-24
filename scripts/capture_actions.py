"""Capture entry and worker contracts; the existing controller owns each session."""
from dataclasses import dataclass
import time
from typing import Callable
from backend_actions import ActionSpec, PreparedWork


@dataclass(frozen=True)
class ControlCapabilities:
    start: Callable
    close: Callable
    languages: Callable
    current: Callable


def provide_controls(cap):
    def start(mode):
        # niri owns capture; let the dismissed panel finish its surface teardown.
        time.sleep(.2)
        return cap.start(mode)
    def close(request):
        cap.close()
        return 'Screenshot closed'
    def languages(request):
        cap.languages()
        return 'OCR languages refreshed'
    def demo_languages(request):
        cap.current()['languages'] = ['eng', 'vie']
    specs = [ActionSpec(action, {'shell'}, lambda request, mode=mode: start(mode), lambda request: None)
        for action, mode in (('screenshot', 'screen'), ('screenshotArea', 'area'), ('screenshotWindow', 'window'))]
    specs.extend((ActionSpec('captureClose', {'shell'}, close, lambda request: cap.close()),
        ActionSpec('captureLanguages', {'shell'}, languages, demo_languages)))
    return tuple(specs), lambda: {}


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


@dataclass(frozen=True)
class LeaseCapabilities:
    preferences: Callable
    current: Callable
    export: Callable
    annotate: Callable
    ocr: Callable
    install_text: Callable


def provide_sessions(cap):
    def prepare(action, request):
        token=request.get('token')
        if type(token) is not str: raise ValueError('Missing screenshot session')
        if action=='captureExport':
            operation=lambda:cap.export(request['token'],request.get('operation'),request.get('folder'))
        elif action=='captureAnnotate':
            if token!=cap.current().get('token'): raise ValueError('This screenshot session has ended')
            editor=cap.preferences()['captureEditor']
            operation=lambda:cap.annotate(token,editor,request.get('folder'))
        else:
            language=request.get('language')
            operation=lambda:(token,cap.ocr(token,language))
        return PreparedWork(operation,{'capture_token':token})
    def complete(value):
        if isinstance(value,Exception): return
        token,content=value
        if cap.current().get('token')==token: cap.install_text(content)
    def demo(action, request):
        if action=='captureExport' and request.get('operation') not in ('copy','save'):
            raise ValueError('Unknown screenshot export')
        if action=='captureAnnotate' and request.get('token')!=cap.current().get('token'):
            raise ValueError('This screenshot session has ended')
        if action=='captureOcr': cap.install_text(cap.preferences()['shellName']+'\nLocal screenshot text recognition')
    specs=[]
    for action in ('captureExport','captureAnnotate','captureOcr'):
        specs.append(ActionSpec(action,{'shell'},lambda request:None,
            lambda request,action=action:demo(action,request),execution='worker',
            complete=complete if action=='captureOcr' else lambda value:None,
            presentation=(lambda value:'Text recognized' if value[1] else 'No text found. Try a tighter capture or another OCR language.') if action=='captureOcr' else None,
            prepare=lambda request,action=action:prepare(action,request)))
    return tuple(specs),lambda:{}
