"""Wi-Fi operations; the host retains network sampling and worker publication."""
from dataclasses import dataclass
from typing import Callable

from backend_actions import ActionSpec
from command_runner import CommandError

ACTIONS = ('wifiScan', 'wifiConnect', 'wifiSaved', 'wifiDisconnect', 'wifiForget')


@dataclass(frozen=True)
class WifiCapabilities:
    network: Callable
    run: Callable
    demo_network: Callable


def perform(capabilities, action, request):
    state = capabilities.network(details=True)
    if not state["available"]: raise CommandError("NetworkManager is unavailable")
    interface = request.get("device") or state.get("device")
    if not isinstance(interface, str) or interface != state.get("device") or not interface:
        raise ValueError("No Wi-Fi adapter is available")
    run = capabilities.run
    if action == "wifiScan":
        run("nmcli", "--wait", "15", "device", "wifi", "rescan", "ifname", interface, timeout=18)
        return "Wi-Fi scan completed"
    if action == "wifiDisconnect":
        run("nmcli", "--wait", "15", "device", "disconnect", interface, timeout=18)
        return "Wi-Fi disconnected"
    if action in {"wifiSaved", "wifiForget"}:
        ident = request.get("uuid")
        if not isinstance(ident, str) or not any(n["uuid"] == ident for n in state.get("saved", [])):
            raise ValueError("Saved network is no longer available")
        if action == "wifiForget":
            run("nmcli", "connection", "delete", "uuid", ident)
            return "Saved network removed"
        args = ("connection", "up", "uuid", ident, "ifname", interface)
    else:
        network = next((n for n in state["networks"] if n.get("bssid") == request.get("bssid")), None)
        if not network: raise ValueError("Network is no longer visible; scan again")
        if network.get("enterprise"): raise ValueError("Enterprise Wi-Fi needs a certificate or account. Use Advanced network settings.")
        args = ("device", "wifi", "connect", network["bssid"], "ifname", interface)
    password = request.get("password", "")
    if not isinstance(password, str) or len(password) > 128 or any(c in password for c in "\r\n\x00"):
        raise ValueError("Invalid Wi-Fi password")
    # nmcli's secret agent reads stdin; the password never appears in argv, state or logs.
    run("nmcli", "--wait", "45", "--ask", *args, input=password + "\n", timeout=50)
    return "Wi-Fi connected"


def provide(capabilities):
    def demo(action, request):
        if action in {"wifiConnect", "wifiSaved"}:
            capabilities.demo_network().update(connected=True, ssid=request.get("ssid", "Home Wi-Fi"))
        elif action == "wifiDisconnect":
            capabilities.demo_network().update(connected=False, ssid="")

    complete = lambda value: None
    specs = tuple(ActionSpec(action, {'shell'},
        lambda request, action=action: perform(capabilities, action, request),
        lambda request, action=action: demo(action, request), execution='worker', complete=complete)
        for action in ACTIONS)
    return specs, lambda: {}
