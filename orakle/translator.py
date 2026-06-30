"""Traduction de texte — interface unique, backends interchangeables.

`translate(text, src, dst, settings)` choisit le moteur selon la config :

- **argos** (défaut) : argos-translate, hors-ligne, gratuit. Télécharge au besoin
  le paquet de langue manquant (pivot par l'anglais si pas de lien direct).
- **ollama** : LLM open-weight local (Mistral/Qwen3) via http://localhost:11434.
- **anthropic** : cloud BYOK, facultatif, désactivé par défaut.

Tolérant aux pannes : tout échec d'un backend retombe sur argos, et en dernier
recours on renvoie le texte source (jamais de crash, jamais de perte de dictée).
Aucune dépendance Qt.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger(__name__)


# --- argos-translate (offline, défaut) ---
def _ensure_argos_package(src: str, dst: str) -> None:
    import argostranslate.package as pkg

    def _installed(a: str, b: str) -> bool:
        return any(p.from_code == a and p.to_code == b
                   for p in pkg.get_installed_packages())

    if _installed(src, dst):
        return
    # Lien direct sinon pivot par l'anglais.
    pairs = [(src, dst)] if (src == "en" or dst == "en") else [(src, "en"), ("en", dst)]
    if all(_installed(a, b) for a, b in pairs):
        return
    pkg.update_package_index()
    available = pkg.get_available_packages()
    for a, b in pairs:
        if _installed(a, b):
            continue
        match = next((p for p in available if p.from_code == a and p.to_code == b), None)
        if match is not None:
            path = match.download()
            pkg.install_from_path(path)
            log.info("Paquet de langue Argos installé : %s -> %s", a, b)


def _argos_translate(text: str, src: str, dst: str) -> str:
    import argostranslate.translate as tr

    _ensure_argos_package(src, dst)
    return tr.translate(text, src, dst)


# --- Ollama (LLM local) ---
def _ollama_translate(text: str, src: str, dst: str, host: str, model: str) -> str:
    import requests

    names = {"fr": "français", "en": "anglais", "es": "espagnol"}
    prompt = (
        f"Traduis le texte suivant du {names.get(src, src)} vers le "
        f"{names.get(dst, dst)}. Ne renvoie QUE la traduction, sans préambule, "
        f"sans guillemets, sans explication.\n\n{text}"
    )
    r = requests.post(
        f"{host.rstrip('/')}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=60,
    )
    r.raise_for_status()
    return (r.json().get("response") or "").strip()


# --- Anthropic (cloud BYOK, facultatif) ---
def _anthropic_translate(text: str, src: str, dst: str, tcfg: dict) -> str:
    import anthropic

    key = tcfg.get("anthropic_key") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("clé Anthropic absente")
    names = {"fr": "French", "en": "English", "es": "Spanish"}
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model=tcfg.get("anthropic_model", "claude-haiku-4-5"),
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": (
                f"Translate the following text from {names.get(src, src)} to "
                f"{names.get(dst, dst)}. Return ONLY the translation, no preamble.\n\n{text}"
            ),
        }],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def translate(text: str, src: str, dst: str, settings: Optional[dict] = None) -> str:
    """Traduit `text` de `src` vers `dst` selon la config (repli argos puis source)."""
    if not text or src == dst:
        return text
    tcfg = (settings or {}).get("translation", {}) if settings else {}
    engine = tcfg.get("engine", "argos")
    try:
        if engine == "ollama":
            o = tcfg.get("ollama", {})
            return _ollama_translate(
                text, src, dst,
                o.get("host", "http://localhost:11434"),
                o.get("model", "mistral"),
            )
        if engine == "anthropic" and tcfg.get("byok_enabled"):
            return _anthropic_translate(text, src, dst, tcfg)
        return _argos_translate(text, src, dst)
    except Exception as exc:
        log.warning("Traduction via « %s » échouée (%s) — repli Argos", engine, exc)
        try:
            return _argos_translate(text, src, dst)
        except Exception as exc2:
            log.error("Traduction Argos impossible (%s) — texte source conservé", exc2)
            return text
