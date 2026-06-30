"""System tray ORAKLE : icône d'état + menu contextuel.

L'icône reflète l'état (idle / recording / processing). Les icônes sont dessinées
en code (QPainter) pour éviter tout asset binaire à ce stade ; elles pourront
être remplacées par des PNG de `resources/` plus tard.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ui.dictionary_window import DictionaryWindow

# Libellé -> code (None = détection automatique).
_LANG_CHOICES = [("Auto", None), ("Français", "fr"), ("English", "en"), ("Español", "es")]

_STATE_COLORS = {
    "idle": "#5b8def",        # bleu
    "recording": "#e8553c",   # rouge
    "processing": "#e8a13c",  # orange
}

_STATE_LABELS = {
    "idle": "prêt",
    "recording": "enregistrement…",
    "processing": "transcription…",
}


def _make_icon(color_hex: str) -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color_hex))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(8, 8, 48, 48)
    p.end()
    return QIcon(pix)


class OrakleTray(QSystemTrayIcon):
    def __init__(self, controller, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self._controller = controller
        self._dict_window = None
        self._icons = {state: _make_icon(c) for state, c in _STATE_COLORS.items()}
        self.setIcon(self._icons["idle"])
        self.setToolTip("ORAKLE — maintenir Ctrl+1 (ou double-tap) pour dicter")

        menu = QMenu()
        self._status_action = QAction("État : prêt", menu)
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)
        menu.addSeparator()

        # Sous-menu Langue (forçage / auto), exclusif.
        lang_menu = menu.addMenu("Langue")
        self._lang_group = QActionGroup(menu)
        self._lang_group.setExclusive(True)
        current = controller.settings.get("force_language")
        for label, code in _LANG_CHOICES:
            act = QAction(label, menu, checkable=True)
            act.setChecked(code == current)
            act.setData(code)
            act.triggered.connect(lambda _checked, c=code: self._set_language(c))
            self._lang_group.addAction(act)
            lang_menu.addAction(act)

        dict_action = QAction("Dictionnaire…", menu)
        dict_action.triggered.connect(self._open_dictionary)
        menu.addAction(dict_action)
        menu.addSeparator()
        quit_action = QAction("Quitter", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)
        self.setContextMenu(menu)

        controller.state_changed.connect(self._on_state)
        controller.text_injected.connect(self._on_injected)
        controller.error.connect(self._on_error)

    def _on_state(self, state: str) -> None:
        self.setIcon(self._icons.get(state, self._icons["idle"]))
        self._status_action.setText(f"État : {_STATE_LABELS.get(state, state)}")

    def _on_injected(self, text: str) -> None:
        # Notification de dictée : désactivée par défaut (réglable). On évite de
        # spammer une bulle Windows à chaque phrase dictée.
        if not self._controller.settings.get("show_notifications", False):
            return
        short = (text[:40] + "…") if len(text) > 40 else text
        self.showMessage("ORAKLE", short, self._icons["idle"], 2000)

    def _on_error(self, msg: str) -> None:
        self.showMessage(
            "ORAKLE — erreur", msg, QSystemTrayIcon.MessageIcon.Critical, 4000
        )

    def _set_language(self, code) -> None:  # noqa: ANN001
        self._controller.set_force_language(code)

    def _open_dictionary(self) -> None:
        if self._dict_window is None:
            self._dict_window = DictionaryWindow()
            self._dict_window.saved.connect(self._controller.reload_dictionary)
        else:
            self._dict_window._load()  # rafraîchir depuis le disque
        self._dict_window.show()
        self._dict_window.raise_()
        self._dict_window.activateWindow()

    def _quit(self) -> None:
        self._controller.shutdown()
        app = QApplication.instance()
        if app is not None:
            app.quit()
