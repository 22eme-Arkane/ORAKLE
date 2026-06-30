"""Point d'entrée ORAKLE : QApplication + system tray + contrôleur.

L'app vit dans le tray (aucune fenêtre au démarrage). Maintenir Ctrl+1 pour
dicter (Phase 1). Lancer avec :  python main.py
"""
from __future__ import annotations

import logging
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from orakle.controller import Controller
from ui.tray import OrakleTray


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> int:
    _setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("ORAKLE")
    app.setQuitOnLastWindowClosed(False)  # l'app vit en tray

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "ORAKLE", "Aucun system tray disponible.")
        return 1

    controller = Controller()
    tray = OrakleTray(controller)
    tray.show()
    controller.start()
    logging.getLogger(__name__).info("ORAKLE démarré — maintenir Ctrl+1 pour dicter")

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
