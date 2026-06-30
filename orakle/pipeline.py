"""Orchestration : audio -> STT -> [traduction] -> correction -> injection.

Pur Python, aucun couplage Qt.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import numpy as np

from . import injector, translator
from .command_parser import parse_command
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
            languages=settings.get("languages"),
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

    def _maybe_translate(self, text: str) -> str:
        """Si le texte débute par une commande de traduction, traduit le reste."""
        tcfg = self.settings.get("translation", {})
        cmd = parse_command(
            text,
            keywords=tcfg.get("command_keywords"),
            linkers=tcfg.get("linkers"),
        )
        if cmd is None:
            return text
        src, dst, content = cmd
        log.info("Commande de traduction détectée : %s -> %s", src, dst)
        translated = translator.translate(content, src, dst, self.settings)
        return translated or content

    def run(self, audio: np.ndarray, language: Optional[str] = None) -> str:
        """Transcrit, (traduit), corrige et injecte. Retourne le texte injecté."""
        text = self._transcriber.transcribe(
            audio, language=language, initial_prompt=self._initial_prompt()
        )
        text = self._apply_corrections(text)
        if not text:
            log.info("Transcription vide — rien à injecter")
            return ""
        text = self._maybe_translate(text)
        if not text:
            return ""
        inj = self.settings.get("injection", {})
        injector.inject(
            text,
            method=inj.get("method", "clipboard_paste"),
            restore_clipboard=inj.get("restore_clipboard", True),
            append_space=self.settings.get("append_trailing_space", True),
        )
        return text
