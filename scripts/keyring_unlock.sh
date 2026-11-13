#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Role: unlock the login keyring with the password PAM just accepted (Phase 3 caller:
# qml/services/LockState.qml; Phase 0 of the lock port ships it uncalled).
# Vendored from snowarch/iNiR v3.1.0 scripts/keyring/{unlock,is_unlocked}.sh @ edca6cc
# (GPL-3.0, itself based on https://unix.stackexchange.com/a/602935); the two helpers
# are inlined into one standalone script. Requires UNLOCK_PASSWORD in the environment;
# never prompts, so a caller bug cannot block the unlock path.

set -euo pipefail

if [[ -z "${UNLOCK_PASSWORD:-}" ]]; then
    printf 'keyring_unlock.sh: UNLOCK_PASSWORD is required\n' >&2
    exit 2
fi

locked_state=$(busctl --user get-property org.freedesktop.secrets \
    /org/freedesktop/secrets/collection/login \
    org.freedesktop.Secret.Collection Locked 2>/dev/null || true)
if [[ "${locked_state}" == "b false" ]]; then
    exit 0  # already unlocked
fi

killall -q -u "$(whoami)" gnome-keyring-daemon || true
eval "$(printf '%s' "${UNLOCK_PASSWORD}" | gnome-keyring-daemon --daemonize --login | sed -e 's/^/export /')"
unset UNLOCK_PASSWORD
