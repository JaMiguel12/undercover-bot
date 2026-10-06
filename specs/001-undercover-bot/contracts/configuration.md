# Contrat : configuration

Lue par `bot/config.py` (pydantic-settings) depuis les variables d'environnement et le fichier
`.env`. Un fichier `.env.example`, sans valeur secrète, liste toutes les variables.

## Variables d'environnement

| Variable | Obligatoire | Défaut | Rôle |
|---|---|---|---|
| `BOT_TOKEN` | oui | — | Jeton du bot Telegram (secret) |
| `GROQ_API_KEY` | oui | — | Clé d'API Groq (secret) |
| `GROQ_MODEL` | oui | `llama-3.3-70b-versatile` dans `.env.example` | Identifiant du modèle ; jamais codé en dur |
| `DATABASE_URL` | non | `sqlite+aiosqlite:///./data/undercover.db` | Base SQLite (chemin sur le volume Docker) |
| `DESCRIPTION_TIMEOUT` | non | `60` | Secondes pour décrire (FR-024) |
| `VOTE_TIMEOUT` | non | `90` | Secondes pour voter (FR-029) |
| `GUESS_TIMEOUT` | non | `60` | Secondes pour la devinette de Mr. White (FR-034) |
| `LOBBY_TIMEOUT` | non | `600` | Expiration d'un lobby inactif (FR-006) |
| `SOLO_WAIT_TIMEOUT` | non | `120` | Compte à rebours du mode solo (FR-010) |

## Valeurs de jeu configurables (fichier de configuration, pas en dur dans la logique)

Fournies dans un fichier de configuration du jeu chargé au démarrage (chemin par défaut
`data/game_config.json`) :

- **Répartition des rôles** par total de joueurs, de 4 à 8 (FR-015, FR-016) ;
- **Barème de points** : points par civil, par undercover, pour Mr. White, pour la devinette
  réussie (FR-039).

Un fichier absent ou invalide fait échouer le démarrage avec une erreur explicite ; les valeurs par
défaut des tableaux du brief sont livrées dans le dépôt.

## Règles

- Aucun secret dans le dépôt : `.env` est dans `.gitignore` (principe VIII).
- Les délais sont des entiers en secondes, strictement positifs ; une valeur invalide fait échouer
  le démarrage.
- Le modèle Groq se change uniquement par `GROQ_MODEL`.
