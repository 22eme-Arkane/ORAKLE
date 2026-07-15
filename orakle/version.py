"""Version d'ORAKLE + vérification de mise à jour (GitHub Releases).

`fetch_latest()` interroge l'API publique GitHub (un simple GET anonyme,
désactivable via le réglage `check_updates`) et `is_newer()` compare les
versions. Aucune donnée utilisateur n'est envoyée — cohérent avec le principe
zéro télémétrie. Module pur (requests uniquement), aucun couplage Qt.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

VERSION = "0.1.1"

GITHUB_REPO = "22eme-Arkane/ORAKLE"
API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"

log = logging.getLogger(__name__)


def parse_version(v: str) -> tuple[int, ...]:
    """'v0.1.1' / '0.1.1' -> (0, 1, 1). Tolérant ; () si rien de numérique."""
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3])


def is_newer(latest: str, current: str = VERSION) -> bool:
    lt, ct = parse_version(latest), parse_version(current)
    return bool(lt) and lt > ct


def fetch_latest(timeout: float = 8.0) -> Optional[tuple[str, str]]:
    """Retourne (version, url_page) de la dernière release, ou None si échec.

    Best-effort : hors-ligne / API indisponible -> None, jamais d'exception.
    """
    try:
        import requests

        r = requests.get(
            API_LATEST,
            timeout=timeout,
            headers={"Accept": "application/vnd.github+json"},
        )
        r.raise_for_status()
        data = r.json()
        tag = (data.get("tag_name") or "").strip()
        url = data.get("html_url") or RELEASES_PAGE
        if not tag:
            return None
        return tag.lstrip("vV"), url
    except Exception as exc:
        log.debug("Vérification de mise à jour impossible (%s)", exc)
        return None
