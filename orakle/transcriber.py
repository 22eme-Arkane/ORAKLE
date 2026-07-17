"""Transcription via faster-whisper (CTranslate2).

Chargement paresseux du modèle (le 1er run peut télécharger les poids).
Sélection du device en auto : CUDA seulement s'il est RÉELLEMENT utilisable
(GPU présent ET DLL cuBLAS chargeables), sinon CPU int8. Un filet de repli
bascule sur CPU si l'inférence GPU échoue malgré tout. Aucun couplage Qt.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# Indices d'une erreur liée au GPU/aux DLL CUDA (cuBLAS/cuDNN manquantes).
_GPU_ERROR_HINTS = ("cublas", "cudnn", "cuda", "gpu", ".dll", ".so")


class Transcriber:
    def __init__(
        self,
        model: str = "small",
        device: str = "auto",
        compute_type: str = "int8",
        languages: Optional[list[str]] = None,
    ) -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self._languages = {l.lower() for l in (languages or [])}
        self._model = None
        self._active_device = "cpu"

    @staticmethod
    def _cuda_usable() -> bool:
        """True seulement si un GPU CUDA est présent ET ses DLL chargeables.

        ctranslate2 ne bundle pas les bibliothèques CUDA : un GPU détecté ne
        garantit pas que cuBLAS/cuDNN sont installées. On le vérifie réellement
        pour éviter un crash à l'inférence (« cublas64_12.dll is not found »).
        """
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() <= 0:
                return False
        except Exception:
            return False
        # Vérifier le chargement effectif de cuBLAS (DLL Windows / .so Linux).
        import ctypes

        try:
            if sys.platform.startswith("win"):
                ctypes.WinDLL("cublas64_12.dll")
            else:
                ctypes.CDLL("libcublas.so.12")
        except OSError:
            return False
        return True

    def _resolve_device(self) -> tuple[str, str]:
        """Retourne (device, compute_type) effectifs."""
        if self.device != "auto":
            return self.device, self.compute_type
        if self._cuda_usable():
            return "cuda", "float16"
        return "cpu", "int8"

    def _build_model(self, device: str, compute_type: str) -> None:
        from faster_whisper import WhisperModel

        log.info(
            "Chargement Whisper '%s' (device=%s, compute=%s)…",
            self.model_name, device, compute_type,
        )
        try:
            # Cache local d'abord : sans réseau. Au démarrage de Windows le
            # Wi-Fi n'est pas toujours prêt — la vérification HuggingFace
            # bloquait la 1re dictée pendant des dizaines de secondes.
            self._model = WhisperModel(
                self.model_name, device=device, compute_type=compute_type,
                local_files_only=True,
            )
        except Exception:
            # Modèle pas (encore) en cache : téléchargement normal.
            self._model = WhisperModel(
                self.model_name, device=device, compute_type=compute_type
            )
        self._active_device = device

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        device, compute_type = self._resolve_device()
        try:
            self._build_model(device, compute_type)
        except Exception as exc:
            if device != "cpu":
                log.warning(
                    "Init Whisper sur %s impossible (%s) — repli CPU int8",
                    device, exc,
                )
                self._build_model("cpu", "int8")
            else:
                raise

    def warm(self) -> None:
        """Précharge le modèle (au démarrage, en tâche de fond).

        Sans ça, le modèle se charge à la PREMIÈRE dictée : 8 s à 1 min de
        latence surprise pendant laquelle les appuis suivants sont ignorés.
        """
        try:
            self._ensure_model()
            log.info("Whisper prêt (device=%s)", self._active_device)
        except Exception:
            log.exception("Préchargement Whisper impossible — chargera à la 1re dictée")

    def _detect_restricted(self, audio: np.ndarray) -> Optional[str]:
        """Détection de langue restreinte au set autorisé (FR/EN/ES).

        Best-effort : si l'API `detect_language` n'est pas disponible/échoue,
        retourne None -> Whisper fera sa détection automatique non restreinte.
        Toujours JOURNALISER le résultat : indispensable pour diagnostiquer les
        « il écrit en français quand je parle espagnol ».
        """
        if not self._languages:
            return None
        try:
            # vad_filter : ne pas détecter la langue sur le silence de début.
            raw_lang, raw_prob, all_probs = self._model.detect_language(  # type: ignore[attr-defined]
                audio, vad_filter=True
            )
        except TypeError:
            try:  # versions plus anciennes sans vad_filter
                raw_lang, raw_prob, all_probs = self._model.detect_language(audio)  # type: ignore[attr-defined]
            except Exception:
                log.info("détection de langue indisponible -> auto Whisper")
                return None
        except Exception:
            log.info("détection de langue indisponible -> auto Whisper")
            return None
        best = None
        try:
            for lang_code, prob in (all_probs or []):
                if lang_code in self._languages and (best is None or prob > best[1]):
                    best = (lang_code, prob)
        except Exception:
            pass
        if best is not None:
            log.info(
                "langue détectée : %s (%.2f) [brut : %s %.2f]",
                best[0], best[1], raw_lang, raw_prob,
            )
            return best[0]
        if raw_lang in self._languages:
            log.info("langue détectée : %s (%.2f)", raw_lang, raw_prob)
            return raw_lang
        log.info("langue détectée hors set (%s %.2f) -> auto", raw_lang, raw_prob)
        return None

    def _generate(
        self,
        audio: np.ndarray,
        language: Optional[str],
        initial_prompt: Optional[str],
    ) -> str:
        assert self._model is not None
        segments, _info = self._model.transcribe(
            audio,
            language=language,
            initial_prompt=initial_prompt,
            beam_size=5,
            vad_filter=True,
        )
        return "".join(seg.text for seg in segments).strip()

    @staticmethod
    def _looks_like_gpu_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(hint in msg for hint in _GPU_ERROR_HINTS)

    def transcribe(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
        initial_prompt: Optional[str] = None,
    ) -> str:
        if audio is None or len(audio) == 0:
            return ""
        self._ensure_model()
        # langue None/"" -> détection auto (restreinte au set si possible).
        resolved = language or self._detect_restricted(audio)
        if resolved is None:
            # Détection interne Whisper : NE PAS passer l'initial_prompt (le
            # biais du dictionnaire est en français et aimanterait la sortie
            # vers le français quelle que soit la langue parlée).
            initial_prompt = None
        try:
            return self._generate(audio, resolved, initial_prompt)
        except Exception as exc:
            # Filet de sécurité : si l'inférence GPU casse (DLL CUDA absentes),
            # on reconstruit le modèle sur CPU et on réessaie une fois.
            if self._active_device != "cpu" and self._looks_like_gpu_error(exc):
                log.warning(
                    "Inférence GPU impossible (%s) — bascule CPU int8 et réessai",
                    exc,
                )
                self._build_model("cpu", "int8")
                return self._generate(audio, resolved, initial_prompt)
            raise
