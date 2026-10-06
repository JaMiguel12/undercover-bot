# UNDERCOVER_BRIEF — Bot Telegram « Undercover »

> **À l'attention de Claude Code.** Ce document est la **source de vérité** du projet. Il sert d'entrée à toutes les commandes Spec Kit (`/speckit.constitution`, `/speckit.specify`, `/speckit.plan`, etc.).
> Règles d'usage :
> - Ne jamais inventer une règle de jeu absente de ce document. En cas d'ambiguïté, **poser la question** (via `/speckit.clarify`) plutôt que supposer.
> - Les sections 1 à 5 et 9 décrivent le **QUOI** (fonctionnel). Les sections 7 et 8 décrivent le **COMMENT** (technique) et ne doivent être utilisées qu'à partir de `/speckit.plan`.
> - Toute l'interface utilisateur (messages du bot) est **en français**.

> **Révision 2 (2026-10-01)** : certaines règles de jeu ont été modifiées après essais (un mot par
> description, 3 tours avant chaque vote, Mr. White supprimé, deux types de partie, solo à 60 s).
> Voir `specs/001-undercover-bot/revision-2.md` : elle remplace les sections 2.2 à 2.9 sur ces points.

---

## 0. Mode d'emploi Spec Kit

Placer ce fichier dans `docs/UNDERCOVER_BRIEF.md` à la racine du projet, puis exécuter dans l'ordre :

```text
/speckit.constitution Lis docs/UNDERCOVER_BRIEF.md section 6 et établis la constitution du projet à partir de ces principes.

/speckit.specify Lis docs/UNDERCOVER_BRIEF.md sections 1 à 5 et 9. Rédige la spécification fonctionnelle complète du bot Undercover, sans aucun choix technique. Chaque règle de jeu doit devenir une exigence testable.

/speckit.clarify

/speckit.plan Lis docs/UNDERCOVER_BRIEF.md sections 7 et 8 et applique exactement cette stack et cette structure.

/speckit.tasks Découpe en user stories livrables dans cet ordre : (1) base de mots + chargeur + tests, (2) moteur de jeu pur + tests, (3) lobby Telegram, (4) déroulement complet d'une partie entre humains, (5) agents IA Zendaya IA, Kendall IA et BFF Diva IA (dont le mode solo), (6) persistance et reprise après redémarrage, (7) classement, (8) Docker.

/speckit.analyze

/speckit.implement
```

L'annexe A contient la base de mots : l'extraire telle quelle dans `data/words.json`.

---

## 1. Vision

Un bot Telegram qui permet à un groupe d'amis de jouer à **Undercover** directement dans un groupe Telegram, **par écrit**. Quand il manque des joueurs, trois agents IA — **Zendaya IA**, **Kendall IA** et **BFF Diva IA** — rejoignent automatiquement la partie et jouent comme des humains (décrire, voter, deviner). Un joueur seul peut même faire une partie contre les trois IA (mode solo).

Public : un cercle d'amis francophones (Cameroun). Ton du bot : fun, direct, avec des emojis modérés.

---

## 2. Règles du jeu

### 2.1 Rôles et mots

Chaque partie utilise un **trio de mots** proches mais différents, tiré de la base (annexe A). Les trois mots du trio sont **mélangés aléatoirement** puis attribués ainsi :

| Rôle | Mot reçu | Équipe |
|---|---|---|
| Civil | Mot A (commun à tous les civils) | Civils |
| Undercover | Mot B (proche de A) | Infiltrés |
| Mr. White | Mot C (proche de A et B, différent des deux) | Infiltrés |

- **Personne ne connaît son rôle** au début : chacun reçoit seulement son mot. Un undercover ou Mr. White doit déduire lui-même, en écoutant les descriptions, que son mot est différent.
- Le rôle d'un joueur n'est révélé qu'à son élimination ou en fin de partie.

### 2.2 Nombre de joueurs et complétion par les IA

- De **1 à 8 joueurs humains**. Taille maximale d'une partie : **8 joueurs** au total.
- Les IA complètent automatiquement au lancement, **toujours dans l'ordre de priorité : Zendaya IA, puis Kendall IA, puis BFF Diva IA**.
- Règle générale : on ajoute **jusqu'à 3 IA** pour atteindre **8 joueurs au total**. Exceptions : avec 1 humain (mode solo), la partie se joue à **4** ; avec 2 humains, à **5**. Les totaux obtenus vont donc de 4 à 8.

| Humains | IA ajoutées | Total |
|---|---|---|
| 1 (mode solo, voir ci-dessous) | Zendaya IA + Kendall IA + BFF Diva IA | 4 |
| 2 | Zendaya IA + Kendall IA + BFF Diva IA | 5 |
| 3 | Zendaya IA + Kendall IA + BFF Diva IA | 6 |
| 4 | Zendaya IA + Kendall IA + BFF Diva IA | 7 |
| 5 | Zendaya IA + Kendall IA + BFF Diva IA | 8 |
| 6 | Zendaya IA + Kendall IA | 8 |
| 7 | Zendaya IA | 8 |
| 8 | Aucune | 8 |
| 9+ | Inscription refusée (« partie complète ») | — |

**Mode solo (1 seul humain)** : quand le créateur appuie sur « Lancer » alors qu'il est le seul humain inscrit, le bot ne lance pas tout de suite. Il publie un **dernier appel** dans le groupe et démarre un compte à rebours de **2 minutes** (configurable, `SOLO_WAIT_TIMEOUT`), affiché et mis à jour dans le message du lobby.
- Si personne ne rejoint pendant ce délai, les 3 IA entrent et la partie démarre à 4.
- Si d'autres humains rejoignent pendant le compte à rebours, la partie démarre à la fin du délai (ou dès que le créateur appuie à nouveau sur « Lancer »), avec la complétion normale du tableau ci-dessus.
- Le créateur peut annuler pendant le compte à rebours.
- À partir de 2 humains, « Lancer » démarre la partie immédiatement.

### 2.3 Répartition des rôles (sur le total, IA incluses)

| Total | Civils | Undercover | Mr. White |
|---|---|---|---|
| 4 (mode solo) | 3 | 1 | 0 |
| 5 | 3 | 1 | 1 |
| 6 | 4 | 1 | 1 |
| 7 | 5 | 1 | 1 |
| 8 | 5 | 2 | 1 |

Cette table doit être **configurable** (fichier de config), pas codée en dur dans la logique. Les IA peuvent tirer n'importe quel rôle, exactement comme les humains.

### 2.4 Déroulement d'une partie

1. **Lobby** : un joueur crée la partie dans le groupe, les autres rejoignent, le créateur lance.
2. **Distribution** : le bot tire un trio, attribue les rôles aléatoirement, et envoie à chaque humain **son mot en message privé**.
3. **Tours** : répétition de [phase de description → phase de vote → élimination → vérification de victoire] jusqu'à la fin.
4. **Fin** : le bot révèle tous les rôles et les trois mots, attribue les points, affiche le classement de la partie.

### 2.5 Phase de description

- Chaque joueur **vivant** parle **une fois par tour**, dans l'ordre annoncé par le bot.
- Ordre du premier tour : aléatoire, **Mr. White ne parle jamais en premier**. Aux tours suivants, le premier orateur est le joueur vivant suivant dans l'ordre initial, avec la même contrainte.
- Une description = **un mot ou une courte expression, 6 mots maximum**, envoyée comme message dans le groupe quand c'est son tour.
- Le bot ne prend en compte que le message du **joueur dont c'est le tour**. Les autres messages du groupe sont ignorés : les joueurs peuvent discuter librement.
- **Délai : 60 secondes** (configurable). Passé ce délai, le joueur « passe son tour » et le bot le signale.
- Une description qui contient le mot secret du joueur (comparaison normalisée, voir 2.7) est refusée. Si le bot est administrateur du groupe, il supprime le message ; dans tous les cas, il demande une autre description dans le délai restant.
- Le bot récapitule les descriptions du tour avant d'ouvrir le vote.

### 2.6 Phase de vote

- Le bot publie dans le groupe un message avec **un bouton par joueur vivant**.
- Chaque joueur vivant vote une fois. Il ne peut pas voter pour lui-même, mais peut **changer son vote** tant que le vote est ouvert.
- Le vote se clôt quand **tous les vivants ont voté** ou après **90 secondes** (configurable). Les non-votants comptent comme abstention.
- Le joueur ayant le plus de voix est éliminé. Le bot affiche ensuite **qui a voté pour qui**.
- **Égalité** : revote limité aux joueurs à égalité (ceux-ci votent aussi). **Nouvelle égalité** : tirage au sort parmi eux.
- **Aucun vote exprimé** : personne n'est éliminé, un nouveau tour de description commence.

### 2.7 Élimination et devinette de Mr. White

- À l'élimination, le bot révèle le **rôle** du joueur, mais pas son mot.
- Si le joueur éliminé est **Mr. White**, il a **une seule tentative** pour deviner le **mot des civils** :
  - humain : le bot lui demande en message privé, avec un délai de 60 secondes ;
  - IA : l'agent propose un mot à partir des descriptions publiques.
- **Comparaison normalisée** : minuscules, accents supprimés, espaces et tirets unifiés, articles initiaux retirés (le, la, les, l', un, une, des).
- **Devinette correcte** : Mr. White gagne seul et la partie s'arrête immédiatement.

### 2.8 Conditions de victoire (vérifiées après chaque élimination)

1. Mr. White devine correctement → **victoire de Mr. White** (seul).
2. Tous les undercovers et Mr. White sont éliminés → **victoire des Civils**.
3. Il ne reste **qu'un seul civil vivant** (ou aucun) → **victoire des Infiltrés** (undercovers + Mr. White, vivants ou non).

### 2.9 Points (configurables)

| Issue | Points |
|---|---|
| Victoire des Civils | +2 pour chaque civil (vivant ou éliminé) |
| Victoire des Infiltrés | +10 par undercover, +6 pour Mr. White |
| Victoire de Mr. White par devinette | +10 pour Mr. White uniquement |

Les points sont cumulés **par groupe Telegram**. Les IA ont aussi un score et apparaissent au classement.

---

## 3. Expérience Telegram

### 3.1 Commandes

**Dans le groupe**

| Commande | Effet |
|---|---|
| `/nouvelle` | Crée un lobby (une seule partie active par groupe) |
| `/lancer` | Lance la partie (créateur uniquement) |
| `/annuler` | Annule le lobby ou la partie en cours (créateur uniquement) |
| `/etat` | Affiche la phase, les joueurs vivants et à qui c'est le tour |
| `/regles` | Résumé des règles |
| `/classement` | Classement cumulé du groupe |

**En privé**

| Commande | Effet |
|---|---|
| `/start` | Active le bot pour ce joueur (indispensable pour recevoir son mot) |
| `/monmot` | Renvoie le mot du joueur pour sa partie en cours |
| `/aide` | Aide |

### 3.2 Lobby

- Le message de lobby contient les boutons **« Rejoindre »** et **« Quitter »**, et pour le créateur **« Lancer »** et **« Annuler »**. Il est mis à jour en direct avec la liste des inscrits.
- Chaque inscrit est marqué ✅ s'il peut recevoir des messages privés, ou ⚠️ s'il doit d'abord démarrer le bot. Un bouton lien profond (`t.me/<bot>?start=...`) est affiché pour ces derniers.
- **Contrainte Telegram critique** : un bot ne peut pas écrire en privé à quelqu'un qui ne l'a jamais démarré. Le lancement est donc **bloqué** tant qu'un inscrit ne peut pas recevoir de message privé ; le bot liste les joueurs concernés.
- Le lobby expire après 10 minutes d'inactivité.
- Un utilisateur ne peut être inscrit que dans **une seule partie à la fois**, tous groupes confondus. Les IA, elles, peuvent jouer dans plusieurs groupes en parallèle.

### 3.3 Confidentialité

- **Aucun mot secret ne doit jamais apparaître dans le groupe** avant la fin de la partie. C'est l'exigence la plus importante : elle doit être couverte par des tests.
- Les IA sont affichées dans le groupe avec le préfixe « 🤖 » (par exemple « 🤖 Zendaya IA : … »).

### 3.4 Prérequis BotFather (à documenter dans le README)

- Désactiver le privacy mode (`/setprivacy` → Disable) pour que le bot lise les descriptions dans le groupe.
- Optionnel : mettre le bot administrateur du groupe pour qu'il puisse supprimer les descriptions interdites.

---

## 4. Agents IA : Zendaya IA, Kendall IA et BFF Diva IA

### 4.1 Identité

| Agent | Priorité | Personnalité (appliquée au style des indices uniquement) |
|---|---|---|
| Zendaya IA | 1 | Posée, analytique, indices subtils |
| Kendall IA | 2 | Joueuse, un peu taquine, indices imagés |
| BFF Diva IA | 3 | Expressive, spontanée, indices tirés de la vie quotidienne |

Les agents ne parlent **que lorsque c'est leur tour** (description) et agissent silencieusement pour le vote. Pas de discussion libre en v1.

### 4.2 Information accessible (équité)

Un agent reçoit **uniquement** ce qu'un joueur humain saurait :

- son propre mot ;
- l'historique public : descriptions, votes, éliminations et rôles révélés ;
- la liste des joueurs vivants.

Il ne reçoit **jamais** son rôle, ni les mots ou les rôles des autres. Le moteur construit pour cela une **vue publique** dédiée : l'agent n'a jamais accès à l'état complet de la partie.

### 4.3 Actions

| Action | Sortie attendue du LLM (JSON strict) | Validation | Solution de repli |
|---|---|---|---|
| Décrire | `{"description": "..."}` | ≤ 6 mots, ne contient pas son mot ni sa racine évidente, ne répète pas une description déjà donnée dans la partie | 3 tentatives, puis « Je passe mon tour 🤐 » |
| Voter | `{"vote": "<nom exact>"}` | Joueur vivant, pas soi-même | Vote aléatoire parmi les joueurs valides |
| Deviner (si Mr. White éliminé) | `{"guess": "..."}` | Un mot ou une expression | « Je ne sais pas » (devinette ratée) |

### 4.4 Stratégie à encoder dans les prompts

- L'agent compare son mot avec les descriptions des autres. Si les indices ne collent pas à son mot, il est probablement infiltré : il doit rester vague et se fondre dans la majorité.
- S'il pense être civil, il donne des indices assez précis pour être reconnu par les autres civils, sans rendre le mot devinable par Mr. White.
- Pour voter, il cible le joueur dont les descriptions collent le moins au mot qu'il estime être celui de la majorité.
- Pour Mr. White éliminé : il déduit le mot des civils à partir des indices de la majorité.

### 4.5 Comportement réaliste et robustesse

- Avant chaque message, l'agent affiche l'indicateur « en train d'écrire » pendant 2 à 5 secondes (délai aléatoire).
- Les appels au LLM ont un délai maximal (timeout) et gèrent les erreurs 429 (limite de requêtes) avec un backoff exponentiel limité à 3 essais, puis déclenchent la solution de repli.
- **Une IA ne doit jamais bloquer une partie.**
- Les prompts sont rédigés en français et centralisés dans un module dédié.

---

## 5. Base de mots

- **Format** : `data/words.json`, un tableau d'objets `{ "id", "categorie", "mots": [3 mots] }` (voir annexe A : 201 trios, 15 catégories).
- **Tirage** : ne pas réutiliser un trio déjà joué dans le même groupe tant que tous les trios n'ont pas été joués. L'historique est stocké par groupe.
- **Validation au démarrage** : exactement 3 mots distincts par trio, aucun doublon d'id. Une base invalide empêche le bot de démarrer, avec une erreur explicite.
- La base doit pouvoir être enrichie en éditant le JSON, sans toucher au code.

---

## 6. Principes du projet (pour `/speckit.constitution`)

1. **Simplicité d'abord** : pas de sur-ingénierie. Chaque abstraction doit être justifiée par un besoin réel.
2. **Moteur de jeu pur** : toute la logique de jeu vit dans un module sans aucune dépendance à Telegram, à la base de données ou au LLM. Elle est déterministe quand on lui fournit une graine aléatoire, et testée unitairement.
3. **Confidentialité des mots** : aucune fuite de mot secret dans le groupe. Cette règle est couverte par des tests.
4. **Équité des IA** : les agents n'accèdent qu'à la vue publique.
5. **Résilience** : l'état est persisté après chaque transition, le bot reprend une partie en cours après un redémarrage, et une panne du LLM ne bloque jamais le jeu.
6. **Tests avant fusion** : tout nouveau comportement du moteur arrive avec ses tests.
7. **Français** pour tous les textes utilisateur. Code et identifiants en anglais, commentaires en français.
8. **Secrets** uniquement dans `.env` (jamais commité). Un `.env.example` est fourni.

---

## 7. Choix techniques (pour `/speckit.plan`)

| Élément | Choix |
|---|---|
| Langage | Python 3.12 |
| Bot Telegram | aiogram 3.x, en long polling (le webhook est hors périmètre v1) |
| Persistance | SQLite, via SQLAlchemy 2.x (async) + aiosqlite |
| Configuration | pydantic-settings + `.env` |
| LLM | Groq via le SDK officiel `groq`. Modèle configurable par `GROQ_MODEL` : choisir un modèle disponible dans la documentation Groq au moment du développement, ne pas le coder en dur |
| Timers | Tâches asyncio. Les échéances (deadlines) sont stockées en base pour pouvoir être reprogrammées au redémarrage |
| Tests | pytest + pytest-asyncio. Moteur couvert à ≥ 90 % |
| Qualité | ruff (lint + format) |
| Déploiement | Dockerfile + docker-compose, volume pour le fichier SQLite |

**Moteur = machine à états** :
`LOBBY → DISTRIBUTION → DESCRIPTION → VOTE → (REVOTE) → (MR_WHITE_GUESS) → CHECK_VICTORY → DESCRIPTION … → ENDED` (et `CANCELLED` depuis n'importe quel état).

**Variables d'environnement** : `BOT_TOKEN`, `GROQ_API_KEY`, `GROQ_MODEL`, `DATABASE_URL`, `DESCRIPTION_TIMEOUT=60`, `VOTE_TIMEOUT=90`, `GUESS_TIMEOUT=60`, `LOBBY_TIMEOUT=600`, `SOLO_WAIT_TIMEOUT=120`.

---

## 8. Structure du projet suggérée

```text
undercover-bot/
├── bot/
│   ├── main.py            # point d'entrée, dispatcher aiogram
│   ├── config.py          # settings (pydantic-settings)
│   ├── handlers/
│   │   ├── lobby.py
│   │   ├── game.py        # descriptions, votes
│   │   └── private.py     # /start, /monmot, devinette Mr. White
│   ├── keyboards.py
│   ├── texts.py           # TOUS les textes FR du bot
│   └── orchestrator.py    # fait le lien entre moteur, Telegram, IA et timers
├── game/                  # MOTEUR PUR — aucun import de Telegram/DB/LLM
│   ├── models.py          # Player, Role, GameState, PublicView
│   ├── engine.py          # machine à états
│   ├── rules.py           # complétion IA, répartition des rôles, victoire, points
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
├── docs/UNDERCOVER_BRIEF.md
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 9. Critères d'acceptation

1. Avec 1 seul humain, « Lancer » déclenche un compte à rebours de 2 minutes. Si personne ne rejoint, Zendaya IA, Kendall IA et BFF Diva IA entrent et la partie se joue à 4 (3 civils, 1 undercover, pas de Mr. White). Avec 2 humains, les 3 IA entrent immédiatement (total 5).
2. Avec 3 humains, les 3 IA sont ajoutées (total 6). Avec 4 humains, les 3 IA (total 7). Avec 5 humains, les 3 IA (total 8). Avec 6 humains, Zendaya IA et Kendall IA (total 8). Avec 7 humains, Zendaya IA seule (total 8). Avec 8 humains, aucune IA.
3. Si un 2e humain rejoint pendant le compte à rebours solo, la partie démarre avec 2 humains + 3 IA. Un 9e humain ne peut pas rejoindre.
4. Si un inscrit n'a jamais démarré le bot, le lancement est bloqué et le bot le nomme.
5. Chaque humain reçoit en privé un mot du trio tiré. Les civils ont tous le même mot, et l'undercover et Mr. White ont chacun un mot différent.
6. Aucun message envoyé dans le groupe ne contient un mot secret avant l'écran de fin (test automatisé sur tous les textes émis).
7. Mr. White n'est jamais le premier orateur d'un tour.
8. Une égalité déclenche un revote. Une nouvelle égalité déclenche un tirage au sort.
9. Si Mr. White est éliminé et devine le mot des civils (avec la normalisation), il gagne seul et la partie s'arrête.
10. Quand il ne reste qu'un civil vivant, les infiltrés gagnent. Quand tous les infiltrés sont éliminés, les civils gagnent.
11. Si le bot redémarre pendant un vote, la partie reprend au même vote avec un délai restant cohérent.
12. Si Groq est indisponible, les IA passent leur tour et votent aléatoirement, et la partie va jusqu'au bout.
13. Une IA ne reçoit jamais d'information sur les mots ou les rôles des autres joueurs (test sur la vue publique).
14. Un trio n'est pas rejoué dans un groupe tant que tous les autres trios n'ont pas été joués.
15. `/classement` affiche les scores cumulés du groupe, IA comprises.

---

## 10. Hors périmètre (v1)

- Mode présentiel ou oral.
- Webhook et hébergement serverless.
- Interface web d'administration.
- Discussion libre des IA en dehors de leurs actions.
- Parties en privé (sans groupe).
- Langues autres que le français.

---

## Annexe A — Base de mots (`data/words.json`)

201 trios en 15 catégories. L'ordre des mots dans un trio n'a pas d'importance : il est mélangé à chaque partie.

```json
[
  {"id": 1, "categorie": "Nourriture et boissons", "mots": ["café", "thé", "chocolat chaud"]},
  {"id": 2, "categorie": "Nourriture et boissons", "mots": ["ndolé", "eru", "okok"]},
  {"id": 3, "categorie": "Nourriture et boissons", "mots": ["bobolo", "miondo", "water fufu"]},
  {"id": 4, "categorie": "Nourriture et boissons", "mots": ["achu", "koki", "sanga"]},
  {"id": 5, "categorie": "Nourriture et boissons", "mots": ["poulet DG", "poulet frites", "poulet yassa"]},
  {"id": 6, "categorie": "Nourriture et boissons", "mots": ["poisson braisé", "soya", "porc braisé"]},
  {"id": 7, "categorie": "Nourriture et boissons", "mots": ["riz sauté", "riz jollof", "riz cantonais"]},
  {"id": 8, "categorie": "Nourriture et boissons", "mots": ["pizza", "burger", "shawarma"]},
  {"id": 9, "categorie": "Nourriture et boissons", "mots": ["mangue", "papaye", "ananas"]},
  {"id": 10, "categorie": "Nourriture et boissons", "mots": ["safou", "olive", "datte"]},
  {"id": 11, "categorie": "Nourriture et boissons", "mots": ["arachide", "noix de cajou", "pistache"]},
  {"id": 12, "categorie": "Nourriture et boissons", "mots": ["pâtes", "couscous", "semoule"]},
  {"id": 13, "categorie": "Nourriture et boissons", "mots": ["bissap", "jus de gingembre", "jus d'ananas"]},
  {"id": 14, "categorie": "Nourriture et boissons", "mots": ["vin de palme", "bière", "vin rouge"]},
  {"id": 15, "categorie": "Nourriture et boissons", "mots": ["glace", "yaourt", "milkshake"]},
  {"id": 16, "categorie": "Nourriture et boissons", "mots": ["croissant", "pain au chocolat", "brioche"]},
  {"id": 17, "categorie": "Nourriture et boissons", "mots": ["sucre", "miel", "sirop"]},
  {"id": 18, "categorie": "Nourriture et boissons", "mots": ["sel", "poivre", "piment"]},
  {"id": 19, "categorie": "Nourriture et boissons", "mots": ["oignon", "ail", "échalote"]},
  {"id": 20, "categorie": "Nourriture et boissons", "mots": ["tomate", "poivron", "aubergine"]},
  {"id": 21, "categorie": "Nourriture et boissons", "mots": ["banane", "plantain", "patate douce"]},
  {"id": 22, "categorie": "Nourriture et boissons", "mots": ["omelette", "œuf dur", "œuf au plat"]},
  {"id": 23, "categorie": "Nourriture et boissons", "mots": ["frites", "chips", "plantain frit"]},
  {"id": 24, "categorie": "Nourriture et boissons", "mots": ["gâteau", "tarte", "cupcake"]},
  {"id": 25, "categorie": "Nourriture et boissons", "mots": ["Coca-Cola", "Fanta", "Sprite"]},
  {"id": 26, "categorie": "Nourriture et boissons", "mots": ["bonbon", "chocolat", "chewing-gum"]},
  {"id": 27, "categorie": "Nourriture et boissons", "mots": ["mayonnaise", "ketchup", "moutarde"]},
  {"id": 28, "categorie": "Nourriture et boissons", "mots": ["beignet", "crêpe", "gaufre"]},
  {"id": 29, "categorie": "Nourriture et boissons", "mots": ["sardine", "thon", "maquereau"]},
  {"id": 30, "categorie": "Maison et objets", "mots": ["fourchette", "cuillère", "couteau"]},
  {"id": 31, "categorie": "Maison et objets", "mots": ["assiette", "bol", "plat"]},
  {"id": 32, "categorie": "Maison et objets", "mots": ["lit", "canapé", "matelas"]},
  {"id": 33, "categorie": "Maison et objets", "mots": ["oreiller", "coussin", "couverture"]},
  {"id": 34, "categorie": "Maison et objets", "mots": ["télévision", "projecteur", "écran d'ordinateur"]},
  {"id": 35, "categorie": "Maison et objets", "mots": ["ventilateur", "climatiseur", "éventail"]},
  {"id": 36, "categorie": "Maison et objets", "mots": ["réfrigérateur", "congélateur", "glacière"]},
  {"id": 37, "categorie": "Maison et objets", "mots": ["balai", "serpillière", "aspirateur"]},
  {"id": 38, "categorie": "Maison et objets", "mots": ["savon", "shampoing", "gel douche"]},
  {"id": 39, "categorie": "Maison et objets", "mots": ["brosse à dents", "dentifrice", "fil dentaire"]},
  {"id": 40, "categorie": "Maison et objets", "mots": ["bougie", "lampe torche", "lampe tempête"]},
  {"id": 41, "categorie": "Maison et objets", "mots": ["clé", "cadenas", "serrure"]},
  {"id": 42, "categorie": "Maison et objets", "mots": ["parapluie", "imperméable", "bottes de pluie"]},
  {"id": 43, "categorie": "Maison et objets", "mots": ["porte", "portail", "fenêtre"]},
  {"id": 44, "categorie": "Maison et objets", "mots": ["chaise", "tabouret", "banc"]},
  {"id": 45, "categorie": "Maison et objets", "mots": ["table", "bureau", "étagère"]},
  {"id": 46, "categorie": "Maison et objets", "mots": ["marmite", "casserole", "poêle"]},
  {"id": 47, "categorie": "Maison et objets", "mots": ["seau", "bassine", "cuvette"]},
  {"id": 48, "categorie": "Maison et objets", "mots": ["groupe électrogène", "panneau solaire", "batterie"]},
  {"id": 49, "categorie": "Maison et objets", "mots": ["réveil", "horloge", "sablier"]},
  {"id": 50, "categorie": "Maison et objets", "mots": ["sac à dos", "valise", "sacoche"]},
  {"id": 51, "categorie": "Maison et objets", "mots": ["portefeuille", "porte-monnaie", "sac à main"]},
  {"id": 52, "categorie": "Transports", "mots": ["bendskin", "taxi", "clando"]},
  {"id": 53, "categorie": "Transports", "mots": ["avion", "hélicoptère", "montgolfière"]},
  {"id": 54, "categorie": "Transports", "mots": ["vélo", "trottinette", "skateboard"]},
  {"id": 55, "categorie": "Transports", "mots": ["bateau", "pirogue", "ferry"]},
  {"id": 56, "categorie": "Transports", "mots": ["train", "métro", "tramway"]},
  {"id": 57, "categorie": "Transports", "mots": ["voiture", "camion", "pick-up"]},
  {"id": 58, "categorie": "Transports", "mots": ["ambulance", "voiture de police", "camion de pompiers"]},
  {"id": 59, "categorie": "Transports", "mots": ["aéroport", "gare", "port"]},
  {"id": 60, "categorie": "Transports", "mots": ["passeport", "carte d'identité", "permis de conduire"]},
  {"id": 61, "categorie": "Transports", "mots": ["casque", "ceinture de sécurité", "airbag"]},
  {"id": 62, "categorie": "Transports", "mots": ["station-service", "garage", "car wash"]},
  {"id": 63, "categorie": "Animaux", "mots": ["chat", "chien", "lapin"]},
  {"id": 64, "categorie": "Animaux", "mots": ["lion", "tigre", "léopard"]},
  {"id": 65, "categorie": "Animaux", "mots": ["éléphant", "rhinocéros", "hippopotame"]},
  {"id": 66, "categorie": "Animaux", "mots": ["singe", "gorille", "chimpanzé"]},
  {"id": 67, "categorie": "Animaux", "mots": ["serpent", "lézard", "crocodile"]},
  {"id": 68, "categorie": "Animaux", "mots": ["moustique", "mouche", "abeille"]},
  {"id": 69, "categorie": "Animaux", "mots": ["poule", "canard", "dinde"]},
  {"id": 70, "categorie": "Animaux", "mots": ["vache", "chèvre", "mouton"]},
  {"id": 71, "categorie": "Animaux", "mots": ["requin", "dauphin", "baleine"]},
  {"id": 72, "categorie": "Animaux", "mots": ["aigle", "hibou", "perroquet"]},
  {"id": 73, "categorie": "Animaux", "mots": ["fourmi", "termite", "cafard"]},
  {"id": 74, "categorie": "Animaux", "mots": ["papillon", "libellule", "coccinelle"]},
  {"id": 75, "categorie": "Animaux", "mots": ["cheval", "âne", "zèbre"]},
  {"id": 76, "categorie": "Animaux", "mots": ["tortue", "escargot", "crabe"]},
  {"id": 77, "categorie": "Animaux", "mots": ["girafe", "chameau", "autruche"]},
  {"id": 78, "categorie": "Animaux", "mots": ["rat", "hamster", "écureuil"]},
  {"id": 79, "categorie": "Lieux", "mots": ["plage", "piscine", "lac"]},
  {"id": 80, "categorie": "Lieux", "mots": ["école", "université", "lycée"]},
  {"id": 81, "categorie": "Lieux", "mots": ["hôpital", "pharmacie", "clinique"]},
  {"id": 82, "categorie": "Lieux", "mots": ["marché", "supermarché", "boutique de quartier"]},
  {"id": 83, "categorie": "Lieux", "mots": ["boîte de nuit", "bar", "cabaret"]},
  {"id": 84, "categorie": "Lieux", "mots": ["restaurant", "tourne-dos", "fast-food"]},
  {"id": 85, "categorie": "Lieux", "mots": ["stade", "gymnase", "salle de sport"]},
  {"id": 86, "categorie": "Lieux", "mots": ["cinéma", "théâtre", "salle de concert"]},
  {"id": 87, "categorie": "Lieux", "mots": ["banque", "distributeur de billets", "kiosque Mobile Money"]},
  {"id": 88, "categorie": "Lieux", "mots": ["montagne", "colline", "volcan"]},
  {"id": 89, "categorie": "Lieux", "mots": ["forêt", "savane", "désert"]},
  {"id": 90, "categorie": "Lieux", "mots": ["prison", "commissariat", "tribunal"]},
  {"id": 91, "categorie": "Lieux", "mots": ["bibliothèque", "librairie", "papeterie"]},
  {"id": 92, "categorie": "Lieux", "mots": ["hôtel", "auberge", "Airbnb"]},
  {"id": 93, "categorie": "Métiers", "mots": ["médecin", "infirmier", "pharmacien"]},
  {"id": 94, "categorie": "Métiers", "mots": ["policier", "gendarme", "militaire"]},
  {"id": 95, "categorie": "Métiers", "mots": ["avocat", "juge", "notaire"]},
  {"id": 96, "categorie": "Métiers", "mots": ["professeur", "directeur d'école", "surveillant"]},
  {"id": 97, "categorie": "Métiers", "mots": ["cuisinier", "serveur", "boulanger"]},
  {"id": 98, "categorie": "Métiers", "mots": ["chauffeur", "pilote", "mécanicien"]},
  {"id": 99, "categorie": "Métiers", "mots": ["ingénieur", "technicien", "architecte"]},
  {"id": 100, "categorie": "Métiers", "mots": ["coiffeur", "barbier", "esthéticienne"]},
  {"id": 101, "categorie": "Métiers", "mots": ["footballeur", "basketteur", "boxeur"]},
  {"id": 102, "categorie": "Métiers", "mots": ["chanteur", "rappeur", "DJ"]},
  {"id": 103, "categorie": "Métiers", "mots": ["journaliste", "présentateur TV", "influenceur"]},
  {"id": 104, "categorie": "Métiers", "mots": ["photographe", "vidéaste", "monteur vidéo"]},
  {"id": 105, "categorie": "Métiers", "mots": ["maçon", "menuisier", "électricien"]},
  {"id": 106, "categorie": "Métiers", "mots": ["bayam-sellam", "call-boxeur", "vendeur à la sauvette"]},
  {"id": 107, "categorie": "Sport et loisirs", "mots": ["football", "handball", "basketball"]},
  {"id": 108, "categorie": "Sport et loisirs", "mots": ["tennis", "badminton", "ping-pong"]},
  {"id": 109, "categorie": "Sport et loisirs", "mots": ["natation", "plongée", "surf"]},
  {"id": 110, "categorie": "Sport et loisirs", "mots": ["boxe", "karaté", "judo"]},
  {"id": 111, "categorie": "Sport et loisirs", "mots": ["échecs", "dames", "Ludo"]},
  {"id": 112, "categorie": "Sport et loisirs", "mots": ["jeu de cartes", "dominos", "dés"]},
  {"id": 113, "categorie": "Sport et loisirs", "mots": ["PlayStation", "Xbox", "Nintendo Switch"]},
  {"id": 114, "categorie": "Sport et loisirs", "mots": ["EA FC", "eFootball", "Football Manager"]},
  {"id": 115, "categorie": "Sport et loisirs", "mots": ["carton jaune", "carton rouge", "coup franc"]},
  {"id": 116, "categorie": "Sport et loisirs", "mots": ["gardien", "défenseur", "attaquant"]},
  {"id": 117, "categorie": "Sport et loisirs", "mots": ["Ligue des champions", "Coupe du monde", "CAN"]},
  {"id": 118, "categorie": "Sport et loisirs", "mots": ["yoga", "pilates", "musculation"]},
  {"id": 119, "categorie": "Sport et loisirs", "mots": ["karaoké", "concert", "festival"]},
  {"id": 120, "categorie": "Musique et médias", "mots": ["makossa", "bikutsi", "afrobeat"]},
  {"id": 121, "categorie": "Musique et médias", "mots": ["guitare", "basse", "ukulélé"]},
  {"id": 122, "categorie": "Musique et médias", "mots": ["piano", "orgue", "synthétiseur"]},
  {"id": 123, "categorie": "Musique et médias", "mots": ["tam-tam", "djembé", "balafon"]},
  {"id": 124, "categorie": "Musique et médias", "mots": ["WhatsApp", "Telegram", "Signal"]},
  {"id": 125, "categorie": "Musique et médias", "mots": ["TikTok", "Instagram", "Snapchat"]},
  {"id": 126, "categorie": "Musique et médias", "mots": ["YouTube", "Netflix", "Canal+"]},
  {"id": 127, "categorie": "Musique et médias", "mots": ["Facebook", "X (Twitter)", "LinkedIn"]},
  {"id": 128, "categorie": "Musique et médias", "mots": ["podcast", "radio", "livre audio"]},
  {"id": 129, "categorie": "Musique et médias", "mots": ["film", "série", "clip vidéo"]},
  {"id": 130, "categorie": "Musique et médias", "mots": ["micro", "enceinte", "écouteurs"]},
  {"id": 131, "categorie": "Technologie", "mots": ["smartphone", "tablette", "ordinateur portable"]},
  {"id": 132, "categorie": "Technologie", "mots": ["clavier", "souris", "pavé tactile"]},
  {"id": 133, "categorie": "Technologie", "mots": ["Wi-Fi", "Bluetooth", "4G"]},
  {"id": 134, "categorie": "Technologie", "mots": ["Android", "iOS", "Windows"]},
  {"id": 135, "categorie": "Technologie", "mots": ["clé USB", "disque dur", "carte SD"]},
  {"id": 136, "categorie": "Technologie", "mots": ["imprimante", "scanner", "photocopieuse"]},
  {"id": 137, "categorie": "Technologie", "mots": ["mot de passe", "code PIN", "empreinte digitale"]},
  {"id": 138, "categorie": "Technologie", "mots": ["e-mail", "SMS", "fax"]},
  {"id": 139, "categorie": "Technologie", "mots": ["ChatGPT", "Claude", "Gemini"]},
  {"id": 140, "categorie": "Technologie", "mots": ["crédit de communication", "forfait internet", "carte SIM"]},
  {"id": 141, "categorie": "Technologie", "mots": ["chargeur", "power bank", "multiprise"]},
  {"id": 142, "categorie": "Technologie", "mots": ["Python", "JavaScript", "Java"]},
  {"id": 143, "categorie": "Technologie", "mots": ["selfie", "portrait", "photo de groupe"]},
  {"id": 144, "categorie": "Vêtements et style", "mots": ["chemise", "t-shirt", "polo"]},
  {"id": 145, "categorie": "Vêtements et style", "mots": ["jean", "pantalon", "short"]},
  {"id": 146, "categorie": "Vêtements et style", "mots": ["baskets", "sandales", "mocassins"]},
  {"id": 147, "categorie": "Vêtements et style", "mots": ["robe", "jupe", "kaba"]},
  {"id": 148, "categorie": "Vêtements et style", "mots": ["casquette", "bonnet", "chapeau"]},
  {"id": 149, "categorie": "Vêtements et style", "mots": ["bracelet", "collier", "bague"]},
  {"id": 150, "categorie": "Vêtements et style", "mots": ["lunettes de soleil", "lunettes de vue", "lentilles"]},
  {"id": 151, "categorie": "Vêtements et style", "mots": ["veste", "manteau", "blouson"]},
  {"id": 152, "categorie": "Vêtements et style", "mots": ["cravate", "nœud papillon", "écharpe"]},
  {"id": 153, "categorie": "Vêtements et style", "mots": ["tresses", "perruque", "tissage"]},
  {"id": 154, "categorie": "Vêtements et style", "mots": ["parfum", "déodorant", "crème"]},
  {"id": 155, "categorie": "Corps et santé", "mots": ["genou", "coude", "épaule"]},
  {"id": 156, "categorie": "Corps et santé", "mots": ["œil", "oreille", "nez"]},
  {"id": 157, "categorie": "Corps et santé", "mots": ["dent", "langue", "lèvre"]},
  {"id": 158, "categorie": "Corps et santé", "mots": ["rhume", "grippe", "toux"]},
  {"id": 159, "categorie": "Corps et santé", "mots": ["cheveux", "barbe", "sourcils"]},
  {"id": 160, "categorie": "Corps et santé", "mots": ["pansement", "seringue", "thermomètre"]},
  {"id": 161, "categorie": "Nature et météo", "mots": ["pluie", "orage", "tempête"]},
  {"id": 162, "categorie": "Nature et météo", "mots": ["soleil", "lune", "étoile"]},
  {"id": 163, "categorie": "Nature et météo", "mots": ["rivière", "fleuve", "cascade"]},
  {"id": 164, "categorie": "Nature et météo", "mots": ["manguier", "palmier", "baobab"]},
  {"id": 165, "categorie": "Nature et météo", "mots": ["sable", "terre", "boue"]},
  {"id": 166, "categorie": "Nature et météo", "mots": ["rose", "tulipe", "tournesol"]},
  {"id": 167, "categorie": "Nature et météo", "mots": ["feu", "fumée", "braise"]},
  {"id": 168, "categorie": "Nature et météo", "mots": ["nuage", "brouillard", "vapeur"]},
  {"id": 169, "categorie": "Vie sociale et événements", "mots": ["mariage", "dot", "fiançailles"]},
  {"id": 170, "categorie": "Vie sociale et événements", "mots": ["anniversaire", "baptême", "communion"]},
  {"id": 171, "categorie": "Vie sociale et événements", "mots": ["Noël", "Nouvel An", "Pâques"]},
  {"id": 172, "categorie": "Vie sociale et événements", "mots": ["vacances", "week-end", "jour férié"]},
  {"id": 173, "categorie": "Vie sociale et événements", "mots": ["examen", "concours", "soutenance"]},
  {"id": 174, "categorie": "Vie sociale et événements", "mots": ["diplôme", "attestation", "relevé de notes"]},
  {"id": 175, "categorie": "Vie sociale et événements", "mots": ["stage", "emploi", "alternance"]},
  {"id": 176, "categorie": "Vie sociale et événements", "mots": ["salaire", "prime", "pourboire"]},
  {"id": 177, "categorie": "Vie sociale et événements", "mots": ["tontine", "épargne", "crédit"]},
  {"id": 178, "categorie": "Vie sociale et événements", "mots": ["cadeau", "surprise", "bouquet de fleurs"]},
  {"id": 179, "categorie": "Culture et personnages", "mots": ["Samuel Eto'o", "Didier Drogba", "Roger Milla"]},
  {"id": 180, "categorie": "Culture et personnages", "mots": ["Messi", "Cristiano Ronaldo", "Neymar"]},
  {"id": 181, "categorie": "Culture et personnages", "mots": ["Naruto", "One Piece", "Dragon Ball"]},
  {"id": 182, "categorie": "Culture et personnages", "mots": ["Superman", "Batman", "Spider-Man"]},
  {"id": 183, "categorie": "Culture et personnages", "mots": ["Harry Potter", "Le Seigneur des anneaux", "Star Wars"]},
  {"id": 184, "categorie": "Culture et personnages", "mots": ["magicien", "sorcier", "marabout"]},
  {"id": 185, "categorie": "Culture et personnages", "mots": ["roi", "président", "chef traditionnel"]},
  {"id": 186, "categorie": "Culture et personnages", "mots": ["vampire", "zombie", "fantôme"]},
  {"id": 187, "categorie": "Divers", "mots": ["or", "argent", "bronze"]},
  {"id": 188, "categorie": "Divers", "mots": ["stylo", "crayon", "feutre"]},
  {"id": 189, "categorie": "Divers", "mots": ["cahier", "livre", "carnet"]},
  {"id": 190, "categorie": "Divers", "mots": ["tableau noir", "tableau blanc", "paperboard"]},
  {"id": 191, "categorie": "Divers", "mots": ["brique", "parpaing", "pierre"]},
  {"id": 192, "categorie": "Divers", "mots": ["facture", "reçu", "ticket de caisse"]},
  {"id": 193, "categorie": "Divers", "mots": ["journal", "magazine", "bande dessinée"]},
  {"id": 194, "categorie": "Divers", "mots": ["drapeau", "hymne national", "blason"]},
  {"id": 195, "categorie": "Divers", "mots": ["couronne", "trône", "sceptre"]},
  {"id": 196, "categorie": "Divers", "mots": ["carte routière", "boussole", "GPS"]},
  {"id": 197, "categorie": "Divers", "mots": ["sirène", "alarme", "klaxon"]},
  {"id": 198, "categorie": "Divers", "mots": ["fusée", "satellite", "station spatiale"]},
  {"id": 199, "categorie": "Divers", "mots": ["robot", "androïde", "cyborg"]},
  {"id": 200, "categorie": "Divers", "mots": ["pièce de monnaie", "billet", "carte bancaire"]},
  {"id": 201, "categorie": "Divers", "mots": ["enveloppe", "colis", "lettre"]}
]
```
