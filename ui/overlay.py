"""Overlay d'enregistrement — capsule sombre avec onde de forme animée.

Inspiré de Wispr Flow : une petite pastille en bas-centre de l'écran apparaît
pendant l'enregistrement (barres réagissant au niveau du micro) et disparaît à
la fin. Fenêtre sans cadre, toujours au-dessus, **NON focusable** : elle ne doit
jamais voler le focus du champ cible (sinon le Ctrl+V d'injection irait au
mauvais endroit).
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QApplication, QWidget

_N_BARS = 15
_W, _H = 190, 60
_BG = QColor(18, 20, 32, 235)        # sombre cohérent avec le thème (bg1)
_BAR = QColor(150, 180, 255)          # bleu clair (même teinte que l'icône idle)


class RecordingOverlay(QWidget):
    def __init__(self, level_provider: Optional[Callable[[], float]] = None) -> None:
        super().__init__(None)
        self._level_provider = level_provider or (lambda: 0.0)
        self._phase = 0.0
        self._bars = [0.12] * _N_BARS

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.resize(_W, _H)

        self._timer = QTimer(self)
        self._timer.setInterval(40)  # ~25 fps
        self._timer.timeout.connect(self._tick)

    # --- placement bas-centre de l'écran principal ---
    def _reposition(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + geo.height() - self.height() - 80
        self.move(x, y)

    # --- API publique (appelée sur le thread principal Qt) ---
    def show_overlay(self) -> None:
        self._bars = [0.12] * _N_BARS
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start()

    def hide_overlay(self) -> None:
        self._timer.stop()
        self.hide()

    # --- animation ---
    def _tick(self) -> None:
        self._phase += 0.35
        level = max(0.0, min(1.0, self._level_provider()))
        n = _N_BARS
        mid = (n - 1) / 2
        for i in range(n):
            bell = 1.0 - abs((i - mid) / mid)          # enveloppe en cloche 0..1
            osc = 0.5 + 0.5 * math.sin(self._phase + i * 0.55)
            target = 0.12 + (0.25 + 0.75 * level) * (0.35 + 0.65 * bell) * osc
            self._bars[i] += (target - self._bars[i]) * 0.4  # lissage
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        radius = h / 2

        path = QPainterPath()
        path.addRoundedRect(QRectF(0.0, 0.0, float(w), float(h)), radius, radius)
        p.fillPath(path, _BG)

        n = _N_BARS
        pad = 24.0
        slot = (w - 2 * pad) / n
        bar_w = min(4.0, slot * 0.55)
        max_h = h * 0.55
        cy = h / 2.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_BAR)
        for i in range(n):
            bh = max(3.0, self._bars[i] * max_h)
            x = pad + slot * i + (slot - bar_w) / 2.0
            p.drawRoundedRect(QRectF(x, cy - bh / 2.0, bar_w, bh), bar_w / 2.0, bar_w / 2.0)
        p.end()
