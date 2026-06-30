"""Orchestration : audio -> STT -> [traduction] -> correction -> injection.

Pur Python, aucun couplage Qt. La traduction (Phase 5) viendra s'insérer entre
la transcription et la correction via une interface `translator.translate(...)`.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import numpy as np

from . import injector
from .transcriber import Transcriber

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, settings: dict, dictionary: Optional[dict] = None) -> None:
        self.settings = settings
        self.dictionary = dictionary or {}
        self._transcriber = Transcriber(
            model=settings.get("model", "small"),
            device=settings.get("device", "auto"),
            compute_type=settings.get("compute_type", "int8"),
        )

    def _initial_prompt(self) -> Optional[str]:
        """Biaisage Whisper : injecte le vocabulaire perso dans initial_prompt."""
        terms = self.dictionary.get("bias_terms") or []
        return ", ".join(terms) if terms else None

    def _apply_corrections(self, text: str) -> str:
        """Post-correction : remplace les transcriptions fautives connues."""
        corrections = self.dictionary.get("corrections") or {}
        if not corrections or not text:
            return text
        out = text
        for wrong, right in corrections.items():
            if not wrong:
                continue
            pattern = re.compile(r"\b" + re.escape(wrong) + r"\b", re.IGNORECASE)
            out = pattern.sub(right, out)
        return out

    def run(self, audio: np.ndarray, language: Optional[str] = "fr") -> str:
        """Transcrit, corrige et injecte. Retourne le texte injecté (ou '')."""
        text = self._transcriber.transcribe(
            audio, language=language, initial_prompt=self._initial_prompt()
        )
        text = self._apply_corrections(text)
        if not text:
            log.info("Transcription vide — rien à injecter")
            return ""
        inj = self.settings.get("injection", {})
        injector.inject(
            text,
            method=inj.get("method", "clipboard_paste"),
            restore_clipboard=inj.get("restore_clipboard", True),
            append_space=self.settings.get("append_trailing_space", True),
        )
        return text
