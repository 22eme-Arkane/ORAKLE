"""Résolution des chemins de l'application — dev vs. gelé (PyInstaller).

En dev : la racine du dépôt (parent du paquet orakle/).
Gelé (PyInstaller) : le dossier d'extraction sys._MEIPASS, où les datas
(config/ templates, resources/) sont embarquées par le .spec.

Centralisé ici pour que config.py et l'UI n'aient jamais à connaître le mode.
"""
from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """Racine des ressources embarquées (templates config/, resources/)."""
    if getattr(sys, "frozen", False):  # exécutable PyInstaller
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent
