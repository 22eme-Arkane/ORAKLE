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

from orakle.paths import app_root

APP_NAME = "orakle"

_DEFAULTS_DIR = app_root() / "config"

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


def _merge_missing(user: dict[str, Any], defaults: dict[str, Any]) -> bool:
    """Ajoute à `user` les clés du template absentes (récursif). True si modifié."""
    changed = False
    for key, value in defaults.items():
        if key not in user:
            user[key] = value
            changed = True
        elif isinstance(value, dict) and isinstance(user.get(key), dict):
            changed = _merge_missing(user[key], value) or changed
    return changed


def load_settings() -> dict[str, Any]:
    """Réglages utilisateur ; complète avec les clés du template (migration)."""
    _ensure_user_files()
    path = user_config_dir() / SETTINGS_FILENAME
    try:
        data = _load_json(path)
    except (OSError, json.JSONDecodeError):
        return _load_json(_DEFAULTS_DIR / "settings.default.json")
    # Migration douce : les réglages ajoutés par les nouvelles versions
    # apparaissent dans le fichier utilisateur (valeurs par défaut), sans
    # jamais écraser une valeur existante.
    try:
        defaults = _load_json(_DEFAULTS_DIR / "settings.default.json")
        if _merge_missing(data, defaults):
            _save_json(path, data)
    except (OSError, json.JSONDecodeError):
        pass
    return data


def save_settings(data: dict[str, Any]) -> None:
    _save_json(user_config_dir() / SETTINGS_FILENAME, data)


def export_all(path: str | Path) -> None:
    """Exporte réglages + dictionnaire dans un seul JSON portable."""
    bundle = {
        "orakle_export": 1,
        "settings": load_settings(),
        "dictionary": load_dictionary(),
    }
    _save_json(Path(path), bundle)


def import_all(path: str | Path) -> None:
    """Importe un export ORAKLE (réglages + dictionnaire). Lève si invalide."""
    data = _load_json(Path(path))
    if not isinstance(data, dict) or "orakle_export" not in data:
        raise ValueError("Ce fichier n'est pas un export ORAKLE.")
    settings = data.get("settings")
    dictionary = data.get("dictionary")
    if isinstance(settings, dict) and settings:
        save_settings(settings)
    if isinstance(dictionary, dict) and dictionary:
        save_dictionary(dictionary)


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
