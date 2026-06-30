"""Chargement / sauvegarde des réglages et du dictionnaire ORAKLE.

Gère le dossier de config utilisateur (cross-platform) et copie les templates
par défaut au premier lancement. Aucun couplage avec Qt : module pur Python.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

APP_NAME = "orakle"

# Ce fichier vit dans orakle/config.py ; le dépôt est le parent du paquet.
_PKG_DIR = Path(__file__).resolve().parent
_REPO_DIR = _PKG_DIR.parent
_DEFAULTS_DIR = _REPO_DIR / "config"

SETTINGS_FILENAME = "settings.json"
DICTIONARY_FILENAME = "dictionary.json"


def user_config_dir() -> Path:
    """Dossier de config utilisateur selon l'OS (créé au besoin par l'appelant)."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


def _ensure_user_files() -> None:
    """Crée le dossier utilisateur et copie les templates par défaut si absents."""
    d = user_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    pairs = [
        (_DEFAULTS_DIR / "settings.default.json", d / SETTINGS_FILENAME),
        (_DEFAULTS_DIR / "dictionary.default.json", d / DICTIONARY_FILENAME),
    ]
    for src, dst in pairs:
        if not dst.exists() and src.exists():
            shutil.copyfile(src, dst)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: dict[str, Any]) -> None:
    """Écriture atomique (tmp + replace) pour ne jamais corrompre le fichier."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def load_settings() -> dict[str, Any]:
    """Réglages utilisateur ; retombe sur le template si lecture impossible."""
    _ensure_user_files()
    path = user_config_dir() / SETTINGS_FILENAME
    try:
        return _load_json(path)
    except (OSError, json.JSONDecodeError):
        return _load_json(_DEFAULTS_DIR / "settings.default.json")


def save_settings(data: dict[str, Any]) -> None:
    _save_json(user_config_dir() / SETTINGS_FILENAME, data)


def load_dictionary() -> dict[str, Any]:
    """Dictionnaire perso ; retombe sur le template si lecture impossible."""
    _ensure_user_files()
    path = user_config_dir() / DICTIONARY_FILENAME
    try:
        return _load_json(path)
    except (OSError, json.JSONDecodeError):
        return _load_json(_DEFAULTS_DIR / "dictionary.default.json")


def save_dictionary(data: dict[str, Any]) -> None:
    _save_json(user_config_dir() / DICTIONARY_FILENAME, data)
