#!/usr/bin/env bash
# Adds an autostart entry for the daemon and an app-menu entry for the settings GUI.
# Run as your normal user (no sudo):  bash install.sh
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$HOME/.config/autostart" "$HOME/.local/share/applications"
cat > "$HOME/.config/autostart/labwc-asus-dial.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=labwc-AsusDial
Comment=ASUS Dial overlay and per-app profiles
Exec=python3 "$DIR/asus_dial_overlay.py"
Path=$DIR
Terminal=false
DESKTOP
cat > "$HOME/.local/share/applications/labwc-asus-dial-config.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=ASUS Dial settings
Comment=Functions and per-app profiles for the ASUS Dial
Exec=python3 "$DIR/asus_dial_config.py"
Path=$DIR
Terminal=false
Categories=Settings;
DESKTOP
echo "Installed. The daemon will start at your next login (or run: python3 $DIR/asus_dial_overlay.py &)."
