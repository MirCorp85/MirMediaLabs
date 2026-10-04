#!/usr/bin/env bash
# Register this copy of MIR MEDIA LABS with the desktop: app-menu entry + optional autostart.
# Usage: linux/install-launchers.sh [--autostart] [--uninstall]
set -e
ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
UNITS="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

if [[ " $* " == *" --uninstall "* ]]; then
  systemctl --user disable --now mirmedialabs.service 2>/dev/null || true
  rm -f "$APPS/mirmedialabs.desktop" "$UNITS/mirmedialabs.service"
  systemctl --user daemon-reload 2>/dev/null || true
  echo "Launchers removed."; exit 0
fi

chmod +x "$ROOT/start-mirmedialabs.sh" "$ROOT/stop-mirmedialabs.sh"
mkdir -p "$APPS" "$UNITS"
sed "s|@ROOT@|$ROOT|g" "$ROOT/linux/mirmedialabs.desktop.in" > "$APPS/mirmedialabs.desktop"
sed "s|@ROOT@|$ROOT|g" "$ROOT/linux/mirmedialabs.service.in" > "$UNITS/mirmedialabs.service"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
systemctl --user daemon-reload
if [[ " $* " == *" --autostart "* ]]; then
  systemctl --user enable --now mirmedialabs.service
  echo "Autostart on login enabled (systemctl --user status mirmedialabs)."
fi
echo "Installed: app menu entry 'MIR MEDIA LABS'."
