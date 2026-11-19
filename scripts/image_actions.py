"""Open a clipboard image with the user's default viewer via a private copy.

Callers: scripts/desktop_backend.py provider composition; qml/panels/ClipboardPanel.qml through the imageOpen action.
Touches: XDG pictures/Screenshots (Annotation-* copy, mode 0600), xdg-open.
INVARIANT: only local, user-owned images are copied; the source file is never modified.
REL: scripts/command_runner.py::spawn – detached argv helper; scripts/content_types.py – image signature.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Callable
from urllib.parse import unquote, urlsplit
from backend_actions import ActionSpec, PreparedWork
from content_types import image_type


def pictures_directory():
    home = Path.home()
    config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config')) / 'user-dirs.dirs'
    try:
        match = re.search(r'^XDG_PICTURES_DIR="([^"\n]+)"', config.read_text(), re.M)
        if match:
            value = match[1].replace('$HOME', str(home))
            if Path(value).is_absolute() and '\x00' not in value: return Path(value)
    except OSError: pass
    return home / 'Pictures'


def open_image(runner, value):
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError('Choose a local image')
    url = urlsplit(value)
    if url.scheme:
        if url.scheme != 'file' or url.netloc not in ('', 'localhost') or url.query or url.fragment:
            raise ValueError('Choose a local image')
        value = unquote(url.path)
    if not Path(value).is_absolute() or any(ord(c) < 32 for c in value):
        raise ValueError('Choose a local image')
    image = Path(value).resolve(strict=True)
    if not image.is_file() or image.stat().st_uid != os.getuid(): raise ValueError('Choose an image owned by your user')
    if image.stat().st_size > 64 * 1024 * 1024: raise ValueError('Image exceeds 64 MiB')
    with image.open('rb') as source:
        suffix = image_type(source.read(24))[1]
        source.seek(0)
        folder = pictures_directory() / 'Screenshots'
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        # The viewer needs a stable path outside the clipboard cache; keep a private copy.
        with tempfile.NamedTemporaryFile(dir=folder, prefix='Annotation-', suffix='.' + suffix, delete=False) as output:
            target = Path(output.name)
            try: shutil.copyfileobj(source, output)
            except OSError:
                target.unlink(missing_ok=True)
                raise
    runner.spawn([runner.executable('xdg-open'), str(target)])
    return 'Opened image · copy saved at ' + str(target)


@dataclass(frozen=True)
class ImageCapabilities:
    open: Callable


def provide_image(cap):
    def prepare(request):
        return PreparedWork(lambda: cap.open(request.get('path')))
    return ((ActionSpec('imageOpen', {'shell'}, lambda request: None, lambda request: None,
        execution='worker', complete=lambda value: None, prepare=prepare),), lambda: {})
