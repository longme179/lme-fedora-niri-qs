#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The harness's eyes: screenshot what the screen shows around our own clicks.

grim on niri does NOT capture the hardware cursor (probed 2026-11-27: three parked
positions, zero pixel change around any of them).  But the harness knows exactly
where it moved the pointer, so the eyes work differently:

    click -> park pointer there -> grim -> draw a red crosshair at the known
    point -> crop a window -> save JPG + a JSON sidecar with everything the
    probe knows about that moment.

VLM (or a human) can then answer "what was under the pointer when it was
clicked": the delegate, the gap between delegates, the fold edge, the wallpaper
behind a half-clipped entry.  That is the evidence the "clicks look wrong when
I watch it" report needs.

No VLM call happens here.  This module only captures; interpretation stays with
the caller so a run is never at the mercy of a network round trip.
"""
import json
import os
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw

WAYLAND_ENV = {"WAYLAND_DISPLAY": "wayland-1", "XDG_RUNTIME_DIR": "/run/user/1000",
               "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
CROSS_ARMS = 28          # px, each side of the centre
CROP_HALF = 220          # px, half-size of the saved crop (a 440x440 window)


class Eyes:
    """Screenshot bookkeeping for one run.  Cheap to construct, does nothing until asked."""

    def __init__(self, out_dir, width=1920, height=1080):
        self.dir = Path(out_dir) / "eyes"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.width, self.height = width, height
        self.count = 0
        self.manifest = []

    # ---- capture ---------------------------------------------------------------------------

    def look(self, at_point, tag="", note="", crop_half=CROP_HALF):
        """Screenshot the screen NOW and mark `at_point` (the pointer's last known position).

        Returns the file stem (eyes/<stem>.jpg + .json), or None when grim fails —
        the eyes never fail a run.
        """
        self.count += 1
        stamp = f"{self.count:03d}"
        stem = f"{stamp}_{tag or 'look'}"
        shot = self.dir / f"{stem}.png"
        try:
            subprocess.run(["grim", str(shot)], env={**WAYLAND_ENV, **os.environ},
                           check=True, timeout=5)
        except Exception as error:  # noqa: BLE001  (a failed look is a missing photo, not a failure)
            self.manifest.append({"n": self.count, "tag": tag, "at": round(time.time() * 1000, 3),
                                  "point": list(at_point), "error": str(error)[:200], "note": note})
            return None
        try:
            record = self._annotate(shot, stem, at_point, tag, note, crop_half)
        finally:
            shot.unlink(missing_ok=True)
        return record

    def _annotate(self, shot, stem, at_point, tag, note, crop_half):
        x, y = int(round(at_point[0])), int(round(at_point[1]))
        image = Image.open(shot).convert("RGB")
        draw = ImageDraw.Draw(image)
        # The crosshair marks the exact point the pointer was parked at; the ring
        # gives the VLM a region to talk about without counting pixels.
        draw.line((x - CROSS_ARMS, y, x - 8, y), fill=(255, 40, 40), width=3)
        draw.line((x + 8, y, x + CROSS_ARMS, y), fill=(255, 40, 40), width=3)
        draw.line((x, y - CROSS_ARMS, x, y - 8), fill=(255, 40, 40), width=3)
        draw.line((x, y + 8, x, y + CROSS_ARMS), fill=(255, 40, 40), width=3)
        draw.ellipse((x - 34, y - 34, x + 34, y + 34), outline=(255, 40, 40), width=2)
        left = max(0, x - crop_half)
        top = max(0, y - crop_half)
        right = min(image.width, x + crop_half)
        bottom = min(image.height, y + crop_half)
        crop = image.crop((left, top, right, bottom))
        jpg = self.dir / f"{stem}.jpg"
        crop.save(jpg, quality=88)
        record = {"n": self.count, "tag": tag, "at": round(time.time() * 1000, 3),
                  "point": [x, y], "crop": [left, top, right, bottom], "note": note,
                  "file": str(jpg.relative_to(self.dir.parent))}
        (self.dir / f"{stem}.json").write_text(json.dumps(record, ensure_ascii=False))
        self.manifest.append(record)
        return record

    # ---- reporting -------------------------------------------------------------------------

    def dump(self):
        """One manifest for the whole run, in capture order."""
        (self.dir / "manifest.json").write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=1))
        return self.manifest
