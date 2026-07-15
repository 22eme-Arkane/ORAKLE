"""Point d'entrée ORAKLE : QApplication + system tray + contrôleur.

L'app vit dans le tray (aucune fenêtre au démarrage). Maintenir Ctrl+1 pour
dicter (Phase 1). Lancer avec :  python main.py
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from PyQt6.QtCore import QLockFile
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from orakle import config
from orakle.controller import Controller
from orakle.version import VERSION
from ui.app_icon import load_logo_icon
from ui.overlay import RecordingOverlays
from ui.tray import OrakleTray


def _setup_logging() -> None:
    """Console + fichier %APPDATA%/orakle/orakle.log.

    Le fichier est essentiel pour l'exe fenêtré (console invisible) : c'est le
    seul moyen de diagnostiquer un problème en version installée.
    """
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)
    try:
        log_dir = config.user_config_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_dir / "orakle.log", maxBytes=512_000, backupCount=1, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception:  # jamais bloquer le démarrage pour un souci de log
        pass


def main() -> int:
    _setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("ORAKLE")
    app.setQuitOnLastWindowClosed(False)  # l'app vit en tray
    _logo = load_logo_icon()
    if _logo is not None:
        app.setWindowIcon(_logo)  # icône fenêtres + barre des tâches

    # Instance unique : deux ORAKLE = deux hooks clavier et deux micros qui se
    # battent (« ça ne répond plus »). QLockFile gère les verrous périmés.
    lock_dir = config.user_config_dir()
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(lock_dir / "orakle.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        logging.getLogger(__name__).warning("ORAKLE déjà lancé — sortie")
        QMessageBox.information(
            None, "ORAKLE",
            "ORAKLE est déjà lancé.\nSon icône se trouve près de l'horloge "
            "(zone de notification, sous la flèche ^).",
        )
        return 0

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
    logging.getLogger(__name__).info(
        "ORAKLE %s démarré — maintenir %s pour dicter",
        VERSION, controller.settings.get("hotkey", "<ctrl>+1"),
    )

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
