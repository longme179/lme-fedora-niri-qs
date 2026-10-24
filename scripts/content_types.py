"""Shared text/image formats and normalized image paths."""
from __future__ import annotations
from pathlib import Path

MAX_TEXT = 1024 * 1024
EXTENSIONS = {'.png','.jpg','.jpeg','.webp','.gif','.bmp'}


def image_type(data: bytes) -> tuple[str, str]:
    for prefix, mime, suffix in [(b"\x89PNG\r\n\x1a\n", "image/png", "png"),
                                 (b"\xff\xd8\xff", "image/jpeg", "jpg"),
                                 (b"GIF87a", "image/gif", "gif"), (b"GIF89a", "image/gif", "gif"),
                                 (b"BM", "image/bmp", "bmp")]:
        if data.startswith(prefix): return mime, suffix
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP": return "image/webp", "webp"
    raise ValueError("Unsupported clipboard image format")


def image_path(value):
    if not isinstance(value,str) or not value or len(value)>4096 or any(ord(c)<32 for c in value):
        raise ValueError('Choose a wallpaper image path')
    path=Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError('Choose an absolute PNG, JPEG, WebP, GIF, or BMP path')
    try: path=path.resolve()
    except RuntimeError as exc: raise ValueError('Wallpaper path contains a symlink loop') from exc
    text=str(path)
    if path.suffix.lower() not in EXTENSIONS or len(text)>4096 or any(ord(c)<32 or 0xd800<=ord(c)<=0xdfff for c in text):
        raise ValueError('Choose an absolute PNG, JPEG, WebP, GIF, or BMP path')
    return text
