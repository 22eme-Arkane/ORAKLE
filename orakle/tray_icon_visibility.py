"""Rendre l'icône ORAKLE toujours visible près de l'horloge (Windows 11).

Par défaut, Windows range les icônes tray des nouvelles apps derrière la
flèche ^ (icônes masquées) : impossible de voir la pastille d'état. Windows 11
mémorise ce choix par application dans le registre utilisateur :

    HKCU\\Control Panel\\NotifyIconSettings\\<id>\\
        ExecutablePath  (REG_SZ)   chemin de l'exe propriétaire de l'icône
        IsPromoted      (REG_DWORD) 1 = visible dans la barre, 0 = masquée

On promeut UNIQUEMENT notre propre icône (ExecutablePath == notre exe), et
seulement en version installée/frozen : en dev l'exe est python.exe, partagé
avec d'autres apps — on ne promeut pas pour éviter les effets de bord.
L'entrée n'existe qu'APRÈS le premier affichage de l'icône -> appeler avec un
léger différé après tray.show(). Best-effort : jamais bloquant.
"""
from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger(__name__)

_KEY_PATH = r"Control Panel\NotifyIconSettings"


def _own_exe() -> str | None:
    """Chemin de l'exe dont Windows crédite l'icône tray (frozen seulement)."""
    if not getattr(sys, "frozen", False):
        return None
    return os.path.normcase(os.path.abspath(sys.executable))


def promote_tray_icon() -> bool:
    """Marque l'icône ORAKLE « toujours visible ». True si au moins une entrée
    a été promue (ou l'était déjà). Sans effet hors Windows / en mode dev."""
    exe = _own_exe()
    if exe is None or not sys.platform.startswith("win"):
        log.info("promotion icône tray : ignorée (mode dev ou non-Windows)")
        return False
    try:
        import winreg
    except ImportError:
        return False
    promoted = False
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY_PATH)
    except OSError:
        log.info("promotion icône tray : clé NotifyIconSettings absente "
                 "(Windows < 11 ? réglage manuel nécessaire)")
        return False
    try:
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(root, sub, 0,
                                    winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
                    path, _t = winreg.QueryValueEx(k, "ExecutablePath")
                    if os.path.normcase(str(path)) != exe:
                        continue
                    try:
                        current, _t2 = winreg.QueryValueEx(k, "IsPromoted")
                    except OSError:
                        current = 0
                    if int(current) != 1:
                        winreg.SetValueEx(k, "IsPromoted", 0, winreg.REG_DWORD, 1)
                        log.info("icône tray promue en zone visible (%s)", sub)
                    promoted = True
            except OSError:
                continue
    finally:
        winreg.CloseKey(root)
    if not promoted:
        log.info("promotion icône tray : entrée pas encore créée par Windows")
    return promoted
