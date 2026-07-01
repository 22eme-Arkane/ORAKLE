"""Point d'entrée ORAKLE : QApplication + system tray + contrôleur.

L'app vit dans le tray (aucune fenêtre au démarrage). Maintenir Ctrl+1 pour
dicter (Phase 1). Lancer avec :  python main.py
"""
from __future__ import annotations

import logging
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from orakle.controller import Controller
from ui.app_icon import load_logo_icon
from ui.overlay import RecordingOverlays
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
    _logo = load_logo_icon()
    if _logo is not None:
        app.setWindowIcon(_logo)  # icône fenêtres + barre des tâches

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "ORAKLE", "Aucun system tray disponible.")
        return 1

    controller = Controller()
    tray = OrakleTray(controller)
    tray.show()

    # Overlay d'enregistrement (capsule + onde de forme) sur TOUS les écrans, branché
    # sur l'état. Le niveau micro est mis à l'échelle pour l'affichage (RMS voix ~0,02-0,1).
    overlay = RecordingOverlays(
        level_provider=lambda: min(1.0, controller.recorder.level * 12.0)
    )

    def _on_state(state: str) -> None:
        if state == "recording":
            overlay.show_overlay()
        else:
            overlay.hide_overlay()

    controller.state_changed.connect(_on_state)
    controller.start()
    logging.getLogger(__name__).info("ORAKLE démarré — maintenir Ctrl+1 pour dicter")

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
