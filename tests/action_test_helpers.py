"""Complete only acknowledged fake worker actions; no hardware/session discovery."""
from concurrent.futures import wait


def complete_action(live, request):
    result = live.handle(request)
    if not result.get('pending'): return result
    job = live.feature_jobs[request['action']]
    finished, _ = wait([job], timeout=2)
    if not finished: raise AssertionError('Fake worker did not finish')
    live.finish_features()
    return dict(live.last_result)
