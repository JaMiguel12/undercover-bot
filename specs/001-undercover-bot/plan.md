# Implementation Plan: Bot Telegram « Undercover »

**Branch**: `001-undercover-bot` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-undercover-bot/spec.md`

## Summary

Un bot Telegram qui fait jouer Undercover par écrit dans un groupe, avec trois agents IA (Zendaya IA,
Kendall IA, BFF Diva IA) qui complètent la partie, y compris en mode solo. L'approche technique
applique exactement la pile et la structure imposées par les sections 7 et 8 du brief :

- un **moteur de jeu pur** (`game/`), machine à états déterministe avec graine aléatoire, sans
  aucun import Telegram, base de données ou LLM ;
- un **orchestrateur** (`bot/orchestrator.py`) qui relie le moteur à Telegram (aiogram, long
  polling), aux agents IA (Groq) et aux minuteries (tâches asyncio) ;
- une **persistance SQLite** (SQLAlchemy 2 async) de l'état de chaque partie après chaque
  transition, avec les échéances stockées en base pour reprogrammer les minuteries au redémarrage ;
- une **base de mots** JSON validée au démarrage ; un **module de textes** unique pour tout le
  français du bot.

Les décisions détaillées et leurs alternatives sont dans [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12 (installé en local via `py -3.12` ; le Python 3.14 par défaut de
la machine n'est pas utilisé)

**Primary Dependencies**: aiogram 3.x (long polling), SQLAlchemy 2.x (async) + aiosqlite,
pydantic-settings, SDK officiel `groq`

**Storage**: SQLite (fichier, volume Docker) ; états de partie sérialisés en JSON par partie,
scores et historique des trios dans des tables dédiées

**Testing**: pytest + pytest-asyncio ; couverture du moteur ≥ 90 % (pytest-cov) ; lint et format
avec ruff

**Target Platform**: conteneur Linux (Docker + docker-compose) ; développement sous Windows 11

**Project Type**: service unique (bot), sans interface web

**Performance Goals**: pas de cible de débit ; l'action d'un joueur (clic, message) reçoit sa
réponse dans le groupe en moins de 2 secondes hors appel LLM ; le temps de réponse d'une IA est
dominé par l'indicateur « en train d'écrire » (2 à 5 s) et le timeout LLM

**Constraints**: délais configurables (description 60 s, vote 90 s, devinette 60 s, lobby 600 s,
attente solo 120 s) ; une IA ne bloque jamais une partie ; aucun secret hors `.env`

**Scale/Scope**: un cercle d'amis ; quelques groupes en parallèle, 1 à 8 humains par partie ;
201 trios de mots

## Constitution Check

*GATE: doit passer avant la Phase 0. Réévalué après la Phase 1.*

| Principe | Verdict | Comment le plan le respecte |
|---|---|---|
| I. Simplicité d'abord | OK | Un seul processus, SQLite, pas de file de messages ni de cache. Un état de partie = un document JSON, pas de modèle relationnel fin. Pas de couche « service » générique. |
| II. Moteur de jeu pur | OK | `game/` n'importe ni aiogram, ni SQLAlchemy, ni groq. Le hasard passe par un `random.Random` injecté ; le temps par des événements `Timeout`. Un test d'import interdit vérifie l'absence de ces dépendances. |
| III. Confidentialité des mots | OK | Tous les textes de groupe sortent de `bot/texts.py` ; un test rejoue des parties complètes avec un faux bot et vérifie qu'aucun message de groupe ne contient un mot secret avant l'écran de fin. |
| IV. Équité des IA | OK | L'agent ne reçoit qu'un `PublicView` construit par le moteur ; le client LLM ne reçoit jamais `GameState`. Test sur la vue publique. |
| V. Résilience | OK | Persistance après chaque transition ; échéances en base ; repli pour chaque action IA (3 essais, backoff, puis repli) ; test de reprise après redémarrage. |
| VI. Tests avant fusion | OK | Chaque user story du plan de tâches livre ses tests ; moteur ≥ 90 %. |
| VII. Français / conventions | OK | Textes FR dans `bot/texts.py` ; code et identifiants en anglais, commentaires en français ; prompts FR dans `ai/prompts.py`. |
| VIII. Secrets | OK | `BOT_TOKEN` et `GROQ_API_KEY` dans `.env` (ignoré par git) ; `.env.example` fourni. |

Aucune violation : la table *Complexity Tracking* reste vide.

**Réévaluation après Phase 1** : inchangée. Les contrats et le modèle de données n'ajoutent ni
dépendance ni couche supplémentaire.

## Project Structure

### Documentation (this feature)

```text
specs/001-undercover-bot/
├── plan.md              # Ce fichier
├── research.md          # Phase 0 : décisions et alternatives
├── data-model.md        # Phase 1 : entités du moteur et tables
├── quickstart.md        # Phase 1 : guide de validation
├── contracts/           # Phase 1 : interfaces exposées
│   ├── telegram-commands.md
│   ├── callback-data.md
│   ├── ai-actions.md
│   ├── words-schema.md
│   └── configuration.md
└── tasks.md             # Phase 2 (/speckit-tasks, non créé ici)
```

### Source Code (repository root)

Structure imposée par la section 8 du brief, complétée par les dossiers de tests :

```text
undercover-bot/            # racine du dépôt actuel
├── bot/
│   ├── main.py            # point d'entrée, dispatcher aiogram
│   ├── config.py          # settings (pydantic-settings)
│   ├── handlers/
│   │   ├── lobby.py
│   │   ├── game.py        # descriptions, votes
│   │   └── private.py     # /start, /monmot, devinette Mr. White
│   ├── keyboards.py
│   ├── texts.py           # TOUS les textes FR du bot
│   └── orchestrator.py    # lien entre moteur, Telegram, IA et minuteries
├── game/                  # MOTEUR PUR : aucun import Telegram/DB/LLM
│   ├── models.py          # Player, Role, GameState, PublicView
│   ├── engine.py          # machine à états
│   ├── rules.py           # complétion IA, répartition, victoire, points
│   ├── words.py           # chargement, validation, tirage
│   └── normalize.py
├── ai/
│   ├── agent.py           # décrire / voter / deviner
│   ├── prompts.py
│   └── groq_client.py
├── db/
│   ├── models.py
│   └── repository.py
├── data/words.json
├── tests/
│   ├── unit/              # moteur, règles, normalisation, mots (sans réseau)
│   ├── integration/       # orchestrateur + faux bot + faux LLM + SQLite en mémoire
│   └── conftest.py
├── docs/UNDERCOVER_BRIEF.md
├── specs/                 # artefacts Spec Kit
├── pyproject.toml         # dépendances, ruff, pytest
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── README.md
```

**Structure Decision**: projet unique, tel que prescrit par la section 8 du brief. Les seuls ajouts
sont `tests/unit` et `tests/integration` (séparent les tests du moteur pur, sans réseau, de ceux de
l'orchestrateur) et `pyproject.toml` pour la configuration des outils. La frontière de dépendance
est à sens unique : `bot` → (`game`, `ai`, `db`) ; `ai` et `db` → `game.models` ; `game` → rien.

## Complexity Tracking

Aucune violation de la constitution à justifier.
