#!/usr/bin/env bash
# Builds the compiled Linux edition of MIR MEDIA LABS (run ON Linux x86_64 — Nuitka can't cross-compile).
#   installer/build_linux.sh [--bump] [--public] [--update-url URL] [--publish --notes "what changed"]
#
#   dist/MirMediaLabs-<ver>-linux-x86_64.tar.gz
#     MirMediaLabs/app/MirMediaLabs    server + launcher, compiled by Nuitka (no .py ships, web UI embedded)
#     MirMediaLabs/install.sh          per-user installer (~/.local/share/MirMediaLabs, menu entry, autostart)
# Needs: curl, gcc, patchelf. uv + Python 3.12 are fetched into installer/build-linux/ on first run.
set -euo pipefail
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
ROOT="$(dirname "$HERE")"
BUILD="$HERE/build-linux"
TOOLS="$BUILD/tools"
PY="$BUILD/nvenv/bin/python"
BUMP=0; PUBLIC=0; PUBLISH=0; NOTES=""; URL="${MML_UPDATE_URL:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --bump) BUMP=1 ;;
    --publish) PUBLISH=1 ;;
    --notes) NOTES="$2"; shift ;;
    --public) PUBLIC=1 ;;
    --update-url) URL="$2"; shift ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
  shift
done
[ "$PUBLIC" = 1 ] && URL="-"
if [ -z "$URL" ] && [ -f "$HERE/signing/update_url.txt" ]; then
  URL="$(tr -d '[:space:]' < "$HERE/signing/update_url.txt")"
fi
[ -z "$URL" ] && URL="-"              # no channel configured → auto-update off
export NUITKA_CACHE_DIR="$TOOLS/nuitka-cache" PYTHONUTF8=1

for t in curl gcc patchelf; do
  command -v "$t" >/dev/null || { echo "missing $t (sudo apt install curl build-essential patchelf)"; exit 1; }
done

# 0. build venv: Python 3.12 + Nuitka
if [ ! -x "$PY" ]; then
  mkdir -p "$TOOLS"
  UV="$(command -v uv || true)"
  if [ -z "$UV" ]; then
    [ -x "$TOOLS/uv" ] || curl -LsSf https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz \
      | tar -xz -C "$TOOLS" --strip-components=1
    UV="$TOOLS/uv"
  fi
  export UV_PYTHON_INSTALL_DIR="$TOOLS/python" UV_CACHE_DIR="$TOOLS/uvcache"
  "$UV" venv "$BUILD/nvenv" --python 3.12 --managed-python
  "$UV" pip install --python "$PY" nuitka ordered-set zstandard flask requests cryptography qrcode pillow
fi
[ -f "$HERE/pc_version.json" ] || echo '{"version": "1.0.0"}' > "$HERE/pc_version.json"
[ "$BUMP" = 1 ] && "$PY" "$HERE/build_tool.py" bump
VER="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$HERE/pc_version.json")"
echo "== MIR MEDIA LABS Linux v$VER"

# 1. keys + staged source (server code + generated _buildinfo / _assets) — same as Windows
"$PY" "$HERE/build_tool.py" keys
SRC="$BUILD/src"
"$PY" "$HERE/build_tool.py" stage "$SRC" "$URL"

# 2. compile (standalone folder)
APPOUT="$BUILD/appout"
rm -rf "$APPOUT"
"$PY" -m nuitka --assume-yes-for-downloads --standalone --deployment --lto=yes \
  --python-flag=no_docstrings --python-flag=no_asserts \
  --nofollow-import-to=imageio_ffmpeg --nofollow-import-to=tkinter --nofollow-import-to=PIL \
  --output-filename=MirMediaLabs --output-dir="$APPOUT" "$SRC/app_main.py"

# 3. package: app + installer + icon (never data/, never source)
PKG="$BUILD/pkg/MirMediaLabs"
rm -rf "$BUILD/pkg"
mkdir -p "$PKG/updates"
cp -r "$APPOUT/app_main.dist" "$PKG/app"
cp "$ROOT/linux/install.sh" "$PKG/install.sh"
cp "$ROOT/linux/engine_setup.py" "$PKG/engine_setup.py"
cp "$ROOT/MirMediaLabs-icon-1024.png" "$PKG/"
for f in LICENSE NOTICE; do [ -f "$ROOT/$f" ] && cp "$ROOT/$f" "$PKG/"; done
if [ "$PUBLIC" = 0 ]; then
  for f in version.json MirMediaLabs.apk; do [ -f "$ROOT/updates/$f" ] && cp "$ROOT/updates/$f" "$PKG/updates/"; done
fi
printf '{"version": "%s", "platform": "linux-x86_64"}\n' "$VER" > "$PKG/build.json"
chmod +x "$PKG/install.sh" "$PKG/app/MirMediaLabs"
mkdir -p "$ROOT/dist"
OUT="$ROOT/dist/MirMediaLabs-$VER-linux-x86_64.tar.gz"
tar -C "$BUILD/pkg" -czf "$OUT" MirMediaLabs
echo "built $OUT ($(du -h "$OUT" | cut -f1))"

# 4. publish to the update channel (signs linux.json into updates/pc/, beside the Windows version.json)
if [ "$PUBLISH" = 1 ]; then "$PY" "$HERE/build_tool.py" publish-linux "$OUT" "$NOTES"; fi
