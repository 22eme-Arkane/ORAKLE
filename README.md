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

- ✅ **Phase 0 — Socle** : squelette, config utilisateur, tray, logging.
- ✅ **Phase 1 — MVP push-to-talk FR** : maintenir `Ctrl+1` → parler → texte injecté.
- ✅ **Phase 2 — Mode mains-libres** : double-tap `Ctrl+1` → enregistrement continu,
  un tap simple ferme et écrit. Overlay onde de forme au-dessus de la barre des tâches.
- ✅ **Phase 3 — Multilingue FR/EN/ES** : détection auto restreinte au set, forçage
  depuis le menu du tray.
- ✅ **Phase 4 — Dictionnaire personnalisé** : biais `initial_prompt` + corrections,
  éditeur dans le tray (« Dictionnaire… »).
- ✅ **Phase 5 — Traduction à la volée** : « traduis français vers espagnol … » →
  Argos (hors-ligne, défaut) / Ollama (LLM local) / Anthropic (BYOK optionnel).
- ✅ **Phase 6 — Réglages & packaging** : fenêtre Réglages complète (« Réglages… »
  dans le tray), export/import de configuration, build PyInstaller (`build.ps1`).

### En plus de la roadmap
- 🔇 **Sourdine automatique** : le son des autres applications (Spotify, VLC…) est
  coupé pendant la dictée puis restauré (WASAPI/pycaw, désactivable).
- 🎤 **Choix du microphone** dans le tray (périphériques WASAPI actifs).
- 🟡🔵 **Pastilles d'état** pensées pour le daltonisme (jaune = enregistrement,
  bleu = transcription).

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

## Build Windows (.exe)

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Produit `dist\ORAKLE\ORAKLE.exe` (dossier autonome, icône médaillon).

> ⚠️ Le build **n'embarque pas** la traduction hors-ligne Argos (elle tirerait
> plusieurs Go via torch). Dans l'exe, la traduction passe par **Ollama** (local)
> ou **Anthropic** (BYOK). La version Python garde Argos. Le modèle Whisper est
> téléchargé au premier usage (cache utilisateur), pas embarqué.

## Plateformes

- ✅ **Windows** (cible primaire) et **Linux/X11**.
- ⚠️ **Linux/Wayland** : l'écoute clavier globale et l'injection sont restreintes
  par le compositeur (peut nécessiter `ydotool` / portails).
- macOS : autoriser le micro et l'accessibilité (contrôle clavier).

## Licence

GPL-3.0.
