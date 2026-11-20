# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 LBlab
"""
Tiny translation helper.

Source strings are English. When the system language is Italian the Italian text
from IT below is used instead; every other language falls back to English.
Override the detection with  ASUS_DIAL_LANG=en  or  ASUS_DIAL_LANG=it.
"""
import os


def _detect():
    for var in ("ASUS_DIAL_LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = os.environ.get(var, "").strip()
        if value and value not in ("C", "POSIX"):
            return value.split(":")[0].lower()
    return "en"


LANG = _detect()
IS_IT = LANG.startswith("it")

# English text -> Italian text. Keep the {placeholders} identical.
IT = {
    # --- built-in function names
    "Scroll": "Scorrimento",
    "Horizontal scroll": "Scorrimento orizzontale",
    "Volume": "Volume",
    "Brightness": "Luminosità",
    "Zoom": "Zoom",
    "Tabs": "Schede",
    "Default": "Predefinito",
    # --- core
    "Unreadable configuration ({exc}): using defaults.":
        "Configurazione illeggibile ({exc}): uso i valori predefiniti.",
    "invalid shortcut: '{text}'": "scorciatoia non valida: «{text}»",
    "unknown key: '{part}'": "tasto sconosciuto: «{part}»",
    # --- daemon
    "Warning: layer-shell is not available, using a normal window.":
        "Attenzione: layer-shell non disponibile, uso una finestra normale.",
    "Cannot take control of the Dial ({exc}).\n"
    "If Input Remapper has an active preset on this device, stop it and try again.":
        "Impossibile prendere il controllo della Dial ({exc}).\n"
        "Se Input Remapper ha un preset attivo su questo dispositivo, fermalo e riprova.",
    "App detection not available ({exc}): using only the default profile.":
        "Rilevamento app non disponibile ({exc}): uso solo il profilo predefinito.",
    'Function "{name}": {exc}': 'Funzione "{name}": {exc}',
    "Permission denied on /dev/input/*: add your user to the 'input' group "
    "(sudo usermod -aG input $USER), then log out and in.":
        "Permesso negato su /dev/input/*: aggiungi il tuo utente al gruppo 'input' "
        "(sudo usermod -aG input $USER) ed esci/rientra.",
    'Device "{name}" not found.': 'Dispositivo "{name}" non trovato.',
    # --- GUI: general
    "ASUS Dial – Settings": "ASUS Dial – Impostazioni",
    "App profiles": "Profili per app",
    "Functions": "Funzioni",
    "Settings": "Impostazioni",
    "Cancel": "Annulla",
    "OK": "OK",
    "Saved. The daemon applies the changes within a couple of seconds.":
        "Salvato. Il demone applica le modifiche entro un paio di secondi.",
    "Error while saving: {exc}": "Errore nel salvataggio: {exc}",
    "Window list not available: {exc}": "Elenco delle finestre non disponibile: {exc}",
    # --- GUI: function descriptions
    "clockwise: {cw}  ·  counter-clockwise: {ccw}":
        "orario: {cw}  ·  antiorario: {ccw}",
    "Vertical wheel": "Rotella verticale",
    "Horizontal wheel": "Rotella orizzontale",
    # --- GUI: function dialog
    "Function": "Funzione",
    "Keys / shortcuts": "Tasti / scorciatoie",
    "Mouse wheel": "Rotella del mouse",
    "Command": "Comando",
    "Name:": "Nome:",
    "Type:": "Tipo:",
    "Clockwise:": "Senso orario:",
    "Counter-clockwise:": "Senso antiorario:",
    "Examples: <b>ctrl+z</b>, <b>ctrl+shift+z</b>, <b>left</b>, <b>pagedown</b>, "
    "<b>volumeup</b>, <b>next</b> (next track). Leave empty to do nothing in that direction.":
        "Esempi: <b>ctrl+z</b>, <b>ctrl+shift+z</b>, <b>left</b>, <b>pagedown</b>, "
        "<b>volumeup</b>, <b>next</b> (traccia successiva). Lascia vuoto per non fare nulla "
        "in quel verso.",
    "Axis:": "Asse:",
    "Vertical": "Verticale",
    "Horizontal": "Orizzontale",
    "With keys held:": "Con tasti premuti:",
    "Follow rotation direction (clockwise = up / right)":
        "Segui il senso di rotazione (orario = su / destra)",
    "Invert": "Inverti",
    "Held keys: e.g. <b>ctrl</b> (zoom), <b>alt</b>, <b>shift</b>, <b>ctrl+shift</b>. "
    "Without “Follow rotation direction” the wheel behaves like the Dial's normal scroll.":
        "Tasti premuti: ad es. <b>ctrl</b> (zoom), <b>alt</b>, <b>shift</b>, "
        "<b>ctrl+shift</b>. Senza «Segui il senso di rotazione» la rotella si comporta "
        "come lo scroll normale della Dial.",
    "Command run on every tick, without a shell. Examples: <b>playerctl next</b> or "
    "<b>wpctl set-volume @DEFAULT_AUDIO_SINK@ 2%+</b>.":
        "Comando eseguito a ogni scatto, senza shell. Esempio: <b>playerctl next</b> "
        "oppure <b>wpctl set-volume @DEFAULT_AUDIO_SINK@ 2%+</b>.",
    "Enter a name for the function.": "Scrivi un nome per la funzione.",
    # --- GUI: profiles tab
    "App": "App",
    "Add app…": "Aggiungi app…",
    "Remove profile": "Rimuovi profilo",
    "Default (all other apps)": "Predefinito (tutte le altre app)",
    "<b>Default profile</b>": "<b>Profilo predefinito</b>",
    "<b>Profile for:</b> {app}": "<b>Profilo di:</b> {app}",
    "Starting function:": "Funzione iniziale:",
    "Functions in the ring (in the order they appear):":
        "Funzioni nell'anello (nell'ordine in cui compaiono):",
    "▲ Up": "▲ Su",
    "▼ Down": "▼ Giù",
    "Remove from ring": "Togli dall'anello",
    "Add to ring": "Aggiungi all'anello",
    "The app is recognised by its <i>app-id</i>. The “Default” profile applies to every "
    "app without its own profile.":
        "L'app viene riconosciuta dal suo <i>app-id</i>. Il profilo «Predefinito» vale per "
        "tutte le app senza un profilo proprio.",
    "The ring must keep at least one function.":
        "Nell'anello deve restare almeno una funzione.",
    "Add app": "Aggiungi app",
    "Add": "Aggiungi",
    "Pick one of the open apps or type the app-id:":
        "Scegli una delle app aperte oppure scrivi l'app-id:",
    "Window list not available: type the app-id by hand (run the daemon with --debug "
    "to see it).":
        "Elenco delle finestre non disponibile: scrivi l'app-id a mano (lo vedi lanciando "
        "il demone con --debug).",
    # --- GUI: functions tab
    "Name": "Nome",
    "What it does": "Cosa fa",
    "New function…": "Nuova funzione…",
    "Edit…": "Modifica…",
    "Delete": "Elimina",
    "A function is what the Dial does when you turn it: press keys, move the mouse wheel "
    "(with modifiers such as Ctrl) or run a command. After creating one, add it to the "
    "ring in the “App profiles” tab.":
        "Una funzione è ciò che la Dial fa quando la giri: premere tasti, muovere la "
        "rotella (con modificatori come Ctrl) o lanciare un comando. Dopo averla creata "
        "aggiungila all'anello nella scheda «Profili per app».",
    "At least one function must remain.": "Deve restare almeno una funzione.",
    # --- GUI: settings tab
    "Invert rotation direction (menu, volume, brightness, zoom…)":
        "Inverti il senso di rotazione (menu, volume, luminosità, zoom…)",
    "Normal scrolling is unchanged: it always follows the Dial.":
        "Lo scorrimento normale non cambia: segue sempre la Dial.",
    "Ticks needed to move one item in the menu:":
        "Scatti per spostarsi di una voce nel menu:",
    "Close the menu after (seconds):": "Chiudi il menu dopo (secondi):",
}

# Function names saved in the config by earlier (Italian-only) versions.
LEGACY_IT_NAMES = {
    "Scorrimento": "Scroll",
    "Scorrimento orizzontale": "Horizontal scroll",
    "Luminosità": "Brightness",
    "Schede": "Tabs",
}


def tr(text, /, **kwargs):
    """Translate `text` (an English source string) and fill in {placeholders}."""
    if IS_IT:
        text = IT.get(text, text)
    return text.format(**kwargs) if kwargs else text


def display_name(name):
    """Name of a function as shown to the user: built-in names follow the language,
    names typed by the user are left alone."""
    if IS_IT:
        return IT.get(name, name)
    return LEGACY_IT_NAMES.get(name, name)
