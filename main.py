"""Point d'entrée ORAKLE : QApplication + system tray + contrôleur.

L'app vit dans le tray (aucune fenêtre au démarrage). Maintenir Ctrl+1 pour
dicter (Phase 1). Lancer avec :  python main.py
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from PyQt6.QtCore import QLockFile, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from orakle import config
from orakle.controller import Controller
from orakle.tray_icon_visibility import promote_tray_icon
from orakle.version import VERSION
from ui.app_icon import load_logo_icon
from ui.overlay import RecordingOverlays
from ui.toast import StatusToast
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
    # Windows 11 : demander l'icône « toujours visible » près de l'horloge.
    # Différé : Windows crée l'entrée registre après le 1er affichage du tray.
    QTimer.singleShot(4000, promote_tray_icon)

    # Overlay d'enregistrement (capsule + onde de forme) sur TOUS les écrans, branché
    # sur l'état. Le niveau micro est mis à l'échelle pour l'affichage (RMS voix ~0,02-0,1).
    overlay = RecordingOverlays(
        level_provider=lambda: min(1.0, controller.recorder.level * 12.0)
    )
    # Toast discret bas-droite : « Transcription… » puis « Texte inséré » +
    # bouton Copier. C'est LE retour visuel qui manquait entre la fin de la
    # capture et l'arrivée du texte (3 à 8 s de traitement).
    toast = StatusToast()

    def _toast_on() -> bool:
        return bool(controller.settings.get("show_status_toast", True))

    def _on_state(state: str) -> None:
        if state == "recording":
            overlay.show_overlay()
            toast.hide()
            return
        overlay.hide_overlay()
        if state == "processing" and _toast_on():
            toast.show_processing()
        elif state == "idle":
            toast.on_idle()

    controller.state_changed.connect(_on_state)
    controller.text_injected.connect(
        lambda text: toast.show_result(text) if _toast_on() else None
    )
    controller.nothing_heard.connect(
        lambda: toast.show_info("Aucun texte reconnu") if _toast_on() else None
    )
    controller.error.connect(
        lambda msg: toast.show_error(msg) if _toast_on() else None
    )
    # Appui pendant une transcription en cours : re-signaler le toast au lieu
    # d'ignorer en silence (« je le fais plusieurs fois sans comprendre »).
    controller.busy_hint.connect(
        lambda: toast.show_processing() if _toast_on() else None
    )
    controller.start()
    logging.getLogger(__name__).info(
        "ORAKLE %s démarré — maintenir %s pour dicter",
        VERSION, controller.settings.get("hotkey", "<ctrl>+1"),
    )

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
