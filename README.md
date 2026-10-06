# 🕵️ Undercover — bot Telegram

Un bot Telegram pour jouer à **Undercover** par écrit, dans un groupe d'amis. Quand il manque des
joueurs, trois agents IA — **Zendaya IA**, **Kendall IA** et **BFF Diva IA** — rejoignent la partie
et jouent comme des humains. Un joueur seul peut même affronter les trois IA.

Tous les messages du bot sont en français.

## Comment ça se joue

1. Dans le groupe, un joueur tape `/nouvelle`. Le **créateur choisit le type de partie** avec les
   boutons du lobby (☠️ *Avec élimination* ou 🔄 *Sans élimination*), les autres appuient sur
   **Rejoindre**, puis le créateur appuie sur **Lancer**.
2. Chaque joueur reçoit **son mot en message privé**. Les Civils ont tous le même mot ; les
   Undercovers en ont un différent, mais proche. Personne ne connaît son rôle.
3. **3 tours de description** : à chaque tour, chacun dit **un seul mot** (60 secondes) pour décrire
   le sien, sans le prononcer. Puis le groupe **vote** (90 secondes). Égalité : revote, puis tirage
   au sort.
4. **Avec élimination** : le plus voté est éliminé (son rôle est révélé) et on rejoue 3 tours de
   description avant le vote suivant, jusqu'à une victoire. Les Civils gagnent quand tous les
   Undercovers sont éliminés ; les Undercovers gagnent quand il ne reste qu'un Civil.
5. **Sans élimination** : un seul vote. Le plus voté est l'accusé : si c'est un Undercover, les Civils
   gagnent, sinon les Undercovers gagnent. On révèle les rôles, les mots et les points, puis une
   **nouvelle partie démarre toute seule au bout de 60 secondes** avec les mêmes joueurs, jusqu'à ce
   que le créateur tape `/annuler`.

Complétion par les IA : de 1 à 8 humains, les IA arrivent dans l'ordre Zendaya IA, Kendall IA,
BFF Diva IA pour atteindre 8 joueurs (4 en mode solo, 5 avec 2 humains). Avec un seul humain,
« Lancer » déclenche un dernier appel de **30 secondes** avant l'entrée des IA.

## Prérequis Telegram (BotFather)

1. Créez le bot avec [@BotFather](https://t.me/BotFather) (`/newbot`) et notez le jeton.
2. **Désactivez le mode privé** : `/setprivacy` → choisissez votre bot → **Disable**. Sans cela, le
   bot ne lit pas les descriptions écrites dans le groupe.
3. *(Optionnel)* Ajoutez le bot comme **administrateur** du groupe : il pourra alors supprimer les
   descriptions qui contiennent le mot secret du joueur. Sans ce droit, il demande simplement une
   autre description.
4. **Chaque joueur doit démarrer le bot une fois en privé** (`/start`), sinon le bot ne peut pas lui
   envoyer son mot. Le lobby affiche ✅ ou ⚠️ pour chaque inscrit et bloque le lancement tant qu'un
   joueur n'a pas démarré le bot.

## Commandes

| Dans le groupe | Effet |
|---|---|
| `/nouvelle` | Crée un lobby (une seule partie active par groupe) |
| `/lancer` | Lance la partie (créateur) |
| `/annuler` | Annule le lobby ou la partie (créateur) |
| `/etat` | Phase, joueurs vivants, joueur courant |
| `/regles` | Résumé des règles |
| `/classement` | Classement cumulé du groupe, IA comprises |

| En privé | Effet |
|---|---|
| `/start` | Active le bot pour recevoir son mot |
| `/monmot` | Renvoie son mot pour la partie en cours |
| `/aide` | Aide |

## Installation locale

Prérequis : **Python 3.12**.

```text
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

Renseignez ensuite `.env` (jamais commité) :

| Variable | Rôle | Défaut |
|---|---|---|
| `BOT_TOKEN` | Jeton du bot Telegram (secret) | — |
| `GROQ_API_KEY` | Clé d'API [Groq](https://console.groq.com) (secret) | — |
| `GROQ_MODEL` | Modèle Groq. La liste dépend de votre compte : au démarrage, le bot vérifie que le modèle est accessible et affiche les modèles disponibles sinon ([documentation](https://console.groq.com/docs/models)) | `openai/gpt-oss-120b` (dans `.env.example`) |
| `DATABASE_URL` | Base SQLite | `sqlite+aiosqlite:///./data/undercover.db` |
| `DESCRIPTION_TIMEOUT` | Secondes pour décrire | `60` |
| `VOTE_TIMEOUT` | Secondes pour voter | `90` |
| `LOBBY_TIMEOUT` | Expiration d'un lobby inactif | `600` |
| `SOLO_WAIT_TIMEOUT` | Temps pour rejoindre avant l'entrée des IA (mode solo) | `30` |
| `RESTART_DELAY` | Pause avant la nouvelle partie automatique (mode sans élimination) | `60` |

Lancement :

```text
python -m bot.main
```

Au démarrage, le bot valide `data/words.json` et `data/game_config.json` ; en cas d'erreur il
s'arrête avec un message explicite. Si une partie était en cours, elle **reprend** là où elle
s'était arrêtée, avec les délais restants.

## Docker

```text
copy .env.example .env      # puis renseigner BOT_TOKEN, GROQ_API_KEY, GROQ_MODEL
docker compose up --build
```

La base SQLite vit dans le volume `undercover-data` : elle survit à `docker compose restart` et à
la reconstruction de l'image. Aucun secret n'est embarqué dans l'image.

## Personnaliser le jeu

- **Base de mots** : éditez `data/words.json`. Chaque entrée est
  `{"id": 202, "categorie": "...", "mots": ["mot A", "mot B", "mot C"]}` avec un `id` unique et
  exactement 3 mots distincts. Aucune modification de code n'est nécessaire ; une base invalide
  empêche le démarrage.
- **Rôles, points et tours** : éditez `data/game_config.json` (répartition des rôles pour 4 à 8
  joueurs, barème de points, nombre de tours de description avant chaque vote).

## Tests et qualité

```text
pytest                                       # toute la suite, sans réseau
pytest tests/unit --cov=game --cov-fail-under=90   # moteur couvert à plus de 90 %
ruff check . ; ruff format --check .
```

## Architecture

```text
game/    moteur pur (aucune dépendance à Telegram, à la base ou au LLM) : règles, machine à états
ai/      agents IA : prompts, client Groq, agent (décrire, voter)
db/      persistance SQLite (SQLAlchemy 2 asynchrone)
bot/     Telegram (aiogram 3), textes français, orchestrateur
data/    base de mots et configuration du jeu
specs/   spécification, plan et tâches (Spec Kit)
```

Principes : le moteur est pur et testé ; aucun mot secret n'apparaît dans le groupe avant la fin
(testé automatiquement) ; les IA ne reçoivent que la vue publique de la partie ; une panne du LLM
ne bloque jamais une partie.
