"""Injection de texte dans l'application active.

Méthode par défaut : presse-papier + Ctrl+V (robuste pour accents et débit).
Le presse-papier précédent est sauvegardé puis restauré. Fallback : frappe
caractère par caractère via pynput. Aucun couplage Qt.
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)


def _paste_via_clipboard(text: str, restore: bool = True) -> bool:
    import pyperclip
    from pynput.keyboard import Controller, Key

    previous = None
    if restore:
        try:
            previous = pyperclip.paste()
        except Exception:
            previous = None

    pyperclip.copy(text)
    time.sleep(0.03)  # laisser le presse-papier se mettre à jour

    kb = Controller()
    with kb.pressed(Key.ctrl):
        kb.press("v")
        kb.release("v")
    time.sleep(0.05)

    if restore and previous is not None:
        # Certaines applis lisent le presse-papier en différé après le Ctrl+V ;
        # restaurer trop tôt collerait l'ANCIEN contenu. On tourne dans le
        # thread worker, donc ce délai ne bloque rien côté UI.
        time.sleep(0.3)
        try:
            pyperclip.copy(previous)
        except Exception:
            pass
    return True


def _type_text(text: str) -> bool:
    from pynput.keyboard import Controller

    Controller().type(text)
    return True


def inject(
    text: str,
    method: str = "clipboard_paste",
    restore_clipboard: bool = True,
    append_space: bool = False,
) -> bool:
    """Injecte `text` là où se trouve le curseur. Retourne True si réussi."""
    if not text:
        return False
    if append_space:
        text = text + " "
    try:
        if method == "clipboard_paste":
            return _paste_via_clipboard(text, restore=restore_clipboard)
        return _type_text(text)
    except Exception as exc:
        log.warning("Injection presse-papier échouée (%s) — fallback frappe", exc)
        try:
            return _type_text(text)
        except Exception as exc2:
            log.error("Injection par frappe échouée : %s", exc2)
            return False
