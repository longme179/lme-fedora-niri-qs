"""Characterize coordinator/domain seams with manual jobs and no real hardware."""
from contextlib import nullcontext
import copy
import json
import os
from pathlib import Path
from unittest.mock import patch

from test_backend import FakeRunner, backend
from test_features import ManualExecutor
from test_clipboard import PNG

ACTIONS = ('recordStop','palettePreview','recordStart','lock','imageAnnotate',
    'wallpaper','wallpaperNext','wallpaperResetOutput','gowallThemes','gowallGenerate',
    'gowallSave','gowallApply','batterySaver','fileSearch','captureExport',
    'captureAnnotate','captureOcr','chargeMode','weatherSearch','weatherDetect','weatherRefresh')


def configured(case, demo=False, settings=False):
    env = patch.dict(os.environ, XDG_CONFIG_HOME=str(case.root/'config'), XDG_STATE_HOME=str(case.root/'state'))
    env.start(); case.addCleanup(env.stop)
    case.preferences = backend.Preferences(case.root/'config/settings.json')
    live = case.make_backend(FakeRunner(available=backend.TOOLS), demo=demo)
    live.settings_only = settings
    live.feature_executor.shutdown(); live.feature_executor = ManualExecutor()
    live.charge_executor.shutdown(); live.charge_executor = ManualExecutor()
    case.addCleanup(live.weather.close)
    events = []
    def event(name, result):
        def call(*args, **kwargs):
            events.append([name,args,kwargs]); return copy.deepcopy(result)
        return call
    image=case.root/'image.png'; image.write_bytes(PNG)
    live.preferences.values.update(fileSearchEnabled=True, fileSearchRoots=[str(case.root)],
        wallpaperPlaylist=[str(image)], captureEditor='satty')
    live.niri_state=lambda:dict(available=True,workspaces=[dict(output='eDP-test')],windows=[])
    live.saver_snapshot=lambda:dict(active=False,busy=False,error='',warnings=[])
    live.saver_preflight=event('saver_preflight',None)
    live.toggle_battery_saver=event('toggle_saver','Battery saver changed')
    def guard(**kwargs):
        events.append(['guard',[],kwargs]); return nullcontext()
    live.battery_saver.guard=guard
    live.recorder.start=event('record_start','Recording requested')
    live.recorder.stop=event('record_stop','Recording saved')
    live.lock_session=event('lock','Session locked')
    live.apply_wallpaper=event('wallpaper','Wallpaper applied')
    live.wallpapers.advance=event('wallpaper_next','Next wallpaper')
    live.wallpapers.reset_output=event('wallpaper_reset','Wallpaper reset')
    live.image_utilities.themes=event('themes',['dracula','nord'])
    live.image_utilities.generate=event('generate',dict(images=[],operation='palette',log='ok'))
    live.image_utilities.save=event('save','Image saved')
    live.image_utilities.apply=event('apply','Image applied')
    live.capture.state.update(token='lease',path=str(image))
    live.capture.export=event('export','Screenshot exported')
    live.capture.annotate=event('annotate','Screenshot annotated')
    live.capture.ocr=event('ocr','Recognized text')
    live.charging=lambda:dict(canSet=True,reason='')
    live.set_charge=event('charge','Charge mode updated')
    live.weather.search=event('weather_search',None)
    live.weather.detect=event('weather_detect',None)
    live.weather.refresh=event('weather_refresh',None)
    search=patch.object(backend,'search_files',side_effect=event('search',dict(query='docs',entries=[],truncated=False)))
    search.start(); case.addCleanup(search.stop)
    palette=patch.object(backend,'palette_preview',side_effect=event('palette',dict(colors={},path=str(image))))
    palette.start(); case.addCleanup(palette.stop)
    annotate=patch.object(backend,'annotate_image',side_effect=event('image_annotate','Image annotated'))
    annotate.start(); case.addCleanup(annotate.stop)
    requests = {
        'recordStop':{}, 'palettePreview':dict(path=str(image)),
        'recordStart':dict(mode='output',output='eDP-test',audio='none'), 'lock':{},
        'imageAnnotate':dict(path=str(image)), 'wallpaper':dict(path=str(image),output=''),
        'wallpaperNext':dict(output='eDP-test'), 'wallpaperResetOutput':dict(output='eDP-test'),
        'gowallThemes':{}, 'gowallGenerate':dict(operation='palette',paths=[str(image)],options={}),
        'gowallSave':dict(path=str(image),destination=str(case.root/'saved.png')),
        'gowallApply':dict(path=str(image),output='eDP-test'), 'batterySaver':dict(enabled=True),
        'fileSearch':dict(query='docs'), 'captureExport':dict(token='lease',operation='copy'),
        'captureAnnotate':dict(token='lease'), 'captureOcr':dict(token='lease',language='eng'),
        'chargeMode':dict(value=85), 'weatherSearch':dict(query='City'), 'weatherDetect':{}, 'weatherRefresh':{}}
    return live, events, requests


def selected(live):
    return copy.deepcopy(dict(fileSearch=live.file_search, palettePreview=live.palette_preview,
        imageUtilities=live.image_utilities.state, capture=live.capture.state,
        batterySaver=live.battery_saver_state, featureKeys=list(live.feature_snapshot())))


def normalize(case, value):
    def stable(item):
        if isinstance(item,FakeRunner): return '<FakeRunner>'
        if hasattr(item,'is_set'): return {'cancelled':item.is_set()}
        return str(item)
    text=json.dumps(value,ensure_ascii=False,default=stable)
    for original,replacement in ((str(case.root),'<root>'),(str(Path.home()),'<home>'),
                                 (str(Path(backend.__file__).resolve().parents[1]),'<checkout>')):
        text=text.replace(original,replacement)
    return json.loads(text)


def trace(case, action, demo, settings):
    live, events, requests = configured(case,demo,settings)
    reply=live.handle(dict(action=action,**requests[action]))
    before=dict(reply=reply,events=copy.deepcopy(events),calls=copy.deepcopy(live.runner.calls),
        pending=sorted(live.feature_jobs),charge=live.charge_job is not None,state=selected(live))
    if live.feature_jobs:
        live.feature_executor.complete(); live.finish_features()
    if live.charge_job is not None:
        live.charge_executor.complete(); live.finish_charge()
    after=dict(result=live.last_result,events=events,calls=live.runner.calls,
        pending=sorted(live.feature_jobs),charge=live.charge_job is not None,state=selected(live))
    return normalize(case,dict(before=before,after=after))
