# Tasks: Bot Telegram « Undercover »

**Input**: documents de conception dans `/specs/001-undercover-bot/` : [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Prérequis**: plan.md et spec.md (présents), constitution v1.0.0

**Tests**: **obligatoires**. Le principe VI de la constitution impose que tout comportement du moteur arrive avec ses tests, et les principes III (confidentialité) et IV (équité) exigent des tests automatisés. Les tests d'une story sont écrits d'abord et DOIVENT échouer avant l'implémentation.

**Organisation**: les tâches sont groupées par *story de livraison*, dans l'ordre demandé (1 base de mots, 2 moteur, 3 lobby, 4 partie entre humains, 5 IA et mode solo, 6 persistance et reprise, 7 classement, 8 Docker).

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, aucune dépendance à une tâche inachevée)
- **[US1]…[US8]** : story de livraison (voir la correspondance ci-dessous)
- Chaque tâche indique son chemin de fichier exact (racine du dépôt, structure de plan.md)

## Correspondance avec les user stories de spec.md

Les stories de livraison ci-dessous suivent le découpage du brief ; elles sont différentes des stories de priorité de `spec.md` (US1 à US6 de la spec), qui décrivent la valeur utilisateur.

| Story de livraison | Contenu | Stories de spec.md | Exigences principales |
|---|---|---|---|
| US1 | Base de mots, chargeur, tirage | — (socle de la spec 1) | FR-056 à FR-059 |
| US2 | Moteur de jeu pur | spec US1 (règles), US4 (équité) | FR-014 à FR-040, FR-049 |
| US3 | Lobby Telegram | spec US3 | FR-001 à FR-008a, FR-041 à FR-042 (partiel) |
| US4 | Partie complète entre humains | spec US1, US4 (confidentialité) | FR-019 à FR-038, FR-043, FR-045 |
| US5 | Agents IA et mode solo | spec US2 | FR-009 à FR-013, FR-044, FR-047 à FR-055 |
| US6 | Persistance et reprise | spec US6 | FR-007, FR-058, FR-060 |
| US7 | Classement | spec US5 | FR-040, FR-041 (classement) |
| US8 | Docker et documentation | — | FR-046 |

---

## Phase 1: Setup (infrastructure partagée)

**But**: initialiser le projet et l'outillage.

- [X] T001 Créer l'arborescence de plan.md avec des fichiers `__init__.py` vides : `bot/`, `bot/handlers/`, `game/`, `ai/`, `db/`, `data/`, `tests/`, `tests/unit/`, `tests/integration/`
- [X] T002 Écrire `pyproject.toml` : Python `>=3.12`, dépendances runtime `aiogram>=3.0,<4`, `sqlalchemy[asyncio]>=2.0`, `aiosqlite`, `pydantic-settings`, `groq` ; groupe `dev` avec `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff` ; configuration ruff (lint + format) et pytest (`asyncio_mode = "auto"`, `testpaths = ["tests"]`)
- [X] T003 [P] Écrire `.gitignore` à la racine : `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.coverage`, `data/*.db`
- [X] T004 [P] Écrire `.env.example` sans aucune valeur secrète : `BOT_TOKEN=`, `GROQ_API_KEY=`, `GROQ_MODEL=llama-3.3-70b-versatile`, `DATABASE_URL=sqlite+aiosqlite:///./data/undercover.db`, `DESCRIPTION_TIMEOUT=60`, `VOTE_TIMEOUT=90`, `GUESS_TIMEOUT=60`, `LOBBY_TIMEOUT=600`, `SOLO_WAIT_TIMEOUT=120` (contrat : [contracts/configuration.md](contracts/configuration.md))
- [X] T005 Créer l'environnement virtuel avec `py -3.12 -m venv .venv`, installer `pip install -e ".[dev]"`, et vérifier `python --version` = 3.12 et `pytest --collect-only` sans erreur

---

## Phase 2: Fondations (prérequis bloquants)

**But**: briques communes à toutes les stories. Aucune story ne démarre avant la fin de cette phase.

- [X] T006 [P] Test de normalisation dans `tests/unit/test_normalize.py` : minuscules, accents supprimés, espaces et tirets unifiés, articles initiaux retirés (« le, la, les, l', un, une, des »), cas `L'ananas` / `un Ananas` / `ananas` égaux, `Coca-Cola` / `coca cola` égaux ; `contains_secret_or_root(text, word)` : vrai si le texte contient le mot (normalisé, mot entier ou expression) ou un mot partageant un préfixe commun d'au moins 5 caractères avec lui (« cuisinier » / « cuisinière »), faux pour un mot court sans lien (« thé » / « thème »)
- [X] T007 Implémenter `game/normalize.py` : `normalize(text) -> str` selon FR-035 et `contains_secret_or_root(text, word) -> bool` selon research.md R6 (aucun import hors bibliothèque standard)
- [X] T008 [P] Test de configuration dans `tests/unit/test_config.py` : valeurs par défaut des délais, erreur explicite si `BOT_TOKEN`, `GROQ_API_KEY` ou `GROQ_MODEL` manque, délai non entier ou ≤ 0 refusé
- [X] T009 [P] Écrire `data/game_config.json` : répartition des rôles pour 4 à 8 joueurs (`4 → 3/1/0`, `5 → 3/1/1`, `6 → 4/1/1`, `7 → 5/1/1`, `8 → 5/2/1`), barème de points (civil +2, undercover +10, Mr. White +6, devinette +10) (la complétion IA reste une règle fixe dans `game/rules.py`, FR-009)
- [X] T010 Implémenter `bot/config.py` : `Settings` (pydantic-settings, lit `.env`) avec les 9 variables du contrat, et chargeur du fichier `data/game_config.json` qui échoue avec une erreur explicite s'il est absent ou invalide (FR-016)

**Checkpoint**: normalisation, configuration et table de jeu prêtes.

---

## Phase 3: US1 - Base de mots, chargeur et tests (Priority: P1) 🎯 MVP technique

**Goal**: la base de 201 trios est livrée, validée au démarrage et tirable sans répétition par groupe.

**Independent Test**: `pytest tests/unit/test_words.py` passe ; charger une base avec un doublon d'id lève une erreur qui nomme l'id ; tirer 201 fois dans un groupe renvoie 201 trios distincts.

### Tests for US1 (écrire d'abord, doivent échouer)

- [X] T011 [P] [US1] Tests du chargeur dans `tests/unit/test_words.py` : fichier non tableau, objet sans les trois champs, `id` en double (message nommant l'id), trio avec ≠ 3 mots, mot vide, deux mots identiques après normalisation (ex. « Thé » et « the ») ; trio valide accepté
- [X] T012 [P] [US1] Tests du tirage dans `tests/unit/test_words_draw.py` : `draw` n'inclut jamais un trio de `played_ids` ; avec tous les trios joués le cycle recommence ; tirage déterministe pour une graine donnée ; les trois mots d'un trio sont mélangés (A, B, C varient selon la graine) (FR-014, FR-058)
- [X] T013 [P] [US1] Test de la base livrée dans `tests/unit/test_words_file.py` : `data/words.json` contient exactement 201 trios et 15 catégories, ids uniques, chaque trio valide

### Implementation for US1

- [X] T014 [US1] Extraire l'annexe A de `docs/UNDERCOVER_BRIEF.md` telle quelle dans `data/words.json` (bloc JSON entre les balises de code de l'annexe) ; vérifier 201 trios (aucune retouche du contenu)
- [X] T015 [US1] Ajouter `WordTrio` (`id` int, `category` str, `words` tuple de 3 str) dans `game/models.py`
- [X] T016 [US1] Implémenter `game/words.py` : `load_words(path) -> list[WordTrio]` avec validation « id unique, exactement 3 mots distincts par trio » et une erreur `WordsError` explicite nommant l'id fautif (FR-057)
- [X] T017 [US1] Implémenter dans `game/words.py` : `draw(trios, played_ids, rng) -> tuple[WordTrio, civilian_word, undercover_word, mr_white_word]` qui exclut `played_ids`, repart de zéro quand tout est joué, et mélange les trois mots avec `rng` (FR-014, FR-058)

**Checkpoint**: US1 complète et testable seule ; `ruff check game/ tests/` propre.

---

## Phase 4: US2 - Moteur de jeu pur et tests (Priority: P2)

**Goal**: toute la logique de jeu (complétion IA, rôles, descriptions, votes, éliminations, devinette, victoire, points, vue publique) existe dans `game/`, sans dépendance à Telegram, à la base de données ou au LLM.

**Independent Test**: `pytest tests/unit --cov=game --cov-fail-under=90` passe ; une partie complète est jouable en pur Python avec des événements simulés, deux exécutions avec la même graine donnent le même résultat.

### Tests for US2 (écrire d'abord, doivent échouer)

- [X] T018 [P] [US2] Tests des règles dans `tests/unit/test_rules.py` : complétion IA pour 1 à 8 humains et refus du 9e (table FR-009, ordre Zendaya IA, Kendall IA, BFF Diva IA), répartition des rôles pour les totaux 4 à 8 (FR-015), points pour les trois issues (FR-039), victoire (FR-037 : civils, infiltrés si ≤ 1 civil vivant, Mr. White par devinette)
- [X] T019 [P] [US2] Tests de la distribution dans `tests/unit/test_engine_start.py` : les civils ont tous le mot A, l'undercover le mot B, Mr. White le mot C (FR-014), nombres de rôles conformes, aucun rôle exposé, déterminisme à graine égale
- [X] T020 [P] [US2] Tests des descriptions dans `tests/unit/test_engine_description.py` : « un mot ou une courte expression, 6 mots maximum » (7 mots refusé), seul l'orateur courant est pris en compte, mot secret interdit (comparaison normalisée) refusé, expiration → tour passé, Mr. White jamais premier orateur au tour 1 et aux tours suivants (FR-021) sur 200 graines, premier orateur suivant dans l'ordre initial
- [X] T021 [P] [US2] Tests du vote dans `tests/unit/test_engine_vote.py` : pas de vote pour soi, vote modifiable, clôture quand tous ont voté ou à l'expiration, abstentions, élimination du plus voté, égalité → revote entre ex æquo, nouvelle égalité → tirage au sort, aucun vote → pas d'élimination et `no_vote_streak` +1, 3 tours consécutifs sans vote → `CANCELLED` sans point (FR-032)
- [X] T022 [P] [US2] Tests de l'élimination et de la devinette dans `tests/unit/test_engine_guess.py` : rôle révélé sans le mot (FR-033), Mr. White éliminé a une seule tentative, devinette correcte avec normalisation (« L'Ananas » = « ananas ») → victoire de Mr. White seul et fin immédiate, devinette ratée → la partie continue
- [X] T023 [P] [US2] Tests de la fin et de l'annulation dans `tests/unit/test_engine_end.py` : victoire des civils, victoire des infiltrés avec 1 civil vivant, points attribués par issue, annulation depuis chaque phase, partie à 4 sans Mr. White jouable jusqu'au bout
- [X] T024 [P] [US2] Tests de la vue publique dans `tests/unit/test_public_view.py` : `PublicView` ne contient ni le rôle du lecteur ni les mots ou rôles des autres joueurs vivants ; contient l'historique public et les rôles révélés des éliminés (FR-049, principe IV)
- [X] T025 [P] [US2] Tests de sérialisation et de pureté dans `tests/unit/test_engine_purity.py` : `GameState.to_dict()` puis `from_dict()` redonne un état identique ; test d'import : `game/` n'importe ni `aiogram`, ni `sqlalchemy`, ni `groq`, ni `asyncio` (principe II)
- [X] T026 [P] [US2] Test de simulation complète dans `tests/unit/test_engine_simulation.py` : 300 parties avec joueurs simulés (descriptions, votes aléatoires) pour 4 à 8 joueurs, chaque partie se termine, aucune exception, résultats identiques pour une graine fixe

### Implementation for US2

- [X] T027 [US2] Compléter `game/models.py` : `Role` (`CIVILIAN`, `UNDERCOVER`, `MR_WHITE`), `Phase` (`LOBBY`, `DISTRIBUTION`, `DESCRIPTION`, `VOTE`, `REVOTE`, `MR_WHITE_GUESS`, `CHECK_VICTORY`, `ENDED`, `CANCELLED`), `Player` (`id` au format `h:<user_id>` ou `ai:<nom>`, `name`, `is_ai`, `role`, `word`, `alive`, `can_dm`), `Description` (`round`, `player_id`, `text` ≤ 6 mots, `skipped`), `VoteRound`, `Elimination`, `GameState` (champs de [data-model.md](data-model.md)), `Outcome`, avec le champ `solo_waiting` (bool) et `to_dict`/`from_dict` JSON
- [X] T028 [US2] Ajouter dans `game/models.py` (après T027) les événements d'entrée (`Join`, `Leave`, `Launch`, `Cancel`, `Describe`, `CastVote`, `Guess`, `Timeout(kind)`) et les effets de sortie (`SendGroup`, `SendPrivate`, `DeleteMessage`, `RequestAIAction`, `StartTimer`, `CancelTimer`, `UpdateLobby`) qui référencent des clés de texte (R3 de [research.md](research.md))
- [X] T029 [US2] Implémenter `game/rules.py` : `ai_completion(n_humans)` (ordre Zendaya IA, Kendall IA, BFF Diva IA ; 9+ refusé), `role_distribution(total, config)`, `check_victory(state)`, `compute_points(state, config)` ; tables lues depuis la config fournie, aucune valeur codée en dur (FR-009, FR-015, FR-016, FR-037, FR-039)
- [X] T030 [US2] Implémenter dans `game/engine.py` la distribution : tirage du trio via `game.words.draw`, mélange, attribution des rôles et des mots, ordre des orateurs avec Mr. White jamais premier (FR-014, FR-018, FR-021)
- [X] T031 [US2] Implémenter dans `game/engine.py` la phase de description : validation (≤ 6 mots, mot secret refusé via `contains_secret_or_root` pour les humains comme pour les IA, seul l'orateur courant), expiration `Timeout`, récapitulatif avant le vote (FR-020 à FR-026)
- [X] T032 [US2] Implémenter dans `game/engine.py` la phase de vote et le revote : un bulletin par vivant, pas pour soi, remplaçable, clôture sur complétude ou expiration, plus voté éliminé, égalité → revote, nouvelle égalité → tirage au sort via `rng`, `no_vote_streak` et annulation à 3 (FR-027 à FR-032)
- [X] T033 [US2] Implémenter dans `game/engine.py` l'élimination, la devinette de Mr. White (une seule tentative, comparaison normalisée) et `CHECK_VICTORY` avec attribution des points à la fin (FR-033 à FR-039)
- [X] T034 [US2] Implémenter dans `game/engine.py` le lobby pur (inscription, départ, transfert du créateur, 8 humains maximum, annulation depuis n'importe quelle phase) et `public_view(state, player_id) -> PublicView` (FR-003, FR-008, FR-008a, FR-049)
- [X] T035 [US2] Vérifier `pytest tests/unit --cov=game --cov-fail-under=90` et `ruff check game/ tests/` ; corriger les écarts

**Checkpoint**: le moteur joue une partie complète seul ; US1 et US2 indépendantes de tout transport.

---

## Phase 5: US3 - Lobby Telegram (Priority: P3)

**Goal**: dans un groupe, on crée un lobby, on rejoint, on quitte, le message se met à jour en direct, et le lancement est bloqué tant qu'un inscrit ne peut pas recevoir de message privé.

**Independent Test**: avec un faux bot (sans réseau), un scénario complet de lobby passe ; sur un vrai groupe de test, `/nouvelle`, les boutons et le blocage ⚠️ fonctionnent.

### Tests for US3 (écrire d'abord)

- [X] T036 [P] [US3] Créer le faux bot dans `tests/integration/fakes.py` : enregistre chaque message envoyé (groupe vs privé), les éditions, les suppressions, les indicateurs de frappe, et simule les clics de boutons et les messages de joueurs
- [X] T037 [P] [US3] Tests du lobby dans `tests/integration/test_lobby.py` : `/nouvelle` crée un lobby avec Rejoindre, Quitter, Lancer, Annuler ; un 2e lobby dans le groupe est refusé ; mise à jour en direct de la liste ; ✅/⚠️ par inscrit ; lancement bloqué avec les joueurs nommés et lien `https://t.me/<bot>?start=<game_id>` ; 9e joueur refusé (« partie complète ») ; un utilisateur déjà inscrit ailleurs refusé ; expiration à 10 minutes ; transfert du créateur ; seul le créateur lance ou annule

### Implementation for US3

- [X] T038 [US3] Écrire `bot/texts.py` (textes de lobby en français, ton fun et direct, emojis modérés) : lobby, inscrit ✅/⚠️, lancement bloqué, partie complète, déjà inscrit, créateur transféré, lobby expiré ; toute chaîne utilisateur vit ici (principe VII)
- [X] T039 [P] [US3] Écrire `bot/keyboards.py` : clavier du lobby et lien profond, données de rappel `<action>:<game_id>[:<argument>]` ≤ 64 octets ([contracts/callback-data.md](contracts/callback-data.md))
- [X] T040 [US3] Écrire `bot/orchestrator.py` (première version) : registre des parties actives en mémoire, verrou asyncio par partie, application des événements au moteur avec un `random.Random` injecté, exécution des effets vers le bot, minuteries asyncio (expiration du lobby selon `LOBBY_TIMEOUT`), règle « une seule partie par utilisateur, tous groupes confondus » (FR-007)
- [X] T041 [US3] Écrire `bot/handlers/lobby.py` : `/nouvelle`, `/lancer`, `/annuler`, boutons `join`, `leave`, `launch`, `cancel`, mise à jour du message de lobby (FR-001 à FR-008a)
- [X] T042 [US3] Écrire `bot/handlers/private.py` (première version) : `/start` (marque `can_dm`, lien profond), `/aide` (FR-042)
- [X] T043 [US3] Écrire `bot/main.py` : charge `Settings`, valide `data/words.json` au démarrage (erreur explicite et arrêt avec code non nul, FR-057), construit le dispatcher aiogram en long polling et enregistre les routeurs

**Checkpoint**: un lobby se remplit et se lance (la partie démarre sans IA à ce stade) ; US3 testable via faux bot et groupe de test.

---

## Phase 6: US4 - Déroulement complet d'une partie entre humains (Priority: P4)

**Goal**: 2 à 8 humains jouent une partie complète : mot en privé, tours de description, vote, élimination, devinette de Mr. White, victoire, écran de fin ; aucun mot secret n'apparaît dans le groupe avant la fin.

**Independent Test**: un test d'intégration rejoue des parties entières avec le faux bot ; sur un groupe réel avec deux comptes, une partie se termine sur l'écran de fin.

### Tests for US4 (écrire d'abord)

- [X] T044 [P] [US4] Test de confidentialité dans `tests/integration/test_confidentiality.py` : rejoue des parties complètes sur de nombreuses graines (égalité, revote, tirage, devinette réussie et ratée, tour passé, description refusée, annulation) et vérifie qu'**aucun** message de groupe émis avant l'écran de fin ne contient l'un des trois mots du trio (comparaison normalisée) (FR-043, principe III)
- [X] T045 [P] [US4] Tests du parcours dans `tests/integration/test_full_game.py` : chaque humain reçoit son mot en privé, civils identiques, descriptions dans l'ordre, messages hors tour ignorés, description à mot secret refusée et supprimée si le bot est administrateur, récapitulatif avant le vote, vote avec boutons (un par vivant), qui-a-voté-pour-qui publié, révélation du rôle sans le mot, fin avec rôles, trois mots et classement de la partie
- [X] T046 [P] [US4] Tests de la devinette dans `tests/integration/test_mr_white_guess.py` : demande en privé, 60 secondes, bonne réponse normalisée → victoire seule, mauvaise ou absente → tentative ratée

### Implementation for US4

- [X] T047 [US4] Compléter `bot/texts.py` : distribution du mot, annonce d'ordre, tour passé, description refusée, récapitulatif, ouverture et clôture du vote, qui-a-voté-pour-qui, égalité et revote, tirage, élimination (rôle sans mot), demande de devinette, écran de fin (rôles, trois mots, points, classement de la partie), règles (`/regles`), état (`/etat`)
- [X] T048 [P] [US4] Compléter `bot/keyboards.py` : clavier de vote avec un bouton par joueur vivant (`vote:<game_id>:<player_id>`)
- [X] T049 [US4] Écrire `bot/handlers/game.py` : réception des descriptions dans le groupe (seul l'orateur courant), suppression du message interdit si le bot est administrateur, bouton `vote` avec confirmation discrète, bouton obsolète « Ce vote est terminé », `/etat`, `/regles`
- [X] T050 [US4] Compléter `bot/handlers/private.py` : `/monmot` et réception de la devinette de Mr. White en privé (FR-034, FR-042)
- [X] T051 [US4] Compléter `bot/orchestrator.py` : distribution des mots en privé au lancement, minuteries `DESCRIPTION_TIMEOUT`, `VOTE_TIMEOUT`, `GUESS_TIMEOUT` pilotées par les effets `StartTimer`/`CancelTimer`, enchaînement des tours jusqu'à l'écran de fin, annulation par le créateur à tout moment
- [X] T052 [US4] Vérifier `pytest` complet et `ruff check .` ; corriger les écarts

**Checkpoint**: une partie complète 100 % humaine fonctionne, confidentialité vérifiée par test.

---

## Phase 7: US5 - Agents IA Zendaya IA, Kendall IA, BFF Diva IA et mode solo (Priority: P5)

**Goal**: les trois IA complètent la partie selon le tableau, jouent comme des humains (décrire, voter, deviner), ne savent que ce qu'un humain saurait, ne bloquent jamais la partie ; un joueur seul affronte les trois IA après un compte à rebours.

**Independent Test**: avec un faux LLM, des parties à 1 à 8 humains vont jusqu'au bout ; avec un LLM en panne (erreurs 429 et timeouts), elles vont aussi jusqu'au bout.

### Tests for US5 (écrire d'abord)

- [X] T053 [P] [US5] Tests de l'agent dans `tests/unit/test_agent.py` avec un faux client LLM : description valide acceptée ; > 6 mots, mot secret, racine évidente, répétition d'une description déjà donnée → nouvelle tentative, 3 échecs → « Je passe mon tour 🤐 » ; vote invalide ou pour soi-même → vote aléatoire valide ; devinette absente → « Je ne sais pas » ; aucune méthode ne lève d'exception (FR-050 à FR-052, FR-055)
- [X] T054 [P] [US5] Tests du client Groq dans `tests/unit/test_groq_client.py` avec un faux SDK : timeout, 429 avec backoff exponentiel limité à 3 essais puis `LLMUnavailable`, modèle lu depuis `GROQ_MODEL`
- [X] T055 [P] [US5] Test d'équité dans `tests/unit/test_ai_fairness.py` : l'entrée envoyée au LLM est construite uniquement depuis `PublicView` ; le module `ai/` n'importe pas `GameState` ; le texte du prompt ne contient ni le rôle de l'IA ni les mots ou rôles des autres joueurs vivants (FR-049, principe IV)
- [X] T056 [P] [US5] Tests de complétion et du mode solo dans `tests/integration/test_ai_completion.py` : pour 2 à 8 humains les IA entrent comme dans le tableau et le total est exact ; avec 1 humain, « Lancer » publie un dernier appel et un compte à rebours de `SOLO_WAIT_TIMEOUT` mis à jour dans le lobby ; sans arrivant la partie démarre à 4 (3 civils, 1 undercover, pas de Mr. White) ; un 2e humain pendant le compte à rebours → 2 humains + 3 IA ; un second « Lancer » abrège ; le créateur peut annuler
- [X] T057 [P] [US5] Tests de résilience dans `tests/integration/test_ai_resilience.py` : LLM indisponible pendant toute la partie, 100 parties simulées toutes terminées ; préfixe « 🤖 » sur chaque message d'IA ; indicateur de frappe de 2 à 5 secondes avant chaque message d'IA ; vote d'IA silencieux ; IA dans plusieurs groupes en parallèle ; extension du test de confidentialité avec des IA

### Implementation for US5

- [X] T058 [US5] Écrire `ai/prompts.py` : prompts en français centralisés ; trois personnalités appliquées au style des indices uniquement (Zendaya IA posée et analytique, Kendall IA joueuse et imagée, BFF Diva IA expressive et issue de la vie quotidienne) ; stratégie de la section 4.4 du brief ; sortie JSON stricte `{"description": "..."}`, `{"vote": "<nom exact>"}`, `{"guess": "..."}` ([contracts/ai-actions.md](contracts/ai-actions.md))
- [X] T059 [P] [US5] Écrire `ai/groq_client.py` : client asynchrone sur le SDK `groq`, mode JSON, modèle lu dans `GROQ_MODEL` (jamais codé en dur), timeout, backoff exponentiel sur 429 limité à 3 essais, erreur typée `LLMUnavailable`
- [X] T060 [US5] Écrire `ai/agent.py` : `describe`, `vote`, `guess` qui ne reçoivent qu'une `PublicView`, valident chaque sortie (la détection du mot secret et de sa racine réutilise `game.normalize.contains_secret_or_root`, sans seconde implémentation) et appliquent les replis (3 tentatives puis « Je passe mon tour 🤐 » ; vote aléatoire valide ; « Je ne sais pas ») ; `ai/` ne doit pas importer `GameState`
- [X] T061 [US5] Compléter `game/engine.py` et `game/rules.py` : complétion IA au lancement (ordre fixe, totaux 4 à 8), mode solo (drapeau `solo_waiting` dans `GameState` en phase `LOBBY`, compte à rebours, lancement abrégé, annulation), partie à 4 sans Mr. White ; ajouter les tests unitaires correspondants dans `tests/unit/test_engine_solo.py` (FR-009 à FR-013)
- [X] T062 [US5] Compléter `bot/orchestrator.py` : exécution de `RequestAIAction` hors du verrou de la partie avec un délai global, indicateur de frappe 2 à 5 s avant chaque message d'IA, préfixe « 🤖 » (FR-044), vote d'IA silencieux, devinette d'IA, repli garanti pour qu'une IA ne bloque jamais la partie ; minuterie `SOLO_WAIT_TIMEOUT` et mise à jour du compte à rebours dans le lobby (FR-054, FR-055)
- [X] T063 [US5] Compléter `bot/handlers/lobby.py` et `bot/texts.py` : dernier appel dans le groupe, compte à rebours solo, texte des IA et de leurs repli
- [X] T064 [US5] Vérifier `pytest` complet et `ruff check .` ; corriger les écarts

**Checkpoint**: tout nombre d'humains de 1 à 8 donne une partie jouable, même sans LLM.

---

## Phase 8: US6 - Persistance et reprise après redémarrage (Priority: P6)

**Goal**: l'état est sauvegardé après chaque transition ; un redémarrage reprend la partie au même point avec les délais restants.

**Independent Test**: démarrer une partie, l'interrompre pendant un vote, redémarrer l'orchestrateur sur la même base : le même vote reprend avec le temps restant.

### Tests for US6 (écrire d'abord)

- [X] T065 [P] [US6] Tests du dépôt dans `tests/integration/test_repository.py` (SQLite en mémoire) : sauvegarde et relecture d'un `GameState` identique, une seule partie non terminée par groupe, table `participants` refusant un 2e inscrit dans une autre partie, `users.can_dm` (conservé après un redémarrage), historique `played_trios` par groupe avec remise à zéro quand tout est joué
- [X] T066 [P] [US6] Tests de reprise dans `tests/integration/test_resume.py` : arrêt pendant un vote, un tour de description, une devinette de Mr. White, le compte à rebours solo et un lobby ; au redémarrage, même phase, même vote, minuterie reprogrammée avec `max(0, deadline_at - maintenant)`, échéance dépassée traitée immédiatement ; aucun doublon de message (critère 11 du brief, FR-060)

### Implementation for US6

- [X] T067 [US6] Écrire `db/models.py` (SQLAlchemy 2 async) : tables `games` (`game_id` clé primaire, `chat_id` indexé, `phase`, `state_json`, `deadline_kind`, `deadline_at` UTC nullable, `lobby_message_id`, `updated_at`), `participants` (`game_id`, `user_id` clé composite), `users` (`user_id`, `display_name`, `can_dm`, `started_at`), `scores` (`chat_id`, `player_id`, `display_name`, `points`, `games_played`), `played_trios` (`chat_id`, `trio_id`, `played_at`) ([data-model.md](data-model.md))
- [X] T068 [US6] Écrire `db/repository.py` : création du moteur asynchrone à partir de `DATABASE_URL`, création des tables au démarrage, sauvegarde atomique de l'état et de l'échéance dans la même transaction, lecture des parties non terminées, `participants`, `users`, `played_trios` (une session par opération)
- [X] T069 [US6] Brancher `bot/orchestrator.py` et `bot/handlers/private.py` sur `db/repository.py` : sauvegarde après chaque transition ; remplacement du registre en mémoire par la base pour la règle « une seule partie par utilisateur » (FR-007), l'historique des trios (FR-058) et le statut `users.can_dm` (écrit par `/start`, lu pour les marques ✅/⚠️ du lobby, FR-004)
- [X] T070 [US6] Implémenter la reprise dans `bot/orchestrator.py` et `bot/main.py` : au démarrage, relire les parties non terminées, restaurer les verrous et reprogrammer chaque minuterie avec le temps restant
- [X] T071 [US6] Vérifier `pytest` complet et `ruff check .` ; corriger les écarts

**Checkpoint**: arrêt et relance du bot sans perte de partie.

---

## Phase 9: US7 - Classement (Priority: P7)

**Goal**: les scores sont cumulés par groupe, IA comprises, et consultables avec `/classement`.

**Independent Test**: jouer plusieurs parties dans un groupe puis `/classement` affiche la somme des points par joueur ; un autre groupe a ses propres scores.

### Tests for US7 (écrire d'abord)

- [X] T072 [P] [US7] Tests dans `tests/integration/test_leaderboard.py` : points cumulés sur plusieurs parties pour les trois issues, IA présentes au classement, groupes indépendants, partie annulée sans point, `/classement` sans score renvoie un message dédié (FR-040, SC-010)

### Implementation for US7

- [X] T073 [US7] Compléter `db/repository.py` : `add_scores(chat_id, points_by_player)` appelé à la fin de partie dans la même transaction que la sauvegarde finale ; `get_leaderboard(chat_id)` trié par points décroissants
- [X] T074 [US7] Compléter `bot/orchestrator.py` : enregistrement des points à l'issue d'une victoire (jamais à l'annulation) ; compléter `bot/texts.py` et `bot/handlers/game.py` : commande `/classement` et affichage du classement de la partie dans l'écran de fin
- [X] T075 [US7] Vérifier `pytest` complet et `ruff check .` ; corriger les écarts

**Checkpoint**: le classement cumulé fonctionne de bout en bout.

---

## Phase 10: US8 - Docker et documentation (Priority: P8)

**Goal**: le bot se déploie en une commande dans un conteneur, avec un volume pour SQLite, et le README documente l'installation et les prérequis Telegram.

**Independent Test**: `docker compose up --build` démarre le bot, il répond à `/regles` dans le groupe, la base survit à `docker compose restart`.

- [X] T076 [P] [US8] Écrire `Dockerfile` : image Python 3.12 slim, installation des dépendances depuis `pyproject.toml`, utilisateur non root, commande `python -m bot.main`, aucun secret dans l'image
- [X] T077 [P] [US8] Écrire `.dockerignore` : `.env`, `.venv/`, `.git/`, `__pycache__/`, `tests/`, `specs/`, `data/*.db`
- [X] T078 [US8] Écrire `docker-compose.yml` : service du bot, `env_file: .env`, volume nommé monté sur le dossier de la base SQLite, `restart: unless-stopped`
- [X] T079 [US8] Écrire `README.md` en français : présentation, installation locale (`py -3.12`), variables d'environnement, prérequis BotFather (`/setprivacy` → Disable ; bot administrateur optionnel pour supprimer les descriptions interdites, FR-046), commandes, tests, Docker, personnalisation de `data/words.json` et `data/game_config.json`
- [ ] T080 [US8] Valider : `docker compose build`, démarrage, `/regles` dans un groupe de test, `docker compose restart` sans perte de la base — *Fait le 2026-10-01 : image construite, utilisateur non root, erreur explicite sans secrets, base SQLite conservée entre deux conteneurs sur le même volume. Reste : `/regles` dans un vrai groupe (jeton requis).*

**Checkpoint**: livraison conteneurisée complète.

---

## Phase 11: Finitions et transversal

**But**: qualité et vérifications finales.

- [X] T081 [P] Exécuter `ruff check .` et `ruff format --check .` sur tout le dépôt et corriger
- [X] T082 Exécuter `pytest --cov=game --cov-fail-under=90` et confirmer le seuil du moteur (principe VI)
- [X] T083 [P] Vérifier qu'aucun secret n'apparaît dans le code, les journaux, les tests ni les messages du bot (`BOT_TOKEN`, `GROQ_API_KEY`) et que `.env` est ignoré par git (principe VIII)
- [X] T084 [P] Configurer la journalisation dans `bot/main.py` (niveaux, aucun mot secret ni secret dans les logs)
- [ ] T085 Parcourir les 10 scénarios de [quickstart.md](quickstart.md) sur un groupe de test réel et noter les écarts
- [X] T086 Retirer le commentaire « Sync Impact Report » de `.specify/memory/constitution.md` avant le commit (prévu par la procédure de constitution)

---

## Dépendances et ordre d'exécution

### Dépendances entre phases

- **Setup (Phase 1)** : aucune dépendance
- **Fondations (Phase 2)** : dépend de Setup ; **bloque** toutes les stories
- **Stories** : strictement séquentielles dans l'ordre demandé, car chacune s'appuie sur la précédente
  - US1 (mots) → US2 (le moteur utilise `WordTrio` et `draw`)
  - US2 → US3 (le lobby utilise le moteur)
  - US3 → US4 (la partie complète s'appuie sur le lobby et l'orchestrateur)
  - US4 → US5 (les IA s'ajoutent à l'orchestrateur et au parcours humain)
  - US4 → US6 (la persistance s'appuie sur les transitions définies) ; placée après US5 pour que les états IA et solo soient aussi sauvegardés
  - US6 → US7 (le classement utilise la base)
  - US1 à US7 → US8 (Docker et documentation)
- **Finitions (Phase 11)** : après toutes les stories

### Dans chaque story

- Les tests sont écrits d'abord et doivent échouer
- Modèles avant règles, règles avant moteur, moteur avant orchestrateur, orchestrateur avant gestionnaires
- Les tâches qui modifient le même fichier (`game/engine.py`, `bot/orchestrator.py`, `bot/texts.py`) ne sont **pas** parallélisables

### Opportunités de parallélisme

- Setup : T003 et T004 en parallèle
- Fondations : T006, T008 et T009 en parallèle
- US1 : les trois tâches de tests T011 à T013 en parallèle
- US2 : les neuf tâches de tests T018 à T026 en parallèle
- US3 : T036, T037 en parallèle ; T039 en parallèle
- US4 : T044 à T046 en parallèle ; T048 en parallèle
- US5 : T053 à T057 en parallèle ; T059 en parallèle de T058
- US6 : T065, T066 en parallèle
- US8 : T076, T077 en parallèle

### Exemple de parallélisme : US2

```text
Tâches de tests lancées ensemble :
  T018 tests/unit/test_rules.py
  T019 tests/unit/test_engine_start.py
  T020 tests/unit/test_engine_description.py
  T021 tests/unit/test_engine_vote.py
  T022 tests/unit/test_engine_guess.py
  T023 tests/unit/test_engine_end.py
  T024 tests/unit/test_public_view.py
  T025 tests/unit/test_engine_purity.py
  T026 tests/unit/test_engine_simulation.py
```

---

## Stratégie d'implémentation

### MVP d'abord

1. Phases 1 et 2 (Setup et Fondations)
2. US1 (base de mots) : valider seule
3. US2 (moteur pur) : valider seule, c'est le premier jalon de valeur car il contient toutes les règles
4. Premier produit jouable : **US1 à US4** (partie complète entre humains), puis **US5** pour les IA

### Livraison incrémentale

1. Setup + Fondations → base prête
2. US1 → base de mots testée
3. US2 → moteur testé (≥ 90 %)
4. US3 → lobby utilisable dans un groupe
5. US4 → partie entre humains jouable (premier MVP jouable)
6. US5 → IA et mode solo
7. US6 → reprise après redémarrage
8. US7 → classement
9. US8 → Docker et README
10. Finitions

Chaque story ajoute de la valeur sans casser les précédentes ; arrêt et validation possibles à chaque point de contrôle.

## Notes

- `[P]` = fichiers différents, aucune dépendance
- Le label `[USn]` rattache chaque tâche à une story de livraison (voir la correspondance avec la spec)
- Les contraintes de modèle de données sont citées entre guillemets dans les tâches pour ne pas être laissées à l'interprétation
- Ne commiter qu'après accord explicite de l'utilisateur

---

## Phase 12: Révision 2 des règles (2026-10-01)

**But**: appliquer [revision-2.md](revision-2.md) (demandes du propriétaire après essais réels).

- [X] T087 Compte à rebours solo à 30 s (temps pour rejoindre ; passé de 120 à 60 puis 30) : `SOLO_WAIT_TIMEOUT`, `Timeouts.solo_wait`, `.env.example`, README
- [X] T088 Descriptions à un seul mot : `MAX_DESCRIPTION_WORDS = 1` dans `game/models.py`, prompts, textes
- [X] T089 Suppression de Mr. White : rôle, phase de devinette, points, `GUESS_TIMEOUT`, devinette des IA, tests ; table de rôles `{civilians, undercovers}` dans `data/game_config.json`
- [X] T090 3 tours de description avant chaque vote (`description_rounds`, `sub_round`, récapitulatif par joueur) dans `game/engine.py`
- [X] T091 Deux types de partie : `GameMode`, événement `SetMode`, boutons du lobby (`bot/keyboards.py`, `bot/handlers/lobby.py`), mode « sans élimination » (accusé, victoire, points)
- [X] T092 Nouvelle partie automatique en mode sans élimination (`bot/orchestrator.py` : pause de 60 s (`RESTART_DELAY`), mêmes membres, `/annuler` arrête la série)
- [X] T093 Tests : moteur (3 tours, un mot, deux modes), intégration (choix du mode, relance, arrêt), configuration, agents IA
- [X] T094 Reprise : les parties enregistrées avec les anciennes règles sont annulées au chargement (`db/repository.py`)
- [X] T095 Documentation : README, revision-2.md, notes dans spec.md et dans le brief

