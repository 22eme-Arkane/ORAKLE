"""Contrôleur : relie raccourci -> enregistreur -> pipeline -> état du tray.

Pont entre les threads (pynput, worker de transcription) et la boucle Qt. Les
changements d'état sont publiés via des signaux Qt pour que le tray et l'overlay
(thread principal) se mettent à jour en sécurité. La transcription tourne dans
un thread worker dédié : elle ne bloque JAMAIS la boucle Qt.

Flux du raccourci (voir hotkey.py) :
- on_start   : démarrer la capture (tentative) ;
- on_confirm : capture confirmée -> état "recording" (overlay visible) ;
- on_commit  : arrêter + transcrire + injecter ;
- on_cancel  : arrêter + jeter (appui trop bref).
"""
from __future__ import annotations

import logging
import threading

from PyQt6.QtCore import QObject, pyqtSignal

from orakle import config
from orakle.audio_ducker import AudioDucker
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
        self.ducker = AudioDucker(
            enabled=bool(self.settings.get("mute_media_while_recording", True)),
            targets=self.settings.get("mute_targets", []),
        )
        self.hotkey = HotkeyManager(
            hotkey=self.settings.get("hotkey", "<ctrl>+1"),
            on_start=self._rec_start,
            on_confirm=self._rec_confirm,
            on_commit=self._rec_commit,
            on_cancel=self._rec_cancel,
            hold_threshold_ms=int(self.settings.get("hold_threshold_ms", 300)),
            double_tap_window_ms=int(self.settings.get("double_tap_window_ms", 400)),
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
        self.ducker.unmute()

    def reload_dictionary(self) -> None:
        """Recharge le dictionnaire (après édition) sans redémarrer l'app."""
        self.dictionary = config.load_dictionary()
        self.pipeline.dictionary = self.dictionary
        log.info("Dictionnaire rechargé")

    def set_force_language(self, code: Optional[str]) -> None:
        """Force une langue de transcription (None = détection auto). Persisté."""
        self.settings["force_language"] = code
        try:
            config.save_settings(self.settings)
        except Exception:
            log.exception("Échec sauvegarde de la langue forcée")
        log.info("Langue forcée : %s", code or "auto")

    # --- callbacks raccourci (thread pynput) ---
    def _rec_start(self) -> None:
        """Démarre la capture (tentative). N'affiche pas encore l'overlay."""
        if self._busy:
            return
        try:
            self.recorder.start()
        except Exception as exc:
            log.exception("Échec démarrage enregistrement")
            self.error.emit(str(exc))

    def _rec_confirm(self) -> None:
        """Capture confirmée -> état recording (icône + overlay) + mute audio."""
        if self.recorder.is_recording:
            self.state_changed.emit("recording")
            # Couper le son des autres apps pendant la prise (anti-interférence).
            self.ducker.mute()

    def _rec_cancel(self) -> None:
        """Appui trop bref -> on jette l'audio, retour au repos."""
        if self.recorder.is_recording:
            self.recorder.stop()
        self.ducker.unmute()
        self.state_changed.emit("idle")

    def _rec_commit(self) -> None:
        """Fin d'enregistrement -> transcription + injection."""
        if not self.recorder.is_recording:
            return
        audio = self.recorder.stop()
        self.ducker.unmute()  # restaurer le son dès la fin de capture
        self.state_changed.emit("processing")
        self._busy = True
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    # --- worker (thread dédié, hors boucle Qt) ---
    def _process(self, audio) -> None:  # noqa: ANN001
        try:
            # None = détection automatique (restreinte au set FR/EN/ES).
            lang = self.settings.get("force_language")
            text = self.pipeline.run(audio, language=lang)
            if text:
                self.text_injected.emit(text)
        except Exception as exc:
            log.exception("Échec du pipeline")
            self.error.emit(str(exc))
        finally:
            self.ducker.unmute()  # sécurité : ne jamais laisser une app muette
            self._busy = False
            self.state_changed.emit("idle")
