#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 LBlab
"""
labwc-AsusDial settings: functions, per-app profiles, rotation direction.
Saves to ~/.config/asus-dial/config.json; the daemon re-reads the file by itself.

Run:  python3 asus_dial_config.py
"""
import copy
import re
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from dial_core import (ToplevelTracker, load_config, normalize, parse_combo,  # noqa: E402
                       save_config)
from dial_i18n import display_name, tr  # noqa: E402

TYPE_LABELS = [("keys", tr("Keys / shortcuts")), ("wheel", tr("Mouse wheel")),
               ("command", tr("Command"))]


def describe(fn):
    t = fn.get("type")
    if t == "wheel":
        label = tr("Horizontal wheel") if fn.get("axis") == "h" else tr("Vertical wheel")
        return label + (f' + {fn["mods"]}' if fn.get("mods") else "")
    return tr("clockwise: {cw}  ·  counter-clockwise: {ccw}",
              cw=fn.get("cw") or "—", ccw=fn.get("ccw") or "—")


def message(parent, text, kind=Gtk.MessageType.ERROR):
    dlg = Gtk.MessageDialog(transient_for=parent, modal=True, message_type=kind,
                            buttons=Gtk.ButtonsType.OK, text=text)
    dlg.run()
    dlg.destroy()


def hint(markup):
    lab = Gtk.Label(xalign=0, wrap=True)
    lab.set_markup(f"<small>{markup}</small>")
    return lab


# ----------------------------------------------------------- function dialog
class FunctionDialog(Gtk.Dialog):
    def __init__(self, parent, fn=None):
        super().__init__(title=tr("Function"), transient_for=parent, modal=True)
        self.fn = fn
        self.add_button(tr("Cancel"), Gtk.ResponseType.CANCEL)
        self.add_button(tr("OK"), Gtk.ResponseType.OK)
        self.set_default_size(460, -1)
        box = self.get_content_area()
        box.set_spacing(8)
        box.set_border_width(12)

        row = Gtk.Box(spacing=8)
        row.pack_start(Gtk.Label(label=tr("Name:")), False, False, 0)
        self.name = Gtk.Entry()
        row.pack_start(self.name, True, True, 0)
        box.pack_start(row, False, False, 0)

        row = Gtk.Box(spacing=8)
        row.pack_start(Gtk.Label(label=tr("Type:")), False, False, 0)
        self.type = Gtk.ComboBoxText()
        for tid, label in TYPE_LABELS:
            self.type.append(tid, label)
        row.pack_start(self.type, True, True, 0)
        box.pack_start(row, False, False, 0)

        self.stack = Gtk.Stack()
        box.pack_start(self.stack, False, False, 0)

        # keys
        g = Gtk.Grid(row_spacing=6, column_spacing=8)
        self.k_cw, self.k_ccw = Gtk.Entry(), Gtk.Entry()
        for r, (lab, ent) in enumerate(((tr("Clockwise:"), self.k_cw),
                                        (tr("Counter-clockwise:"), self.k_ccw))):
            g.attach(Gtk.Label(label=lab, xalign=0), 0, r, 1, 1)
            ent.set_hexpand(True)
            g.attach(ent, 1, r, 1, 1)
        g.attach(hint(tr(
            "Examples: <b>ctrl+z</b>, <b>ctrl+shift+z</b>, <b>left</b>, <b>pagedown</b>, "
            "<b>volumeup</b>, <b>next</b> (next track). Leave empty to do nothing in that "
            "direction.")), 0, 2, 2, 1)
        self.stack.add_named(g, "keys")

        # wheel
        g = Gtk.Grid(row_spacing=6, column_spacing=8)
        g.attach(Gtk.Label(label=tr("Axis:"), xalign=0), 0, 0, 1, 1)
        self.w_axis = Gtk.ComboBoxText()
        self.w_axis.append("v", tr("Vertical"))
        self.w_axis.append("h", tr("Horizontal"))
        self.w_axis.set_hexpand(True)
        g.attach(self.w_axis, 1, 0, 1, 1)
        g.attach(Gtk.Label(label=tr("With keys held:"), xalign=0), 0, 1, 1, 1)
        self.w_mods = Gtk.Entry()
        g.attach(self.w_mods, 1, 1, 1, 1)
        self.w_follow = Gtk.CheckButton(
            label=tr("Follow rotation direction (clockwise = up / right)"))
        g.attach(self.w_follow, 0, 2, 2, 1)
        self.w_invert = Gtk.CheckButton(label=tr("Invert"))
        g.attach(self.w_invert, 0, 3, 2, 1)
        g.attach(hint(tr(
            "Held keys: e.g. <b>ctrl</b> (zoom), <b>alt</b>, <b>shift</b>, <b>ctrl+shift</b>. "
            "Without “Follow rotation direction” the wheel behaves like the Dial's normal "
            "scroll.")), 0, 4, 2, 1)
        self.stack.add_named(g, "wheel")

        # command
        g = Gtk.Grid(row_spacing=6, column_spacing=8)
        self.c_cw, self.c_ccw = Gtk.Entry(), Gtk.Entry()
        for r, (lab, ent) in enumerate(((tr("Clockwise:"), self.c_cw),
                                        (tr("Counter-clockwise:"), self.c_ccw))):
            g.attach(Gtk.Label(label=lab, xalign=0), 0, r, 1, 1)
            ent.set_hexpand(True)
            g.attach(ent, 1, r, 1, 1)
        g.attach(hint(tr(
            "Command run on every tick, without a shell. Examples: <b>playerctl next</b> or "
            "<b>wpctl set-volume @DEFAULT_AUDIO_SINK@ 2%+</b>.")), 0, 2, 2, 1)
        self.stack.add_named(g, "command")

        self.type.connect("changed", lambda c: c.get_active_id() and
                          self.stack.set_visible_child_name(c.get_active_id()))
        fn = fn or {"type": "keys", "name": "", "cw": "", "ccw": ""}
        self.name.set_text(display_name(fn.get("name", "")))
        self.k_cw.set_text(fn.get("cw", "") if fn["type"] == "keys" else "")
        self.k_ccw.set_text(fn.get("ccw", "") if fn["type"] == "keys" else "")
        self.c_cw.set_text(fn.get("cw", "") if fn["type"] == "command" else "")
        self.c_ccw.set_text(fn.get("ccw", "") if fn["type"] == "command" else "")
        self.w_axis.set_active_id(fn.get("axis", "v") if fn["type"] == "wheel" else "v")
        self.w_mods.set_text(fn.get("mods", "") if fn["type"] == "wheel" else "")
        self.w_follow.set_active(bool(fn.get("follow_rotation", True)))
        self.w_invert.set_active(bool(fn.get("invert", False)))
        box.show_all()
        self.type.set_active_id(fn["type"])
        self.stack.set_visible_child_name(fn["type"])

    def collect(self):
        """Return the function dict, or raise ValueError with the reason."""
        name = self.name.get_text().strip()
        if not name:
            raise ValueError(tr("Enter a name for the function."))
        orig = (self.fn or {}).get("name")
        if orig is not None and name == display_name(orig):
            name = orig                  # untouched built-in name keeps following the language
        t = self.type.get_active_id()
        out = {"name": name, "type": t}
        if t == "keys":
            out["cw"], out["ccw"] = self.k_cw.get_text().strip(), self.k_ccw.get_text().strip()
            parse_combo(out["cw"])
            parse_combo(out["ccw"])
        elif t == "wheel":
            out["axis"] = self.w_axis.get_active_id() or "v"
            out["mods"] = self.w_mods.get_text().strip()
            out["follow_rotation"] = self.w_follow.get_active()
            out["invert"] = self.w_invert.get_active()
            parse_combo(out["mods"])
        else:
            out["cw"], out["ccw"] = self.c_cw.get_text().strip(), self.c_ccw.get_text().strip()
        return out


# ----------------------------------------------------------------- main window
class ConfigWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title=tr("ASUS Dial – Settings"))
        self.set_default_size(780, 540)
        self.cfg = load_config()
        self.cur_key = ""
        self._loading = False

        self.tracker = None
        try:
            tr_ = ToplevelTracker()
            tr_.connect()
            tr_.attach_glib()
            self.tracker = tr_
        except OSError as exc:
            print(tr("Window list not available: {exc}", exc=exc), file=sys.stderr)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add(outer)
        nb = Gtk.Notebook()
        outer.pack_start(nb, True, True, 0)
        nb.append_page(self.build_profiles(), Gtk.Label(label=tr("App profiles")))
        nb.append_page(self.build_functions(), Gtk.Label(label=tr("Functions")))
        nb.append_page(self.build_settings(), Gtk.Label(label=tr("Settings")))
        self.status = Gtk.Label(xalign=0, margin=6)
        outer.pack_start(self.status, False, False, 0)

        self.refresh_profiles("")

    # ---- saving
    def save(self):
        try:
            save_config(self.cfg)
            self.status.set_text(
                tr("Saved. The daemon applies the changes within a couple of seconds."))
        except OSError as exc:
            self.status.set_text(tr("Error while saving: {exc}", exc=exc))

    def fname(self, fid):
        for f in self.cfg["functions"]:
            if f["id"] == fid:
                return display_name(f["name"])
        return fid

    def profile(self, key=None):
        key = self.cur_key if key is None else key
        return self.cfg["default"] if key == "" else self.cfg["apps"][key]

    # ============================================================== profiles
    def build_profiles(self):
        page = Gtk.Box(spacing=12, margin=12)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        left.set_size_request(230, -1)
        self.prof_store = Gtk.ListStore(str, str)
        self.prof_view = Gtk.TreeView(model=self.prof_store)
        self.prof_view.append_column(
            Gtk.TreeViewColumn(tr("App"), Gtk.CellRendererText(), text=1))
        self.prof_view.get_selection().connect("changed", self.on_profile_selected)
        sw = Gtk.ScrolledWindow()
        sw.add(self.prof_view)
        left.pack_start(sw, True, True, 0)
        b = Gtk.Button(label=tr("Add app…"))
        b.connect("clicked", self.on_add_app)
        left.pack_start(b, False, False, 0)
        self.btn_del_prof = Gtk.Button(label=tr("Remove profile"))
        self.btn_del_prof.connect("clicked", self.on_del_app)
        left.pack_start(self.btn_del_prof, False, False, 0)
        page.pack_start(left, False, False, 0)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.prof_title = Gtk.Label(xalign=0)
        right.pack_start(self.prof_title, False, False, 0)

        row = Gtk.Box(spacing=8)
        row.pack_start(Gtk.Label(label=tr("Starting function:")), False, False, 0)
        self.start_combo = Gtk.ComboBoxText()
        self.start_combo.connect("changed", self.on_start_changed)
        row.pack_start(self.start_combo, True, True, 0)
        right.pack_start(row, False, False, 0)

        right.pack_start(Gtk.Label(
            label=tr("Functions in the ring (in the order they appear):"), xalign=0),
            False, False, 0)
        self.menu_store = Gtk.ListStore(str, str)
        self.menu_view = Gtk.TreeView(model=self.menu_store)
        self.menu_view.append_column(
            Gtk.TreeViewColumn(tr("Function"), Gtk.CellRendererText(), text=1))
        sw = Gtk.ScrolledWindow()
        sw.add(self.menu_view)
        right.pack_start(sw, True, True, 0)

        row = Gtk.Box(spacing=6)
        for label, cb in ((tr("▲ Up"), lambda _b: self.move_menu(-1)),
                          (tr("▼ Down"), lambda _b: self.move_menu(1)),
                          (tr("Remove from ring"), self.on_menu_remove)):
            b = Gtk.Button(label=label)
            b.connect("clicked", cb)
            row.pack_start(b, False, False, 0)
        right.pack_start(row, False, False, 0)

        row = Gtk.Box(spacing=6)
        self.add_combo = Gtk.ComboBoxText()
        row.pack_start(self.add_combo, True, True, 0)
        b = Gtk.Button(label=tr("Add to ring"))
        b.connect("clicked", self.on_menu_add)
        row.pack_start(b, False, False, 0)
        right.pack_start(row, False, False, 0)
        right.pack_start(hint(tr(
            "The app is recognised by its <i>app-id</i>. The “Default” profile applies to "
            "every app without its own profile.")), False, False, 0)
        page.pack_start(right, True, True, 0)
        return page

    def refresh_profiles(self, select):
        self._loading = True
        self.prof_store.clear()
        self.prof_store.append(["", tr("Default (all other apps)")])
        for k in sorted(self.cfg["apps"]):
            self.prof_store.append([k, k])
        self._loading = False
        sel = select if (select == "" or select in self.cfg["apps"]) else ""
        for i, row in enumerate(self.prof_store):
            if row[0] == sel:
                self.prof_view.get_selection().select_path(Gtk.TreePath.new_from_string(str(i)))
                break
        self.cur_key = sel
        self.refresh_editor()

    def on_profile_selected(self, selection):
        if self._loading:
            return
        model, it = selection.get_selected()
        if it is None:
            return
        self.cur_key = model[it][0]
        self.refresh_editor()

    def refresh_editor(self, keep_row=None):
        self._loading = True
        p = self.profile()
        self.btn_del_prof.set_sensitive(self.cur_key != "")
        self.prof_title.set_markup(
            tr("<b>Default profile</b>") if self.cur_key == ""
            else tr("<b>Profile for:</b> {app}", app=GLib.markup_escape_text(self.cur_key)))
        self.menu_store.clear()
        self.start_combo.remove_all()
        for fid in p["menu"]:
            self.menu_store.append([fid, self.fname(fid)])
            self.start_combo.append(fid, self.fname(fid))
        self.start_combo.set_active_id(p["start"])
        self.add_combo.remove_all()
        for f in self.cfg["functions"]:
            if f["id"] not in p["menu"]:
                self.add_combo.append(f["id"], display_name(f["name"]))
        self.add_combo.set_active(0 if self.add_combo.get_model().iter_n_children(None) else -1)
        if keep_row is not None and 0 <= keep_row < len(p["menu"]):
            self.menu_view.get_selection().select_path(
                Gtk.TreePath.new_from_string(str(keep_row)))
        self._loading = False

    def selected_menu_row(self):
        model, it = self.menu_view.get_selection().get_selected()
        return None if it is None else model.get_path(it)[0]

    def on_start_changed(self, combo):
        if self._loading or combo.get_active_id() is None:
            return
        self.profile()["start"] = combo.get_active_id()
        self.save()

    def move_menu(self, delta):
        i = self.selected_menu_row()
        menu = self.profile()["menu"]
        if i is None or not 0 <= i + delta < len(menu):
            return
        menu[i], menu[i + delta] = menu[i + delta], menu[i]
        self.save()
        self.refresh_editor(i + delta)

    def on_menu_remove(self, _b):
        i = self.selected_menu_row()
        p = self.profile()
        if i is None:
            return
        if len(p["menu"]) <= 1:
            message(self, tr("The ring must keep at least one function."))
            return
        del p["menu"][i]
        if p["start"] not in p["menu"]:
            p["start"] = p["menu"][0]
        self.save()
        self.refresh_editor(min(i, len(p["menu"]) - 1))

    def on_menu_add(self, _b):
        fid = self.add_combo.get_active_id()
        if not fid:
            return
        self.profile()["menu"].append(fid)
        self.save()
        self.refresh_editor(len(self.profile()["menu"]) - 1)

    def on_add_app(self, _b):
        dlg = Gtk.Dialog(title=tr("Add app"), transient_for=self, modal=True)
        dlg.add_button(tr("Cancel"), Gtk.ResponseType.CANCEL)
        dlg.add_button(tr("Add"), Gtk.ResponseType.OK)
        box = dlg.get_content_area()
        box.set_spacing(8)
        box.set_border_width(12)
        box.pack_start(Gtk.Label(
            label=tr("Pick one of the open apps or type the app-id:"), xalign=0),
            False, False, 0)
        combo = Gtk.ComboBoxText.new_with_entry()
        for a in (self.tracker.open_apps() if self.tracker else []):
            combo.append_text(a)
        box.pack_start(combo, False, False, 0)
        if not self.tracker or not self.tracker.ok:
            box.pack_start(hint(tr(
                "Window list not available: type the app-id by hand (run the daemon with "
                "--debug to see it).")), False, False, 0)
        box.show_all()
        key = ""
        if dlg.run() == Gtk.ResponseType.OK:
            key = (combo.get_active_text() or "").strip().lower()
        dlg.destroy()
        if not key:
            return
        if key not in self.cfg["apps"]:
            self.cfg["apps"][key] = copy.deepcopy(self.cfg["default"])
            self.save()
        self.refresh_profiles(key)

    def on_del_app(self, _b):
        if self.cur_key and self.cur_key in self.cfg["apps"]:
            del self.cfg["apps"][self.cur_key]
            self.save()
            self.refresh_profiles("")

    # ============================================================== functions
    def build_functions(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=12)
        self.func_store = Gtk.ListStore(str, str, str)
        view = Gtk.TreeView(model=self.func_store)
        view.append_column(Gtk.TreeViewColumn(tr("Name"), Gtk.CellRendererText(), text=1))
        view.append_column(Gtk.TreeViewColumn(tr("What it does"), Gtk.CellRendererText(), text=2))
        view.connect("row-activated", lambda *_: self.on_func_edit(None))
        self.func_view = view
        sw = Gtk.ScrolledWindow()
        sw.add(view)
        page.pack_start(sw, True, True, 0)
        row = Gtk.Box(spacing=6)
        for label, cb in ((tr("New function…"), self.on_func_new),
                          (tr("Edit…"), self.on_func_edit),
                          (tr("Delete"), self.on_func_delete)):
            b = Gtk.Button(label=label)
            b.connect("clicked", cb)
            row.pack_start(b, False, False, 0)
        page.pack_start(row, False, False, 0)
        page.pack_start(hint(tr(
            "A function is what the Dial does when you turn it: press keys, move the mouse "
            "wheel (with modifiers such as Ctrl) or run a command. After creating one, add it "
            "to the ring in the “App profiles” tab.")), False, False, 0)
        self.refresh_functions()
        return page

    def refresh_functions(self):
        self.func_store.clear()
        for f in self.cfg["functions"]:
            self.func_store.append([f["id"], display_name(f["name"]), describe(f)])

    def selected_func(self):
        model, it = self.func_view.get_selection().get_selected()
        return None if it is None else model[it][0]

    def run_func_dialog(self, fn):
        dlg = FunctionDialog(self, fn)
        try:
            while dlg.run() == Gtk.ResponseType.OK:
                try:
                    return dlg.collect()
                except ValueError as exc:
                    message(dlg, str(exc))
            return None
        finally:
            dlg.destroy()

    def on_func_new(self, _b):
        data = self.run_func_dialog(None)
        if not data:
            return
        base = re.sub(r"[^a-z0-9]+", "-", data["name"].lower()).strip("-") or "function"
        ids = {f["id"] for f in self.cfg["functions"]}
        fid, n = base, 2
        while fid in ids:
            fid, n = f"{base}-{n}", n + 1
        data["id"] = fid
        self.cfg["functions"].append(data)
        self.save()
        self.refresh_functions()
        self.refresh_editor()

    def on_func_edit(self, _b):
        fid = self.selected_func()
        if fid is None:
            return
        old = next(f for f in self.cfg["functions"] if f["id"] == fid)
        data = self.run_func_dialog(old)
        if not data:
            return
        data["id"] = fid
        self.cfg["functions"][self.cfg["functions"].index(old)] = data
        self.save()
        self.refresh_functions()
        self.refresh_editor()

    def on_func_delete(self, _b):
        fid = self.selected_func()
        if fid is None:
            return
        if len(self.cfg["functions"]) <= 1:
            message(self, tr("At least one function must remain."))
            return
        self.cfg["functions"] = [f for f in self.cfg["functions"] if f["id"] != fid]
        self.cfg = normalize(self.cfg)       # also removes it from every profile
        self.save()
        self.refresh_functions()
        self.refresh_profiles(self.cur_key)

    # ============================================================== settings
    def build_settings(self):
        page = Gtk.Grid(row_spacing=10, column_spacing=10, margin=16)
        st = self.cfg["settings"]
        self.inv = Gtk.CheckButton(
            label=tr("Invert rotation direction (menu, volume, brightness, zoom…)"))
        self.inv.set_active(bool(st["invert_rotation"]))
        self.inv.connect("toggled", lambda c: self.set_setting("invert_rotation", c.get_active()))
        page.attach(self.inv, 0, 0, 2, 1)
        page.attach(hint(tr("Normal scrolling is unchanged: it always follows the Dial.")),
                    0, 1, 2, 1)

        page.attach(Gtk.Label(label=tr("Ticks needed to move one item in the menu:"), xalign=0),
                    0, 2, 1, 1)
        spin = Gtk.SpinButton.new_with_range(1, 5, 1)
        spin.set_value(st["step_ticks"])
        spin.connect("value-changed", lambda s: self.set_setting("step_ticks", int(s.get_value())))
        page.attach(spin, 1, 2, 1, 1)

        page.attach(Gtk.Label(label=tr("Close the menu after (seconds):"), xalign=0), 0, 3, 1, 1)
        spin2 = Gtk.SpinButton.new_with_range(1, 15, 1)
        spin2.set_value(st["menu_timeout_ms"] / 1000)
        spin2.connect("value-changed",
                      lambda s: self.set_setting("menu_timeout_ms", int(s.get_value() * 1000)))
        page.attach(spin2, 1, 3, 1, 1)
        return page

    def set_setting(self, key, value):
        self.cfg["settings"][key] = value
        self.save()


def main():
    win = ConfigWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
