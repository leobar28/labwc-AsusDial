#!/usr/bin/env bash
# One-time setup: lets your user read the Dial and create virtual input devices.
# Usage:  sudo bash setup-permissions.sh
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo: sudo bash setup-permissions.sh"; exit 1; }
USER_NAME="${SUDO_USER:?run it with sudo from your normal user account}"
usermod -aG input "$USER_NAME"
echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' \
  > /etc/udev/rules.d/99-labwc-asus-dial.rules
echo uinput > /etc/modules-load.d/labwc-asus-dial.conf
modprobe uinput
udevadm control --reload
udevadm trigger
echo "Done. Log out and back in so the 'input' group applies to your session."
