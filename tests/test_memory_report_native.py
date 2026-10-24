"""Opt-in inventory against private Quickshell instances and a detached job."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get('LME_TEST_MEMORY_UI')=='1', 'private Wayland release inventory')
class NativeMemoryCase(unittest.TestCase):
    def test_preview_settings_and_surviving_detached_job_are_counted_once(self):
        import migration_startup as startup
        from memory_report import collect
        from launchpad import Launchpad
        with startup.Launch('preview','memory-preview') as main, \
                startup.Launch('settings','memory-settings') as settings, \
                tempfile.TemporaryDirectory() as state, patch.dict(os.environ,XDG_STATE_HOME=state):
            jobs=Launchpad()
            entry=dict(name='Release fixture',kind='command',terminal=False,cwd='',
                command=f'{sys.executable} -c "import time; time.sleep(30)"')
            jobs.run('release',{'release':entry},'unused')
            relay=jobs.jobs['release']['process']
            try:
                # Drop controller ownership without terminating the detached job.
                jobs.jobs.clear()
                deadline=time.monotonic()+10
                while True:
                    report=collect()
                    rows={row['pid']:row for row in report['processes']}
                    backends=[row for row in rows.values() if row['role']=='backend']
                    if {main.process.pid,settings.process.pid,relay.pid}<=rows.keys() and len(backends)>=2: break
                    if time.monotonic()>=deadline: self.fail(str(report))
                    time.sleep(.05)
                self.assertEqual(rows[relay.pid]['role'],'Launchpad relay')
                payloads=[row for row in rows.values() if row['parent']==relay.pid]
                self.assertEqual(len(payloads),1); self.assertEqual(payloads[0]['role'],'job payload')
                self.assertEqual(len(rows),len(report['processes']))
                for pid in (main.process.pid,settings.process.pid,relay.pid,payloads[0]['pid']):
                    self.assertGreater(rows[pid]['pss_kib'],0)
                self.assertEqual(report['measured_pss_kib'],sum(row['pss_kib'] or 0 for row in rows.values()))
                self.assertNotIn('time.sleep',str(report))
            finally:
                relay.terminate(); relay.wait(timeout=3)


if __name__=='__main__': unittest.main()
