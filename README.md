# ORAKLE

**Dictée vocale locale, multilingue et hors-ligne** — type Wispr Flow, mais
sans abonnement ni cloud obligatoire. Parlez, le texte s'écrit là où est le
curseur, dans n'importe quelle application.

- 🔒 **Local-first** : transcription (Whisper) et traduction (Argos) tournent sur
  votre machine. Aucune donnée ne sort sauf si vous activez explicitement un
  moteur cloud.
- 🌍 **Multilingue** : FR / EN / ES, écriture dans la langue parlée + mode
  traduction à la volée.
- ⌨️ **Un seul raccourci** : maintenir `Ctrl+1` → parler → relâcher → le texte
  est injecté.
- 🆓 **Open-source** (GPL-3.0), aucun crédit cloud requis.

> ORAKLE est un projet **autonome**, sans aucun lien avec d'autres projets.

---

## État d'avancement

- ✅ **Phase 0 — Socle** : squelette, config utilisateur, tray minimal, logging.
- ✅ **Phase 1 — MVP push-to-talk FR** : maintenir `Ctrl+1` → enregistrer →
  transcrire (faster-whisper `small`, FR) → injecter via presse-papier.
- ⏳ Phase 2 — mode toggle (double-tap) + retour visuel d'overlay.
- ⏳ Phase 3 — multilingue FR/EN/ES.
- ⏳ Phase 4 — dictionnaire personnalisé (éditeur).
- ⏳ Phase 5 — mode traduction (Argos / Ollama).
- ⏳ Phase 6 — réglages complets, packaging, BYOK optionnel.

---

## Installation

Python **3.12** requis.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Le premier lancement télécharge le modèle Whisper `small` (~ 500 Mo) si absent.
> Sur GPU NVIDIA (CUDA), le device passe automatiquement en `cuda` ; sinon CPU
> `int8`.

## Lancement

```powershell
python main.py
```

L'app démarre dans le **system tray** (aucune fenêtre). **Maintenir `Ctrl+1`**,
parler en français, relâcher → le texte transcrit s'écrit à l'emplacement du
curseur. Clic droit sur l'icône → **Quitter**.

---

## Configuration

Au premier lancement, les templates sont copiés vers le dossier utilisateur :

- Windows : `%APPDATA%\orakle\`
- Linux : `~/.config/orakle/`
- macOS : `~/Library/Application Support/orakle/`

Fichiers : `settings.json` (raccourci, modèle, langues…) et `dictionary.json`
(vocabulaire perso). Lisibles et portables.

---

## Plateformes

- ✅ **Windows** (cible primaire) et **Linux/X11**.
- ⚠️ **Linux/Wayland** : l'écoute clavier globale et l'injection sont restreintes
  par le compositeur (peut nécessiter `ydotool` / portails).
- macOS : autoriser le micro et l'accessibilité (contrôle clavier).

## Licence

GPL-3.0.
