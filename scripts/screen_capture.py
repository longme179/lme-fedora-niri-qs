"""Private screenshot sessions, flattened PNG export and local Tesseract OCR."""
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import time
import threading
import uuid
from urllib.parse import unquote, urlsplit
from clipboard import image_type

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def png_size(path):
    if path.stat().st_size > 64 * 1024 * 1024: raise ValueError('Image exceeds 64 MiB')
    with path.open('rb') as stream: header = stream.read(24)
    if len(header) != 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b'IHDR': raise ValueError('Expected a PNG image')
    width, height = struct.unpack('>II', header[16:24])
    if not width or not height or max(width, height) > 16384 or width * height > 32_000_000: raise ValueError('Image exceeds 32 megapixels or 16384 pixels per side')
    return width, height


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


def annotation_editor(runner, editor):
    # DMS NiriService.qml (a1e6f6d6): open Satty/Swappy with an argv path.
    # Copyright (c) 2025 Avenge Media LLC; MIT notice in third_party/DankMaterialShell-LICENSE.
    if editor not in ('auto', 'satty', 'swappy'): raise ValueError('Choose Auto, Satty or Swappy')
    chosen = next((name for name in ('satty', 'swappy') if runner.available(name)), None) if editor == 'auto' else editor
    if not chosen or not runner.available(chosen):
        raise ValueError('Install swappy (Fedora) or satty, or choose an installed screenshot editor in Behavior settings')
    return chosen, runner.executable(chosen)


def annotate_image(runner, editor, value):
    chosen, binary = annotation_editor(runner, editor)
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
        if suffix == 'png': png_size(image)
        source.seek(0)
        folder = pictures_directory() / 'Screenshots'
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Editing a clipboard cache file in place would desynchronize its stored bytes and preview.
        with tempfile.NamedTemporaryFile(dir=folder, prefix='Annotation-', suffix='.' + suffix, delete=False) as output:
            target = Path(output.name)
            try: shutil.copyfileobj(source, output)
            except OSError:
                target.unlink(missing_ok=True)
                raise
    runner.spawn([binary, '-f', str(target)])
    return 'Opened ' + chosen + ' · image copy saved at ' + str(target)


class ScreenCapture:
    def __init__(self, runner):
        self.runner = runner
        self.directory = None
        self.state = {'status': 'idle', 'error': '', 'ocrText': '', 'languages': []}
        self.deadline = 0
        self.stamp = None
        self.lock = threading.RLock()

    def close(self):
        with self.lock:
            if self.directory: self.directory.cleanup(); self.directory = None
            self.state = {'status': 'idle', 'error': '', 'ocrText': '', 'languages': self.state.get('languages', [])}
            self.stamp = None

    def start(self, mode):
        if mode not in ('screen', 'area', 'window'): raise ValueError('Unknown screenshot mode')
        if self.state['status'] in ('pending', 'ready'): raise ValueError('Finish or close the current screenshot first')
        self.close()
        base = Path(os.environ.get('XDG_RUNTIME_DIR', tempfile.gettempdir())) / ('lme-captures-' + str(os.getuid()))
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        if base.is_symlink() or base.stat().st_uid != os.getuid(): raise ValueError('Unsafe screenshot runtime directory')
        base.chmod(0o700)
        self.directory = tempfile.TemporaryDirectory(prefix='capture-', dir=base)
        folder = Path(self.directory.name)
        self.state = {'status': 'pending', 'error': '', 'mode': mode, 'token': uuid.uuid4().hex,
                      'path': str(folder / 'original.png'), 'renderPath': str(folder / 'edited.png'),
                      'saveFolder': str(pictures_directory() / 'Screenshots'), 'ocrText': '', 'languages': []}
        # shortcut: niri has no cancellation event, replace this timeout when its IPC adds one.
        self.deadline = time.monotonic() + 120
        action = {'screen': 'screenshot-screen', 'area': 'screenshot', 'window': 'screenshot-window'}[mode]
        try:
            self.runner.run('niri', 'msg', 'action', action, '--path', self.state['path'])
        except (RuntimeError, OSError): self.close(); raise
        return 'Choose an area in niri' if mode == 'area' else 'Capturing screenshot…'

    def refresh(self):
        if self.state['status'] != 'pending': return self.state
        if time.monotonic() >= self.deadline:
            self.state.update(status='error', error='Capture cancelled or timed out. Try again.')
            return self.state
        path = Path(self.state['path'])
        if path.is_file():
            try:
                stat = path.stat()
                stamp = (stat.st_size, stat.st_mtime_ns)
                if self.stamp != stamp: self.stamp = stamp; return self.state
                width, height = png_size(path)
                self.state.update(status='ready', width=width, height=height, url=path.as_uri())
                path.chmod(0o600)
            except (OSError, ValueError) as exc:
                self.state.update(status='error', error=str(exc))
        return self.state

    def rendered(self, token):
        if self.state['status'] != 'ready' or token != self.state.get('token'): raise ValueError('This screenshot session has ended')
        path = Path(self.state['renderPath'])
        if path.is_symlink() or not path.is_file(): raise ValueError('Render the edited image first')
        width, height = png_size(path)
        if (width, height) != (self.state['width'], self.state['height']): raise ValueError('Edited image dimensions do not match')
        path.chmod(0o600)
        return path

    def export(self, token, operation, folder=None):
        with self.lock:
            image = self.rendered(token)
            source = image.open('rb')
        try: return self._export(source, token, operation, folder)
        finally: source.close()

    def annotate(self, token, editor, folder):
        chosen, binary = annotation_editor(self.runner, editor)
        # Persist the flattened image before launching; closing the studio deletes runtime files.
        with self.lock:
            with self.rendered(token).open('rb') as source: self._export(source,token,'save',folder)
            path=self.state['savedPath']
        self.runner.spawn([binary,'-f',path])
        return 'Opened '+chosen+' · edited PNG saved at '+path

    def _export(self, source, token, operation, folder):
        if operation == 'copy':
            # wl-copy's clipboard owner forks; captured pipes would stay open in that child.
            try: completed = subprocess.run([self.runner.executable('wl-copy'), '--type', 'image/png'], stdin=source, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except subprocess.TimeoutExpired as exc: raise ValueError('Clipboard copy timed out') from exc
            if completed.returncode: raise ValueError('Could not copy the edited screenshot')
            return 'Edited screenshot copied'
        if operation != 'save': raise ValueError('Unknown screenshot export')
        if not isinstance(folder, str) or not folder.strip() or len(folder) > 4096 or '\x00' in folder: raise ValueError('Choose a screenshot folder')
        destination = Path(folder).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        name = time.strftime('Screenshot-%Y-%m-%d-%H%M%S-') + uuid.uuid4().hex[:8] + '.png'
        target = destination / name
        # Exclusive creation protects existing files even when saving twice in one second.
        with target.open('xb') as output:
            try:
                os.fchmod(output.fileno(), 0o600)
                shutil.copyfileobj(source, output)
            except OSError:
                target.unlink(missing_ok=True)
                raise
        if self.state.get('token') == token: self.state['savedPath'] = str(target)
        return 'Saved ' + str(target)

    def languages(self):
        output = self.runner.run('tesseract', '--list-langs', timeout=5)
        languages = [line.strip() for line in output.splitlines() if re.fullmatch(r'[A-Za-z0-9_]{2,32}', line.strip()) and line.strip() != 'osd']
        self.state['languages'] = languages
        return languages

    def ocr(self, token, language):
        with self.lock: image = self.rendered(token)
        languages = self.languages()
        if not isinstance(language, str) or not language or not all(part in languages for part in language.split('+')): raise ValueError('Choose installed OCR languages')
        text = self.runner.run('tesseract', str(image), 'stdout', '-l', language, '--psm', '3', timeout=45)
        if len(text) > 262144: raise ValueError('Recognized text exceeds 256 KiB')
        return text.strip()
