# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 LBlab
"""Tests for dial_core (no GTK, no real input devices needed).  Run: python3 tests/test_core.py"""
import importlib
import os
import socket
import struct
import sys
import tempfile
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# tiny stand-in for python-evdev so the tests run anywhere
evdev = types.ModuleType("evdev")
ecodes = types.ModuleType("evdev.ecodes")
for name, val in dict(KEY_LEFTCTRL=29, KEY_LEFTSHIFT=42, KEY_Z=44, KEY_VOLUMEUP=115,
                      KEY_PAGEDOWN=109, KEY_NEXTSONG=163).items():
    setattr(ecodes, name, val)
evdev.ecodes = ecodes
sys.modules.setdefault("evdev", evdev)
sys.modules.setdefault("evdev.ecodes", ecodes)

os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
import dial_core as c  # noqa: E402
importlib.reload(c)


def test_combos():
    assert c.parse_combo("ctrl+shift+z") == [29, 42, 44]
    assert c.parse_combo("volumeup") == [115]
    assert c.parse_combo("next") == [163]
    assert c.parse_combo("") == []
    for bad in ("ctrl+", "foobar"):
        try:
            c.parse_combo(bad)
        except ValueError:
            continue
        raise AssertionError("should have failed: " + bad)


def test_config():
    n = c.normalize({"functions": [{"id": "a", "name": "A", "type": "keys"}],
                     "default": {"menu": ["a", "zz"], "start": "zz"},
                     "apps": {"Firefox": {"menu": ["nope"]}}})
    assert n["default"] == {"start": "a", "menu": ["a"]}
    assert list(n["apps"]) == ["firefox"] and n["apps"]["firefox"]["menu"] == ["a"]
    assert c.normalize("broken") == c.normalize(None)
    cfg = c.normalize(None)
    cfg["apps"]["gimp"] = dict(cfg["default"])
    c.save_config(cfg)
    assert c.load_config()["apps"]["gimp"]["start"] == "scroll"
    assert c.config_mtime() > 0 and c.cw_sign(cfg) == -1


def _msg(obj, op, payload=b""):
    return struct.pack("=II", obj, ((8 + len(payload)) << 16) | op) + payload


def _ws(s):
    b = s.encode() + b"\0"
    return struct.pack("=I", len(b)) + b + b"\0" * (-len(b) % 4)


def test_toplevel_tracker():
    changes = []
    tr = c.ToplevelTracker(on_change=lambda: changes.append(1))
    a, b = socket.socketpair()
    tr.connect(a)
    b.setblocking(True)
    assert b.recv(100) == _msg(1, 1, struct.pack("=I", 2)) + _msg(1, 0, struct.pack("=I", 3))
    b.sendall(_msg(2, 0, struct.pack("=I", 7) + _ws("wl_compositor") + struct.pack("=I", 4)))
    b.sendall(_msg(2, 0, struct.pack("=I", 9) + _ws("zwlr_foreign_toplevel_manager_v1")
                   + struct.pack("=I", 3)))
    tr.pump()
    assert b.recv(200) == _msg(2, 0, struct.pack("=I", 9)
                               + _ws("zwlr_foreign_toplevel_manager_v1") + struct.pack("=II", 3, 4))
    h1, h2 = 0xFF000001, 0xFF000002
    b.sendall(_msg(4, 0, struct.pack("=I", h1)) + _msg(h1, 1, _ws("firefox"))
              + _msg(h1, 0, _ws("Page")) + _msg(h1, 4, struct.pack("=II", 4, 0)) + _msg(h1, 5))
    b.sendall(_msg(4, 0, struct.pack("=I", h2)) + _msg(h2, 1, _ws("org.gimp.GIMP"))
              + _msg(h2, 4, struct.pack("=II", 4, 2)) + _msg(h2, 5))
    tr.pump()
    assert tr.active_app == "org.gimp.GIMP"
    assert tr.open_apps() == ["firefox", "org.gimp.GIMP"]
    chunk = (_msg(h2, 4, struct.pack("=II", 0, 0)) + _msg(h2, 5)
             + _msg(h1, 4, struct.pack("=II", 4, 2)) + _msg(h1, 5))
    b.sendall(chunk[:13])
    tr.pump()
    b.sendall(chunk[13:])
    tr.pump()
    assert tr.active_app == "firefox"
    b.sendall(_msg(h1, 6))
    tr.pump()
    assert tr.active_app is None and tr.open_apps() == ["org.gimp.GIMP"] and len(changes) >= 4


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
