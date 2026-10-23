"""Local content handlers; protocol and persistence policy remain with the host."""
from dataclasses import dataclass
from typing import Callable

from backend_actions import ActionSpec
from content_types import MAX_TEXT
from desktop_features import calculate
from storage import write_json


@dataclass(frozen=True)
class LocalContentCapabilities:
    run: Callable
    prepare_notes: Callable
    notifications: Callable
    save_history: Callable
    history_path: Callable
    demo_calculator: Callable


def provide(capabilities):
    def copy_text(request):
        text = request.get('text')
        if not isinstance(text, str) or len(text.encode()) > MAX_TEXT:
            raise ValueError('Invalid copy text')
        capabilities.run('wl-copy', '--type', 'text/plain;charset=utf-8', input=text)
        return 'Copied'

    def copy_demo(request):
        if not isinstance(request.get('text'), str): raise ValueError('Text is required')

    def notifications(request):
        if not isinstance(request.get('entries'), list): raise ValueError('Invalid notification history')
        history = capabilities.notifications(request['entries'])
        write_json(capabilities.history_path(), history)
        capabilities.save_history(history)
        return ''

    def calculate_demo(request):
        capabilities.demo_calculator({'query': request.get('query'), 'result': calculate(request.get('query')), 'error': ''})

    no_op = lambda request: None
    handlers = [('calculate', lambda request: calculate(request.get('query')), calculate_demo),
                ('copyText', copy_text, copy_demo),
                ('notesInit', lambda request: capabilities.prepare_notes(), no_op),
                ('notificationSave', notifications, no_op)]
    return tuple(ActionSpec(name, {'shell'}, live, demo) for name, live, demo in handlers), lambda: {}
