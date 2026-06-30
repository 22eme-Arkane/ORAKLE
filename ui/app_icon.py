"""Chargement de l'icône d'application (logo) + variantes d'état pour le tray.

Le logo est lu depuis `resources/logo.ico` ou `resources/logo.png` (le 1er
trouvé). S'il est absent, les appelants retombent sur un rendu par défaut.

Pour le tray, on superpose une petite pastille de couleur sur le logo afin de
garder l'indication d'état (rouge = enregistrement, orange = transcription ;
rien au repos), sans perdre l'identité visuelle.
"""
from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

_RES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources"
)
_PNG = os.path.join(_RES_DIR, "logo.png")
_ICO = os.path.join(_RES_DIR, "logo.ico")
# Icône d'app : .ico d'abord (multi-tailles natif Windows). Pixmap tray : .png
# d'abord (512² net) sinon .ico.
_ICON_ORDER = (_ICO, _PNG)
_PIXMAP_ORDER = (_PNG, _ICO)


def _first_existing(paths) -> Optional[str]:
    for p in paths:
        if os.path.isfile(p):
            return p
    return None

_STATE_DOT = {
    "recording": "#e8553c",   # rouge
    "processing": "#e8a13c",   # orange
}


def logo_file() -> Optional[str]:
    """Un fichier logo existant (n'importe quel format), ou None."""
    return _first_existing(_ICON_ORDER)


def load_logo_icon() -> Optional[QIcon]:
    path = _first_existing(_ICON_ORDER)
    if not path:
        return None
    icon = QIcon(path)
    return None if icon.isNull() else icon


def load_logo_pixmap(size: int = 256) -> Optional[QPixmap]:
    path = _first_existing(_PIXMAP_ORDER)
    if not path:
        return None
    pm = QPixmap(path)
    if pm.isNull():
        return None
    if pm.width() != size or pm.height() != size:
        pm = pm.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return pm


def state_icon(base: QPixmap, state: str) -> QIcon:
    """Logo + pastille de couleur d'état (logo seul si état idle/inconnu)."""
    color = _STATE_DOT.get(state)
    if color is None:
        return QIcon(base)
    pm = QPixmap(base)  # copie pour ne pas altérer la base
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    d = int(pm.width() * 0.32)
    margin = max(1, int(pm.width() * 0.03))
    x = pm.width() - d - margin
    y = pm.height() - d - margin
    p.setPen(QColor(255, 255, 255, 235))
    p.setBrush(QColor(color))
    p.drawEllipse(x, y, d, d)
    p.end()
    return QIcon(pm)
