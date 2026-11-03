"""A malformed or failing command costs one result, never the backend loop."""
from contextlib import redirect_stderr
import io
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from action_pending import emit, handle_line
from storage import read_json


class SupervisorCase(unittest.TestCase):
    def test_deep_json_is_reported_without_escaping(self):
        deep = ('[' * 100000 + ']' * 100000).encode()
        result = handle_line(lambda request: None, deep)
        self.assertEqual(result, {'ok': False, 'action': '', 'message': 'Invalid JSON input'})

    def test_raising_handler_becomes_one_failed_result(self):
        def handle(request):
            raise RuntimeError('boom')
        result = handle_line(handle, b'{"action":"setting","key":"accent"}')
        self.assertFalse(result['ok'])
        self.assertEqual(result['action'], 'setting')
        self.assertIn('boom', result['message'])

    def test_non_string_action_is_reported_as_empty(self):
        def handle(request):
            raise AttributeError('shape')
        result = handle_line(handle, b'{"action": 5}')
        self.assertEqual(result['action'], '')
        self.assertIn('shape', result['message'])

    def test_valid_line_still_returns_none(self):
        seen = []
        self.assertIsNone(handle_line(seen.append, b'{"action":"refresh"}'))
        self.assertEqual(seen[0]['action'], 'refresh')

    def test_snapshot_failure_is_logged_not_raised(self):
        class Broken:
            client_serial = 0
            feature_jobs = {}
            charge_job = None

            def snapshot(self):
                raise RuntimeError('probe failed')

        error = io.StringIO()
        with redirect_stderr(error):
            emit(Broken(), '')
        self.assertIn('probe failed', error.getvalue())

    def test_oversized_json_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.json'
            path.write_text('[' + '0,' * 2000 + '0]')
            self.assertEqual(read_json(path, [], limit=1024), [])
            self.assertEqual(len(read_json(path, [])), 2001)
