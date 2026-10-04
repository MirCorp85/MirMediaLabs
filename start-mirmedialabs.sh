#!/usr/bin/env bash
# MIR MEDIA LABS - start the server (if not running) and open the studio window.
# Usage: ./start-mirmedialabs.sh [--server-only] [--foreground]
set -e
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PORT="${MML_PORT:-5400}"
PY="${MML_PYTHON:-python3}"
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
mkdir -p "$HERE/data/logs"

listening() { (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; }

if ! listening; then
  cd "$HERE/server"
  if [[ " $* " == *" --foreground "* ]]; then        # systemd runs us this way
    exec "$PY" -u medialab.py
  fi
  setsid "$PY" -u medialab.py >>"$HERE/data/logs/server_out.log" 2>>"$HERE/data/logs/server_err.log" < /dev/null &
  echo $! > "$HERE/data/server.pid"
  for _ in $(seq 1 40); do listening && break; sleep 0.25; done
fi
[[ " $* " == *" --server-only "* ]] && exit 0

URL="http://127.0.0.1:$PORT/?client=desktop"
PROFILE="$HERE/data/window"
for b in microsoft-edge google-chrome google-chrome-stable chromium chromium-browser brave-browser; do
  if command -v "$b" >/dev/null 2>&1; then
    setsid "$b" --app="$URL" --window-size=1500,950 --user-data-dir="$PROFILE" \
      --no-first-run --no-default-browser-check >/dev/null 2>&1 < /dev/null &
    exit 0
  fi
done
xdg-open "$URL" >/dev/null 2>&1 &
