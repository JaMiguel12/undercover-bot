# Modèle de données : Bot Telegram « Undercover »

Deux niveaux : les **entités du moteur** (module `game/`, objets purs en mémoire, sérialisables
en JSON) et les **tables** de persistance (module `db/`). Les noms sont en anglais (principe VII).

## 1. Entités du moteur (`game/models.py`)

### Role (énumération)
`CIVILIAN`, `UNDERCOVER`, `MR_WHITE`. Équipe dérivée : `CIVILIAN` → Civils ; les deux autres → Infiltrés.

### Phase (énumération)
`LOBBY`, `DISTRIBUTION`, `DESCRIPTION`, `VOTE`, `REVOTE`, `MR_WHITE_GUESS`, `CHECK_VICTORY`,
`ENDED`, `CANCELLED`.

### Player
| Champ | Type | Règle |
|---|---|---|
| `id` | str | Identifiant stable : `h:<user_id>` pour un humain, `ai:zendaya` / `ai:kendall` / `ai:diva` |
| `name` | str | Nom affiché (nom Telegram, ou « Zendaya IA », etc.) |
| `is_ai` | bool | Vrai pour les trois agents |
| `role` | Role \| None | Vide avant la distribution ; jamais exposé aux IA |
| `word` | str \| None | Vide avant la distribution |
| `alive` | bool | Faux après élimination |
| `can_dm` | bool | Humain : peut recevoir un message privé (✅/⚠️) |

### WordTrio
`id` (int, unique), `category` (str), `words` (3 chaînes distinctes). Après tirage : `civilian_word`
(A), `undercover_word` (B), `mr_white_word` (C), issus d'un mélange aléatoire des trois mots.

### Description
`round` (int), `player_id`, `text` (≤ 6 mots), `skipped` (bool).

### VoteRound
`round`, `kind` (`VOTE` \| `REVOTE`), `candidates` (ids, pour un revote), `ballots` (dict
`voter_id → target_id`), `tie_break_drawn` (bool).

### Elimination
`round`, `player_id`, `role_revealed`, `by` (`vote` \| `draw`), `mr_white_guess` (str \| None),
`guess_correct` (bool \| None).

### GameState
| Champ | Type | Règle |
|---|---|---|
| `game_id` | str | Identifiant unique |
| `chat_id` | int | Groupe Telegram ; une seule partie active par groupe (FR-001) |
| `creator_id` | str | Transmissible si le créateur quitte (FR-008a) |
| `phase` | Phase | Voir transitions ci-dessous |
| `players` | list[Player] | 1 à 8 humains au lobby, 4 à 8 joueurs après complétion |
| `trio` | WordTrio \| None | Tiré au lancement |
| `round` | int | Numéro de tour, à partir de 1 |
| `initial_order` | list[str] | Ordre initial fixé au tour 1 (Mr. White jamais premier) |
| `first_pos` | int | Position du premier orateur du tour dans `initial_order` |
| `speaking_order` | list[str] | Ordre de passage du tour courant (joueurs vivants) |
| `speaker_index` | int | Orateur courant du tour |
| `descriptions` | list[Description] | Historique public |
| `vote_rounds` | list[VoteRound] | Historique public |
| `eliminations` | list[Elimination] | Historique public |
| `solo_waiting` | bool | Vrai pendant le compte à rebours du mode solo (phase `LOBBY`) ; l'échéance `solo_wait` est portée par `deadline_at` |
| `no_vote_streak` | int | Tours consécutifs sans vote ; annulation à 3 (FR-032) |
| `guess_player_id` | str \| None | Mr. White éliminé dont la devinette est attendue |
| `points` | dict[str, int] | Points attribués à la fin (vide si annulée) |
| `outcome` | Outcome \| None | `CIVILIANS`, `INFILTRATORS`, `MR_WHITE_GUESS`, `CANCELLED` |
| `rng_seed` | int | Graine du hasard (déterminisme, tests et reprise) |

### PublicView (immuable, construite par le moteur pour une IA)
`viewer_id`, `own_word`, `alive_players` (id, nom), `descriptions`, `vote_history` (qui a voté pour
qui), `eliminations` (joueur + rôle révélé). **Aucun champ** pour le rôle du lecteur, ni les mots
ou rôles des autres joueurs encore en jeu (FR-049, principe IV).

### Effects (sorties du moteur)
`SendGroup(text_key, params)`, `SendPrivate(player_id, text_key, params)`, `DeleteMessage`,
`RequestAIAction(player_id, kind)`, `StartTimer(kind, seconds)`, `CancelTimer(kind)`,
`UpdateLobby`. Les effets référencent des clés de texte ; `bot/texts.py` produit le français.

### Transitions de phase

```text
LOBBY ──start──▶ DISTRIBUTION ──▶ DESCRIPTION ──(tous ont parlé)──▶ VOTE
  │                                   ▲                              │
  │                                   │                    (égalité) ▼
  │                                   │                           REVOTE ──(égalité)──▶ tirage
  │                                   │                              │
  │                                   └────── CHECK_VICTORY ◀── (Mr. White éliminé ?) MR_WHITE_GUESS
  │                                              │
  └──cancel (toute phase)──▶ CANCELLED           └──▶ ENDED
```

- `LOBBY` avec `solo_waiting` : « Lancer » par l'unique humain active le drapeau et l'échéance
  `SOLO_WAIT_TIMEOUT` ; l'expiration, ou un second « Lancer », déclenche la distribution avec la
  complétion normale ; un join ne change pas le drapeau ; « Annuler » → `CANCELLED`.
- `VOTE` sans aucun bulletin : pas d'élimination, `no_vote_streak += 1`, retour à `DESCRIPTION` ;
  à 3, `CANCELLED`.
- `CHECK_VICTORY` : devinette correcte → `ENDED` (`MR_WHITE_GUESS`) ; plus d'infiltrés vivants →
  `ENDED` (`CIVILIANS`) ; ≤ 1 civil vivant → `ENDED` (`INFILTRATORS`) ; sinon nouveau tour.

## 2. Configuration du jeu (`game/rules.py`, valeurs lues depuis la config)

- **Complétion IA** : table humains → liste d'IA (priorité fixe Zendaya, Kendall, BFF Diva).
- **Répartition des rôles** : table total → (civils, undercovers, Mr. White) ; défauts 4 → 3/1/0,
  5 → 3/1/1, 6 → 4/1/1, 7 → 5/1/1, 8 → 5/2/1 ; fournie par configuration, pas codée en dur (FR-016).
- **Points** : civils +2 par civil ; infiltrés +10 par undercover, +6 pour Mr. White ; devinette de
  Mr. White +10 pour lui seul (FR-039).

## 3. Tables de persistance (`db/models.py`)

### games
| Colonne | Type | Note |
|---|---|---|
| `game_id` | text, clé primaire | |
| `chat_id` | integer, index | |
| `phase` | text | Copie de `state.phase` pour filtrer les parties actives |
| `state_json` | text | `GameState` sérialisé, mis à jour à chaque transition |
| `deadline_kind` | text, nullable | `description`, `vote`, `guess`, `lobby`, `solo_wait` |
| `deadline_at` | datetime (UTC), nullable | Échéance absolue pour la reprise (FR-060) |
| `lobby_message_id` | integer, nullable | Message de lobby à rééditer |
| `updated_at` | datetime | |

Contrainte : au plus une ligne non terminée (`phase` ∉ {`ENDED`, `CANCELLED`}) par `chat_id`.

### participants
`game_id`, `user_id` (clé composite). Sert à refuser une seconde inscription d'un humain dans
n'importe quel groupe (FR-007). Les lignes d'une partie terminée ou annulée sont supprimées.

### users
`user_id` (clé primaire), `display_name`, `can_dm` (bool, vrai après `/start`), `started_at`.

### scores
`chat_id`, `player_id` (clé composite), `display_name`, `points` (integer), `games_played`.
Les IA ont des lignes comme les humains (FR-040).

### played_trios
`chat_id`, `trio_id` (clé composite), `played_at`. Quand tous les trios d'un groupe sont joués, les
lignes du groupe sont effacées et le cycle recommence (FR-058).

## 4. Règles de validation (issues des exigences)

- Une description : ≤ 6 mots, ne contient pas le mot du joueur (comparaison normalisée), émise par
  l'orateur courant uniquement (FR-022, FR-023, FR-025).
- Un vote : émis par un joueur vivant, cible vivante, différente de l'électeur ; modifiable tant que
  le vote est ouvert (FR-028).
- Base de mots : id unique, exactement 3 mots distincts par trio, sinon arrêt au démarrage (FR-057).
- Humains : 1 à 8 par lobby ; un utilisateur dans une seule partie à la fois (FR-003, FR-007).
- Normalisation : minuscules, accents supprimés, espaces et tirets unifiés, articles initiaux
  retirés (le, la, les, l', un, une, des) (FR-035).
