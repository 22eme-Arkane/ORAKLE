"""Capture micro via sounddevice — flux « chaud » (persistant).

Ouvrir/fermer un flux sounddevice à chaque dictée coûte ~300-500 ms : sur un
appui court, le micro finit de s'ouvrir alors qu'on relâche déjà -> 0 échantillon.

On garde donc UN flux ouvert en continu (pré-ouvert au démarrage via `warm()`).
Le callback n'accumule les échantillons QUE lorsqu'on est « armé » (entre
start() et stop()). start()/stop() deviennent instantanés.

Confidentialité : le micro est techniquement ouvert tant que l'app tourne
(l'indicateur Windows « micro utilisé » s'affiche), MAIS aucun son n'est
bufferisé/gardé hors dictée — le callback jette les blocs quand on n'est pas armé.
Mono 16 kHz float32 (format attendu par faster-whisper). Aucun couplage Qt.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
CHANNELS = 1


class Recorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE, device=None) -> None:  # noqa: ANN001
        self.sample_rate = sample_rate
        # Périphérique d'entrée : None = défaut système ; sinon nom (sous-chaîne)
        # ou index sounddevice (ex. « Focusrite »).
        self.device = device or None
        self._stream = None
        self._stream_lock = threading.Lock()
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._armed = False
        self._level = 0.0

    @property
    def is_recording(self) -> bool:
        return self._armed

    @property
    def level(self) -> float:
        """Niveau audio instantané (RMS du dernier bloc), pour l'overlay."""
        return self._level

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            log.debug("sounddevice status: %s", status)
        if not self._armed:
            return  # hors dictée : on jette le bloc (rien n'est gardé)
        with self._lock:
            self._frames.append(indata.copy())
        try:
            self._level = float(np.sqrt(np.mean(np.square(indata, dtype=np.float32))))
        except Exception:
            pass

    def _open(self, sd, device):  # noqa: ANN001
        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=CHANNELS,
            dtype="float32",
            device=device,
            callback=self._callback,
        )
        stream.start()
        return stream

    def _ensure_stream(self) -> None:
        with self._stream_lock:
            if self._stream is not None:
                return
            import sounddevice as sd  # import paresseux

            try:
                self._stream = self._open(sd, self.device)
            except Exception as exc:
                if self.device is not None:
                    log.warning(
                        "Micro « %s » indisponible (%s) — bascule sur le défaut",
                        self.device, exc,
                    )
                    self._stream = self._open(sd, None)
                else:
                    raise
            # Journaliser le périphérique réellement utilisé.
            try:
                idx = self._stream.device
                name = sd.query_devices(idx)["name"]
                log.info("micro: flux ouvert (chaud) — périphérique: %s", name)
            except Exception:
                log.info("micro: flux ouvert (chaud)")

    def set_device(self, device) -> None:  # noqa: ANN001
        """Change de micro : ferme le flux courant et rouvre sur le nouveau."""
        self.device = device or None
        self.close()
        self.warm()

    @staticmethod
    def list_input_devices() -> list[dict]:
        """Périphériques d'entrée (name, index), via WASAPI de préférence.

        MME (host API par défaut) tronque les noms à 31 caractères et duplique
        chaque périphérique dans toutes les host APIs -> on filtre sur WASAPI
        (noms complets, une entrée par vrai périphérique). Repli : toutes APIs.
        """
        import sounddevice as sd

        try:
            apis = sd.query_hostapis()
            wasapi = next(
                (i for i, a in enumerate(apis) if "wasapi" in a["name"].lower()),
                None,
            )
        except Exception:
            wasapi = None

        def _collect(api_filter) -> list[dict]:
            out, seen = [], set()
            for i, d in enumerate(sd.query_devices()):
                if d.get("max_input_channels", 0) <= 0:
                    continue
                if api_filter is not None and d.get("hostapi") != api_filter:
                    continue
                name = d.get("name", f"device {i}")
                if name in seen:
                    continue
                seen.add(name)
                out.append({"index": i, "name": name})
            return out

        devices = _collect(wasapi) if wasapi is not None else []
        return devices or _collect(None)

    def warm(self) -> None:
        """Pré-ouvre le flux (coûteux ~centaines de ms) pour que start() soit
        instantané. À appeler au démarrage de l'app (idéalement en tâche de fond)."""
        try:
            self._ensure_stream()
        except Exception:
            log.exception("Impossible d'ouvrir le micro (warm)")

    def start(self) -> None:
        """Arme la capture (instantané si le flux est déjà chaud)."""
        self._ensure_stream()
        with self._lock:
            self._frames = []
        self._level = 0.0
        self._armed = True

    def stop(self) -> Optional[np.ndarray]:
        """Désarme et renvoie l'audio mono 1D float32 capturé (ou tableau vide)."""
        if not self._armed:
            return None
        self._armed = False
        self._level = 0.0
        with self._lock:
            frames = self._frames
            self._frames = []
        if not frames:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(frames, axis=0)
        if audio.ndim > 1:
            audio = audio.reshape(-1, audio.shape[-1])[:, 0]
        return audio.astype(np.float32, copy=False)

    def close(self) -> None:
        """Ferme le flux micro (à l'arrêt de l'app)."""
        self._armed = False
        with self._stream_lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                finally:
                    self._stream = None
