"""JSON-line acknowledgement and projection of existing coordinator ownership."""
import json
import sys

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


def emit(backend, catalog_error):
    """Publish one snapshot; a broken probe must not stop the shell."""
    try:
        emit_snapshot(backend.snapshot(), catalog_error, backend.client_serial,
                      backend.feature_jobs, backend.charge_job is not None)
    except Exception as error:
        print(f"Snapshot failed: {type(error).__name__}: {error}", file=sys.stderr)


def handle_line(handle, line):
    try:
        request = json.loads(line.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        return {'ok': False, 'action': '', 'message': 'Invalid JSON input'}
    try:
        handle(request)
    except Exception as error:
        action = request.get('action', '') if isinstance(request, dict) else ''
        message = str(error)[:300] or type(error).__name__
        return {'ok': False, 'action': action if isinstance(action, str) else '', 'message': message}
    return None
