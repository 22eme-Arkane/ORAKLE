# CLAUDE.md — Projet ORAKLE (dictée vocale locale multilingue)

> Fichier de contexte machine-to-machine. À placer à la racine du dépôt ORAKLE.
> Sert de guardrail architectural à travers les sessions Claude Code.

---

## 0. PÉRIMÈTRE DU PROJET — À LIRE EN PREMIER (GUARDRAIL CRITIQUE)

**ORAKLE est un projet autonome et indépendant. Ce n'est PAS un module de PANDORA.**

- Travailler EXCLUSIVEMENT dans le dossier `orakle/` (nouveau dépôt dédié).
- **NE PAS** travailler dans le dossier de PANDORA, ni dans un sous-dossier de PANDORA.
- **NE PAS** lire, importer, modifier, copier ou référencer des fichiers de PANDORA.
- Aucune dépendance partagée, aucun code commun, aucun `import` croisé entre les
  deux projets : ils évoluent séparément.
- Nouveau dépôt Git dédié : `ORAKLE` (ex. `github.com/22eme-Arkane/ORAKLE`),
  distinct du dépôt PANDORA.
- Si le contexte de session mentionne PANDORA, l'ignorer pour ce projet : seul
  ce fichier fait foi pour ORAKLE.

> En cas de doute sur l'emplacement de travail : créer/rester dans un dossier
> `orakle/` neuf, jamais à l'intérieur de l'arborescence PANDORA.

---

## 1. Vision

ORAKLE est un outil de **dictée vocale locale** type Wispr Flow, qui transforme
la parole en texte injecté dans **n'importe quelle application** via un raccourci
clavier global. Multilingue (FR / EN / ES) avec écriture dans la langue parlée,
et mode traduction à la volée. **Aucun abonnement, aucun cloud obligatoire,
propriété totale des données.**

### Cas d'usage cible

1. Maintenir `Ctrl+1` → parler → relâcher → le texte transcrit s'écrit là où est le curseur.
2. Double-tap `Ctrl+1` → mode mains-libres, parler longtemps → un tap `Ctrl+1` ferme et écrit.
3. Parler en FR / EN / ES → le texte sort dans la langue détectée.
4. Dire « translate français vers espagnol » puis parler en FR → le texte sort en ES.

---

## 2. Principes non négociables (GUARDRAILS)

- **Local-first.** La transcription (Whisper) et la traduction (Argos) tournent
  hors-ligne sur la machine. Aucune dépendance à un service payant pour le cœur.
- **Crédits cloud jamais requis.** La traduction « qualité » se fait avec un LLM
  **open-weight local via Ollama** (Mistral / Qwen3, Apache 2.0), gratuit et
  hors-ligne. Un moteur cloud BYOK (clé Anthropic) reste possible en dernier
  recours facultatif, mais l'outil doit être 100 % fonctionnel sans aucune clé.
- **Zéro télémétrie.** Aucune donnée audio ni texte ne quitte la machine sauf si
  l'utilisateur active explicitement un moteur cloud.
- **Données utilisateur portables.** Config et dictionnaire en JSON lisible, dans
  un dossier utilisateur clair, exportables/importables.
- **Open-source.** Licence GPL-3.0 (cohérence avec les autres projets de l'auteur).
- **Simplicité d'usage > richesse de fonctions.** L'app vit dans le system tray ;
  l'interaction normale ne demande aucune fenêtre.
- **Latence faible.** Cible : < 1,5 s entre relâchement de la touche et texte écrit
  pour un clip de quelques secondes (modèle `small` sur CPU correct).

---

## 3. Stack technique

| Rôle | Lib | Justification |
|---|---|---|
| UI / tray / fenêtre réglages | **PyQt6** | Familiarité de l'auteur, tray system inclus |
| STT local | **faster-whisper** (CTranslate2) | Multilingue, rapide CPU/GPU, `initial_prompt` |
| Capture audio | **sounddevice** | Simple, bas niveau, cross-platform |
| Hotkey global + injection | **pynput** | Écoute clavier globale + contrôle clavier cross-platform |
| Traduction offline (défaut) | **argos-translate** (basé OPUS-MT / CTranslate2) | FR↔EN↔ES hors-ligne, rapide, minuscule. OPUS-MT = Apache 2.0 |
| Traduction « qualité » (option) | **Ollama** + LLM open-weight local | Plus fluide. Mistral (Apache 2.0, fort en langues EU) ou Qwen3 (Apache 2.0, 100+ langues, petites tailles 1.7B/8B) |
| Presse-papier (injection fiable) | **pyperclip** (+ pynput pour Ctrl+V) | Gère accents/débit, plus robuste que la frappe simulée |
| Config | JSON (stdlib) | Lisible, portable |

Python **3.12**.

### Choix de modèle Whisper

- Défaut : `small` (bon compromis multilingue précision/vitesse sur CPU).
- Configurable : `base` (plus léger), `medium` / `large-v3` (meilleure précision FR/ES si GPU).
- Si CUDA dispo → `device="cuda"`, sinon `device="cpu"`, `compute_type="int8"` sur CPU.

---

## 4. Architecture / arborescence

```
orakle/
├── main.py                  # Point d'entrée : init tray + boucle Qt
├── orakle/
│   ├── config.py            # Chargement/sauvegarde settings + paths utilisateur
│   ├── hotkey.py            # Machine à états du raccourci (hold / double-tap toggle)
│   ├── recorder.py          # Capture micro (sounddevice), start/stop, buffer PCM
│   ├── transcriber.py       # faster-whisper : transcription + initial_prompt
│   ├── translator.py        # Traduction : argos (défaut) / Ollama local / cloud BYOK
│   ├── command_parser.py    # Détecte/parse "translate <src> vers <dst>"
│   ├── dictionary.py        # Vocabulaire perso : biais + post-correction
│   ├── injector.py          # Injection texte (presse-papier + Ctrl+V, fallback frappe)
│   ├── controller.py        # Glue raccourci↔recorder↔pipeline↔état tray (signaux Qt)
│   └── pipeline.py          # Orchestration : audio → STT → [traduction] → correction → injection
├── ui/
│   ├── tray.py              # QSystemTrayIcon + menu (langue, mode, réglages, quitter)
│   └── settings_window.py   # Fenêtre réglages + éditeur de dictionnaire
├── resources/               # Icônes tray (idle / recording / processing)
├── config/                  # Templates par défaut (copiés vers le dossier user au 1er run)
│   ├── settings.default.json
│   └── dictionary.default.json
├── requirements.txt
├── README.md
└── CLAUDE.md
```

Dossier utilisateur (créé au premier lancement) :
- Linux : `~/.config/orakle/`
- Windows : `%APPDATA%\orakle\`
- macOS : `~/Library/Application Support/orakle/`

---

## 5. Spécification fonctionnelle détaillée

### 5.1 Machine à états du raccourci (`hotkey.py`)

Un **seul** raccourci (`Ctrl+1` par défaut, configurable) doit gérer deux modes.
Distinction par durée d'appui.

Paramètres (configurables) :
- `hold_threshold = 300 ms` : au-delà → c'est un maintien (push-to-talk).
- `double_tap_window = 400 ms` : deux taps rapprochés → toggle mains-libres.

États : `IDLE → ARMED → RECORDING_HOLD | RECORDING_TOGGLE → PROCESSING → IDLE`

Logique :
```
key_down:
    démarrer enregistrement + timer t0
key_up:
    durée = now - t0
    si durée >= hold_threshold:
        # PUSH-TO-TALK : on a maintenu
        stop_record(); lancer pipeline; -> IDLE
    sinon:
        # tap court : c'était peut-être le 1er d'un double-tap
        annuler l'enregistrement courant
        si un tap précédent < double_tap_window:
            # DOUBLE-TAP : entrer en mode toggle
            start_record(); état = RECORDING_TOGGLE
        sinon:
            mémoriser ce tap (attendre un éventuel 2e)
en mode RECORDING_TOGGLE, key_down/up (tap simple) suivant:
    stop_record(); lancer pipeline; -> IDLE
```

> Important : un tap simple **isolé** (pas de maintien, pas de 2e tap) ne doit
> rien faire après expiration de `double_tap_window` → éviter les déclenchements
> accidentels.

Retour visuel : l'icône tray change d'état (idle / recording / processing).
Optionnel : petit overlay « 🎙 Enregistrement… » non focusable.

> **État d'implémentation (Phase 1)** : seul le mode MAINTIEN (push-to-talk) est
> actif. Le double-tap / toggle viendra en Phase 2 ; `hotkey.py` est structuré
> pour l'accueillir.

### 5.2 Langues & écriture dans la langue parlée

- Whisper détecte automatiquement la langue. Restreindre la détection au set
  configuré (`fr`, `en`, `es`) pour fiabiliser (éviter qu'un mot ambigu parte en
  portugais/italien).
- Le texte transcrit sort tel quel dans la langue détectée → exigence « écrire
  dans la langue parlée » satisfaite par défaut.
- Possibilité de **forcer** une langue depuis le menu tray (utile en milieu bruyant).

### 5.3 Mode traduction (`command_parser.py` + `translator.py`)

Déclencheur : la transcription **commence par** un mot-clé de traduction
(`translate`, `traduis`, `traduire`, `traducir` — multilingue, configurable).

Format attendu (souple) : `translate <langue_source> vers|to|a|en <langue_cible>`
puis le contenu parlé.

Parsing :
1. Détecter le préfixe de commande.
2. Mapper les noms de langues vers codes ISO (`français/french/francais → fr`,
   `anglais/english/inglés → en`, `espagnol/spanish/español → es`).
3. Mots de liaison acceptés : `vers`, `to`, `a`, `en`, `→`.
4. Le **reste** du clip (après l'énoncé de la commande) est le contenu à traduire.

> Deux stratégies possibles pour séparer la commande du contenu :
> **(A)** L'utilisateur dit la commande puis fait une courte pause, puis parle →
> on coupe sur la 1re ponctuation/silence. **(B) Recommandé pour v1 :** la
> commande et le contenu sont dans le même clip ; on retire du texte transcrit
> le segment correspondant au préfixe « translate … vers … » via regex, le reste
> est traduit. Documenter le comportement choisi.

Traduction (architecture à 3 paliers, configurable) :
- Forcer Whisper à transcrire en **langue source** (pas de détection auto ici).
- **Palier 1 — défaut, offline, gratuit : argos-translate** (`src → dst`).
  Vérifier au démarrage que les paquets de langue Argos requis sont installés ;
  proposer le téléchargement automatique si absent. Rapide et minuscule, idéal
  pour la latence d'une dictée.
- **Palier 2 — option « qualité », local, gratuit : LLM via Ollama.** Si Ollama
  est détecté (`localhost:11434`) et ce moteur activé, router vers un modèle
  open-weight local (recommandé : `mistral` ou `qwen3`). Prompt système strict :
  « traduis de <src> vers <dst>, ne renvoie QUE la traduction, sans préambule ».
  Aucun crédit, aucune donnée ne sort de la machine.
- **Palier 3 — option facultative, cloud BYOK** (clé Anthropic). Désactivé par
  défaut. À n'utiliser que si l'utilisateur le choisit explicitement.
- **Rappel guardrail** : ne PAS utiliser `task="translate"` de Whisper (sort
  toujours en anglais). La traduction passe TOUJOURS par un moteur dédié.
- **Rappel licence** : éviter NLLB-200 (CC-BY-NC, non commercial, incompatible
  avec une réutilisation libre du projet GPL). OPUS-MT = Apache 2.0, propre.
  Pour Ollama, privilégier les modèles Apache 2.0 (Mistral, Qwen3).
- L'`abstraction translator.py` expose une interface unique `translate(text, src, dst)`
  et choisit le backend selon la config ; les paliers sont interchangeables.

### 5.4 Dictionnaire personnalisé (`dictionary.py`)

Deux mécanismes complémentaires :
1. **Biaisage (avant transcription)** — injecter le vocabulaire utilisateur dans
   `initial_prompt` de faster-whisper. Liste de termes (noms propres, jargon VJ /
   ciné / code : « MadMapper », « projection mapping », « Seedance », « PyQt »,
   « fal.ai »…). Limiter la longueur du prompt (tokens) ; prioriser les termes
   par fréquence/épinglage.
2. **Post-correction (après transcription)** — table de remplacement
   `{ "mauvaise transcription": "terme correct" }`, appliquée par recherche
   insensible à la casse, en respectant les limites de mots. Utile pour les
   termes que Whisper massacre systématiquement.

Édition via la fenêtre réglages (ajout/suppression). Persistance dans
`dictionary.json`. Possibilité de dictionnaires par langue.

### 5.5 Injection de texte (`injector.py`)

- Méthode par défaut : copier le texte dans le presse-papier (pyperclip) puis
  simuler `Ctrl+V` (pynput). Plus fiable pour accents et débit.
- Sauvegarder/restaurer le contenu précédent du presse-papier après injection.
- Fallback : frappe caractère par caractère (pynput) si le paste échoue.
- Option « ajouter un espace final » configurable.

---

## 6. Contraintes & pièges connus (à respecter)

- **Whisper translate = anglais uniquement.** Ne jamais s'en servir pour FR→ES.
  → Toujours moteur de traduction séparé. (Cf. 5.3)
- **Linux/Wayland** : l'écoute clavier globale et l'injection sont restreintes
  sous Wayland (sécurité du compositeur). Cible primaire : **Windows** et **X11**.
  Documenter clairement le statut Wayland (peut nécessiter `ydotool` / portails).
- **Permissions micro** (macOS surtout) : demander/guider l'autorisation.
- **Latence GPU vs CPU** : tester les deux ; exposer le choix de modèle.
- **Conflit de raccourci** : `Ctrl+1` peut être pris par d'autres apps. Le
  raccourci doit être reconfigurable et l'app doit signaler un conflit détecté.
- **Paquets Argos manquants** : gérer proprement (téléchargement guidé), ne pas
  crasher.
- **Ollama absent** : si le palier 2 est activé mais Ollama injoignable, basculer
  proprement sur Argos (palier 1) avec un avertissement, ne pas crasher.
- **Restauration presse-papier** : ne pas écraser durablement le clipboard utilisateur.

---

## 7. Roadmap par phases

> Construire de façon **incrémentale**, chaque phase livrable et testable seule.

**Phase 0 — Socle** ✅
- Squelette projet (nouveau dossier `orakle/`), `config.py`, app tray minimale
  (icône + quitter), logging.

**Phase 1 — Dictée mono-langue (FR) push-to-talk** ✅
- `hotkey.py` mode maintien uniquement, `recorder.py`, `transcriber.py` (FR),
  `injector.py`. Maintenir Ctrl+1 → parler → texte injecté. **MVP utilisable.**

**Phase 2 — Mode toggle + retour visuel**
- Machine à états complète (double-tap), icônes d'état, overlay optionnel.

**Phase 3 — Multilingue FR/EN/ES**
- Détection auto restreinte au set, forçage langue depuis le menu.

**Phase 4 — Dictionnaire personnalisé**
- Biaisage `initial_prompt` + post-correction + éditeur dans la fenêtre réglages.

**Phase 5 — Mode traduction**
- `command_parser.py` + argos-translate FR↔EN↔ES (palier 1), gestion paquets de
  langue. Palier 2 Ollama branché derrière l'interface `translator.py`.

**Phase 6 — Finitions**
- Réglages complets (modèle, raccourci, langues, espace final, moteur de
  traduction), export/import config, packaging (PyInstaller), README, palier 3
  BYOK optionnel.

---

## 8. Critères d'acceptation (definition of done)

- [x] Le projet vit dans son propre dossier `orakle/`, indépendant de PANDORA.
- [x] Maintenir Ctrl+1 et parler en FR écrit le texte FR dans n'importe quel champ.
- [ ] Double-tap Ctrl+1 démarre l'enregistrement mains-libres ; un tap le ferme et écrit.
- [x] Un tap isolé ne déclenche aucune action parasite. *(en mode maintien : un tap trop court n'enclenche aucun pipeline)*
- [ ] Parler en EN ou ES écrit dans la bonne langue sans config.
- [ ] « translate français vers espagnol » + parole FR → texte ES injecté.
- [ ] Ajouter un mot au dictionnaire améliore sa reconnaissance / sa correction. *(biais + correction déjà câblés ; éditeur UI à venir)*
- [x] Aucune connexion réseau requise pour le fonctionnement de base (hors 1er téléchargement du modèle).
- [x] Le presse-papier de l'utilisateur est restauré après injection.
- [ ] Le raccourci est reconfigurable depuis les réglages. *(reconfigurable via settings.json ; UI à venir)*
- [x] L'app vit en tray et démarre sans ouvrir de fenêtre.

---

## 9. Config par défaut (référence)

`settings.default.json` :
```json
{
  "hotkey": "<ctrl>+1",
  "hold_threshold_ms": 300,
  "double_tap_window_ms": 400,
  "languages": ["fr", "en", "es"],
  "force_language": null,
  "model": "small",
  "device": "auto",
  "compute_type": "int8",
  "append_trailing_space": true,
  "translation": {
    "engine": "argos",
    "_engine_options": ["argos", "ollama", "anthropic"],
    "ollama": {
      "host": "http://localhost:11434",
      "model": "mistral"
    },
    "command_keywords": ["translate", "traduis", "traduire", "traducir"],
    "linkers": ["vers", "to", "a", "en"],
    "byok_enabled": false
  },
  "injection": {
    "method": "clipboard_paste",
    "restore_clipboard": true
  }
}
```

`dictionary.default.json` :
```json
{
  "bias_terms": ["projection mapping", "MadMapper", "Resolume", "PyQt6"],
  "corrections": {
    "made mapper": "MadMapper",
    "pi qt": "PyQt6"
  }
}
```

---

## 10. Style & conventions

- Code commenté en français, identifiants/API en anglais (convention habituelle).
- Type hints partout, modules découplés (le pipeline ne connaît pas Qt).
- Pas de logique métier dans l'UI ; l'UI appelle `pipeline`/`config`.
- Tests unitaires prioritaires sur `command_parser`, `dictionary`, machine à états `hotkey`.
- Threads : la transcription/traduction ne doivent JAMAIS bloquer la boucle Qt
  (worker thread + signaux).

---

## 11. Première instruction à Claude Code

> **Vérifier d'abord le périmètre (section 0)** : créer/travailler dans un dossier
> `orakle/` NEUF, jamais dans PANDORA.
>
> Démarre par la **Phase 0** puis la **Phase 1** (MVP push-to-talk FR).
> Crée d'abord l'arborescence et `requirements.txt`, puis implémente le chemin
> minimal : maintenir Ctrl+1 → enregistrer → transcrire (faster-whisper `small`,
> FR) → injecter via presse-papier. Ne passe à la phase suivante qu'une fois ce
> chemin testé manuellement et fonctionnel. Respecte tous les guardrails de la
> section 2.
