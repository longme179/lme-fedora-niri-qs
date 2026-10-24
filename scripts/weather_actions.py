"""Entry calls are synchronous; WeatherClient retains its asynchronous controller."""
from dataclasses import dataclass
from typing import Callable
from backend_actions import ActionSpec
from weather import location


@dataclass(frozen=True)
class WeatherCapabilities:
    preferences: Callable
    search: Callable
    detect: Callable
    refresh: Callable
    demo_state: Callable
    update: Callable


def provide(cap):
    def search(request):
        cap.search(request.get('query'))
        return 'Searching locations'
    def detect(request):
        cap.detect()
        return 'Detecting approximate location'
    def refresh(request):
        cap.refresh(cap.preferences()['weatherAutoLocation'])
        return 'Refreshing weather'
    def demo_search(request):
        query=request.get('query')
        if not isinstance(query,str) or not 2<=len(query.strip())<=100:
            raise ValueError('Enter a city name of 2–100 characters.')
        cap.demo_state()['weather']['search']={'query':query,'loading':False,'error':'',
            'results':[{'name':query.strip(),'country':'Demo','latitude':10.82,'longitude':106.63}]}
    def select(request, demo=False):
        place = location(request.get('location'))
        if not place: raise ValueError('Select a city first.')
        values = {'weatherLocation':place,'weatherAutoLocation':False}
        if demo: cap.preferences().update(values)
        else:
            cap.update(values)
            return 'Weather location updated'
    return (ActionSpec('weatherSearch',{'shell','settings'},search,demo_search),
            ActionSpec('weatherDetect',{'shell','settings'},detect,lambda request:None),
            ActionSpec('weatherRefresh',{'shell'},refresh,lambda request:None),
            ActionSpec('weatherSelect',{'shell','settings'},select,lambda request:select(request,demo=True))),lambda:{}
