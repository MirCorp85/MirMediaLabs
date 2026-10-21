#!/usr/bin/env bash
# MIR MEDIA LABS - set up a cloned repository on Linux (beta): the app's own venv + the render engine
# (headless ComfyUI + PyTorch for NVIDIA CUDA or AMD ROCm, Ollama, models), all inside this folder.
#   ./setup.sh                       guided
#   ./setup.sh --yes                 recommended choices, no questions
#   ./setup.sh --components image,ace --muse none --skip-models
set -euo pipefail
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null || { echo "Python 3.10+ is needed (e.g. sudo apt install python3 python3-venv)."; exit 1; }
echo "== App packages -> $HERE/runtime/app"
[ -x "$HERE/runtime/app/bin/python" ] || "$PY" -m venv "$HERE/runtime/app"
"$HERE/runtime/app/bin/python" -m pip install --upgrade pip >/dev/null
"$HERE/runtime/app/bin/python" -m pip install -r "$HERE/requirements.txt"
mkdir -p "$HERE/data/logs"
echo "== Render engine"
"$PY" "$HERE/linux/engine_setup.py" --dir "$HERE" "$@"
echo
echo "Done. Start the studio with ./start-mirmedialabs.sh  ->  http://127.0.0.1:5400"
