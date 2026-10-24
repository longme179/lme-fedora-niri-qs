"""Synchronous display entry contracts; the controller/watchdog retain ownership."""
from dataclasses import dataclass
import time
from typing import Callable

from backend_actions import ActionSpec
from display_control import validate_layout


@dataclass(frozen=True)
class PreviewCapabilities:
    current: Callable
    install: Callable
    snapshot: Callable
    start: Callable
    decide: Callable
    saver_pending: Callable
    guard: Callable
    save: Callable
    demo_save: Callable


def provide(cap):
    def refresh(request):
        cap.install(cap.snapshot())
        return 'Displays refreshed'

    def apply(request):
        if cap.saver_pending(): raise ValueError('Wait for Battery saver to finish')
        with cap.guard(): cap.start(request.get('layout'))
        cap.install(cap.snapshot())
        return 'Display preview requested; confirm within 20 seconds'

    def decide(request, keep):
        layout = cap.decide(request.get('token'), keep)
        if keep: cap.save(layout)
        cap.install(cap.snapshot())
        return 'Display layout saved' if keep else 'Restoring displays'

    def demo_refresh(request):
        if not cap.current()['outputs']:
            cap.install({'outputs': [{'name': 'eDP-1', 'description': 'Lenovo laptop display', 'enabled': True,
                'modes': [{'width': 1920, 'height': 1080, 'refresh': hz * 1000, 'label': f'1920 × 1080 · {hz} Hz'} for hz in (60, 120)],
                'current': {'width': 1920, 'height': 1080, 'refresh': 120000}, 'scale': 1, 'x': 0, 'y': 0, 'width': 1920, 'height': 1080}], 'preview': {}})
        preview = cap.current()['preview']
        if preview.get('status') == 'pending' and time.time() >= preview['deadline']:
            preview['status'] = 'reverted'

    def demo_apply(request):
        layout = validate_layout(request.get('layout'), cap.current()['outputs'])
        cap.current()['preview'] = {'token': 'demo', 'status': 'pending', 'deadline': time.time() + 20, 'layout': layout}

    def demo_decide(request, keep):
        preview = cap.current()['preview']
        if preview.get('status') != 'pending': raise ValueError('No display preview')
        if keep: cap.demo_save(preview['layout'])
        preview['status'] = 'confirmed' if keep else 'reverted'

    specs = [ActionSpec('displayRefresh', {'shell', 'settings'}, refresh, demo_refresh),
        ActionSpec('displayApply', {'shell', 'settings'}, apply, demo_apply)]
    for action, keep in (('displayConfirm', True), ('displayRevert', False)):
        specs.append(ActionSpec(action, {'shell', 'settings'},
            lambda request, keep=keep: decide(request, keep), lambda request, keep=keep: demo_decide(request, keep)))
    return tuple(specs), lambda: {}


@dataclass(frozen=True)
class PlatformCapabilities:
    refresh: Callable
    install: Callable


def provide_platform(cap):
    def refresh(request):
        cap.install(cap.refresh())
        return 'Compositor version checked'
    return ((ActionSpec('platformRefresh', {'shell', 'settings'}, refresh, lambda request: None),), lambda: {})
