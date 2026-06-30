"""Machine à états du raccourci global.

Phase 1 — mode MAINTIEN uniquement (push-to-talk) :
  combo enfoncé  -> on_start()
  combo relâché  -> on_stop()

Structuré pour accueillir en Phase 2 le double-tap (mode mains-libres) via les
seuils `hold_threshold_ms` / `double_tap_window_ms`. L'écoute clavier globale
tourne dans le thread de pynput : les callbacks sont appelés depuis ce thread,
à l'appelant de marshaler vers la boucle Qt si besoin.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

log = logging.getLogger(__name__)

_MOD_NAMES = {"ctrl", "shift", "alt", "cmd"}


class HotkeyManager:
    def __init__(
        self,
        hotkey: str = "<ctrl>+1",
        on_start: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_start = on_start
        self._on_stop = on_stop
        self._mods, self._main = self._parse(hotkey)
        self._listener = None
        self._ctrl_down = False
        self._shift_down = False
        self._alt_down = False
        self._active = False  # le combo est-il actuellement maintenu ?

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

    # --- helpers ---
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
        # Repli sur le code virtuel pour les chiffres (Windows : 0x30-0x39),
        # car Ctrl+chiffre peut ne pas fournir `.char`.
        vk = getattr(key, "vk", None)
        if vk is not None and 0x30 <= vk <= 0x39:
            return chr(vk)
        return None

    def _is_ctrl(self, key) -> bool:  # noqa: ANN001
        from pynput.keyboard import Key

        return key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r)

    def _is_shift(self, key) -> bool:  # noqa: ANN001
        from pynput.keyboard import Key

        return key in (Key.shift, Key.shift_l, Key.shift_r)

    def _is_alt(self, key) -> bool:  # noqa: ANN001
        from pynput.keyboard import Key

        return key in (Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr)

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
        # Touche principale : ne déclenche qu'une fois (auto-repeat ignoré).
        if not self._active and self._key_char(key) == self._main and self._mods_satisfied():
            self._active = True
            self._fire(self._on_start)

    def _on_release(self, key) -> None:  # noqa: ANN001
        released_ctrl = self._is_ctrl(key)
        released_shift = self._is_shift(key)
        released_alt = self._is_alt(key)
        if released_ctrl:
            self._ctrl_down = False
        if released_shift:
            self._shift_down = False
        if released_alt:
            self._alt_down = False

        if not self._active:
            return
        # Le combo se rompt si on relâche la touche principale OU un modificateur requis.
        main_released = self._key_char(key) == self._main
        mod_required_released = (
            (released_ctrl and "ctrl" in self._mods)
            or (released_shift and "shift" in self._mods)
            or (released_alt and "alt" in self._mods)
        )
        if main_released or mod_required_released:
            self._active = False
            self._fire(self._on_stop)

    @staticmethod
    def _fire(cb: Optional[Callable[[], None]]) -> None:
        if cb is None:
            return
        try:
            cb()
        except Exception:
            log.exception("Erreur dans un callback de raccourci")

    # --- cycle de vie ---
    def start(self) -> None:
        from pynput import keyboard

        if self._listener is not None:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.start()
        log.info("Écoute du raccourci %s+%s active",
                 "+".join(sorted(self._mods)), self._main)

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
