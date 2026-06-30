"""Détection et analyse de la commande de traduction parlée.

Format reconnu, au DÉBUT de la transcription :
    <mot-clé> [article] <langue source> <liaison> [article] <langue cible> <contenu…>

Exemples :
    « traduis français vers espagnol bonjour le monde »
        -> ("fr", "es", "bonjour le monde")
    « translate english to spanish hello world »
        -> ("en", "es", "hello world")
    « Traduis du français vers l'espagnol, bonjour »
        -> ("fr", "es", "bonjour")

Stratégie v1 (B) : commande + contenu dans le même clip ; on retire le préfixe
de commande par regex, le reste est le contenu à traduire. Module pur (aucune
dépendance réseau/Qt).
"""
from __future__ import annotations

import re
from typing import Optional

# Noms de langues -> code ISO (FR / EN / ES, orthographes courantes).
_LANG_NAMES = {
    "fr": ("français", "francais", "french", "fr"),
    "en": ("anglais", "english", "inglés", "ingles", "en"),
    "es": ("espagnol", "spanish", "español", "espanol", "es"),
}
_NAME_TO_CODE = {name: code for code, names in _LANG_NAMES.items() for name in names}

# Petits articles tolérés avant un nom de langue. Les formes élidées (l', d')
# collent au mot (« l'espagnol ») : apostrophe droite ' ou courbe ’, sans espace.
_ARTICLE = r"(?:(?:du|de|des|le|la|les|the|from|el)\s+|[dl][’']\s*)?"

_DEFAULT_KEYWORDS = ("translate", "traduis", "traduire", "traducir")
_DEFAULT_LINKERS = ("vers", "to", "a", "en", "→")


def parse_command(
    text: str,
    keywords: Optional[list[str]] = None,
    linkers: Optional[list[str]] = None,
) -> Optional[tuple[str, str, str]]:
    """Retourne (src, dst, contenu) si `text` débute par une commande, sinon None."""
    if not text:
        return None
    kws = [k for k in (keywords or _DEFAULT_KEYWORDS) if k]
    lks = [l for l in (linkers or _DEFAULT_LINKERS) if l]
    if not kws or not lks:
        return None

    names = sorted(_NAME_TO_CODE.keys(), key=len, reverse=True)
    kw = "|".join(re.escape(k.lower()) for k in kws)
    lk = "|".join(re.escape(l.lower()) for l in lks)
    nm = "|".join(re.escape(n) for n in names)

    pat = re.compile(
        rf"^\s*(?:{kw})\s+{_ARTICLE}(?P<src>{nm})\s+(?:{lk})\s+"
        rf"{_ARTICLE}(?P<dst>{nm})\b[\s,:;.\-–—]*(?P<content>.*)$",
        re.IGNORECASE | re.DOTALL,
    )
    m = pat.match(text)
    if not m:
        return None

    src = _NAME_TO_CODE.get(m.group("src").lower())
    dst = _NAME_TO_CODE.get(m.group("dst").lower())
    content = (m.group("content") or "").strip()
    if not src or not dst or src == dst or not content:
        return None
    return src, dst, content
