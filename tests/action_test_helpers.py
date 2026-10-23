"""Complete only acknowledged fake worker actions; no hardware/session discovery."""
import json
from concurrent.futures import wait
from test_backend import FakeRunner


def complete_action(live, request):
    result = live.handle(request)
    if not result.get('pending'): return result
    job = live.feature_jobs[request['action']]
    finished, _ = wait([job], timeout=2)
    if not finished: raise AssertionError('Fake worker did not finish')
    live.finish_features()
    return dict(live.last_result)


def bluez_runner(bluez, service):
    objects = {}
    for index in [0, 1]:
        path = f"/org/bluez/hci{index}"
        objects[path] = {"org.bluez.Adapter1": {"Alias": f"Adapter {index}", "Powered": True}}
        objects[path + "/dev_AA_BB_CC_DD_EE_FF"] = {"org.bluez.Device1": {"Alias": f"Headset {index}", "Paired": True, "Connected": False}}
    runner = FakeRunner({bluez: json.dumps({"data": [objects]}),
        ("busctl", "--system", "get-property", *service, "ActiveProfile"): 's "balanced"',
        ("busctl", "--system", "get-property", *service, "Profiles"): 'aa{sv} 3 1 "Profile" s "balanced" 1 "Profile" s "power-saver" 1 "Profile" s "performance"'})
    return runner, objects
