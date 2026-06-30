"""Contrôleur : relie raccourci -> enregistreur -> pipeline -> état du tray.

Sert de pont entre les threads (pynput, worker de transcription) et la boucle Qt.
Les changements d'état sont publiés via des signaux Qt pour que le tray (thread
principal) mette à jour son icône en toute sécurité. La transcription tourne
dans un thread worker dédié : elle ne bloque JAMAIS la boucle Qt.
"""
from __future__ import annotations

import logging
import threading

from PyQt6.QtCore import QObject, pyqtSignal

from orakle import config
from orakle.hotkey import HotkeyManager
from orakle.pipeline import Pipeline
from orakle.recorder import Recorder

log = logging.getLogger(__name__)


class Controller(QObject):
    # "idle" | "recording" | "processing"
    state_changed = pyqtSignal(str)
    text_injected = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.settings = config.load_settings()
        self.dictionary = config.load_dictionary()
        self.recorder = Recorder()
        self.pipeline = Pipeline(self.settings, self.dictionary)
        self.hotkey = HotkeyManager(
            hotkey=self.settings.get("hotkey", "<ctrl>+1"),
            on_start=self._on_hotkey_start,
            on_stop=self._on_hotkey_stop,
        )
        self._busy = False

    def start(self) -> None:
        self.hotkey.start()
        self.state_changed.emit("idle")

    def shutdown(self) -> None:
        try:
            self.hotkey.stop()
        except Exception:
            log.exception("Erreur à l'arrêt du raccourci")
        if self.recorder.is_recording:
            self.recorder.stop()

    # --- callbacks raccourci (thread pynput) ---
    def _on_hotkey_start(self) -> None:
        if self._busy:
            return  # une transcription est en cours : on ignore
        try:
            self.recorder.start()
            self.state_changed.emit("recording")
        except Exception as exc:
            log.exception("Échec démarrage enregistrement")
            self.error.emit(str(exc))

    def _on_hotkey_stop(self) -> None:
        if not self.recorder.is_recording:
            return
        audio = self.recorder.stop()
        self.state_changed.emit("processing")
        self._busy = True
        threading.Thread(
            target=self._process, args=(audio,), daemon=True
        ).start()

    # --- worker (thread dédié, hors boucle Qt) ---
    def _process(self, audio) -> None:  # noqa: ANN001
        try:
            lang = self.settings.get("force_language") or "fr"
            text = self.pipeline.run(audio, language=lang)
            if text:
                self.text_injected.emit(text)
        except Exception as exc:
            log.exception("Échec du pipeline")
            self.error.emit(str(exc))
        finally:
            self._busy = False
            self.state_changed.emit("idle")
