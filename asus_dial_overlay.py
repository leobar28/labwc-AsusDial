#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 LBlab
"""
labwc-AsusDial daemon: ring overlay + per-app profiles for the ASUS Dial (Wayland).

  - turning the Dial runs the active function of the foreground app's profile
  - press the Dial       -> a ring appears, turn to pick a function
  - press again          -> confirm; the ring closes
  - no action for a few seconds in the menu -> the ring closes, the previous function stays

Functions, per-app profiles and rotation direction are set with asus_dial_config.py
(~/.config/asus-dial/config.json is re-read automatically, no restart needed).

Try it:   python3 asus_dial_overlay.py --debug
(--debug prints the Dial events and the detected app with the profile in use)

Fedora dependencies:
  sudo dnf install python3-evdev python3-gobject python3-cairo gtk3 gtk-layer-shell
"""
import math
import os
import shlex
import signal
import subprocess
import sys
import time

import cairo
import evdev
import gi
from evdev import UInput, ecodes as e

gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import GLib, Gtk, Pango, PangoCairo  # noqa: E402

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell  # noqa: E402
except (ValueError, ImportError):
    GtkLayerShell = None

from dial_core import (ToplevelTracker, config_mtime, cw_sign, load_config,  # noqa: E402
                       parse_combo)
from dial_i18n import display_name, tr  # noqa: E402

DEVICE_NAME = "ASUS ProArt Dial"            # exact device name as shown by evtest
BUTTON_CODES = {e.BTN_MIDDLE, e.BTN_EXTRA}  # buttons that count as a "press"
DEBUG = "--debug" in sys.argv

SIZE = 300         # overlay window side (px)
R_OUT, R_IN = 125, 82


# ------------------------------------------------------------------- overlay
def layer_shell_ok():
    if GtkLayerShell is None:
        return False
    fn = getattr(GtkLayerShell, "is_supported", None)
    return bool(fn()) if fn else True


class Overlay(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.mode = None          # "menu" | "flash"
        self.names = []
        self.sel = 0
        self.title_text = ""
        self.subtitle = ""
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_accept_focus(False)
        self.set_skip_taskbar_hint(True)
        self.set_default_size(SIZE, SIZE)
        visual = self.get_screen().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.connect("draw", self.on_draw)
        self.connect("realize", self.on_realize)

        if layer_shell_ok():
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            if hasattr(GtkLayerShell, "set_keyboard_mode"):
                GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)
            else:
                GtkLayerShell.set_keyboard_interactivity(self, False)
            # no anchors = centred on the screen
        else:
            print(tr("Warning: layer-shell is not available, using a normal window."),
                  file=sys.stderr)
            self.set_keep_above(True)
            self.set_position(Gtk.WindowPosition.CENTER)

    def on_realize(self, _w):
        # click-through window
        self.get_window().input_shape_combine_region(cairo.Region(), 0, 0)

    def open_menu(self, names, sel, subtitle):
        self.mode, self.names, self.sel, self.subtitle = "menu", names, sel, subtitle
        self.title_text = names[sel]
        self.show_all()
        self.queue_draw()

    def move_menu(self, sel):
        self.sel = sel
        self.title_text = self.names[sel]
        self.queue_draw()

    def flash(self, name, subtitle):
        self.mode, self.title_text, self.subtitle = "flash", name, subtitle
        self.show_all()
        self.queue_draw()

    def close_overlay(self):
        self.mode = None
        self.hide()

    def on_draw(self, _w, cr):
        cx = cy = SIZE / 2
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        # background disc
        cr.arc(cx, cy, R_OUT + 14, 0, 2 * math.pi)
        cr.set_source_rgba(0.07, 0.07, 0.09, 0.85)
        cr.fill()

        accent = (0.30, 0.62, 1.0, 1.0)
        if self.mode == "menu" and self.names:
            n = len(self.names)
            gap = 0.07 if n > 1 else 0.0
            for i in range(n):
                a0 = -math.pi / 2 + i * 2 * math.pi / n + gap / 2
                a1 = a0 + 2 * math.pi / n - gap
                if n == 1:
                    a1 = a0 + 2 * math.pi - 0.001
                cr.new_path()
                cr.arc(cx, cy, R_OUT, a0, a1)
                cr.arc_negative(cx, cy, R_IN, a1, a0)
                cr.close_path()
                cr.set_source_rgba(*(accent if i == self.sel else (1, 1, 1, 0.16)))
                cr.fill()
        else:
            cr.arc(cx, cy, (R_OUT + R_IN) / 2, 0, 2 * math.pi)
            cr.set_line_width(R_OUT - R_IN)
            cr.set_source_rgba(accent[0], accent[1], accent[2], 0.9)
            cr.stroke()

        # function name in the middle, profile name below it
        width = int((R_IN * 2 - 16) * Pango.SCALE)
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription("Sans Bold 14"))
        layout.set_width(width)
        layout.set_alignment(Pango.Alignment.CENTER)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_text(self.title_text, -1)
        _tw, th = layout.get_pixel_size()
        y = cy - th / 2 - (8 if self.subtitle else 0)
        cr.set_source_rgba(1, 1, 1, 1)
        cr.move_to(cx - (R_IN - 8), y)
        PangoCairo.show_layout(cr, layout)

        if self.subtitle:
            sub = PangoCairo.create_layout(cr)
            sub.set_font_description(Pango.FontDescription("Sans 9"))
            sub.set_width(width)
            sub.set_alignment(Pango.Alignment.CENTER)
            sub.set_ellipsize(Pango.EllipsizeMode.END)
            sub.set_text(self.subtitle, -1)
            cr.set_source_rgba(1, 1, 1, 0.6)
            cr.move_to(cx - (R_IN - 8), y + th + 4)
            PangoCairo.show_layout(cr, sub)
        return False


# ----------------------------------------------------------------------- app
class DialApp:
    def __init__(self):
        self.dev = self.find_device()
        try:
            self.dev.grab()
        except OSError as exc:
            sys.exit(tr("Cannot take control of the Dial ({exc}).\n"
                        "If Input Remapper has an active preset on this device, "
                        "stop it and try again.", exc=exc))
        os.set_blocking(self.dev.fd, False)

        self.ptr = UInput(
            {e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL, e.REL_HWHEEL,
                        e.REL_WHEEL_HI_RES, e.REL_HWHEEL_HI_RES],
             e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE]},
            name="ASUS Dial overlay (virtual pointer)")
        self.kbd = UInput({e.EV_KEY: list(range(1, 249))},
                          name="ASUS Dial overlay (virtual keys)")

        self.overlay = Overlay()
        self.chosen = {}          # app -> function id picked from the menu (until the daemon stops)
        self.menu_open = False
        self.menu_key = ""
        self.menu_items = []
        self.sel = 0
        self.acc = 0
        self.last_press = 0.0
        self._tid = 0
        self._last_app = object()
        self._bad = set()
        self.load()

        self.tracker = ToplevelTracker()
        try:
            self.tracker.connect()
            self.tracker.attach_glib()
        except OSError as exc:
            print(tr("App detection not available ({exc}): using only the default profile.",
                     exc=exc))
            self.tracker = None

        GLib.io_add_watch(self.dev.fd, GLib.PRIORITY_DEFAULT,
                          GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.on_readable)
        GLib.timeout_add(1500, self.check_config)

    # ---- configuration
    def load(self):
        self.cfg = load_config()
        self.mtime = config_mtime()
        self.funcs = {f["id"]: f for f in self.cfg["functions"]}
        self.cw = cw_sign(self.cfg)
        self._bad.clear()
        if DEBUG:
            print("Configuration loaded; app profiles:", list(self.cfg["apps"]) or "none")

    def check_config(self):
        if config_mtime() != self.mtime:
            self.load()
        return True

    def settings(self, key):
        return self.cfg["settings"][key]

    # ---- profiles
    def app_key(self):
        app = (self.tracker.active_app if self.tracker and self.tracker.ok else None) or ""
        app = app.lower()
        if DEBUG and app != self._last_app:
            self._last_app = app
            label = app if app in self.cfg["apps"] else "default"
            print(f"Active app: {app or '(none)'} -> profile: {label}")
        return app

    def profile(self, key):
        return self.cfg["apps"].get(key) or self.cfg["default"]

    def label(self, key):
        return key if key in self.cfg["apps"] else tr("Default")

    def current_fid(self, key):
        p = self.profile(key)
        fid = self.chosen.get(key)
        return fid if fid in p["menu"] else p["start"]

    @staticmethod
    def find_device():
        denied = False
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
            except PermissionError:
                denied = True
                continue
            if dev.name == DEVICE_NAME:
                return dev
        if denied:
            sys.exit(tr("Permission denied on /dev/input/*: add your user to the 'input' "
                        "group (sudo usermod -aG input $USER), then log out and in."))
        sys.exit(tr('Device "{name}" not found.', name=DEVICE_NAME))

    # ---- output to the system
    def wheel(self, axis, d):
        hi = e.REL_WHEEL_HI_RES if axis == e.REL_WHEEL else e.REL_HWHEEL_HI_RES
        self.ptr.write(e.EV_REL, axis, d)
        self.ptr.write(e.EV_REL, hi, d * 120)
        self.ptr.syn()

    def combo(self, codes):
        for c in codes:
            self.kbd.write(e.EV_KEY, c, 1)
        for c in reversed(codes):
            self.kbd.write(e.EV_KEY, c, 0)
        self.kbd.syn()

    def run_function(self, fn, v):
        clockwise = (v > 0) == (self.cw > 0)
        try:
            if fn["type"] == "wheel":
                if fn.get("follow_rotation"):
                    d = 1 if clockwise else -1
                else:
                    d = 1 if v > 0 else -1
                if fn.get("invert"):
                    d = -d
                axis = e.REL_HWHEEL if fn.get("axis") == "h" else e.REL_WHEEL
                mods = parse_combo(fn.get("mods", ""))
                for m in mods:
                    self.kbd.write(e.EV_KEY, m, 1)
                self.kbd.syn()
                self.wheel(axis, d)
                for m in reversed(mods):
                    self.kbd.write(e.EV_KEY, m, 0)
                self.kbd.syn()
            elif fn["type"] == "keys":
                self.combo(parse_combo(fn.get("cw" if clockwise else "ccw", "")))
            elif fn["type"] == "command":
                cmd = fn.get("cw" if clockwise else "ccw", "").strip()
                if cmd:
                    subprocess.Popen(shlex.split(cmd), stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True)
        except (ValueError, OSError) as exc:
            if fn["id"] not in self._bad:       # warn only once per function
                self._bad.add(fn["id"])
                print(tr('Function "{name}": {exc}',
                         name=display_name(fn.get("name", fn["id"])), exc=exc),
                      file=sys.stderr)

    # ---- timers
    def _timer(self, ms, fn):
        if self._tid:
            GLib.source_remove(self._tid)
        self._tid = GLib.timeout_add(ms, self._fire, fn)

    def _fire(self, fn):
        self._tid = 0
        fn()
        return False

    # ---- Dial events
    def on_readable(self, _fd, cond):
        if cond & (GLib.IO_HUP | GLib.IO_ERR):
            Gtk.main_quit()
            return False
        try:
            for ev in self.dev.read():
                self.handle(ev)
        except BlockingIOError:
            pass
        except OSError:
            Gtk.main_quit()
            return False
        return True

    def handle(self, ev):
        if DEBUG and ev.type != e.EV_SYN:
            print(evdev.categorize(ev) if ev.type == e.EV_KEY else ev)
        if ev.type == e.EV_REL and ev.code == e.REL_WHEEL and ev.value:
            for _ in range(abs(ev.value)):
                self.on_rotate(1 if ev.value > 0 else -1)
        elif ev.type == e.EV_REL and ev.code == e.REL_HWHEEL and ev.value:
            self.wheel(e.REL_HWHEEL, 1 if ev.value > 0 else -1)
        elif ev.type == e.EV_KEY and ev.code in BUTTON_CODES and ev.value == 1:
            now = time.monotonic()
            if now - self.last_press > 0.15:      # debounce
                self.last_press = now
                self.on_press()

    def on_rotate(self, v):
        if not self.menu_open:
            key = self.app_key()
            fn = self.funcs.get(self.current_fid(key))
            if fn:
                self.run_function(fn, v)
            return
        self.acc += 1 if (v > 0) == (self.cw > 0) else -1
        if abs(self.acc) >= self.settings("step_ticks"):
            step = 1 if self.acc > 0 else -1
            self.acc = 0
            self.sel = (self.sel + step) % len(self.menu_items)
            self.overlay.move_menu(self.sel)
        self._timer(self.settings("menu_timeout_ms"), self.cancel_menu)

    def on_press(self):
        if not self.menu_open:
            key = self.app_key()
            self.menu_key = key
            self.menu_items = list(self.profile(key)["menu"])
            fid = self.current_fid(key)
            self.sel = self.menu_items.index(fid) if fid in self.menu_items else 0
            self.acc = 0
            self.menu_open = True
            names = [display_name(self.funcs[i]["name"]) for i in self.menu_items]
            self.overlay.open_menu(names, self.sel, self.label(key))
            self._timer(self.settings("menu_timeout_ms"), self.cancel_menu)
        else:
            self.menu_open = False
            fid = self.menu_items[self.sel]
            if fid not in self.funcs:       # function deleted while the menu was open
                self.overlay.close_overlay()
                return
            self.chosen[self.menu_key] = fid
            self.overlay.flash(display_name(self.funcs[fid]["name"]), self.label(self.menu_key))
            self._timer(self.settings("flash_ms"), self.overlay.close_overlay)

    def cancel_menu(self):
        self.menu_open = False
        self.overlay.close_overlay()

    def cleanup(self):
        for obj, fn in ((self.dev, "ungrab"), (self.ptr, "close"), (self.kbd, "close")):
            try:
                getattr(obj, fn)()
            except Exception:
                pass


def main():
    app = DialApp()
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        app.cleanup()


if __name__ == "__main__":
    main()
