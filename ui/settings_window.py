"""Fenêtre de réglages ORAKLE.

Sections : Général (raccourci, seuils, injection, notifications), Dictée
(modèle Whisper, device, micro), Audio (sourdine des autres apps), Traduction
(moteur, Ollama, BYOK), Export/Import.

Pas d'auto-save : bouton « Enregistrer » explicite -> écrit settings.json puis
émet `saved` (le contrôleur recharge à chaud via reload_settings). Aucune
logique métier ici : lecture/écriture via orakle.config uniquement.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from orakle import config
from orakle.hotkey import HotkeyManager

_STYLE = """
QWidget { background: #0c0e1a; color: #e6e8f0; font-size: 13px; }
QGroupBox {
    border: 1px solid #2a2e45; border-radius: 8px;
    margin-top: 12px; padding: 10px 8px 8px 8px;
    font-weight: 600; color: #9cb4ff;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit, QComboBox, QSpinBox {
    background: #141627; border: 1px solid #2a2e45; border-radius: 6px;
    padding: 4px 6px; selection-background-color: #2d3556;
}
QComboBox QAbstractItemView { background: #141627; border: 1px solid #2a2e45; }
QPushButton {
    background: transparent; border: 1px solid #3a4166; border-radius: 6px;
    padding: 5px 12px;
}
QPushButton:hover { background: #1c2036; }
QPushButton#primary { border: 1px solid #5b8def; color: #9cb4ff; }
QCheckBox::indicator { width: 15px; height: 15px; }
QLabel#hint { color: #8a90b0; font-size: 11px; }
QScrollArea { border: 0; }
"""

_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
_DEVICES = [("CPU (recommandé)", "cpu"), ("Auto (GPU si utilisable)", "auto"), ("GPU (CUDA)", "cuda")]
_ENGINES = [("Argos (hors-ligne, défaut)", "argos"), ("Ollama (LLM local)", "ollama"), ("Anthropic (cloud BYOK)", "anthropic")]


class SettingsWindow(QWidget):
    saved = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ORAKLE — Réglages")
        self.setStyleSheet(_STYLE)
        self.resize(560, 680)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Jamais de défilement horizontal : le contenu s'adapte à la largeur.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setSpacing(10)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # --- Général ---
        g1 = QGroupBox("Général")
        f1 = QFormLayout(g1)
        self._hotkey = QLineEdit()
        self._hotkey.setPlaceholderText("<ctrl>+1")
        f1.addRow("Raccourci :", self._hotkey)
        hint = QLabel("Format : <ctrl>+<touche> — ex. <ctrl>+1, <ctrl>+<alt>+d")
        hint.setObjectName("hint")
        f1.addRow("", hint)
        self._exclusive = QCheckBox("Réserver le raccourci à ORAKLE (invisible pour les autres applications)")
        f1.addRow("", self._exclusive)
        self._hold = QSpinBox()
        self._hold.setRange(100, 1500)
        self._hold.setSuffix(" ms")
        f1.addRow("Seuil de maintien :", self._hold)
        self._dtap = QSpinBox()
        self._dtap.setRange(200, 1500)
        self._dtap.setSuffix(" ms")
        f1.addRow("Fenêtre double-tap :", self._dtap)
        self._space = QCheckBox("Ajouter un espace après le texte injecté")
        f1.addRow("", self._space)
        self._notif = QCheckBox("Notification Windows à chaque dictée")
        f1.addRow("", self._notif)
        self._toast = QCheckBox("Confirmation discrète en bas à droite (« Texte inséré » + bouton Copier)")
        f1.addRow("", self._toast)
        self._updates = QCheckBox("Vérifier les mises à jour au démarrage (GitHub)")
        f1.addRow("", self._updates)
        root.addWidget(g1)

        # --- Dictée ---
        g2 = QGroupBox("Dictée (Whisper)")
        f2 = QFormLayout(g2)
        self._model = QComboBox()
        self._model.addItems(_MODELS)
        f2.addRow("Modèle :", self._model)
        hint2 = QLabel("small = bon compromis CPU. medium/large-v3 = plus précis, plus lent.")
        hint2.setObjectName("hint")
        f2.addRow("", hint2)
        self._device = QComboBox()
        for label, code in _DEVICES:
            self._device.addItem(label, code)
        f2.addRow("Calcul :", self._device)
        self._mic = QComboBox()
        f2.addRow("Microphone :", self._mic)
        root.addWidget(g2)

        # --- Audio ---
        g3 = QGroupBox("Audio")
        f3 = QFormLayout(g3)
        self._duck = QCheckBox("Couper le son des autres applications pendant la dictée")
        f3.addRow("", self._duck)
        root.addWidget(g3)

        # --- Traduction ---
        g4 = QGroupBox("Traduction à la volée")
        f4 = QFormLayout(g4)
        self._engine = QComboBox()
        for label, code in _ENGINES:
            self._engine.addItem(label, code)
        f4.addRow("Moteur :", self._engine)
        self._ollama_host = QLineEdit()
        self._ollama_host.setPlaceholderText("http://localhost:11434")
        f4.addRow("Ollama — hôte :", self._ollama_host)
        self._ollama_model = QLineEdit()
        self._ollama_model.setPlaceholderText("mistral")
        f4.addRow("Ollama — modèle :", self._ollama_model)
        self._byok = QCheckBox("Autoriser le moteur cloud Anthropic (BYOK)")
        f4.addRow("", self._byok)
        self._anthropic_key = QLineEdit()
        self._anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._anthropic_key.setPlaceholderText("clé API Anthropic (optionnel)")
        f4.addRow("Clé Anthropic :", self._anthropic_key)
        hint4 = QLabel("L'app reste 100 % fonctionnelle sans aucune clé.")
        hint4.setObjectName("hint")
        f4.addRow("", hint4)
        root.addWidget(g4)

        # --- Export / Import ---
        g5 = QGroupBox("Sauvegarde de la configuration")
        h5 = QHBoxLayout(g5)
        btn_export = QPushButton("Exporter…")
        btn_export.clicked.connect(self._export)
        btn_import = QPushButton("Importer…")
        btn_import.clicked.connect(self._import)
        h5.addWidget(btn_export)
        h5.addWidget(btn_import)
        h5.addStretch(1)
        root.addWidget(g5)
        root.addStretch(1)

        # --- Boutons bas ---
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(self.close)
        btn_save = QPushButton("Enregistrer")
        btn_save.setObjectName("primary")
        btn_save.clicked.connect(self._save)
        bottom.addWidget(btn_close)
        bottom.addWidget(btn_save)
        outer.addLayout(bottom)

        self._load()

    # --- chargement ---
    def _populate_mics(self, current) -> None:  # noqa: ANN001
        self._mic.clear()
        self._mic.addItem("Auto (défaut système)", None)
        try:
            from orakle.recorder import Recorder

            for dev in Recorder.list_input_devices():
                self._mic.addItem(dev["name"], dev["name"])
        except Exception:
            pass
        idx = self._mic.findData(current)
        self._mic.setCurrentIndex(idx if idx >= 0 else 0)

    def _load(self) -> None:
        s = config.load_settings()
        self._hotkey.setText(s.get("hotkey", "<ctrl>+1"))
        self._exclusive.setChecked(bool(s.get("exclusive_hotkey", True)))
        self._hold.setValue(int(s.get("hold_threshold_ms", 300)))
        self._dtap.setValue(int(s.get("double_tap_window_ms", 400)))
        self._space.setChecked(bool(s.get("append_trailing_space", True)))
        self._notif.setChecked(bool(s.get("show_notifications", False)))
        self._toast.setChecked(bool(s.get("show_status_toast", True)))
        self._updates.setChecked(bool(s.get("check_updates", True)))
        model = s.get("model", "small")
        self._model.setCurrentText(model if model in _MODELS else "small")
        di = self._device.findData(s.get("device", "cpu"))
        self._device.setCurrentIndex(di if di >= 0 else 0)
        self._populate_mics(s.get("input_device"))
        self._duck.setChecked(bool(s.get("mute_media_while_recording", True)))
        t = s.get("translation", {})
        ei = self._engine.findData(t.get("engine", "argos"))
        self._engine.setCurrentIndex(ei if ei >= 0 else 0)
        o = t.get("ollama", {})
        self._ollama_host.setText(o.get("host", "http://localhost:11434"))
        self._ollama_model.setText(o.get("model", "mistral"))
        self._byok.setChecked(bool(t.get("byok_enabled", False)))
        self._anthropic_key.setText(t.get("anthropic_key", ""))

    # --- sauvegarde ---
    def _save(self) -> None:
        hotkey = self._hotkey.text().strip() or "<ctrl>+1"
        mods, main = HotkeyManager._parse(hotkey)
        if main is None:
            QMessageBox.warning(
                self, "ORAKLE",
                "Raccourci invalide : il faut une touche principale.\n"
                "Exemple : <ctrl>+1",
            )
            return
        s = config.load_settings()  # repartir du fichier pour ne rien perdre
        s["hotkey"] = hotkey
        s["exclusive_hotkey"] = self._exclusive.isChecked()
        s["hold_threshold_ms"] = self._hold.value()
        s["double_tap_window_ms"] = self._dtap.value()
        s["append_trailing_space"] = self._space.isChecked()
        s["show_notifications"] = self._notif.isChecked()
        s["show_status_toast"] = self._toast.isChecked()
        s["check_updates"] = self._updates.isChecked()
        s["model"] = self._model.currentText()
        s["device"] = self._device.currentData()
        s["input_device"] = self._mic.currentData()
        s["mute_media_while_recording"] = self._duck.isChecked()
        t = s.setdefault("translation", {})
        t["engine"] = self._engine.currentData()
        o = t.setdefault("ollama", {})
        o["host"] = self._ollama_host.text().strip() or "http://localhost:11434"
        o["model"] = self._ollama_model.text().strip() or "mistral"
        t["byok_enabled"] = self._byok.isChecked()
        key = self._anthropic_key.text().strip()
        if key:
            t["anthropic_key"] = key
        elif "anthropic_key" in t:
            del t["anthropic_key"]
        try:
            config.save_settings(s)
        except Exception as exc:
            QMessageBox.critical(self, "ORAKLE", f"Échec de l'enregistrement :\n{exc}")
            return
        self.saved.emit()
        self.close()

    # --- export / import ---
    def _export(self) -> None:
        path, _f = QFileDialog.getSaveFileName(
            self, "Exporter la configuration", "orakle_config.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            config.export_all(path)
        except Exception as exc:
            QMessageBox.critical(self, "ORAKLE", f"Échec de l'export :\n{exc}")
            return
        QMessageBox.information(self, "ORAKLE", "Configuration exportée.")

    def _import(self) -> None:
        path, _f = QFileDialog.getOpenFileName(
            self, "Importer une configuration", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            config.import_all(path)
        except Exception as exc:
            QMessageBox.critical(self, "ORAKLE", f"Import impossible :\n{exc}")
            return
        self._load()
        self.saved.emit()
        QMessageBox.information(self, "ORAKLE", "Configuration importée et appliquée.")
