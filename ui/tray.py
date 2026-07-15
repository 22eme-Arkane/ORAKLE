"""System tray ORAKLE : icône d'état + menu contextuel.

L'icône reflète l'état (idle / recording / processing). Les icônes sont dessinées
en code (QPainter) pour éviter tout asset binaire à ce stade ; elles pourront
être remplacées par des PNG de `resources/` plus tard.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ui.app_icon import load_logo_pixmap, state_icon
from ui.dictionary_window import DictionaryWindow

# Libellé -> code (None = détection automatique).
_LANG_CHOICES = [("Auto", None), ("Français", "fr"), ("English", "en"), ("Español", "es")]

# Repli (logo absent) : cohérent avec les pastilles d'état (bleu/jaune daltonien).
_STATE_COLORS = {
    "idle": "#8a90b0",        # gris neutre
    "recording": "#ffc83d",   # jaune
    "processing": "#2d7dff",  # bleu
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
        self._settings_window = None
        # Logo si présent (resources/logo.png|ico), sinon ronds de couleur.
        logo = load_logo_pixmap(256)
        if logo is not None:
            self._icons = {
                s: state_icon(logo, s) for s in ("idle", "recording", "processing")
            }
        else:
            self._icons = {s: _make_icon(c) for s, c in _STATE_COLORS.items()}
        self.setIcon(self._icons["idle"])
        hotkey = controller.settings.get("hotkey", "<ctrl>+1")
        pretty = "+".join(p.strip("<>").capitalize() for p in hotkey.split("+") if p)
        self.setToolTip(f"ORAKLE — maintenir {pretty} (ou double-tap) pour dicter")

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

        # Sous-menu Microphone (rempli à l'ouverture pour refléter le matériel).
        self._mic_menu = menu.addMenu("Microphone")
        self._mic_menu.aboutToShow.connect(self._populate_mics)

        dict_action = QAction("Dictionnaire…", menu)
        dict_action.triggered.connect(self._open_dictionary)
        menu.addAction(dict_action)
        settings_action = QAction("Réglages…", menu)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)
        menu.addSeparator()
        quit_action = QAction("Quitter", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)
        self.setContextMenu(menu)

        self._menu = menu
        self._update_action = None
        controller.state_changed.connect(self._on_state)
        controller.text_injected.connect(self._on_injected)
        controller.error.connect(self._on_error)
        controller.update_available.connect(self._on_update_available)

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

    def _populate_mics(self) -> None:
        """Reconstruit le sous-menu Microphone d'après le matériel présent."""
        self._mic_menu.clear()
        self._mic_group = QActionGroup(self._mic_menu)
        self._mic_group.setExclusive(True)
        current = self._controller.settings.get("input_device")

        auto = QAction("Auto (défaut système)", self._mic_menu, checkable=True)
        auto.setChecked(not current)
        auto.triggered.connect(lambda _c: self._controller.set_input_device(None))
        self._mic_group.addAction(auto)
        self._mic_menu.addAction(auto)
        self._mic_menu.addSeparator()

        try:
            from orakle.recorder import Recorder

            for dev in Recorder.list_input_devices():
                name = dev["name"]
                act = QAction(name, self._mic_menu, checkable=True)
                act.setChecked(current == name)
                act.triggered.connect(lambda _c, n=name: self._controller.set_input_device(n))
                self._mic_group.addAction(act)
                self._mic_menu.addAction(act)
        except Exception as exc:  # noqa: BLE001
            err = QAction(f"(énumération impossible : {exc})", self._mic_menu)
            err.setEnabled(False)
            self._mic_menu.addAction(err)

    def _open_dictionary(self) -> None:
        if self._dict_window is None:
            self._dict_window = DictionaryWindow()
            self._dict_window.saved.connect(self._controller.reload_dictionary)
        else:
            self._dict_window._load()  # rafraîchir depuis le disque
        self._dict_window.show()
        self._dict_window.raise_()
        self._dict_window.activateWindow()

    def _on_update_available(self, version: str, url: str) -> None:
        """Nouvelle version sur GitHub : entrée de menu + notification (1 fois)."""
        if self._update_action is not None:
            return
        import webbrowser

        act = QAction(f"⬆ Mettre à jour vers {version}…", self._menu)
        act.triggered.connect(lambda _c: webbrowser.open(url))
        first = self._menu.actions()[0] if self._menu.actions() else None
        self._menu.insertAction(first, act)
        self._update_action = act
        # Notification légitime même si les notifs de dictée sont coupées :
        # unique par session, et c'est une information de sécurité/maj.
        self.showMessage(
            "ORAKLE — mise à jour disponible",
            f"La version {version} est disponible. Clic droit sur l'icône → "
            f"« Mettre à jour » pour la télécharger.",
            QSystemTrayIcon.MessageIcon.Information, 6000,
        )

    def _on_settings_saved(self) -> None:
        self._controller.reload_settings()
        self._controller.reload_dictionary()  # un import peut aussi changer le dico

    def _open_settings(self) -> None:
        from ui.settings_window import SettingsWindow

        if self._settings_window is None:
            self._settings_window = SettingsWindow()
            self._settings_window.saved.connect(self._on_settings_saved)
        else:
            self._settings_window._load()  # rafraîchir depuis le disque
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _quit(self) -> None:
        self._controller.shutdown()
        app = QApplication.instance()
        if app is not None:
            app.quit()
