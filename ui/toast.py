"""Toast d'état — petite notification discrète en bas à droite de l'écran.

Répond au besoin « je ne sais pas si ça travaille ou si ça a bugué » :
- pendant la transcription : « ⏳ Transcription… » (reste affiché) ;
- texte injecté : « ✓ Texte inséré » + bouton **Copier** (filet de sécurité si
  le champ cible avait perdu le focus au moment du collage) ;
- rien reconnu / erreur : message bref.

Fenêtre sans cadre, toujours au-dessus, NON focusable (elle ne doit jamais
voler le focus du champ où le texte est collé) — mais la souris fonctionne,
donc le bouton Copier est cliquable. Les icônes/symboles différencient les
états (pas seulement la couleur — daltonisme).
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

log = logging.getLogger(__name__)

_MARGIN_RIGHT = 14
_MARGIN_BOTTOM = 10
_RESULT_MS = 6000        # durée d'affichage d'un résultat (succès/info/erreur)
_PROCESSING_MAX_MS = 120_000  # filet : jamais un « Transcription… » éternel

_STYLE = """
QFrame#toast {
    background: rgba(18, 20, 32, 240);
    border: 1px solid #2a2e45;
    border-radius: 15px;
}
QLabel { color: #e6e8f0; font-size: 12px; background: transparent; border: 0; }
QLabel#icon { font-size: 13px; }
QPushButton {
    color: #9cb4ff; background: transparent;
    border: 1px solid #3a4166; border-radius: 9px;
    padding: 2px 10px; font-size: 12px;
}
QPushButton:hover { background: #1c2036; }
"""


class StatusToast(QWidget):
    """Un seul toast réutilisé : chaque show_*() remplace le contenu courant."""

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(_STYLE)

        self._mode = ""          # "" | "processing" | "result"
        self._last_text = ""     # texte du bouton Copier

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("toast")
        outer.addWidget(frame)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(12, 6, 10, 6)
        lay.setSpacing(8)
        self._icon = QLabel()
        self._icon.setObjectName("icon")
        self._label = QLabel()
        self._btn_copy = QPushButton("Copier")
        self._btn_copy.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_copy.clicked.connect(self._copy_last)
        lay.addWidget(self._icon)
        lay.addWidget(self._label)
        lay.addWidget(self._btn_copy)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    # --- placement bas-droite de l'écran principal, au-dessus de la taskbar ---
    def _reposition(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        self.adjustSize()
        geo = screen.availableGeometry()  # exclut la barre des tâches
        x = geo.x() + geo.width() - self.width() - _MARGIN_RIGHT
        y = geo.y() + geo.height() - self.height() - _MARGIN_BOTTOM
        self.move(x, y)

    def _present(self, icon: str, text: str, mode: str,
                 with_copy: bool, duration_ms: int) -> None:
        self._mode = mode
        self._icon.setText(icon)
        self._label.setText(text)
        self._btn_copy.setVisible(with_copy)
        self._reposition()
        self.show()
        self.raise_()
        self._hide_timer.stop()
        if duration_ms > 0:
            self._hide_timer.start(duration_ms)

    # --- API publique (thread principal Qt uniquement) ---
    def show_processing(self) -> None:
        """Affiché dès la fin de capture, remplacé par le résultat."""
        self._present("⏳", "Transcription…", "processing",
                      with_copy=False, duration_ms=_PROCESSING_MAX_MS)

    def show_result(self, text: str) -> None:
        """Texte injecté avec succès — bouton Copier en filet de sécurité."""
        self._last_text = text
        self._btn_copy.setText("Copier")
        # Émojis (pas ✓/⚠ texte) : certains rendus de police livrent une boîte
        # vide pour les glyphes symboles, jamais pour les émojis couleur.
        self._present("✅", "Texte inséré", "result",
                      with_copy=True, duration_ms=_RESULT_MS)

    def show_info(self, message: str) -> None:
        self._present("∅", message, "result", with_copy=False,
                      duration_ms=_RESULT_MS)

    def show_error(self, message: str) -> None:
        short = (message[:60] + "…") if len(message) > 60 else message
        self._present("⚠️", short, "result", with_copy=False,
                      duration_ms=_RESULT_MS)

    def on_idle(self) -> None:
        """Retour à l'état repos : ne masque QUE le « Transcription… » resté
        affiché (dictée vide sans signal, etc.) — jamais un résultat en cours
        de lecture."""
        if self._mode == "processing":
            self.hide()

    def hide(self) -> None:  # noqa: D102
        self._hide_timer.stop()
        self._mode = ""
        super().hide()

    # --- bouton Copier ---
    def _copy_last(self) -> None:
        if not self._last_text:
            return
        try:
            import pyperclip

            pyperclip.copy(self._last_text)
        except Exception:
            log.exception("Échec de la copie vers le presse-papier")
            self._btn_copy.setText("Échec !")
            return
        self._btn_copy.setText("Copié !")
        self._hide_timer.stop()
        self._hide_timer.start(1500)
