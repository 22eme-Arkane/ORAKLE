"""Diagnostic du raccourci — à lancer SEUL (fermer ORAKLE d'abord).

Écoute le clavier ~20 s et affiche, pour chaque touche :
  - ce que pynput livre (char, vk, modificateurs) ;
  - ce que la machine à états ORAKLE en déduit (start/confirm/commit/cancel).

Usage :  python tools/diag_hotkey.py
Pendant l'écoute : presser Ctrl+1 en MAINTIEN (~1 s), puis en DOUBLE-TAP.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pynput import keyboard  # noqa: E402

from orakle.hotkey import HotkeyManager  # noqa: E402

DURATION_S = 20


def _desc(key) -> str:  # noqa: ANN001
    char = getattr(key, "char", None)
    vk = getattr(key, "vk", None)
    char_repr = repr(char) if char is not None else "None"
    vk_repr = f"0x{vk:02X}" if isinstance(vk, int) else "None"
    interp = HotkeyManager._key_char(key)
    return f"char={char_repr:8} vk={vk_repr:6} -> _key_char={interp!r}"


def main() -> int:
    print(f"=== Diagnostic raccourci ORAKLE ({DURATION_S} s) ===")
    print("Presse Ctrl+1 en MAINTIEN (~1 s), puis en DOUBLE-TAP. Ctrl+C pour finir.\n")

    hk = HotkeyManager(
        "<ctrl>+1",
        on_start=lambda: print("  >>> MACHINE À ÉTATS : START"),
        on_confirm=lambda: print("  >>> MACHINE À ÉTATS : CONFIRM (overlay/mute)"),
        on_commit=lambda: print("  >>> MACHINE À ÉTATS : COMMIT (transcription)"),
        on_cancel=lambda: print("  >>> MACHINE À ÉTATS : CANCEL (appui bref)"),
    )

    def on_press(key):  # noqa: ANN001
        print(f"PRESS   {_desc(key)}  [ctrl_down={hk._ctrl_down}]")
        hk._on_press(key)

    def on_release(key):  # noqa: ANN001
        print(f"RELEASE {_desc(key)}")
        hk._on_release(key)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    try:
        time.sleep(DURATION_S)
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
    print("\n=== Fin du diagnostic ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
