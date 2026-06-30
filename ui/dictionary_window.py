"""Éditeur de dictionnaire personnalisé.

Deux sections :
- **Termes de biais** : mots/noms propres injectés dans `initial_prompt` de
  Whisper pour qu'il les reconnaisse mieux (ex. « ORAKLE », « MadMapper »).
- **Corrections** : remplacements appliqués après transcription
  (« entendu » -> « corrigé »), insensibles à la casse.

Émet `saved` après écriture pour que le contrôleur recharge le dictionnaire à
chaud. Aucune logique métier ici : on lit/écrit via `orakle.config`.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from orakle import config

_STYLE = """
QWidget { background: #0c0e1a; color: #e6e8f0; font-size: 13px; }
QLabel#title { font-size: 15px; font-weight: 600; color: #9cb4ff; }
QLineEdit, QListWidget, QTableWidget {
    background: #141627; border: 1px solid #2a2e45; border-radius: 6px;
    selection-background-color: #2d3556;
}
QPushButton {
    background: transparent; border: 1px solid #3a4166; border-radius: 6px;
    padding: 5px 12px;
}
QPushButton:hover { background: #1c2036; }
QPushButton#primary { border: 1px solid #5b8def; color: #9cb4ff; }
QHeaderView::section { background: #141627; border: 0; padding: 4px; color: #8a90b0; }
"""


class DictionaryWindow(QWidget):
    saved = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ORAKLE — Dictionnaire")
        self.setStyleSheet(_STYLE)
        self.resize(440, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        # --- Termes de biais ---
        t1 = QLabel("Termes de biais")
        t1.setObjectName("title")
        root.addWidget(t1)
        root.addWidget(QLabel("Noms propres / jargon à mieux reconnaître."))
        self._bias_list = QListWidget()
        self._bias_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        root.addWidget(self._bias_list, 1)
        row1 = QHBoxLayout()
        self._bias_input = QLineEdit()
        self._bias_input.setPlaceholderText("Ajouter un terme… (ex. ORAKLE)")
        self._bias_input.returnPressed.connect(self._add_bias)
        btn_add_bias = QPushButton("Ajouter")
        btn_add_bias.clicked.connect(self._add_bias)
        btn_del_bias = QPushButton("Supprimer")
        btn_del_bias.clicked.connect(self._del_bias)
        row1.addWidget(self._bias_input, 1)
        row1.addWidget(btn_add_bias)
        row1.addWidget(btn_del_bias)
        root.addLayout(row1)

        # --- Corrections ---
        t2 = QLabel("Corrections")
        t2.setObjectName("title")
        root.addWidget(t2)
        root.addWidget(QLabel("« Entendu » → « Corrigé » (insensible à la casse)."))
        self._corr_table = QTableWidget(0, 2)
        self._corr_table.setHorizontalHeaderLabels(["Entendu", "Corrigé"])
        self._corr_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._corr_table.verticalHeader().setVisible(False)
        root.addWidget(self._corr_table, 1)
        row2 = QHBoxLayout()
        self._corr_wrong = QLineEdit()
        self._corr_wrong.setPlaceholderText("entendu")
        self._corr_right = QLineEdit()
        self._corr_right.setPlaceholderText("corrigé")
        self._corr_right.returnPressed.connect(self._add_corr)
        btn_add_corr = QPushButton("Ajouter")
        btn_add_corr.clicked.connect(self._add_corr)
        btn_del_corr = QPushButton("Supprimer")
        btn_del_corr.clicked.connect(self._del_corr)
        row2.addWidget(self._corr_wrong, 1)
        row2.addWidget(self._corr_right, 1)
        row2.addWidget(btn_add_corr)
        row2.addWidget(btn_del_corr)
        root.addLayout(row2)

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
        root.addLayout(bottom)

        self._load()

    # --- chargement / saisie ---
    def _load(self) -> None:
        data = config.load_dictionary()
        self._bias_list.clear()
        for term in data.get("bias_terms", []) or []:
            self._bias_list.addItem(str(term))
        self._corr_table.setRowCount(0)
        for wrong, right in (data.get("corrections") or {}).items():
            self._append_corr_row(str(wrong), str(right))

    def _append_corr_row(self, wrong: str, right: str) -> None:
        r = self._corr_table.rowCount()
        self._corr_table.insertRow(r)
        self._corr_table.setItem(r, 0, QTableWidgetItem(wrong))
        self._corr_table.setItem(r, 1, QTableWidgetItem(right))

    def _add_bias(self) -> None:
        term = self._bias_input.text().strip()
        if not term:
            return
        existing = {self._bias_list.item(i).text().lower()
                    for i in range(self._bias_list.count())}
        if term.lower() not in existing:
            self._bias_list.addItem(term)
        self._bias_input.clear()

    def _del_bias(self) -> None:
        for item in self._bias_list.selectedItems():
            self._bias_list.takeItem(self._bias_list.row(item))

    def _add_corr(self) -> None:
        wrong = self._corr_wrong.text().strip()
        right = self._corr_right.text().strip()
        if not wrong or not right:
            return
        self._append_corr_row(wrong, right)
        self._corr_wrong.clear()
        self._corr_right.clear()

    def _del_corr(self) -> None:
        rows = sorted({i.row() for i in self._corr_table.selectedItems()}, reverse=True)
        for r in rows:
            self._corr_table.removeRow(r)

    # --- sauvegarde ---
    def _save(self) -> None:
        bias = [self._bias_list.item(i).text().strip()
                for i in range(self._bias_list.count())
                if self._bias_list.item(i).text().strip()]
        corrections: dict[str, str] = {}
        for r in range(self._corr_table.rowCount()):
            w_item = self._corr_table.item(r, 0)
            r_item = self._corr_table.item(r, 1)
            wrong = w_item.text().strip() if w_item else ""
            right = r_item.text().strip() if r_item else ""
            if wrong and right:
                corrections[wrong] = right
        try:
            config.save_dictionary({"bias_terms": bias, "corrections": corrections})
        except Exception as exc:
            QMessageBox.critical(self, "ORAKLE", f"Échec de l'enregistrement :\n{exc}")
            return
        self.saved.emit()
        self.close()
