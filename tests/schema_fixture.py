"""Golden inputs; values come from the unmodified preference adapters."""
import copy
import json
from pathlib import Path

BOUNDS = {
 'opacity':(.6,1),'fontSize':(12,20),'barEdgeMargin':(0,64),'barSideMargin':(0,160),'barHeight':(36,64),
 'nightLightTemperature':(2500,6500),'desktopShapeCount':(1,12),'desktopShapeScale':(.5,2),
 'desktopShapeOpacity':(.02,.6),'desktopShapeSpeed':(.1,3),'notificationOpacity':(.6,1),
 'notificationWidth':(300,640),'notificationMargin':(0,64),'notificationRadius':(0,48),
 'notificationPadding':(12,28),'notificationBorderWidth':(0,4),'notificationTitleSize':(12,24),
 'notificationBodySize':(11,22),'notificationIdleSpeed':(6,40),'osdMargin':(0,96),
 'paletteContrast':(-1,1),'recordingBitrate':(1000,100000),'motionSpeed':(.5,2),'motionBounce':(0,1),
 'activityCompactMaxWidth':(120,1200),'activityPopupMaxWidth':(400,1600),'activityPopupMaxHeight':(320,2160),
 'controlWidth':(480,900),'dndUntil':(-1,4102444800000),'clipboardLimit':(20,500),
 'barBorderWidth':(0,4),'barFontSize':(12,16),'peripheralBatteryThreshold':(5,50),'batterySaverBrightness':(1,100),
 'wallpaperPlaylistInterval':(30,86400),'wallpaperTransitionFps':(10,240),'wallpaperTransitionStep':(1,255),
 'wallpaperTransitionAngle':(0,360),'wallpaperTransitionDuration':(.1,30),
}
CHOICES = {
 'surfaceStyle':['smoked','liquid'],'barEdge':['top','bottom'],'nightLightMode':['manual','schedule','sunset'],
 'lyricsMode':['scroll','line'],'desktopShapeStyle':['mixed','flower','circle','square'],
 'notificationPosition':['bar','top-left','top-center','top-right','bottom-left','bottom-center','bottom-right'],
 'osdPosition':['top-left','top-center','top-right','center-left','center','center-right','bottom-left','bottom-center','bottom-right'],
 'osdLayout':['horizontal','vertical'],'weatherUnit':['celsius','fahrenheit'],
 'recordingEncoder':['auto','nvidia','cpu','radeon'],'recordingAudio':['none','system','microphone'],
 'recordingFormat':['mkv','mp4','mov','webm'],'recordingCodec':['auto','h264','hevc','av1','vp9'],
 'recordingFps':[24,30,60,120],'captureEditor':['auto','satty','swappy'],'density':['compact','comfortable'],
 'motionPreset':['smooth','expressive','jelly','jelly-v2'],'paletteSource':['dracula','wallpaper','preset'],
 'paletteMode':['dark','light'],'barStyle':['islands','connected'],
 'wallpaperTransition':['fade','wipe','wave','grow','outer','left','right','top','bottom','simple','none','random'],
}
EXTRA = {
 'themeOverrides':[{'buttonFill':'#ABCDEF'}, {'missing':'#123456'}],
 'fontOverrides':[{'body':'  Roboto  '},{'missing':'x'}], 'shellName':['  New shell  ','x'*48,'x'*49,'bad\nname'],
 'barLayout':[{'left':['clipboard'],'center':[],'right':['settings']},{'left':['clock'],'center':['clock'],'right':[]}],
 'barGestures':[{'clipboard':{'right':'clipboard'}},{'clock':{'left':'agenda'}}],
 'weatherLocation':[{'name':'City','latitude':1,'longitude':2},{'latitude':1,'longitude':2},{'latitude':91,'longitude':0}],
 'tasks':[[{'id':'a','text':'  Keep text  ','done':False}]],'notificationMutedApps':[['a','a','b']],
 'osdOutput':['eDP-1','x'*128,'x'*129,'bad\nname'], 'bluetoothAdapter':['/org/bluez/hci0','/org/bluez/hci12'],
 'nightLightStart':['00:00','23:59','24:00'],'nightLightEnd':['00:00','23:59','24:00'],
}


def normalize(value):
    if isinstance(value, str):
        return value.replace(str(Path.home()), '<HOME>').replace(str(Path.cwd()), '<ROOT>')
    if isinstance(value, list): return [normalize(v) for v in value]
    if isinstance(value, dict): return {k:normalize(v) for k,v in value.items()}
    return value


def expand(value):
    if isinstance(value, dict) and set(value)=={'$float'}: return float(value['$float'])
    if isinstance(value, str): return value.replace('<HOME>',str(Path.home())).replace('<ROOT>',str(Path.cwd()))
    if isinstance(value, list): return [expand(v) for v in value]
    if isinstance(value, dict): return {k:expand(v) for k,v in value.items()}
    return value


def frozen(value):
    return [type(value).__name__, json.dumps(normalize(value),sort_keys=True,ensure_ascii=True,allow_nan=False)]


def outcome(validate, key, value):
    try: return ['ok',*frozen(validate(key,expand(copy.deepcopy(value))))]
    except Exception as error: return ['error',type(error).__name__,normalize(str(error))]


def matrix(defaults):
    common=[None,False,True,0,1,-1,1.0,.6,'','bad','en',[],{}, {'$float':'nan'},{'$float':'inf'},{'$float':'-inf'}]
    result={}
    for key,default in defaults.items():
        values=[normalize(default),*common,*CHOICES.get(key,()),*EXTRA.get(key,())]
        if key in BOUNDS:
            low,high=BOUNDS[key];values += [low-1,low,high,high+1,float(low),float(high)]
        result[key]=list({json.dumps(v,sort_keys=True):v for v in values}.values())
    result['notASetting']=[False,1,'x',None]
    return result
