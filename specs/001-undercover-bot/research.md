# Research : Bot Telegram « Undercover »

Phase 0 du plan. Le brief impose déjà la pile (section 7) et la structure (section 8) ; ce document
consigne les décisions qui restent ouvertes et les vérifications faites au moment du développement.

## R1. Modèle Groq

- **Decision**: `GROQ_MODEL` est une variable d'environnement ; valeur par défaut de
  `.env.example` : `openai/gpt-oss-120b` (révisé le 2026-10-01 : le compte de test n'avait pas accès
  aux modèles Llama, erreur 404 `model_not_found` ; `gpt-oss-120b` répond en JSON en ~1 s). Le bot
  vérifie le modèle au démarrage et journalise les modèles disponibles si le sien est inaccessible. Jamais codé en dur dans le code.
- **Rationale**: la documentation Groq (vérifiée le 2026-10-01) liste quatre modèles de
  production : `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`, `openai/gpt-oss-120b`,
  `openai/gpt-oss-20b`. Le modèle 70B de Llama est multilingue et suffisamment fiable pour produire
  du JSON strict en français ; la latence n'est pas critique puisqu'un délai de « frappe » de 2 à
  5 s est ajouté de toute façon.
- **Alternatives considered**: `llama-3.1-8b-instant` (plus rapide, indices plus faibles en
  français) ; `openai/gpt-oss-20b` (très rapide, comportement JSON moins éprouvé). Le changement
  se fait sans toucher au code, ce qui rend le choix réversible.

## R2. Sortie JSON stricte des agents

- **Decision**: demander le mode JSON du SDK (`response_format={"type": "json_object"}`), puis
  valider la réponse côté application (schéma minimal, règles de la section 4.3 du brief). Toute
  réponse invalide compte comme une tentative échouée.
- **Rationale**: la validation applicative est obligatoire de toute façon (≤ 6 mots, mot interdit,
  joueur vivant, pas de répétition) ; elle couvre aussi un éventuel modèle sans mode JSON.
- **Alternatives considered**: sorties structurées avec schéma strict (support variable selon les
  modèles, donc liaison plus forte au modèle choisi) ; extraction par expression régulière sur du
  texte libre (fragile).

## R3. Forme du moteur pur

- **Decision**: le moteur expose des fonctions qui prennent un `GameState`, un événement et un
  `random.Random`, et renvoient le nouvel état et une liste d'**effets** à exécuter (envoyer un
  message de groupe, un message privé, demander une action à une IA, programmer une échéance).
  Il ne lit jamais l'horloge : les échéances sont des durées demandées dans les effets, et
  l'expiration est un événement `Timeout` injecté par l'orchestrateur.
- **Rationale**: c'est la seule forme qui donne à la fois le déterminisme, la testabilité sans
  mock (principe II) et la reprise après redémarrage (l'état et l'échéance sont sérialisables).
- **Alternatives considered**: moteur à objets avec callbacks (couplage au transport, tests
  difficiles) ; moteur asynchrone (mélange logique et attentes, contraire au principe II).

## R4. Minuteries et reprise

- **Decision**: une tâche asyncio par échéance active ; l'échéance absolue (`deadline_at`) est
  stockée en base avec l'état. Au démarrage, l'orchestrateur relit les parties non terminées et
  reprogramme chaque minuterie avec le temps restant (`max(0, deadline_at - maintenant)`).
  Un verrou asyncio par partie sérialise les événements d'une même partie (clic, message,
  expiration, réponse d'IA).
- **Rationale**: c'est exactement ce que demande le brief (section 7) ; le verrou évite les
  courses entre un dernier vote et l'expiration du délai.
- **Alternatives considered**: planificateur externe ou file de tâches (complexité non justifiée,
  principe I).

## R5. Persistance

- **Decision**: une table `games` porte l'état complet de la partie sérialisé en JSON, plus des
  colonnes d'index (`chat_id`, `phase`, `deadline_at`). Tables séparées pour les scores cumulés par
  groupe, l'historique des trios joués par groupe, et les utilisateurs ayant démarré le bot. La
  session SQLAlchemy est ouverte par opération. La version de SQLAlchemy est `>=2.0`.
- **Rationale**: un document par partie évite de modéliser chaque transition ; la reprise est
  triviale ; l'état est sauvegardé dans la même transaction que la mise à jour de l'échéance.
- **Alternatives considered**: modèle relationnel complet joueurs/tours/votes (beaucoup de code
  pour aucun besoin de requête) ; fichier JSON par partie (pas de transactions, verrouillage
  fragile sous Windows et Docker).

## R6. Détection de « mot secret dans un message »

- **Decision**: comparaison normalisée (minuscules, accents supprimés, espaces et tirets unifiés,
  articles retirés) entre la description et le mot du joueur, sur les mots et sur la phrase
  complète. La racine évidente (règle IA, section 4.3) est approchée par un préfixe commun d'au
  moins 5 caractères ou l'inclusion d'un mot normalisé dans l'autre.
- **Rationale**: suffisant pour les 201 trios ; reste déterministe et testable dans le moteur.
- **Alternatives considered**: racinisation linguistique (dépendance lourde, principe I) ; appel
  au LLM pour juger (non déterministe).

## R7. Test de confidentialité (exigence III)

- **Decision**: un faux `Bot` enregistre chaque message envoyé, en séparant groupe et privé. Un
  test rejoue des parties complètes (graines variées, avec et sans IA, tous les chemins : égalité,
  revote, tirage, devinette réussie et ratée, annulation) et vérifie qu'aucun texte de groupe émis
  avant le message de fin ne contient l'un des trois mots du trio, en comparaison normalisée.
  Les textes sont tous construits dans `bot/texts.py`, ce qui borne la surface à tester.
- **Rationale**: c'est la seule façon de couvrir « tous les textes émis » (critère 6 du brief).
- **Alternatives considered**: revue manuelle (non automatisable, non reproductible).

## R8. Appels LLM, erreurs et limites

- **Decision**: timeout par appel, puis jusqu'à 3 essais avec backoff exponentiel sur les erreurs
  429 et les erreurs réseau ; au-delà, repli (description : « Je passe mon tour 🤐 », vote :
  aléatoire valide, devinette : « Je ne sais pas »). Pour la description, « 3 tentatives » du
  brief s'entend comme 3 réponses valides demandées ; chaque tentative peut elle-même subir le
  backoff sur 429 sans dépasser le délai global de l'action.
- **Rationale**: respecte la section 4.5 du brief et la règle « une IA ne bloque jamais la partie ».
- **Alternatives considered**: bibliothèque de retry tierce (dépendance inutile pour 3 essais).

## R9. Vue publique et équité

- **Decision**: `game.models.PublicView` est un objet immuable construit par une fonction du moteur
  à partir de `GameState` et de l'identifiant de l'IA : son mot, les joueurs vivants, l'historique
  public (descriptions, votes, éliminations avec rôles révélés). Il ne contient aucun champ pour
  le rôle de l'IA ni pour les mots ou rôles des autres. Le module `ai/` n'importe pas `GameState`.
- **Rationale**: rend la fuite impossible par construction plutôt que par discipline (principe IV).
- **Alternatives considered**: filtrer un état complet au moment de construire le prompt (un oubli
  suffit à fuiter).

## R10. Outillage local et déploiement

- **Decision**: Python 3.12 via `py -3.12` ; environnement virtuel dans `.venv` ; dépendances
  déclarées dans `pyproject.toml` (runtime et groupe `dev`). Dockerfile basé sur une image
  Python 3.12 slim, exécution en utilisateur non root, volume pour le fichier SQLite ;
  `docker-compose.yml` lit `.env`.
- **Rationale**: aligne l'environnement local sur le conteneur ; 3.14 est installé par défaut
  mais n'est pas la version du brief.
- **Alternatives considered**: utiliser 3.14 (hors brief, risque de wheels manquantes).

## R11. Versions vérifiées au 2026-10-01

aiogram 3.31, groq 1.7, SQLAlchemy 2.1 (la branche 2.0.54 reste disponible), aiosqlite 0.22,
pydantic-settings 2.15, pytest-asyncio 1.4, ruff 0.16. Les versions exactes seront figées au moment
de la tâche de mise en place du projet ; le plan ne dépend d'aucune fonctionnalité propre à une
version mineure.
