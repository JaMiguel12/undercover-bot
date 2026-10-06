# Quickstart : valider le bot Undercover

Guide de validation de bout en bout. Les détails d'interface sont dans [contracts/](contracts/) et
le modèle dans [data-model.md](data-model.md).

## Prérequis

- Python 3.12 (`py -3.12 --version`), Docker (pour la validation finale).
- Un bot créé via BotFather, avec le **mode privé désactivé** (`/setprivacy` → Disable).
- Un groupe Telegram de test avec au moins 2 comptes humains ; bot optionnellement administrateur.
- Une clé d'API Groq.

## 1. Installation

```text
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env      # puis renseigner BOT_TOKEN, GROQ_API_KEY, GROQ_MODEL
```

## 2. Tests automatisés (sans réseau)

```text
pytest                       # toute la suite
pytest tests/unit --cov=game --cov-fail-under=90
ruff check . ; ruff format --check .
```

Attendu : tout passe ; couverture du moteur ≥ 90 % (SC-001 à SC-005, SC-008, SC-009).

## 3. Scénarios à vérifier (mapping avec les critères d'acceptation du brief)

| # | Scénario | Attendu | Couvre |
|---|---|---|---|
| 1 | Base de mots : ajouter un doublon d'id dans `data/words.json` puis lancer le bot | Démarrage refusé avec une erreur nommant l'id | FR-057 |
| 2 | Solo : 1 humain crée le lobby et appuie sur « Lancer » | Dernier appel + compte à rebours 2 min ; sans arrivant, 3 IA entrent, partie à 4 (3 civils, 1 undercover) | FR-010, FR-011, SC-006 |
| 3 | Un 2e humain rejoint pendant le compte à rebours | Partie à 2 humains + 3 IA (total 5) | FR-011 |
| 4 | Inscrit n'ayant jamais démarré le bot | Lancement bloqué, joueur nommé, lien de démarrage | FR-005 |
| 5 | Jouer une partie : descriptions, vote, égalité | Revote entre ex æquo, puis tirage au sort si nouvelle égalité | FR-031 |
| 6 | Mr. White éliminé, bonne devinette (articles/accents ignorés) | Victoire de Mr. White seul, fin immédiate | FR-035, FR-036 |
| 7 | Couper le réseau vers Groq (clé invalide) | Les IA passent leur tour / votent au hasard, la partie va au bout | FR-055, SC-004 |
| 8 | Redémarrer le bot pendant un vote | Même vote repris avec le délai restant | FR-060, SC-007 |
| 9 | Jouer plusieurs parties, puis `/classement` | Scores cumulés du groupe, IA comprises | FR-040, SC-010 |
| 10 | Relire tous les messages du groupe avant l'écran de fin | Aucun mot secret | FR-043, SC-002 |

## 4. Docker

```text
docker compose up --build
```

Attendu : le bot démarre, se connecte, répond à `/regles` dans le groupe ; le fichier SQLite est
sur le volume et survit à `docker compose restart`.
