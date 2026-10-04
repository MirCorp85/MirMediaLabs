#!/usr/bin/env bash
# MIR MEDIA LABS — Linux installer (ships inside the release tarball).
#   ./install.sh                 install/upgrade into ~/.local/share/MirMediaLabs + app-menu entry
#   ./install.sh --autostart     also start the server at login (systemd --user)
#   ./install.sh --dir PATH      install somewhere else
#   ./install.sh --engine [opts] also set up the render engine: headless ComfyUI + PyTorch (AMD ROCm or
#                                NVIDIA CUDA) + Ollama + models; extra opts go to engine_setup.py
#                                (e.g. --components image,ace  --muse none  --skip-models)
#   ./install.sh --update        (used by the in-app updater) swap the app, keep data, restart
#   ./install.sh --uninstall     remove app + launchers (keeps data/ unless --purge)
set -euo pipefail
PKG="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/MirMediaLabs"
AUTOSTART=0; UPDATE=0; UNINSTALL=0; PURGE=0; ENGINE=0; ENGINE_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DEST="$2"; shift ;;
    --autostart) AUTOSTART=1 ;;
    --update) UPDATE=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --purge) PURGE=1 ;;
    --engine) ENGINE=1 ;;
    --components|--muse) ENGINE_ARGS+=("$1" "$2"); shift ;;
    --no-ollama|--skip-models|--yes|-y) ENGINE_ARGS+=("$1") ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
  shift
done
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
UNITS="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT="$UNITS/mirmedialabs.service"

stop_app() {
  systemctl --user stop mirmedialabs.service 2>/dev/null || true
  if [ -x "$DEST/app/MirMediaLabs" ]; then "$DEST/app/MirMediaLabs" --stop 2>/dev/null || true; fi
}

if [ "$UNINSTALL" = 1 ]; then
  stop_app
  systemctl --user disable mirmedialabs.service 2>/dev/null || true
  rm -f "$APPS/mirmedialabs.desktop" "$UNIT"
  systemctl --user daemon-reload 2>/dev/null || true
  if [ "$PURGE" = 1 ]; then
    rm -rf "$DEST"; echo "MIR MEDIA LABS removed (including library)."
  else
    rm -rf "$DEST/app"; echo "MIR MEDIA LABS removed (your library is kept in $DEST/data)."
  fi
  exit 0
fi

[ "$(uname -m)" = x86_64 ] || { echo "This build is for x86_64 Linux."; exit 1; }
echo "Installing MIR MEDIA LABS -> $DEST"
WAS_RUNNING=0
if (exec 3<>/dev/tcp/127.0.0.1/5400) 2>/dev/null; then WAS_RUNNING=1; fi
stop_app
mkdir -p "$DEST/data/logs" "$DEST/updates"

# swap app/: new copy beside the old one, then rename
rm -rf "$DEST/app.new" "$DEST/app.old"
cp -r "$PKG/app" "$DEST/app.new"
if [ -d "$DEST/app" ]; then mv "$DEST/app" "$DEST/app.old"; fi
mv "$DEST/app.new" "$DEST/app"
rm -rf "$DEST/app.old"
cp "$PKG/MirMediaLabs-icon-1024.png" "$PKG/build.json" "$DEST/"
if [ "$PKG" != "$DEST" ]; then cp "$PKG/install.sh" "$DEST/install.sh"; fi
chmod +x "$DEST/install.sh" "$DEST/app/MirMediaLabs"
for f in "$PKG"/updates/*; do if [ -e "$f" ]; then cp "$f" "$DEST/updates/"; fi; done
for f in LICENSE NOTICE engine_setup.py; do if [ -f "$PKG/$f" ]; then cp "$PKG/$f" "$DEST/"; fi; done

# machine config — engine paths are added by the engine installer; user edits survive upgrades
if [ ! -f "$DEST/mml_config.json" ]; then
  FF="$(command -v ffmpeg || true)"
  if [ -n "$FF" ]; then FFJ="\"$FF\""; else FFJ="null"; fi
  printf '{"port": 5400, "ffmpeg": %s, "comfy_args": [], "installed": "%s"}\n' "$FFJ" "$(date '+%Y-%m-%d %H:%M')" \
    > "$DEST/mml_config.json"
fi

# launchers: app-menu entry + systemd user unit
mkdir -p "$APPS" "$UNITS"
cat > "$APPS/mirmedialabs.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=MIR MEDIA LABS
Comment=Local AI media studio (video, image, music)
Exec="$DEST/app/MirMediaLabs"
Icon=$DEST/MirMediaLabs-icon-1024.png
Terminal=false
Categories=AudioVideo;Graphics;
StartupWMClass=MirMediaLabs
DESK
cat > "$UNIT" <<SVC
[Unit]
Description=MIR MEDIA LABS server (:5400)
After=network-online.target

[Service]
Type=simple
ExecStart="$DEST/app/MirMediaLabs" --server
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
SVC
if command -v update-desktop-database >/dev/null; then update-desktop-database "$APPS" 2>/dev/null || true; fi
systemctl --user daemon-reload 2>/dev/null || true
if [ "$AUTOSTART" = 1 ]; then systemctl --user enable mirmedialabs.service; fi

if [ "$ENGINE" = 1 ]; then
  command -v python3 >/dev/null || { echo "python3 is required for the engine setup"; exit 1; }
  python3 "$DEST/engine_setup.py" --dir "$DEST" "${ENGINE_ARGS[@]}"
elif [ ! -f "$DEST/engine/ComfyUI/main.py" ] && [ "$UPDATE" = 0 ]; then
  echo "Render engine not installed yet - run: $DEST/install.sh --engine   (ComfyUI + PyTorch + Ollama + models, large download)"
fi

command -v ffmpeg >/dev/null || echo "note: ffmpeg not found - install it (e.g. sudo apt install ffmpeg) for clip tools."

if [ "$UPDATE" = 1 ] || [ "$WAS_RUNNING" = 1 ] || [ "$AUTOSTART" = 1 ]; then
  if systemctl --user is-enabled --quiet mirmedialabs.service 2>/dev/null; then
    systemctl --user restart mirmedialabs.service
  else
    "$DEST/app/MirMediaLabs" --server-only
  fi
fi
echo "Done. Launch 'MIR MEDIA LABS' from your app menu, or run: $DEST/app/MirMediaLabs"
