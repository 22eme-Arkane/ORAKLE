"""Machine à états du raccourci global (Phase 2).

Un seul raccourci (`Ctrl+1` par défaut) gère DEUX modes, distingués par la durée
d'appui :

- **Maintien (push-to-talk)** : on garde le raccourci enfoncé, on parle, on
  relâche -> le texte est écrit.
- **Double-tap (mains-libres)** : deux appuis brefs rapprochés -> l'enregistrement
  démarre et reste actif sans rien tenir ; un appui bref suivant ferme et écrit.

Un appui bref **isolé** (ni maintien, ni 2e tap) ne déclenche rien.

Quatre callbacks de haut niveau sont émis (depuis le thread pynput) :
- `on_start`   : commencer la capture audio (peut être tentative, donc annulable).
- `on_confirm` : la capture est confirmée (vrai maintien ou mode mains-libres) ->
                 c'est le moment d'afficher l'overlay. Évite de faire clignoter
                 l'overlay sur les appuis brefs.
- `on_commit`  : arrêter la capture et lancer le pipeline (transcription+injection).
- `on_cancel`  : arrêter la capture et JETER l'audio (appui trop bref).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)

_MOD_NAMES = {"ctrl", "shift", "alt", "cmd"}


class HotkeyManager:
    def __init__(
        self,
        hotkey: str = "<ctrl>+1",
        on_start: Optional[Callable[[], None]] = None,
        on_confirm: Optional[Callable[[], None]] = None,
        on_commit: Optional[Callable[[], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        hold_threshold_ms: int = 300,
        double_tap_window_ms: int = 400,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._on_start = on_start
        self._on_confirm = on_confirm
        self._on_commit = on_commit
        self._on_cancel = on_cancel
        self._mods, self._main = self._parse(hotkey)
        self._hold_s = max(0.0, hold_threshold_ms / 1000.0)
        self._dtap_s = max(0.0, double_tap_window_ms / 1000.0)
        self._now = clock or time.monotonic

        self._listener = None
        self._ctrl_down = False
        self._shift_down = False
        self._alt_down = False

        self._engaged = False        # touche principale enfoncée (anti auto-repeat)
        self._recording = False
        self._mode: Optional[str] = None   # None | "hold" | "toggle"
        self._t_down = 0.0
        self._last_tap: Optional[float] = None   # ts du dernier tap court
        self._closing = False        # le prochain relâchement ferme un toggle
        self._confirm_timer: Optional[threading.Timer] = None
        self._lock = threading.RLock()

    # --- parsing du raccourci ---
    @staticmethod
    def _parse(hotkey: str) -> tuple[set[str], Optional[str]]:
        """'<ctrl>+1' -> ({'ctrl'}, '1')."""
        mods: set[str] = set()
        main: Optional[str] = None
        for part in hotkey.split("+"):
            token = part.strip().strip("<>").lower()
            if token in _MOD_NAMES:
                mods.add(token)
            elif token:
                main = token
        return mods, main

    # --- helpers touches ---
    def _mods_satisfied(self) -> bool:
        if "ctrl" in self._mods and not self._ctrl_down:
            return False
        if "shift" in self._mods and not self._shift_down:
            return False
        if "alt" in self._mods and not self._alt_down:
            return False
        return True

    @staticmethod
    def _key_char(key) -> Optional[str]:  # noqa: ANN001
        try:
            if getattr(key, "char", None):
                return key.char.lower()
        except Exception:
            pass
        vk = getattr(key, "vk", None)
        if vk is not None and 0x30 <= vk <= 0x39:
            return chr(vk)
        return None

    @staticmethod
    def _is_ctrl(key) -> bool:  # noqa: ANN001
        from pynput.keyboard import Key

        return key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r)

    @staticmethod
    def _is_shift(key) -> bool:  # noqa: ANN001
        from pynput.keyboard import Key

        return key in (Key.shift, Key.shift_l, Key.shift_r)

    @staticmethod
    def _is_alt(key) -> bool:  # noqa: ANN001
        from pynput.keyboard import Key

        return key in (Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr)

    @staticmethod
    def _fire(cb: Optional[Callable[[], None]]) -> None:
        if cb is None:
            return
        try:
            cb()
        except Exception:
            log.exception("Erreur dans un callback de raccourci")

    # --- timer de confirmation (maintien -> afficher overlay) ---
    def _cancel_confirm_timer(self) -> None:
        if self._confirm_timer is not None:
            self._confirm_timer.cancel()
            self._confirm_timer = None

    def _arm_confirm_timer(self) -> None:
        self._cancel_confirm_timer()
        if self._hold_s <= 0:
            return
        t = threading.Timer(self._hold_s, self._on_hold_elapsed)
        t.daemon = True
        self._confirm_timer = t
        t.start()

    def _on_hold_elapsed(self) -> None:
        """Appelé ~hold_threshold après l'appui : si toujours maintenu, confirmer."""
        with self._lock:
            if self._mode == "hold" and self._recording and self._engaged:
                self._fire(self._on_confirm)

    # --- machine à états (sous verrou) ---
    def _combo_down(self) -> None:
        with self._lock:
            if self._mode == "toggle":
                # Appui de fermeture du mode mains-libres.
                self._mode = None
                self._recording = False
                self._closing = True
                self._cancel_confirm_timer()
                self._fire(self._on_commit)
                return
            # Début d'un appui : capture tentative (sera confirmée ou annulée).
            self._t_down = self._now()
            self._recording = True
            self._mode = "hold"
            self._fire(self._on_start)
            self._arm_confirm_timer()

    def _combo_up(self) -> None:
        with self._lock:
            if self._closing:
                self._closing = False
                return
            if not self._recording or self._mode is None:
                return
            self._cancel_confirm_timer()
            duration = self._now() - self._t_down
            if self._mode == "hold" and duration >= self._hold_s:
                # Maintien confirmé -> push-to-talk.
                self._recording = False
                self._mode = None
                self._last_tap = None
                self._fire(self._on_commit)
                return
            # Appui bref -> annuler la capture tentative.
            now = self._now()
            self._recording = False
            self._mode = None
            self._fire(self._on_cancel)
            if self._last_tap is not None and (now - self._last_tap) <= self._dtap_s:
                # DOUBLE-TAP -> mode mains-libres.
                self._last_tap = None
                self._mode = "toggle"
                self._recording = True
                self._fire(self._on_start)
                self._fire(self._on_confirm)
            else:
                # 1er tap : mémoriser pour un éventuel 2e.
                self._last_tap = now

    # --- callbacks pynput ---
    def _on_press(self, key) -> None:  # noqa: ANN001
        if self._is_ctrl(key):
            self._ctrl_down = True
            return
        if self._is_shift(key):
            self._shift_down = True
            return
        if self._is_alt(key):
            self._alt_down = True
            return
        if (
            self._key_char(key) == self._main
            and not self._engaged
            and self._mods_satisfied()
        ):
            self._engaged = True
            self._combo_down()

    def _on_release(self, key) -> None:  # noqa: ANN001
        is_ctrl = self._is_ctrl(key)
        is_shift = self._is_shift(key)
        is_alt = self._is_alt(key)
        if is_ctrl:
            self._ctrl_down = False
        if is_shift:
            self._shift_down = False
        if is_alt:
            self._alt_down = False
        if not self._engaged:
            return
        main_released = self._key_char(key) == self._main
        mod_required_released = (
            (is_ctrl and "ctrl" in self._mods)
            or (is_shift and "shift" in self._mods)
            or (is_alt and "alt" in self._mods)
        )
        if main_released or mod_required_released:
            self._engaged = False
            self._combo_up()

    # --- cycle de vie ---
    def start(self) -> None:
        from pynput import keyboard

        if self._listener is not None:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.start()
        log.info(
            "Écoute du raccourci %s+%s active (maintien + double-tap)",
            "+".join(sorted(self._mods)), self._main,
        )

    def stop(self) -> None:
        self._cancel_confirm_timer()
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
