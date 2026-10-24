"""JSON-line acknowledgement and projection of existing coordinator ownership."""
import json

MAX_SERIAL = 9007199254740991


def acknowledge(previous, request):
    value = request.get('clientSerial') if isinstance(request, dict) else None
    return max(previous, value) if type(value) is int and 1 <= value <= MAX_SERIAL else previous


def emit_snapshot(state, catalog_error, acknowledged, active, charging):
    # snapshot() must finish its existing publication before owners are sampled.
    owners = sorted(set(active) | ({'chargeMode'} if charging else set()))
    state = dict(state, catalogValidation={'error': catalog_error},
                 actionPending={'acknowledged': acknowledged, 'active': owners})
    print(json.dumps(state, ensure_ascii=False, allow_nan=False, separators=(',', ':')), flush=True)


def handle_line(handle, line):
    try:
        handle(json.loads(line.decode('utf-8')))
    except (UnicodeError, json.JSONDecodeError):
        return {'ok': False, 'action': '', 'message': 'Invalid JSON input'}
    return None
