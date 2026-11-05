"""Optional Serpantinum audio daemon controls; the daemon remains an external binary."""
from dataclasses import dataclass
from typing import Callable

from backend_actions import ActionSpec
from command_runner import CommandError


@dataclass(frozen=True)
class EqualizerCapabilities:
    run: Callable
    available: Callable


DYNAMICS = ("off", "balanced", "night")
GAINS = 10


def _number(value, minimum=-12, maximum=12):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Equalizer settings must use numeric gain")
    value = float(value)
    if value < minimum or value > maximum or value != value:
        raise ValueError("Equalizer gain is out of range")
    return value


def _command(capabilities, action, request):
    if not capabilities.available("serpantinum-audio"):
        raise CommandError("serpantinum-audio is unavailable")
    if action == "eqStart":
        return capabilities.run("serpantinum-audio", "start")
    if action == "eqStop":
        try:
            return capabilities.run("serpantinum-audio", "ctl", "quit")
        except CommandError:
            return "Equalizer stopped"
    if action == "eqStatus":
        ping = capabilities.run("serpantinum-audio", "ctl", "ping")
        status = capabilities.run("serpantinum-audio", "ctl", "status")
        return ping.strip() + "\n" + status.strip()
    if action == "eqGet":
        return capabilities.run("serpantinum-audio", "ctl", "get").strip()
    gains = request.get("gains", [])
    if not isinstance(gains, list) or len(gains) != GAINS:
        raise ValueError("Ten equalizer band gains are required")
    gains = [_number(item) for item in gains]
    balance = request.get("balance", 0)
    if isinstance(balance, bool) or not isinstance(balance, (int, float)):
        raise ValueError("Balance must be numeric")
    balance = float(balance)
    if balance < -1 or balance > 1:
        raise ValueError("Balance must be between -1 and 1")
    mono = request.get("mono", False)
    swap = request.get("swap", False)
    bypass = request.get("bypass", False)
    dyneq = request.get("dyneq", False)
    if not all(type(item) is bool for item in (mono, swap, bypass, dyneq)):
        raise ValueError("Equalizer switches must be boolean")
    dynamics = request.get("dynamics", "off")
    if dynamics not in DYNAMICS:
        raise ValueError("Unknown dynamics mode")
    args = ["ctl", "set", *[f"{value:g}" for value in gains], f"{balance:g}",
            "1" if mono else "0", "1" if swap else "0", dynamics,
            "1" if bypass else "0", "1" if dyneq else "0"]
    return capabilities.run("serpantinum-audio", *args)


def provide(capabilities):
    def live(request, action):
        return _command(capabilities, action, request)

    def demo(request, action):
        if action == "eqStatus":
            return "ok\nDemo Serpantinum status"
        if action == "eqGet":
            return "set 0 0 0 0 0 0 0 0 0 0 0 0 0 off 0 1"
        return "Demo equalizer applied"

    specs = []
    for ident in ("eqStart", "eqStop", "eqStatus", "eqGet", "eqApply"):
        specs.append(ActionSpec(ident, {"shell", "settings"},
                               lambda request, action=ident: live(request, action),
                               lambda request, action=ident: demo(request, action)))
    return (tuple(specs), lambda: {})