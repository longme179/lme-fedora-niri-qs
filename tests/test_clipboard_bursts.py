"""Every clipboard operation must survive batching; no real selection is read."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from clipboard import History

ROOT = Path(__file__).resolve().parents[1]


class ClipboardBurstCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='clipboard-burst-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = dict(os.environ)
        for name in ('CONFIG', 'STATE', 'DATA', 'CACHE', 'RUNTIME'):
            directory = self.root/name.lower(); directory.mkdir(mode=0o700)
            self.env['XDG_'+name+('_DIR' if name == 'RUNTIME' else '_HOME')] = str(directory)
        config = self.root/'config/lme-shell'; config.mkdir()
        (config/'settings.json').write_text('{"clipboardEnabled":false}')
        binary = self.root/'bin/wl-copy'; binary.parent.mkdir()
        binary.write_text('#!'+sys.executable+'\nimport sys\nsys.stdin.buffer.read()\n')
        binary.chmod(0o700)
        self.env.update(PATH=str(binary.parent)+':'+self.env['PATH'], WAYLAND_DISPLAY='no-wayland',
                        DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(self.root/'no-system-bus'))
        self.directory = self.root/'history'
        history = History(self.directory)
        self.ident = history.store('text', b'Clipboard burst text')
        history.db.close()

    def worker(self, requests, *, regular_file=False):
        payload = ''.join(json.dumps(request)+'\n' for request in requests)
        with tempfile.TemporaryFile(mode='w+') as source:
            source.write(payload); source.seek(0)
            result = subprocess.run([sys.executable, str(ROOT/'scripts/clipboard.py'),
                '--directory', str(self.directory)], env=self.env, text=True, capture_output=True,
                stdin=source if regular_file else None, input=None if regular_file else payload, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_single_operation_and_capture_disabled_keep_existing_contract(self):
        states = self.worker([dict(action='copy', id=self.ident)])
        self.assertEqual(states[-1]['lastResult'], dict(action='copy', ok=True,
                         message='Copied to clipboard', sequence=1))
        self.assertFalse(states[-1]['capturing'])
        self.assertEqual(states[-1]['total'], 1)

    def test_both_orders_deliver_every_result_from_pipe_and_regular_file(self):
        copy = dict(action='copy', id=self.ident)
        search = dict(action='search', query='burst', kind='all')
        for requests in ([copy, search], [search, copy]):
            for regular_file in (False, True):
                with self.subTest(order=[r['action'] for r in requests], file=regular_file):
                    states = self.worker(requests, regular_file=regular_file)
                    results = [s['lastResult'] for s in states if s['lastResult']]
                    self.assertEqual([r['action'] for r in results], [r['action'] for r in requests])
                    self.assertEqual([r['sequence'] for r in results], [1, 2])
                    self.assertTrue(all(r['ok'] for r in results))

    def test_error_is_delivered_before_the_next_success(self):
        states = self.worker([dict(action='copy', id='missing'), dict(action='search', query='', kind='all')])
        results = [s['lastResult'] for s in states if s['lastResult']]
        self.assertEqual([(r['action'], r['ok'], r['sequence']) for r in results],
                         [('copy', False, 1), ('search', True, 2)])
        self.assertEqual(states[-1]['total'], 1)

    def test_requests_crossing_read_boundaries_keep_their_own_state(self):
        requests = [dict(action='search', query=query, kind='text', padding='x'*8200)
                    for query in ('absent', 'burst', 'text')]
        states = self.worker(requests)
        replies = [s for s in states if s['lastResult']]
        self.assertEqual([s['lastResult']['sequence'] for s in replies], [1, 2, 3])
        self.assertEqual([len(s['entries']) for s in replies], [0, 1, 1])

