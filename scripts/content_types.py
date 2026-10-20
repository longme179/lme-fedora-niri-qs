"""Shared text byte bound and image signature recognition."""
from __future__ import annotations

MAX_TEXT = 1024 * 1024


def image_type(data: bytes) -> tuple[str, str]:
    for prefix, mime, suffix in [(b"\x89PNG\r\n\x1a\n", "image/png", "png"),
                                 (b"\xff\xd8\xff", "image/jpeg", "jpg"),
                                 (b"GIF87a", "image/gif", "gif"), (b"GIF89a", "image/gif", "gif"),
                                 (b"BM", "image/bmp", "bmp")]:
        if data.startswith(prefix): return mime, suffix
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP": return "image/webp", "webp"
    raise ValueError("Unsupported clipboard image format")
