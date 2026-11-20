# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 LBlab
"""
Shared parts of the daemon (asus_dial_overlay.py) and the settings GUI (asus_dial_config.py):
  - JSON configuration (~/.config/asus-dial/config.json)
  - parsing of key shortcuts ("ctrl+shift+z")
  - foreground-app detection on Wayland (wlr-foreign-toplevel-management, supported by
    labwc and other wlroots compositors) with a minimal built-in client: no extra packages.
"""
import copy
import json
import os
import socket
import struct

from dial_i18n import tr

CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "asus-dial")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "version": 1,
    "settings": {
        "invert_rotation": True,   # True = clockwise is the opposite of the Dial's +1 value
        "step_ticks": 1,           # dial ticks needed to move one item in the ring menu
        "menu_timeout_ms": 4000,
        "flash_ms": 1200,
    },
    # Function types:
    #   "wheel"   mouse wheel, optionally with held keys
    #             axis: "v" vertical / "h" horizontal; mods: e.g. "ctrl"
    #             follow_rotation: True = clockwise -> up/right,
    #                              False = same as the Dial's native scroll
    #             invert: reverses the result
    #   "keys"    cw / ccw = shortcut for clockwise / counter-clockwise (e.g. "ctrl+z")
    #   "command" cw / ccw = command to run (e.g. "playerctl next"), no shell
    # Built-in names are English; they are translated when displayed (see dial_i18n).
    "functions": [
        {"id": "scroll", "name": "Scroll", "type": "wheel", "axis": "v",
         "mods": "", "follow_rotation": False, "invert": False},
        {"id": "hscroll", "name": "Horizontal scroll", "type": "wheel", "axis": "h",
         "mods": "", "follow_rotation": True, "invert": False},
        {"id": "volume", "name": "Volume", "type": "keys",
         "cw": "volumeup", "ccw": "volumedown"},
        {"id": "brightness", "name": "Brightness", "type": "keys",
         "cw": "brightnessup", "ccw": "brightnessdown"},
        {"id": "zoom", "name": "Zoom", "type": "wheel", "axis": "v",
         "mods": "ctrl", "follow_rotation": True, "invert": False},
        {"id": "tabs", "name": "Tabs", "type": "keys",
         "cw": "ctrl+pagedown", "ccw": "ctrl+pageup"},
    ],
    "default": {"start": "scroll",
                "menu": ["scroll", "hscroll", "volume", "brightness", "zoom", "tabs"]},
    "apps": {},   # "app-id": {"start": "id", "menu": ["id", ...]}
}


# ------------------------------------------------------------- configuration
def _fix_profile(p, ids):
    menu = []
    if isinstance(p, dict) and isinstance(p.get("menu"), list):
        menu = [i for i in p["menu"] if i in ids]
    if not menu:
        menu = [i for i in DEFAULT_CONFIG["default"]["menu"] if i in ids] or sorted(ids)
    start = p.get("start") if isinstance(p, dict) else None
    if start not in menu:
        start = menu[0]
    return {"start": start, "menu": menu}


def normalize(data):
    """Complete and clean up a configuration (even a partial or damaged one)."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if not isinstance(data, dict):
        return cfg
    st = data.get("settings")
    if isinstance(st, dict):
        for k in cfg["settings"]:
            if k in st and isinstance(st[k], type(cfg["settings"][k])):
                cfg["settings"][k] = st[k]
    funcs = data.get("functions")
    if isinstance(funcs, list):
        good = [f for f in funcs if isinstance(f, dict) and f.get("id")
                and f.get("type") in ("keys", "wheel", "command")]
        if good:
            cfg["functions"] = good
    ids = {f["id"] for f in cfg["functions"]}
    cfg["default"] = _fix_profile(data.get("default"), ids)
    apps = data.get("apps")
    cfg["apps"] = {}
    if isinstance(apps, dict):
        for key, prof in apps.items():
            if isinstance(key, str) and key.strip():
                cfg["apps"][key.strip().lower()] = _fix_profile(prof, ids)
    return cfg


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            return normalize(json.load(fh))
    except FileNotFoundError:
        return normalize(None)
    except (OSError, ValueError) as exc:
        print(tr("Unreadable configuration ({exc}): using defaults.", exc=exc))
        return normalize(None)


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)


def config_mtime():
    try:
        return os.stat(CONFIG_PATH).st_mtime_ns
    except OSError:
        return 0


def cw_sign(cfg):
    """The REL_WHEEL value that means clockwise."""
    return -1 if cfg["settings"].get("invert_rotation") else 1


# --------------------------------------------------------------- shortcuts
_MODS = {"ctrl": "LEFTCTRL", "control": "LEFTCTRL", "shift": "LEFTSHIFT",
         "alt": "LEFTALT", "altgr": "RIGHTALT", "super": "LEFTMETA",
         "meta": "LEFTMETA", "win": "LEFTMETA"}
_KEYS = {"plus": "KPPLUS", "minus": "MINUS", "equal": "EQUAL", "return": "ENTER",
         "del": "DELETE", "pgup": "PAGEUP", "pgdn": "PAGEDOWN", "escape": "ESC",
         "bracketleft": "LEFTBRACE", "bracketright": "RIGHTBRACE", "period": "DOT",
         "next": "NEXTSONG", "prev": "PREVIOUSSONG", "previous": "PREVIOUSSONG",
         "playpause": "PLAYPAUSE", "stop": "STOPCD"}


def parse_combo(text):
    """'ctrl+shift+z' -> [KEY_LEFTCTRL, KEY_LEFTSHIFT, KEY_Z]. Empty string -> []."""
    from evdev import ecodes as e
    text = (text or "").strip()
    if not text:
        return []
    codes = []
    for part in text.replace(" ", "").split("+"):
        low = part.lower()
        if not low:
            raise ValueError(tr("invalid shortcut: '{text}'", text=text))
        name = _MODS.get(low) or _KEYS.get(low) or low.upper()
        code = getattr(e, "KEY_" + name, None)
        if not isinstance(code, int):
            raise ValueError(tr("unknown key: '{part}'", part=part))
        codes.append(code)
    return codes


# ------------------------------------- foreground app (Wayland / wlr protocol)
def _wstr(s):
    b = s.encode() + b"\0"
    return struct.pack("=I", len(b)) + b + b"\0" * (-len(b) % 4)


def _read_str(body, off):
    n = struct.unpack_from("=I", body, off)[0]
    s = body[off + 4: off + 4 + max(n - 1, 0)].decode("utf-8", "replace")
    return s, off + 4 + ((n + 3) & ~3)


class ToplevelTracker:
    """Minimal Wayland client: keeps the list of windows and knows which one is active."""

    MANAGER = "zwlr_foreign_toplevel_manager_v1"

    def __init__(self, on_change=None):
        self.sock = None
        self.buf = b""
        self.next_id = 4          # 1 display, 2 registry, 3 callback
        self.kinds = {}           # object id -> "manager" | "handle"
        self.toplevels = {}       # id -> {"app_id", "title", "activated"}
        self.ok = False           # True once the compositor offers the protocol
        self.error = None
        self.on_change = on_change
        self._watch = None

    # -- connection
    def connect(self, sock=None):
        if sock is None:
            name = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
            path = name if name.startswith("/") else os.path.join(
                os.environ.get("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid()), name)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(path)
        sock.setblocking(False)
        self.sock = sock
        self._send(1, 1, struct.pack("=I", 2))    # wl_display.get_registry -> id 2
        self._send(1, 0, struct.pack("=I", 3))    # wl_display.sync -> id 3

    def attach_glib(self):
        from gi.repository import GLib
        self._watch = GLib.io_add_watch(
            self.sock.fileno(), GLib.PRIORITY_DEFAULT,
            GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._on_io)

    def _on_io(self, _fd, cond):
        from gi.repository import GLib
        if cond & (GLib.IO_HUP | GLib.IO_ERR):
            self.ok = False
            return False
        return self.pump()

    def pump(self):
        """Read and process whatever is available. False if the connection is closed."""
        try:
            while True:
                data = self.sock.recv(65536)
                if not data:
                    self.ok = False
                    return False
                self._feed(data)
        except BlockingIOError:
            return True
        except OSError as exc:
            self.error = str(exc)
            self.ok = False
            return False

    # -- protocol
    def _send(self, obj, opcode, payload=b""):
        self.sock.sendall(struct.pack("=II", obj, ((8 + len(payload)) << 16) | opcode) + payload)

    def _feed(self, data):
        self.buf += data
        while len(self.buf) >= 8:
            obj, so = struct.unpack_from("=II", self.buf, 0)
            size, op = so >> 16, so & 0xFFFF
            if size < 8:
                self.buf = b""
                self.error = "invalid Wayland message"
                return
            if len(self.buf) < size:
                return
            body, self.buf = self.buf[8:size], self.buf[size:]
            self._dispatch(obj, op, body)

    def _dispatch(self, obj, op, body):
        if obj == 1 and op == 0:                         # wl_display.error
            try:
                self.error = _read_str(body, 8)[0]
            except struct.error:
                self.error = "compositor error"
        elif obj == 2 and op == 0:                       # wl_registry.global
            name = struct.unpack_from("=I", body, 0)[0]
            iface, off = _read_str(body, 4)
            version = struct.unpack_from("=I", body, off)[0]
            if iface == self.MANAGER and not self.ok:
                mid = self.next_id
                self.next_id += 1
                self.kinds[mid] = "manager"
                self._send(2, 0, struct.pack("=I", name) + _wstr(iface)
                           + struct.pack("=II", min(version, 3), mid))
                self.ok = True
        elif self.kinds.get(obj) == "manager":
            if op == 0:                                  # toplevel(new_id)
                hid = struct.unpack_from("=I", body, 0)[0]
                self.kinds[hid] = "handle"
                self.toplevels[hid] = {"app_id": "", "title": "", "activated": False}
            elif op == 1:                                # finished
                self.ok = False
        elif self.kinds.get(obj) == "handle":
            tl = self.toplevels.get(obj)
            if tl is None:
                return
            if op == 0:
                tl["title"] = _read_str(body, 0)[0]
            elif op == 1:
                tl["app_id"] = _read_str(body, 0)[0]
            elif op == 4:                                # state(array)
                n = struct.unpack_from("=I", body, 0)[0]
                states = struct.unpack_from("=%dI" % (n // 4), body, 4)
                tl["activated"] = 2 in states            # 2 = activated
            elif op == 5:                                # done
                if self.on_change:
                    self.on_change()
            elif op == 6:                                # closed
                self.toplevels.pop(obj, None)
                self.kinds.pop(obj, None)
                try:
                    self._send(obj, 7)                   # destroy
                except OSError:
                    pass
                if self.on_change:
                    self.on_change()

    # -- results
    @property
    def active_app(self):
        for tl in self.toplevels.values():
            if tl["activated"]:
                return tl["app_id"] or None
        return None

    def open_apps(self):
        return sorted({tl["app_id"] for tl in self.toplevels.values() if tl["app_id"]})
