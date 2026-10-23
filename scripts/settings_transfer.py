"""Validated JSON settings transfer; no archive extraction or private preset data."""
# SPDX-License-Identifier: GPL-3.0-or-later
import errno
import json
import os
from pathlib import Path
import tempfile
from desktop_features import APPEARANCE_KEYS

from settings_schema import portable_keys
PORTABLE = set(portable_keys())


def transfer_path(value):
    if not isinstance(value,str) or not value or len(value)>4096 or any(ord(c)<32 for c in value):
        raise ValueError('Choose a JSON file path')
    return Path(value).expanduser().resolve()


def document(values, kind):
    if kind not in ('preset','backup'): raise ValueError('Choose preset or backup')
    return {'schema':1,'kind':kind,'settings':{k:v for k,v in values.items() if kind=='backup' or k in PORTABLE}}


def validate_document(data, validator, defaults):
    if not isinstance(data,dict) or set(data) != {'schema','kind','settings'} or type(data['schema']) is not int or data['schema']!=1 or data['kind'] not in ('preset','backup'):
        raise ValueError('Expected an LME schema 1 settings preset or backup')
    values=data['settings'];allowed=set(defaults) if data['kind']=='backup' else PORTABLE
    if isinstance(values, dict):
        retired = {'connectedPopups'} | ({'favoriteApps', 'wallpaperFavorites'} if data['kind'] == 'backup' else set())
        values = {k:v for k,v in values.items() if k not in retired}
    if not isinstance(values,dict) or not values or not set(values)<=allowed:
        raise ValueError('Unknown or private settings in this document')
    # Validate everything before the caller mutates preferences.
    return {k:validator(k,v) for k,v in values.items()}


def read_document(value, validator, defaults):
    path=transfer_path(value)
    if not path.is_file() or path.stat().st_size>1024*1024: raise ValueError('Settings file must be at most 1 MiB')
    with path.open(encoding='utf-8') as handle:
        return validate_document(json.load(handle),validator,defaults)


def _write(fd, payload):
    try: stream = os.fdopen(fd, 'w', encoding='utf-8')
    except BaseException:
        os.close(fd)
        raise
    with stream as handle:
        handle.write(payload); handle.flush(); os.fsync(handle.fileno())


def _publish(stage, path, payload):
    try: os.link(stage, path)
    except FileExistsError:
        raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(path)) from None
    except OSError as error:
        if error.errno not in (errno.EPERM, errno.EOPNOTSUPP, errno.ENOSYS, errno.EXDEV): raise
        # FAT/removable filesystems retain exclusive creation, with owned-file cleanup.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        identity = os.fstat(fd)
        try: _write(fd, payload)
        except BaseException:
            try:
                current = path.lstat()
                if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino): path.unlink()
            except FileNotFoundError: pass
            raise


def export_document(value, values, kind):
    path = transfer_path(value)
    payload = json.dumps(document(values, kind), indent=2, allow_nan=False)+'\n'
    fd, stage = tempfile.mkstemp(prefix='.lme-export-', dir=path.parent)
    try:
        _write(fd, payload)
        _publish(stage, path, payload)
    finally:
        os.unlink(stage)
    return str(path)
