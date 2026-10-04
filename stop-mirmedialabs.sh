#!/usr/bin/env bash
# Stop the MIR MEDIA LABS server (only the process listening on :5400 - never MirOS or ComfyUI).
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PORT="${MML_PORT:-5400}"
if systemctl --user is-active --quiet mirmedialabs.service 2>/dev/null; then
  systemctl --user stop mirmedialabs.service
fi
PIDS="$(ss -ltnpH "sport = :$PORT" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u)"
[ -z "$PIDS" ] && [ -f "$HERE/data/server.pid" ] && PIDS="$(cat "$HERE/data/server.pid")"
for p in $PIDS; do kill "$p" 2>/dev/null; done
sleep 1
for p in $PIDS; do kill -9 "$p" 2>/dev/null; done
rm -f "$HERE/data/server.pid"
echo "MIR MEDIA LABS stopped."
