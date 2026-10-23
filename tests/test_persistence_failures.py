"""Persistence failure/retry regressions; disposable files and injected I/O faults."""
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from settings_transfer import export_document
from test_backend import Fixture


class NotificationPersistenceCase(Fixture,unittest.TestCase):
    def test_current_success_is_private_and_restorable(self):
        with patch.dict(os.environ,XDG_STATE_HOME=str(self.root/'state')):
            live=self.make_backend()
            self.assertTrue(live.handle(dict(action='notificationSave',entries=[]))['ok'])
            self.assertEqual(live.notification_path.stat().st_mode&0o777,0o600)
            self.assertEqual(self.make_backend().notification_history,[])

    def test_failed_replace_or_fsync_keeps_memory_disk_and_retry_consistent(self):
        with patch.dict(os.environ,XDG_STATE_HOME=str(self.root/'state')):
            live=self.make_backend()
            old=dict(id='old',appName='App',summary='Old',body='Keep me',timestamp=1,urgency=1)
            new=dict(old,id='new',summary='New')
            for fault in ('replace','fsync'):
                self.assertTrue(live.handle(dict(action='notificationSave',entries=[old]))['ok'])
                before=copy.deepcopy(live.notification_history);data=live.notification_path.read_bytes()
                with patch('storage.os.'+fault,side_effect=OSError('Simulated disk failure')):
                    result=live.handle(dict(action='notificationSave',entries=[new]))
                self.assertFalse(result['ok']);self.assertIn('Simulated disk failure',result['message'])
                self.assertEqual(live.notification_path.read_bytes(),data)
                self.assertEqual(live.notification_history,before)
                self.assertEqual(list(live.notification_path.parent.iterdir()),[live.notification_path])
                self.assertTrue(live.handle(dict(action='notificationSave',entries=[new]))['ok'])
                self.assertEqual(self.make_backend().notification_history,live.notification_history)


class ExportPersistenceCase(Fixture,unittest.TestCase):
    def export(self,path): return export_document(str(path),dict(accent='#123456'),'preset')

    def test_current_format_permissions_and_existing_destination_are_preserved(self):
        path=self.root/'preset.json';self.assertEqual(self.export(path),str(path))
        payload=json.dumps(dict(schema=1,kind='preset',settings=dict(accent='#123456')),indent=2)+'\n'
        self.assertEqual(path.read_text(),payload);self.assertEqual(path.stat().st_mode&0o777,0o600)
        with self.assertRaises(FileExistsError) as error:self.export(path)
        self.assertEqual(error.exception.filename,str(path));self.assertEqual(path.read_text(),payload)
        self.assertEqual(list(self.root.iterdir()),[path])

    def test_fsync_failure_leaves_no_destination_and_retry_succeeds(self):
        path=self.root/'preset.json'
        with patch('settings_transfer.os.fsync',side_effect=OSError('Simulated fsync failure')):
            with self.assertRaisesRegex(OSError,'Simulated fsync failure'): self.export(path)
        self.assertFalse(path.exists());self.assertEqual(list(self.root.iterdir()),[])
        self.export(path);self.assertEqual(json.loads(path.read_text())['settings'],dict(accent='#123456'))

    def test_partial_write_does_not_publish_or_leave_a_stage(self):
        path=self.root/'preset.json';original=os.fdopen
        @contextmanager
        def partial(fd,*args,**kwargs):
            with original(fd,*args,**kwargs) as handle:
                class Partial:
                    def write(self,payload):
                        handle.write(payload[:len(payload)//2]);handle.flush();raise OSError('Simulated short write')
                    def __getattr__(self,key):return getattr(handle,key)
                yield Partial()
        with patch('settings_transfer.os.fdopen',partial):
            with self.assertRaisesRegex(OSError,'Simulated short write'): self.export(path)
        self.assertFalse(path.exists());self.assertEqual(list(self.root.iterdir()),[])

    def test_destination_race_never_overwrites_another_writer(self):
        path=self.root/'preset.json';original=os.link
        def competitor(source,dest,*args,**kwargs):
            Path(dest).write_text('another writer')
            return original(source,dest,*args,**kwargs)
        with patch('settings_transfer.os.link',competitor):
            with self.assertRaises(FileExistsError) as error:self.export(path)
        self.assertEqual(error.exception.filename,str(path));self.assertEqual(path.read_text(),'another writer')
        self.assertEqual(list(self.root.iterdir()),[path])
