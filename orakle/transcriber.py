"""Transcription via faster-whisper (CTranslate2).

Chargement paresseux du modèle (le 1er run peut télécharger les poids).
Sélection du device en auto : CUDA si dispo, sinon CPU int8. Aucun couplage Qt.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


class Transcriber:
    def __init__(
        self,
        model: str = "small",
        device: str = "auto",
        compute_type: str = "int8",
    ) -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _resolve_device(self) -> tuple[str, str]:
        """Retourne (device, compute_type) effectifs."""
        if self.device != "auto":
            return self.device, self.compute_type
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda", "float16"
        except Exception:  # ctranslate2 absent ou pas de CUDA
            pass
        return "cpu", "int8"

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        device, compute_type = self._resolve_device()
        log.info(
            "Chargement Whisper '%s' (device=%s, compute=%s)…",
            self.model_name, device, compute_type,
        )
        self._model = WhisperModel(
            self.model_name, device=device, compute_type=compute_type
        )

    def transcribe(
        self,
        audio: np.ndarray,
        language: Optional[str] = "fr",
        initial_prompt: Optional[str] = None,
    ) -> str:
        if audio is None or len(audio) == 0:
            return ""
        self._ensure_model()
        assert self._model is not None
        segments, _info = self._model.transcribe(
            audio,
            language=language,
            initial_prompt=initial_prompt,
            beam_size=5,
            vad_filter=True,
        )
        return "".join(seg.text for seg in segments).strip()
