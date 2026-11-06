"""Glass backdrop snapshot cache: live awww state, bound, cleanup, glass-off skip."""
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from glass_snapshot import GlassSnapshots, color6, flat_png, query_displays
from test_backend import Fixture, FakeRunner


def png_pixel(data):
    """Decode a 1x1 RGB PNG written by flat_png and return (r, g, b)."""
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    pos = 8
    idat = b''
    while pos < len(data):
        (length,) = struct.unpack('>I', data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if kind == b'IDAT':
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    assert raw[:1] == b'\x00' and len(raw) == 4
    return tuple(raw[1:4])


class QueryCase(unittest.TestCase):
    def test_text_and_json_forms_and_color_normalization(self):
        text = ('awww-daemon: eDP-1: 1920x1080, scale: 1, currently displaying: image: /a b.png\n'
                'HDMI-A-1: 1920x1080, scale: 1, currently displaying: color: 000000')
        self.assertEqual(query_displays(text), {'eDP-1': ('image', '/a b.png'), 'HDMI-A-1': ('color', '000000')})
        self.assertEqual(query_displays('eDP-1: 1920x1080, currently displaying: color: 112233ff'),
                         {'eDP-1': ('color', '112233')})
        self.assertEqual(query_displays('eDP-1: 1920x1080, currently displaying: color: #224455'),
                         {'eDP-1': ('color', '224455')})
        import json
        payload = json.dumps({'': [{'name': 'eDP-1', 'displaying': {'color': '335577aa'}},
                                   {'name': 'HDMI-A-1', 'displaying': {'image': '/x.png'}}]})
        self.assertEqual(query_displays(payload), {'eDP-1': ('color', '335577'), 'HDMI-A-1': ('image', '/x.png')})
        # Anything unrecognized yields no displays so callers use the direct-file path.
        self.assertEqual(query_displays('some new awww format v2'), {})
        self.assertEqual(query_displays('{not json'), {})
        self.assertEqual(query_displays(''), {})
        self.assertEqual(color6('0xAABBCC'), 'aabbcc')

    def test_flat_png_carries_the_exact_color(self):
        self.assertEqual(png_pixel(flat_png('112233')), (0x11, 0x22, 0x33))
        self.assertEqual(png_pixel(flat_png('000000')), (0, 0, 0))
        self.assertEqual(png_pixel(flat_png('FF00AA')), (255, 0, 170))
        with self.assertRaises(ValueError):
            flat_png('not-a-color')


class SnapshotCase(unittest.TestCase):
    def test_image_copy_color_tile_revision_and_prune(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / 'cache'
            source = Path(directory) / 'wallpaper.png'
            source.write_bytes(b'image-bytes')
            snap = GlassSnapshots(directory=cache)
            live = {'eDP-1', 'HDMI-A-1'}
            displays = {'eDP-1': ('image', str(source)), 'HDMI-A-1': ('color', '112233')}
            state = snap.refresh(live, displays, True)
            self.assertEqual(state['outputs']['eDP-1']['rev'], 1)
            self.assertEqual(state['outputs']['HDMI-A-1']['rev'], 1)
            self.assertTrue(state['outputs']['eDP-1']['url'].endswith('eDP-1.png'))
            self.assertEqual((cache / 'eDP-1.png').read_bytes(), b'image-bytes')
            self.assertEqual(png_pixel((cache / 'HDMI-A-1.png').read_bytes()), (0x11, 0x22, 0x33))
            # Identical state keeps the revision (no rewrite, shared decode stable).
            again = snap.refresh(live, displays, True)
            self.assertEqual(again['outputs']['eDP-1']['rev'], 1)
            # A new color bumps only that output's revision.
            displays['HDMI-A-1'] = ('color', '445566')
            bumped = snap.refresh(live, displays, True)
            self.assertEqual(bumped['outputs']['HDMI-A-1']['rev'], 2)
            self.assertEqual(bumped['outputs']['eDP-1']['rev'], 1)
            self.assertEqual(png_pixel((cache / 'HDMI-A-1.png').read_bytes()), (0x44, 0x55, 0x66))
            # Removing an output cleans its file.
            pruned = snap.refresh({'eDP-1'}, {'eDP-1': ('image', str(source))}, True)
            self.assertEqual(set(pruned['outputs']), {'eDP-1'})
            self.assertFalse((cache / 'HDMI-A-1.png').exists())
            # Stale files from an earlier session are cleaned too.
            (cache / 'DP-9.png').write_bytes(b'stale')
            snap.refresh({'eDP-1'}, {'eDP-1': ('image', str(source))}, True)
            self.assertFalse((cache / 'DP-9.png').exists())

    def test_glass_off_skips_all_writes_and_missing_source_keeps_old(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / 'cache'
            snap = GlassSnapshots(directory=cache)
            source = Path(directory) / 'wallpaper.png'
            source.write_bytes(b'v1')
            snap.refresh({'eDP-1'}, {'eDP-1': ('image', str(source))}, True)
            before = (cache / 'eDP-1.png').read_bytes()
            # Glass off: no directory work, no revision change.
            skipped = snap.refresh({'eDP-1'}, {'eDP-1': ('color', 'ffffff')}, False)
            self.assertEqual(skipped['outputs']['eDP-1']['rev'], 1)
            self.assertEqual((cache / 'eDP-1.png').read_bytes(), before)
            other = GlassSnapshots(directory=cache / 'nested')
            # Disabled refresh must not even create the directory.
            other.refresh({'eDP-1'}, {'eDP-1': ('color', '000000')}, False)
            self.assertFalse((cache / 'nested').exists())
            # A missing source file keeps the previous snapshot.
            source.write_bytes(b'v2')
            missing = snap.refresh({'eDP-1'}, {'eDP-1': ('image', str(source) + '.gone')}, True)
            self.assertEqual((cache / 'eDP-1.png').read_bytes(), before)

    def test_size_bound_evicts_oldest_and_traversal_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / 'cache'
            snap = GlassSnapshots(directory=cache, max_total=1, max_files=2)
            for name in ('eDP-1', 'HDMI-A-1', 'DP-1', 'DP-2'):
                snap.refresh({name}, {name: ('color', '112233')}, True)
            # Bound is best-effort LRU; at most max_files snapshots survive.
            files = list(cache.glob('*.png'))
            self.assertLessEqual(len(files), 2)
            self.assertLessEqual(sum(p.stat().st_size for p in files), 1024)
            # Path traversal output names never touch the filesystem.
            state = snap.refresh({'../evil'}, {'../evil': ('color', '112233')}, True)
            self.assertEqual(state, {'outputs': state['outputs']})  # no crash, no traversal file
            self.assertFalse((Path(directory) / 'evil.png').exists())


class WallpaperIntegrationCase(Fixture, unittest.TestCase):
    def test_wallpaper_change_and_transition_completion_invalidate(self):
        cache = self.root / 'cache'
        with patch.dict(os.environ, {'XDG_CACHE_HOME': str(cache)}):
            query_v1 = 'awww-daemon: eDP-1: 1920x1080, scale: 1, currently displaying: image: /old.png'
            live = self.make_backend(FakeRunner({('awww', 'query'): query_v1}, available={'awww'}))
            self.addCleanup(live.feature_executor.shutdown, wait=True, cancel_futures=True)
            self.addCleanup(live.wallpapers.close)
            self.preferences.set('surfaceStyle', 'liquid')
            live.wallpapers.power_saving = False
            old = str(self.put('old.png', 'old'))
            new = str(self.put('new.png', 'new'))
            live.runner.responses[('awww', 'query')] = f'awww-daemon: eDP-1: 1920x1080, scale: 1, currently displaying: image: {old}'
            live.wallpapers._glass_refresh()
            self.assertEqual(live.wallpapers.glass_snapshot()['outputs']['eDP-1']['rev'], 1)
            # Apply switches the daemon image; the background job's inline
            # refresh plus the next-cycle transition-completion refresh bump it.
            live.wallpapers.apply(new)
            self.assertEqual(live.wallpapers.glass_snapshot()['outputs']['eDP-1']['rev'], 1)
            live.runner.responses[('awww', 'query')] = f'awww-daemon: eDP-1: 1920x1080, scale: 1, currently displaying: image: {new}'
            live.wallpapers._glass_refresh()
            self.assertEqual(live.wallpapers.glass_snapshot()['outputs']['eDP-1']['rev'], 2)
            # Backend snapshot carries the same revision for the QML binding.
            self.assertEqual(live.feature_snapshot()['glass']['outputs']['eDP-1']['rev'], 2)
            # The apply left a transition-completion refresh pending; the next
            # cycle drains it and then the scheduler goes quiet.
            job = live.wallpapers.due({'eDP-1'}, now=0)
            self.assertIsNotNone(job)
            self.assertEqual(job(), '')
            self.assertIsNone(live.wallpapers.due({'eDP-1'}, now=1))

    def test_glass_off_skips_snapshots_and_malformed_query_falls_back(self):
        cache = self.root / 'cache'
        with patch.dict(os.environ, {'XDG_CACHE_HOME': str(cache)}):
            query = 'awww-daemon: eDP-1: 1920x1080, scale: 1, currently displaying: color: 112233'
            live = self.make_backend(FakeRunner({('awww', 'query'): query}, available={'awww'}))
            self.addCleanup(live.feature_executor.shutdown, wait=True, cancel_futures=True)
            self.addCleanup(live.wallpapers.close)
            # Default surfaceStyle is smoked (glass off): refresh is a no-op.
            live.wallpapers._glass_refresh()
            self.assertEqual(live.wallpapers.glass_snapshot(), {'outputs': {}})
            self.assertFalse((cache / 'lme-shell/glass').exists())
            self.preferences.set('surfaceStyle', 'liquid')
            live.wallpapers.power_saving = True
            live.wallpapers._glass_refresh()
            self.assertEqual(live.wallpapers.glass_snapshot(), {'outputs': {}})
            live.wallpapers.power_saving = False
            live.wallpapers._glass_refresh()
            self.assertEqual(live.wallpapers.glass_snapshot()['outputs']['eDP-1']['kind'], 'color')
            # An unrecognized awww surface leaves the snapshot untouched.
            live.runner.responses[('awww', 'query')] = 'awww v99: entirely new syntax'
            rev = live.wallpapers.glass_snapshot()['outputs']['eDP-1']['rev']
            live.wallpapers._glass_refresh()
            self.assertEqual(live.wallpapers.glass_snapshot()['outputs']['eDP-1']['rev'], rev)


if __name__ == '__main__':
    unittest.main()
