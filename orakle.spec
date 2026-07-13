# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller ORAKLE — build Windows (onedir).

Build :  pwsh ./build.ps1   (ou : pyinstaller orakle.spec --noconfirm)
Sortie : dist/ORAKLE/ORAKLE.exe

Choix :
- onedir (pas onefile) : un outil de dictée se lance souvent ; onefile paierait
  ~10-20 s d'extraction à chaque démarrage.
- collect_all('faster_whisper') : embarque les assets (VAD Silero .onnx requis
  par vad_filter=True) ; idem ctranslate2 (DLLs).
- EXCLUSIONS argostranslate/torch/spacy/stanza : la traduction hors-ligne Argos
  tirerait ~2+ Go dans l'exe. Dans l'exe, la traduction passe par Ollama (local)
  ou Anthropic (BYOK) ; Argos reste disponible en lançant la version Python.
  Sans moteur joignable, le texte source est injecté tel quel (pas de crash).
- Le modèle Whisper n'est PAS embarqué : téléchargé au 1er usage dans le cache
  utilisateur (comme en dev).
"""
from PyInstaller.utils.hooks import collect_all

datas = [
    ("config/settings.default.json", "config"),
    ("config/dictionary.default.json", "config"),
    ("resources/logo.png", "resources"),
    ("resources/logo.ico", "resources"),
]
binaries = []
hiddenimports = ["comtypes", "pycaw", "requests"]

for pkg in ("faster_whisper", "ctranslate2"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Traduction offline Argos : trop lourde pour l'exe (torch & co).
        "argostranslate", "torch", "spacy", "stanza", "sacremoses",
        "sentencepiece", "transformers",
        # Divers lourds inutiles au runtime.
        "tkinter", "matplotlib", "IPython", "pytest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ORAKLE",
    debug=False,
    strip=False,
    upx=False,
    console=False,                 # app tray, pas de console
    icon="resources/logo.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ORAKLE",
)
