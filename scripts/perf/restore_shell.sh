#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Role: restore_shell.sh (perf harness, scripts/perf/standin.py) — put the owner's shell back.
# REL: scripts/perf/standin.py – writes the state dir this script consumes.
#
#   restore_shell.sh <state-dir> [--dry-run] [--force]
#
# standin.py points the Quickshell config symlink at an instrumented tree and runs that shell
# in place of the deployed one. This script undoes it. It is written to run unattended:
# standin.py arms it as a systemd user timer BEFORE anything is touched, so it also runs when
# the harness dies. It is idempotent (a `restored` marker makes it exit) and it never kills a
# shell that may show the lock screen: the lock is an ext-session-lock, and the compositor
# releases it the moment the client dies.
#
# Only two kinds of process are ever touched: a Quickshell main process of this config
# (`quickshell -c lme-shell ...`, no `ipc` word) and a Settings process (`-p .../settings.qml`).
# Everything else, including `quickshell ... ipc call` clients, is left alone.
#
# The stand-in is known by the pid its wrapper recorded (standin.pid), never by its age: a
# deployed shell that an earlier run of this script started is just as young. Only when no pid
# was recorded does the start time against the swap marker decide.
#
# Exit codes: 0 restored (or nothing was swapped, or dry run);
#             1 refused, failed, or the deployed shell is not up (a retry timer is armed);
#             3 deferred: the harness shell may be locked, it is left running and a new timer
#               brings this script back a minute later (it finishes once the lock is gone).
#             --force skips that wait; only a caller that knows no lock was ever requested
#             during its run may pass it.
#
# State dir, written by standin.py:
#   env         KEY=value lines: LINK ORIGINAL TREE QS NIRI START TIMER and the session's
#               XDG_RUNTIME_DIR WAYLAND_DISPLAY NIRI_SOCKET DBUS_SESSION_BUS_ADDRESS
#   files       config files to restore, paths relative to HOME, one per line
#   snap/       their copies from before the swap
#   standin.pid pid of the stand-in (written by its wrapper)
#   swapped     marker touched right before the stand-in starts
#   events.log  what this script did
set -u
umask 077

state="${1:-}"
dry=false force=false
if (($#)); then shift; fi
for arg in "$@"; do
    case "$arg" in
        --dry-run) dry=true ;;
        --force) force=true ;;
        *) echo "restore_shell.sh: unknown argument $arg" >&2; exit 2 ;;
    esac
done
if [[ -z "$state" || ! -d "$state" ]]; then
    echo "usage: restore_shell.sh <state-dir> [--dry-run] [--force]" >&2
    exit 2
fi
log() { printf '%s %s\n' "$(date '+%F %T')" "$*" | tee -a "$state/events.log"; }

exec 9>"$state/restore.lock" || exit 1
flock -w 60 9 || { log "restore: another restore holds the lock"; exit 1; }
if [[ -f "$state/restored" ]]; then log "restore: already done"; exit 0; fi
if [[ ! -f "$state/env" ]]; then log "restore: nothing was swapped (no env file)"; exit 0; fi

LINK="" ORIGINAL="" TREE="" QS="" NIRI="" START="" TIMER=""
while IFS='=' read -r key value; do
    [[ -n "$key" ]] || continue
    case "$key" in
        LINK) LINK="$value" ;; ORIGINAL) ORIGINAL="$value" ;; TREE) TREE="$value" ;;
        QS) QS="$value" ;; NIRI) NIRI="$value" ;; START) START="$value" ;; TIMER) TIMER="$value" ;;
        XDG_RUNTIME_DIR|WAYLAND_DISPLAY|NIRI_SOCKET|DBUS_SESSION_BUS_ADDRESS) export "$key=$value" ;;
    esac
done < "$state/env"
if [[ -z "$LINK" || -z "$ORIGINAL" || ! -d "$ORIGINAL" || ! -x "$NIRI" ]]; then
    log "restore: REFUSED, state incomplete (link=$LINK original=$ORIGINAL niri=$NIRI)"
    exit 1
fi
read -r -a start_argv <<< "$START"
recorded=$(cat "$state/standin.pid" 2>/dev/null || echo 0)
[[ "$recorded" =~ ^[0-9]+$ ]] || recorded=0
log "restore: begin dry=$dry force=$force link=$LINK original=$ORIGINAL standin pid=${recorded:-none}"

is_shell() {  # $1 = pid; returns 0 for a main or Settings process of this config
    local cmd
    cmd=$(tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null) || return 1
    [[ "$cmd" == *quickshell* ]] || return 1
    [[ "$cmd" != *" ipc "* ]] || return 1
    [[ "$cmd" == *" -c lme-shell "* || "$cmd" == *quickshell*lme-shell*settings.qml* ]]
}
is_main() {  # $1 = pid; a main shell (not a Settings process)
    tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null | grep -q ' -c lme-shell '
}
tree_of() {  # $1 = pid; prints the pid and every descendant
    local child
    echo "$1"
    for child in $(cat "/proc/$1/task/$1/children" 2>/dev/null); do tree_of "$child"; done
}
bar_present() { "$NIRI" msg --json layers 2>/dev/null | grep -q '"lme-bar"'; }
arm_retry() {  # a new dead-man timer that runs this script again in a minute
    local retry="${TIMER:+${TIMER}-}retry-$(date +%s)"
    if systemd-run --user --on-active=60 --unit="$retry" --timer-property=AccuracySec=1s \
            /bin/bash "$state/restore_shell.sh" "$state" >> "$state/events.log" 2>&1; then
        log "restore: retry timer $retry armed for 60 s"
    else
        log "restore: ERROR the retry timer could not be armed"
    fi
}

swap_at=$(stat -c %Y "$state/swapped" 2>/dev/null || echo 9999999999)
live=()       # the stand-in (to stop)
deployed=()   # deployed main shells
others=()     # Settings processes
for dir in /proc/[0-9]*; do
    pid=${dir#/proc/}
    is_shell "$pid" || continue
    if (( recorded > 0 )); then
        [[ "$pid" == "$recorded" ]] && live+=("$pid") || others+=("$pid")
    elif (( $(stat -c %Y "$dir" 2>/dev/null || echo 0) >= swap_at - 2 )); then
        live+=("$pid")
    else
        others+=("$pid")
    fi
done
for pid in "${others[@]+"${others[@]}"}"; do is_main "$pid" && deployed+=("$pid"); done
settings=()
for pid in "${others[@]+"${others[@]}"}"; do is_main "$pid" || settings+=("$pid"); done
log "restore: stand-in=${live[*]:-none} deployed shells=${deployed[*]:-none} settings=${settings[*]:-none}"

stop_live() {  # stops the stand-in
    # A scope is only stopped when it is one of niri's own or a transient run unit; any
    # other unit may hold unrelated processes, so such a shell is signalled directly.
    local pid unit
    local -a units=() direct=() alive=()
    for pid in "${live[@]}"; do
        unit=$(awk -F/ '{print $NF}' "/proc/$pid/cgroup" 2>/dev/null | tail -1)
        if [[ "$unit" == app-niri-*.scope || "$unit" == run-*.scope || "$unit" == lme-perf-* ]]; then units+=("$unit"); else direct+=("$pid"); fi
    done
    if (( ${#units[@]} )); then
        for unit in $(printf '%s\n' "${units[@]}" | sort -u); do
            log "restore: systemctl --user stop $unit"
            systemctl --user stop --no-block "$unit" 2>/dev/null
        done
    fi
    if (( ${#direct[@]} )); then
        log "restore: SIGTERM ${direct[*]} (and their children)"
        for pid in "${direct[@]}"; do tree_of "$pid"; done | sort -u | while read -r pid; do kill -TERM "$pid" 2>/dev/null; done
    fi
    local _
    for _ in $(seq 40); do
        alive=()
        for pid in "${live[@]}"; do [[ -d "/proc/$pid" ]] && alive+=("$pid"); done
        (( ${#alive[@]} == 0 )) && return 0
        sleep 0.25
    done
    for pid in "${alive[@]}"; do
        log "restore: SIGKILL $pid"
        kill -KILL "$pid" 2>/dev/null
    done
}

# 1. Stop the stand-in. The lock screen wins: a shell that may be showing it is left alone
#    (an empty answer counts as "may": a frozen shell cannot say that it is unlocked).
left_running=false
if (( ${#live[@]} )); then
    lock_status=$(timeout 10 "$QS" -c lme-shell ipc call lock status 2>/dev/null </dev/null | tail -1)
    log "restore: lock status (harness shell)=${lock_status:-no answer}"
    # `$force` is a command here on purpose: inside [[ ]] the word "false" is a true string.
    if [[ "$lock_status" == unlocked ]] || $force; then
        [[ "$lock_status" == unlocked ]] || log "restore: --force, although the lock state is ${lock_status:-unknown}"
        if $dry; then log "restore: dry run, would stop ${live[*]}"; else stop_live; fi
    else
        log "restore: the harness shell may show the lock screen, leaving it running"
        left_running=true
    fi
fi

# 2. Symlink and config files back to the recorded state.
if [[ -L "$LINK" && "$(readlink -f "$LINK")" == "$ORIGINAL" ]]; then
    log "restore: symlink already points at the original"
elif $dry; then
    log "restore: dry run, symlink -> $ORIGINAL (now: $(readlink "$LINK" 2>/dev/null))"
else
    tmp=$(mktemp -u "$LINK.perf.XXXXXX")
    if ln -s "$ORIGINAL" "$tmp" && mv -T "$tmp" "$LINK"; then
        log "restore: symlink -> $ORIGINAL"
    else
        rm -f "$tmp"
        log "restore: ERROR restoring the symlink"
    fi
fi
if [[ -f "$state/files" ]]; then
    # A file that differs from the snapshot was written during the swap: by the stand-in (a
    # settings migration) or, worst case, by the owner. The snapshot goes back, and the version
    # that was live is kept under after/, so nothing of the owner's can be lost.
    while IFS= read -r rel; do
        [[ -n "$rel" ]] || continue
        cmp -s "$state/snap/$rel" "$HOME/$rel" && continue
        if $dry; then log "restore: dry run, would restore $rel"; continue; fi
        if [[ -f "$state/snap/$rel" ]]; then
            if [[ -f "$HOME/$rel" ]]; then
                mkdir -p "$state/after/$(dirname "$rel")" && cp -a "$HOME/$rel" "$state/after/$rel"
            fi
            mkdir -p "$HOME/$(dirname "$rel")" && cp -a "$state/snap/$rel" "$HOME/$rel" \
                && log "restore: restored $rel" || log "restore: ERROR restoring $rel"
        else
            log "restore: $rel did not exist before the swap, left in place"
        fi
    done < "$state/files"
fi

if $left_running; then
    # Not done. The locked shell stays (killing it would release the session lock); the symlink
    # and the files are already back. A new timer brings this script back.
    if $dry; then log "restore: dry run finished (would defer)"; exit 0; fi
    arm_retry
    log "restore: deferred, the lock screen may be shown"
    exit 3
fi

# 3. The deployed shell must be running again.
if (( ${#deployed[@]} )); then
    log "restore: deployed shell already running (${deployed[*]})"
elif [[ ${#start_argv[@]} -gt 0 && -x "${start_argv[0]}" ]]; then
    if $dry; then
        log "restore: dry run, would start ${start_argv[*]}"
    else
        # Two attempts: --no-duplicate makes the second one a no-op when the first succeeded late.
        for attempt in 1 2; do
            bar_present && break
            log "restore: starting ${start_argv[*]} (attempt $attempt)"
            "$NIRI" msg action spawn -- "${start_argv[@]}" >> "$state/events.log" 2>&1
            for _ in $(seq 30); do
                bar_present && break
                sleep 0.5
            done
        done
        bar_present && log "restore: deployed shell is up (lme-bar layer present)" \
            || log "restore: ERROR lme-bar layer not seen within 15 s of each start"
    fi
else
    log "restore: ERROR cannot start the deployed shell (start=$START)"
fi

if $dry; then log "restore: dry run finished"; exit 0; fi
if bar_present; then
    touch "$state/restored"
    if [[ -n "$TIMER" ]]; then systemctl --user stop "$TIMER.timer" 2>/dev/null; fi
    log "restore: done"
    exit 0
fi
# Not done: the stand-in is gone and the symlink is back, but the owner would have no shell.
# Come back a minute later, at most thirty times.
count=$(( $(cat "$state/retries" 2>/dev/null || echo 0) + 1 ))
echo "$count" > "$state/retries"
if (( count <= 30 )); then
    arm_retry
    log "restore: INCOMPLETE, the deployed shell is not up (attempt $count)"
else
    log "restore: GAVE UP after $count attempts, the deployed shell is not up"
fi
exit 1
