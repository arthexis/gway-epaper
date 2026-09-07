#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNDIR="$ROOT/.run"
PIDFILE="$RUNDIR/epaper.pid"
LOGFILE="$RUNDIR/epaper.log"
CONFIG=${EPAPER_CONFIG:-$ROOT/epaper.toml}
PYTHON=${PYTHON:-python3}

ensure_rundir() {
    mkdir -p "$RUNDIR"
}

is_running() {
    [ -f "$PIDFILE" ] || return 1
    pid=$(cat "$PIDFILE" 2>/dev/null || true)
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null
}

run_foreground() {
    cd "$ROOT"
    PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
        exec "$PYTHON" -c 'from gway_epaper.runtime import run_forever; import os; run_forever(os.environ["EPAPER_CONFIG_PATH"])'
}

start() {
    ensure_rundir
    if is_running; then
        echo "gway-epaper already running (pid $(cat "$PIDFILE"))"
        return 0
    fi
    rm -f "$PIDFILE"
    cd "$ROOT"
    EPAPER_CONFIG_PATH="$CONFIG" \
    PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
        nohup "$PYTHON" -c 'from gway_epaper.runtime import run_forever; import os; run_forever(os.environ["EPAPER_CONFIG_PATH"])' \
        >>"$LOGFILE" 2>&1 &
    pid=$!
    echo "$pid" > "$PIDFILE"
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        echo "gway-epaper started (pid $pid)"
    else
        rm -f "$PIDFILE"
        echo "gway-epaper failed to start; see $LOGFILE" >&2
        return 1
    fi
}

stop() {
    if ! is_running; then
        rm -f "$PIDFILE"
        echo "gway-epaper not running"
        return 0
    fi
    pid=$(cat "$PIDFILE")
    kill "$pid"
    i=0
    while kill -0 "$pid" 2>/dev/null; do
        i=$((i + 1))
        [ "$i" -lt 50 ] || break
        sleep 0.1
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo "gway-epaper did not stop cleanly (pid $pid)" >&2
        return 1
    fi
    rm -f "$PIDFILE"
    echo "gway-epaper stopped"
}

status() {
    if is_running; then
        echo "gway-epaper running (pid $(cat "$PIDFILE"))"
        return 0
    fi
    rm -f "$PIDFILE"
    echo "gway-epaper stopped"
    return 1
}

case "${1:-}" in
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    status) status ;;
    run)
        EPAPER_CONFIG_PATH="$CONFIG"
        export EPAPER_CONFIG_PATH
        run_foreground
        ;;
    *)
        echo "usage: $0 {start|stop|restart|status|run}" >&2
        exit 2
        ;;
esac
