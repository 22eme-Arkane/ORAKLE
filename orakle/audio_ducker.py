"""Mise en sourdine des autres applications audio pendant la dictée (Windows).

Comme Wispr Flow : quand on enregistre, on coupe le son des autres applications
(Spotify, VLC, navigateur, jeux…) pour que la musique ne pollue pas la prise
micro, puis on restaure leur état EXACT à la fin.

Implémentation via WASAPI (pycaw) : on agit sur les *sessions audio par
application*, pas sur le volume système. On ne met pas en pause (geste
destructif/à bascule), on coupe le son (réversible).

Optionnel et tolérant aux pannes : si pycaw est absent ou si COM échoue, le
ducker ne fait RIEN (jamais de crash) — cohérent avec le principe local-first.

Note threads : `mute()` et `unmute()` ré-énumèrent les sessions à chaque appel et
ne conservent aucun objet COM entre les appels. L'état « précédent » est mémorisé
sous forme de simples `pid -> bool`, donc sûr à restaurer depuis un autre thread.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger(__name__)


class AudioDucker:
    def __init__(
        self,
        enabled: bool = True,
        targets: Optional[list[str]] = None,
    ) -> None:
        self.enabled = enabled
        # Noms de process à cibler (minuscules). Vide = toutes les apps.
        self.targets = {t.lower() for t in (targets or [])}
        self._own_pid = os.getpid()
        self._saved: dict[int, bool] = {}   # pid -> état mute précédent
        self._muted = False
        self._warned_unavailable = False    # avertir UNE fois si pycaw indispo

    @staticmethod
    def _sessions():
        # COM doit être initialisé DANS LE THREAD APPELANT : mute() part d'un
        # threading.Timer (confirmation) et unmute() du thread pynput ou du
        # worker. Sans CoInitialize ici, pycaw échoue en silence sur ces threads
        # (le ducking « ne fait rien »). S_FALSE (déjà initialisé) est inoffensif.
        try:
            import comtypes

            comtypes.CoInitialize()
        except Exception:
            pass
        from pycaw.pycaw import AudioUtilities  # import paresseux (Windows + pycaw)

        return AudioUtilities.GetAllSessions()

    def _is_target(self, proc) -> bool:  # noqa: ANN001
        if proc is None:
            return False
        try:
            if proc.pid == self._own_pid:
                return False
        except Exception:
            return False
        if not self.targets:
            return True
        try:
            name = (proc.name() or "").lower()
        except Exception:
            return False
        return name in self.targets

    def mute(self) -> None:
        """Coupe le son des apps ciblées en mémorisant leur état précédent."""
        if not self.enabled or self._muted:
            return
        try:
            saved: dict[int, bool] = {}
            for s in self._sessions():
                proc = s.Process
                if not self._is_target(proc):
                    continue
                vol = s.SimpleAudioVolume
                try:
                    saved[proc.pid] = bool(vol.GetMute())
                    vol.SetMute(1, None)
                except Exception:
                    continue
            self._saved = saved
            self._muted = True
            if saved:
                log.info(
                    "Audio coupé pour %d application(s) le temps de la dictée",
                    len(saved),
                )
        except Exception as exc:
            # pycaw absent / COM indisponible : on n'altère rien, mais on le DIT
            # (une fois) — un échec silencieux ici a déjà masqué un pycaw manquant.
            if not self._warned_unavailable:
                self._warned_unavailable = True
                log.warning(
                    "Sourdine des autres apps indisponible (%s) — "
                    "vérifier que pycaw est installé (pip install pycaw)", exc,
                )
            self._muted = False
            self._saved = {}

    def unmute(self) -> None:
        """Restaure l'état mute précédent des apps coupées (idempotent)."""
        if not self._muted:
            return
        saved = self._saved
        self._saved = {}
        self._muted = False
        if not saved:
            return
        try:
            for s in self._sessions():
                proc = s.Process
                if proc is None:
                    continue
                try:
                    if proc.pid in saved:
                        s.SimpleAudioVolume.SetMute(1 if saved[proc.pid] else 0, None)
                except Exception:
                    continue
        except Exception as exc:
            log.debug("Restauration audio impossible (%s)", exc)
