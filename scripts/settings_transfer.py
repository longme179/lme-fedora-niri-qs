"""Validated JSON settings transfer; no archive extraction or private preset data."""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
from pathlib import Path
from desktop_features import APPEARANCE_KEYS

PORTABLE = set(APPEARANCE_KEYS) | {
    'barEdge','barEdgeMargin','barSideMargin','barHeight','barStyle','barFontSize','barLayout',
    'recordingEnabled','recordingEncoder','recordingFormat','recordingCodec','recordingFps','recordingBitrate','captureEditor','fileSearchEnabled','quickNotes','audioVisualizer','osdEnabled','osdPosition','osdLayout','osdMargin','controlLayout','controlWidth','popupBlur','fontPicker','colorPicker','privacyIndicators','dndWhileSharing',
    'batteryDetails','weatherAutoLocation','weatherUnit','activityEnabled','clipboardEnabled','clipboardImages','clipboardLimit',
    'nightLightMode','nightLightTemperature','nightLightStart','nightLightEnd',
}


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
    if not isinstance(values,dict) or not values or not set(values)<=allowed:
        raise ValueError('Unknown or private settings in this document')
    # Validate everything before the caller mutates preferences.
    return {k:validator(k,v) for k,v in values.items()}


def read_document(value, validator, defaults):
    path=transfer_path(value)
    if not path.is_file() or path.stat().st_size>1024*1024: raise ValueError('Settings file must be at most 1 MiB')
    with path.open(encoding='utf-8') as handle:
        return validate_document(json.load(handle),validator,defaults)


def export_document(value, values, kind):
    path=transfer_path(value)
    payload=json.dumps(document(values,kind),indent=2,allow_nan=False)+'\n'
    # Existing files are never overwritten, including the live settings file.
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8') as handle:
        handle.write(payload);handle.flush();os.fsync(handle.fileno())
    return str(path)
