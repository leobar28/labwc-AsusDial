# labwc-AsusDial

**Vibe-coded** On-screen dial overlay and **per-app profiles** for the **ASUS Dial** (ProArt Studiobook and similar) on Linux / Wayland — built and tested on Fedora Budgie with the **labwc** compositor.

Press the Dial, a ring appears, turn it to pick a function (scroll, volume, brightness, zoom, tab switching, your own shortcuts or commands), press again to confirm. Each app can have its own set of functions.

> Unofficial community project. Not affiliated with or endorsed by ASUS or the labwc project.

## Features

- Circular overlay (GTK3 + gtk-layer-shell) similar to the Windows ProArt Creator Hub one
- Per-app profiles: the foreground app is detected through the `wlr-foreign-toplevel-management` protocol (no extra packages)
- Settings GUI: choose which functions appear in the ring, in which order and which one starts active, per app
- Custom functions: key shortcuts (e.g. `ctrl+z` / `ctrl+shift+z`), mouse wheel with modifiers (e.g. Ctrl+wheel), or shell-free commands (e.g. `playerctl next`)
- Rotation direction can be inverted
- The config file is reloaded automatically, no restart needed
- Interface in English and Italian: follows the system language (override with `ASUS_DIAL_LANG=en` or `it`)

## Status

**Beta.** Tested only on a **ProArt Studiobook 16 W7604**, Fedora Budgie (Wayland, labwc). Reports and patches for other models and compositors are welcome.

Per-app detection needs a compositor that implements `wlr-foreign-toplevel-management` (labwc, Sway, Hyprland, Wayfire, …). It will **not** work on GNOME/Mutter or KDE; there the daemon still runs, using only the default profile.

## Requirements (Fedora)

```bash
sudo dnf install python3-evdev python3-gobject python3-cairo gtk3 gtk-layer-shell
```

## Install

```bash
git clone https://github.com/leobar28/labwc-AsusDial.git
cd labwc-AsusDial

sudo bash setup-permissions.sh   # once: input group + /dev/uinput access, then log out and in
bash install.sh                # autostart entry + "ASUS Dial settings" in the app menu
```

If you use **Input Remapper** on the Dial, stop or disable its preset for "ASUS ProArt Dial": only one program can take exclusive control of the device.

## Usage

Run the daemon (autostart does this at login):

```bash
python3 asus_dial_overlay.py          # add --debug to print events and the detected app
```

Open the settings with `python3 asus_dial_config.py` (or from the app menu).

- **Turn** the Dial: runs the active function of the current app's profile
- **Press**: opens the ring; turn to choose, press again to confirm (it closes by itself after a few seconds)

To add a per-app profile, open the app first, then *Profiles → Add app…* and pick it from the list. You can also type the app-id; `--debug` prints it each time the focused window changes.

## Configuration

Stored in `~/.config/asus-dial/config.json` (edited by the GUI, but plain JSON). Function types:

| type | fields |
|------|--------|
| `keys` | `cw`, `ccw`: shortcut for clockwise / counter-clockwise, e.g. `"ctrl+z"`, `"volumeup"`, `"pagedown"` |
| `wheel` | `axis` (`v`/`h`), `mods` (e.g. `"ctrl"`), `follow_rotation`, `invert` |
| `command` | `cw`, `ccw`: command run at every tick, without a shell |

## How it works

The daemon grabs the Dial's evdev device, and re-emits the result through virtual uinput devices (a pointer for the wheel, a keyboard for keys). The overlay is a click-through layer-shell window. The foreground app comes from a small built-in Wayland client for `wlr-foreign-toplevel-management`.

## Troubleshooting

- *"Permission denied" on `/dev/input`* → run `setup-permissions.sh`, then log out and in.
- *Cannot grab the device* → another program (Input Remapper) is using it.
- *Overlay is a normal window / not on top* → your compositor lacks `layer-shell`; the daemon warns about it.
- *Wrong rotation direction* → *Settings → invert rotation*.
- *Pressing does nothing* → run with `--debug`; the Dial's button is expected as `BTN_MIDDLE` or `BTN_EXTRA`.
- Different device name? Edit `DEVICE_NAME` in `asus_dial_overlay.py` (see `sudo evtest`).

## Tests

```bash
python3 tests/test_core.py
python3 tests/test_i18n.py
```

## License

GPL-3.0-or-later — see [LICENSE](LICENSE). Copyright (C) 2026 LBlab.
