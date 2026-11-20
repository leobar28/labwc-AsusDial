# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 LBlab
"""Checks that every translatable string has an Italian translation with the same placeholders.
Run: python3 tests/test_i18n.py"""
import ast
import os
import string
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import dial_i18n as i18n  # noqa: E402

SOURCES = ("dial_core.py", "asus_dial_overlay.py", "asus_dial_config.py")


def _placeholders(text):
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def _used_strings():
    found = set()
    for name in SOURCES:
        tree = ast.parse(open(os.path.join(ROOT, name), encoding="utf-8").read())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "tr" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                found.add(node.args[0].value)
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "tr" and node.args
                    and not isinstance(node.args[0], ast.Constant)):
                raise AssertionError(f"{name}:{node.lineno}: tr() needs a literal string")
    return found


def test_every_string_is_translated():
    missing = sorted(s for s in _used_strings() if s not in i18n.IT)
    assert not missing, "missing Italian translation:\n" + "\n".join(missing)


def test_placeholders_match():
    for en, it in i18n.IT.items():
        assert _placeholders(en) == _placeholders(it), f"placeholder mismatch: {en!r}"


def test_no_unused_translations():
    builtin = {"Scroll", "Horizontal scroll", "Volume", "Brightness", "Zoom", "Tabs"}
    unused = sorted(set(i18n.IT) - _used_strings() - builtin)
    assert not unused, "unused translations:\n" + "\n".join(unused)


def _run_in(lang):
    code = ("import dial_i18n as i;"
            "print(i.tr('Default'), '|', i.display_name('Scroll'), '|', "
            "i.display_name('Scorrimento'), '|', i.display_name('My own'), '|', "
            "i.tr('Error while saving: {exc}', exc='boom'))")
    env = dict(os.environ, ASUS_DIAL_LANG=lang)
    return subprocess.check_output([sys.executable, "-c", code], cwd=ROOT, env=env, text=True).strip()


def test_language_switch():
    assert _run_in("it_IT.UTF-8") == "Predefinito | Scorrimento | Scorrimento | My own | Errore nel salvataggio: boom"
    assert _run_in("en_US.UTF-8") == "Default | Scroll | Scroll | My own | Error while saving: boom"
    assert _run_in("fr_FR.UTF-8").startswith("Default | Scroll")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
