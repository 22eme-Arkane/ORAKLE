"""Capture micro via sounddevice.

Enregistre en mono 16 kHz float32 (format attendu par faster-whisper).
`start()` ouvre le flux, `stop()` le ferme et renvoie le buffer concaténé.
Aucun couplage Qt.
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
    """Enregistreur micro thread-safe (callback sounddevice + buffer protégé)."""

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate
        self._stream = None
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            log.debug("sounddevice status: %s", status)
        with self._lock:
            self._frames.append(indata.copy())

    def start(self) -> None:
        import sounddevice as sd  # import paresseux : pas de dépendance au chargement

        if self._recording:
            return
        with self._lock:
            self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=CHANNELS,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()
        self._recording = True

    def stop(self) -> Optional[np.ndarray]:
        """Ferme le flux et renvoie l'audio mono 1D float32 (ou tableau vide)."""
        if not self._recording:
            return None
        self._recording = False
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        finally:
            self._stream = None
        with self._lock:
            if not self._frames:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._frames, axis=0)
        if audio.ndim > 1:
            audio = audio.reshape(-1, audio.shape[-1])[:, 0]
        return audio.astype(np.float32, copy=False)
